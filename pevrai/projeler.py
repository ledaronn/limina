"""Ekip ve Workspace için ortak projeler; eski ekip kimlikleri korunur.

Yalnızca kullanıcının proje paneli çağırır. Model araçlarının izin/eklenti
denetimi registry.invoke üzerinde kalır; burada dosya içeriği okunmaz.
"""
from __future__ import annotations

from pathlib import Path
from pevrai import ekip, journal
from pevrai.eklentiler.workspace.service import Service
from pevrai.eklentiler.common import validate, PluginError
from pevrai.eklentiler.workspace.tools import TOOLS


def _service(politika):
    return Service(journal.KOK / "eklentiler" / "workspace.sqlite3", policy=politika)


def _call(politika, name, args):
    spec = next(t for t in TOOLS if t["name"] == name)
    validate(args, spec["parameters"])
    return _service(politika).execute(name, args, actor="user")


def liste(politika) -> list[dict]:
    service = _service(politika)
    legacy = ekip.projeler()
    # Eski proje kimliği kalıcı olarak ortak kayda bağlanır. Kök değişse de
    # geçmiş ekip koşularının ilişkisi korunur; eski JSON bir yedek olarak kalır.
    with service.store.transaction() as db:
        workspaces = service.store.items(db, "workspace", deleted=True)
        bound = {w.get("team_id") for w in workspaces}
        for p in legacy:
            if p["kimlik"] in bound:
                continue
            root = Path(p.get("klasor", "")).resolve()
            if not root.is_dir() or politika.yol_dogrula(str(root), "oku").sonuc == "DENY":
                continue
            w = next((w for w in workspaces if not w.get("deleted") and not w.get("team_id") and Path(w["root"]).resolve() == root), None)
            if w is None:
                w = service.generic(db, "workspace", "create", {"name": p.get("ad") or p["kimlik"],
                                     "root": str(root), "description": p.get("aciklama", "")}, "user")
                workspaces.append(w)
            w["team_id"] = p["kimlik"]
            saved = service.store.save(db, "workspace", w, "user", "team_project_migrate", service.clock(), w["revision"])
            w.update(saved)
            bound.add(p["kimlik"])
    result = []
    for w in workspaces:
        if w.get("deleted"):
            continue
        result.append({"kimlik": w.get("team_id") or w["id"], "workspace_id": w["id"],
                       "ad": w["name"], "klasor": w["root"], "aciklama": w.get("description", ""),
                       "yazilabilir": politika.yol_dogrula(w["root"], "yaz").sonuc != "DENY"})
    migrated = {w.get("team_id") for w in workspaces}
    result.extend({**p, "yazilabilir": politika.yol_dogrula(p.get("klasor", ""), "yaz").sonuc != "DENY"}
                  for p in legacy if p["kimlik"] not in migrated)
    return result


def yaz(politika, ad, klasor, aciklama="", kimlik=None):
    root = Path(klasor).expanduser().resolve()
    decision = politika.yol_dogrula(str(root), "yaz")
    if decision.sonuc == "DENY" or not root.is_dir():
        raise PluginError(decision.gerekce if decision.sonuc == "DENY" else "Proje klasörü mevcut olmalı.")
    rows = liste(politika)
    old = next((p for p in rows if p["kimlik"] == kimlik), None) if kimlik else next((p for p in rows if Path(p["klasor"]).resolve() == root), None)
    if kimlik and old is None:
        raise PluginError("Proje bulunamadı.")
    args = {"name": ad, "root": str(root), "description": aciklama}
    if old and old.get("workspace_id"):
        w = _call(politika, "workspace_get", {"id": old["workspace_id"]})
        w = _call(politika, "workspace_update", {**args, "id": w["id"], "expected_revision": w["revision"]})
    else:
        w = _call(politika, "workspace_create", args)
    return next(p for p in liste(politika) if p.get("workspace_id") == w["id"])


def sil(politika, kimlik):
    row = next((p for p in liste(politika) if p["kimlik"] == kimlik), None)
    if row is None:
        raise PluginError("Proje bulunamadı.")
    if row.get("workspace_id"):
        w = _call(politika, "workspace_get", {"id": row["workspace_id"]})
        _call(politika, "workspace_delete", {"id": w["id"], "expected_revision": w["revision"]})
    if any(p["kimlik"] == kimlik for p in ekip.projeler()):
        error = ekip.proje_sil(kimlik)
        if error:
            raise PluginError(error)
