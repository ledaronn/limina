"""baglam.py — calisma zamani tekilleri: politika, tarayici, MCP koprusu, aktif profil.

Tek yerde dursun diye: arac fonksiyonlari (pevrai.araclar.*), dongu (vekil_v0)
ve pencere ayni nesneleri gorur. Eskiden hepsi vekil_v0'in modul globalleriydi;
araclar ayri modullere tasininca globali paylasmanin yolu bu oldu.

vekil_v0.POLITIKA / TARAYICI / KOPRU adlari geriye donuk uyumluluk icin
buradaki alanlara BAGLI ozellikler olarak duruyor (vekil_v0 sonunda bkz.):
`vekil_v0.POLITIKA = yeni` yazmak B.politika'yi degistirir, araclar da aninda
yeni politikayi gorur.
"""
from __future__ import annotations

from typing import Any


class _Baglam:
    politika: Any = None        # gate.Politika
    tarayici: Any = None        # tarayici.Tarayici
    kopru: Any = None           # mcp_bridge.Kopru
    aktif_profil: str | None = None   # calistir() gorev boyunca; journal kaydina "profil"
    aktif_devam: int = 0              # kendiliginden devam turu; journal kaydina "devam"
    ajan: dict | None = None          # ekip iscisi: [ajanlar.<ad>] tanimi (model.kur(ajan=))
    ajan_adi: str | None = None       # journal kaydina "ajan"
    ekip_pano: str | None = None      # ekip iscisi: pano.jsonl yolu (araclar/ekip_pano)


B = _Baglam()
