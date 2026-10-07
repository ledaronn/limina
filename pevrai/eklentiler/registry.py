"""Small adapter to Pevrai's existing package, gate and tool tables."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

from .common import PluginError, validate
from pevrai.araclar.kayit import sema_cevir
from pevrai.ceviri import t

MANIFESTS = {
    "study": ("Study & Focus", "Dersler, sınavlar, çalışma planları ve kalıcı odak sayacı.", "saat"),
    "notes": ("Smart Notes", "Yerel notlar, tam metin arama, bağlantılar ve sürüm geçmişi.", "dosya"),
    "workspace": ("Workspace", "Projeler, dosya referansları, görevler ve devam etme bağlamı.", "klasor"),
}
CATALOG, TOOLS, OWNERS, ERRORS = {}, {}, {}, {}
for _package, (_label, _description, _icon) in MANIFESTS.items():
    try:
        _module = importlib.import_module(f"{__package__}.{_package}.tools")
        CATALOG[_package] = {"ad": _label, "aciklama": _description, "ikon": _icon,
                             "cekirdek": False, "optional": True,
                             "araclar": {t["name"]: t["risk"] for t in _module.TOOLS}}
        for _tool in _module.TOOLS:
            TOOLS[_tool["name"]] = _tool
            OWNERS[_tool["name"]] = _package
    except ImportError as exc:
        ERRORS[_package] = str(exc)


def available(package):
    return package in CATALOG and (Path(__file__).parent / package / "service.py").is_file()


def enabled(package, policy):
    return available(package) and package not in getattr(policy, "kaldirilan", []) and any(
        name in policy.araclar for name in CATALOG[package]["araclar"])


def catalog(policy):
    result = []
    for key, (label, description, icon) in MANIFESTS.items():
        result.append({"id": key, "name": label, "description": description, "available": available(key),
                       "enabled": enabled(key, policy), "error": ERRORS.get(key),
                       "tools": [_cevrilmis(spec) for name, spec in TOOLS.items()
                                 if OWNERS[name] == key and name in policy.araclar] if enabled(key, policy) else []})
    return result


def invoke(name, args, policy, actor="user", root=None, clock=None):
    package = OWNERS.get(name)
    if package is None or not enabled(package, policy):
        raise PluginError("Eklenti kurulu/etkin değil. Eklentiler panelinden etkinleştirin.")
    validate(args, TOOLS[name]["parameters"])
    decision = policy.karar(name, args)
    if decision.sonuc == "DENY":
        raise PluginError(decision.gerekce)
    # AI ASK approvals are handled by the existing agent loop before this call.
    # The UI is a direct user action, never a model-supplied command.
    module = importlib.import_module(f"{__package__}.{package}.service")
    data_root = Path(root) if root is not None else Path.home() / ".vekil" / "eklentiler"
    kwargs = {"policy": policy}
    if clock is not None:
        kwargs["clock"] = clock
    return module.Service(data_root / (package + ".sqlite3"), **kwargs).execute(name, args, actor)


def model_result(name, args, policy):
    try:
        result = invoke(name, args, policy, actor="ai")
        if name.endswith("_list") and isinstance(result, dict) and "items" in result:
            heavy = {"files", "note_ids", "intervals", "work_intervals", "links"}
            result = {**result, "items": [{**{k: v for k, v in row.items() if k not in heavy},
                       "collection_counts": {k: len(v) for k, v in row.items() if k in heavy}}
                      for row in result["items"]]}
        if name == "workspace_get":
            result = dict(result)
            for key in ("files", "note_ids"):
                if len(result.get(key, [])) > 20:
                    result[key + "_total"] = len(result[key])
                    result[key] = result[key][:20]
                    result["pagination_hint"] = "Diğer dosya/not referansları için workspace_context(limit, offset) kullanın."
        # Valid JSON, bounded output. Large fields can be read in the local UI.
        def compact(value, limit=1200):
            if isinstance(value, str) and len(value) > limit:
                return value[:limit] + "… [uzun alan kısaltıldı; tam içerik UI'da]"
            if isinstance(value, list):
                return [compact(x) for x in value]
            if isinstance(value, dict):
                return {k: compact(v) for k, v in value.items()}
            return value
        payload = json.dumps(result if name == "note_read" else compact(result), ensure_ascii=False)
        if len(payload) > 18000:
            # Preserve IDs/revisions and pagination, never return an invalid JSON tail.
            if isinstance(result, dict) and "items" in result:
                items = []
                for row in result["items"]:
                    candidate = compact(row)
                    if len(json.dumps(items + [candidate], ensure_ascii=False)) > 16000:
                        break
                    items.append(candidate)
                result = {"items": items, "total": result.get("total"), "returned": len(items),
                          "next_offset": args.get("offset", 0) + len(items), "truncated": True}
            else:
                result = {"id": result.get("id") if isinstance(result, dict) else None,
                          "message": "Bağlam çok büyük. Sayfalı listelerde limit=1, uzun notlarda note_read, proje ayrıntılarında workspace_context kullanın; tam kayıt UI'da.", "truncated": True}
            payload = json.dumps(result, ensure_ascii=False)
        escaped = payload.replace("<", "\\u003c").replace(">", "\\u003e")
        return f'<untrusted_content source="local:{name}">\n{escaped}\n</untrusted_content>'
    except (PluginError, OSError, ImportError) as exc:
        from pevrai.sonuc import hata
        payload = json.dumps({"error": str(exc)}, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
        return hata(f'<untrusted_content source="local:{name}">\n{payload}\n</untrusted_content>')


def register(table, schemas, policy_getter):
    for name, spec in TOOLS.items():
        if not available(OWNERS[name]):
            continue
        table[name] = lambda path, args, n=name: model_result(n, args, policy_getter())
    sync_schemas(schemas, policy_getter())


def _cevrilmis(spec):
    """Arac bildirimi, aciklamalari gecerli dilde (config/arayuz.toml [genel] dil).

    Bildirimler tools.py'de Turkce durur; Ingilizce karsiliklar pevrai/ceviri.py
    EN sozlugunde. tests/ceviri_testi.py TOOLS'u tarar: sozlukte olmayan bir
    aciklama testi kirar. Her cagrida cevrilir ki dil degisince
    arac_semalarini_tazele yeni dili gorsun.
    """
    return {"name": spec["name"], "description": t(spec["description"]),
            "parameters": sema_cevir(spec["parameters"]), "risk": spec["risk"]}


def sync_schemas(schemas, policy):
    schemas[:] = [s for s in schemas if s["name"] not in OWNERS]
    for name, spec in TOOLS.items():
        if name in policy.araclar and enabled(OWNERS[name], policy):
            c = _cevrilmis(spec)
            schemas.append({k: c[k] for k in ("name", "description", "parameters")})
