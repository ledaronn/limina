"""Kullanıcı not taslakları: not sürümlerinden ayrı, atomik yerel depo."""
from __future__ import annotations

import json
import re
import threading
from limina import journal

YOL = journal.KOK / "eklentiler" / "not_taslaklari.json"
_KILIT = threading.RLock()


def oku() -> dict:
    with _KILIT:
        if not YOL.exists():
            return {}
        veri = json.loads(YOL.read_text(encoding="utf-8"))
        if not isinstance(veri, dict):
            raise ValueError("Taslak deposu okunamadı.")
        return veri


def yaz(kimlik: str, taslak: dict | None) -> None:
    if not re.fullmatch(r"[a-f0-9]{32}", kimlik):
        raise ValueError("Geçersiz not kimliği.")
    if taslak is not None:
        if (not isinstance(taslak, dict) or set(taslak) != {"title", "body", "baseRevision"}
                or not isinstance(taslak["title"], str) or len(taslak["title"]) > 500
                or not isinstance(taslak["body"], str) or len(taslak["body"]) > 50000
                or type(taslak["baseRevision"]) is not int or taslak["baseRevision"] < 1):
            raise ValueError("Geçersiz not taslağı.")
    with _KILIT:
        veri = oku()
        if taslak is None:
            veri.pop(kimlik, None)
        else:
            veri[kimlik] = taslak
        YOL.parent.mkdir(parents=True, exist_ok=True)
        gecici = YOL.with_suffix(".json.yeni")
        gecici.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        gecici.replace(YOL)
