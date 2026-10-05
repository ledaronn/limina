"""kurulum.py — ilk acilis: kisisel dosyalari sablondan uretir.

Depoda yalnizca SABLONLAR durur (policy.example.toml, config/persona.example.md);
kisisel dosyalar (policy.toml, config/persona.md, config/arayuz.toml) .gitignore'da.
Bu modul eksik olanlari sablondan uretir, VAR OLANA DOKUNMAZ.

Yer tutucular (yalnizca sablonlarda):
    {PROJE}  bu deponun koku (PROJE_KOKU), ileri egik cizgiyle
    {EV}     kullanicinin ev klasoru (Path.home()), ileri egik cizgiyle
    {CALISMA} calisma klasoru (CALISMA = ~/Limina). Zorunlu DEGIL: ilk kurulum
             ekraninda baska klasor secilebilir ya da hic secilmeyebilir
             (ayarlar.calisma_klasoru_degistir), Ayarlar > Dosyalar'dan da.
Ileri egik cizgi bilincli: TOML temel dizesinde ters egik cizgi kacis
karakteridir, Windows yollari kacislamadan yazilamaz; pathlib ikisini de okur.

Cagrilan yerler: pencere.main (GUI), vekil_v0 (CLI, import aninda), testler.
Idempotent ve ucuz: dosyalar varsa hicbir sey yapmaz.
"""
from __future__ import annotations

from pathlib import Path

from limina import KAYNAK_KOK, PROJE_KOKU

POLICY = PROJE_KOKU / "policy.toml"
CALISMA = Path.home() / "Limina"
POLICY_SABLON = KAYNAK_KOK / "policy.example.toml"      # dondurulmus: paket ici
PERSONA = PROJE_KOKU / "config" / "persona.md"
PERSONA_SABLON = KAYNAK_KOK / "config" / "persona.example.md"


def _doldur(metin: str) -> str:
    return (metin.replace("{PROJE}", PROJE_KOKU.as_posix())
                 .replace("{EV}", Path.home().as_posix())
                 .replace("{CALISMA}", CALISMA.as_posix()))


def _sablondan(hedef: Path, sablon: Path) -> bool:
    """hedef yoksa sablondan uretir. Uretildiyse True."""
    if hedef.exists():
        return False
    if not sablon.exists():
        raise FileNotFoundError(f"{hedef.name} yok ve sablonu da yok: {sablon}")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(_doldur(sablon.read_text(encoding="utf-8")), encoding="utf-8")
    return True


def politikayi_hazirla(sessiz: bool = False) -> list[Path]:
    """policy.toml ve config/persona.md eksikse sablondan uretir. policy.toml
    YENI uretildiyse varsayilan calisma klasorunu ve tarayici indirme
    klasorunu acar (politikadaki kokler diskte olsun). Mevcut kurulumda
    klasor ACILMAZ: kullanici calisma klasorunu kaldirdiysa geri dogmamali."""
    uretilen: list[Path] = []
    if _sablondan(POLICY, POLICY_SABLON):
        uretilen.append(POLICY)
    if _sablondan(PERSONA, PERSONA_SABLON):
        uretilen.append(PERSONA)
    from limina.journal import INEN
    for k in ((CALISMA, INEN) if POLICY in uretilen else (INEN,)):
        try:
            k.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    if uretilen and not sessiz:
        print("  Ilk acilis: sablondan uretildi -> " + ", ".join(p.name for p in uretilen))
    return uretilen
