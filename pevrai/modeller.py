# modeller.py — hesapta hangi modeller var, policy.toml'daki adlar hala gecerli mi.
# Dosyayi DEGISTIRMEZ, sadece rapor verir.
#
# ICE AKTARILDIGINDA AGA CIKMAZ ve anahtar aramaz: her sey fonksiyonun icinde.
# Onceki hali modul seviyesinde Client kuruyordu, o yuzden arayuzden cagirilamiyordu.
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from pevrai import PROJE_KOKU

KOK = PROJE_KOKU        # policy.toml proje kokunde


def mevcut_modeller(politika=None) -> list[str]:
    """Secili saglayicinin hesapta erisebildigi model adlari.

    AG CAGRISI YAPAR ve saniyeler surebilir. Arayuzden cagiriliyorsa arka plan
    thread'inde cagir (pencere.Api.model_listesi_getir boyle yapiyor).
    Anahtar yoksa ya da cagri duserse ISTISNA FIRLATIR (pevrai.model.ModelHatasi
    dahil); cagiran yakalar.
    """
    from pevrai import model
    from pevrai.gate import Politika
    pol = politika or Politika(KOK / "policy.toml")
    return model.kur(pol).modeller()


def main() -> int:
    try:
        mevcut = set(mevcut_modeller())
    except Exception as e:
        print(f"Model listesi alinamadi: {type(e).__name__}: {e}")
        return 1

    with open(KOK / "policy.toml", "rb") as f:
        politika = tomllib.load(f).get("model", {})

    for etiket in ("varsayilan", "guclu"):
        ad = politika.get(etiket)
        if not ad:
            continue
        durum = "GECERLI" if ad in mevcut else "ARTIK YOK — Ayarlar > Model'den guncelle"
        print(f"{etiket:12} {ad:32} {durum}")

    print("\nHesabindaki flash-lite modelleri:")
    for ad in sorted(m for m in mevcut if "flash-lite" in m):
        print(f"  {ad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
