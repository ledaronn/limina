"""araclar/kayit.py — yerel arac kayit defteri: @arac ile TEK bildirim.

Eskiden bir arac eklemek 6-8 yere dokunmakti: ARAC_TABLOSU, elle yazilan
FunctionDeclaration, policy.toml [araclar], gate.ARAC_YOL_MODU, sistem
talimatindaki OKUYAN_ARACLAR, paketler.YERLESIK/ARAC_BILGI, TOOLS.md.
Simdi:

    @arac(
        ad="write_file", paket="dosya_duzenleme", risk="WRITE",
        baslik="Dosya yazma", aciklama="Dosya olusturur ya da tam icerigini degistirir.",
        yollar={"path": "yaz"},
        sema={... JSON Schema ...},
        modele="Bir metin dosyasi olusturur veya VAR OLANIN UZERINE YAZAR. ...")
    def write_file(yol, args): ...

Buradan turetilenler:
  - ARAC_TABLOSU (ad -> fonksiyon)             -> dongu
  - semalar()  {"name","description","parameters"} -> modele (saglayici katmani)
  - yol_modlari() {ad: {"path": "yaz", ...}}   -> gate (hangi arguman yol, hangi modda)
  - paketler() {paket: {arac: risk}}           -> paketler.YERLESIK + policy.example
  - bilgiler() {ad: (baslik, aciklama)}        -> Araclar paneli
  - okuyanlar()                                -> sistem talimati ("SADECE okuyan araclarda...")

policy.toml [araclar] yine son soz: kayit defteri VARSAYILAN riski soyler,
politika sikilastirabilir ya da araci tanimayabilir (deny by default).
"modele" metni modele yazilir (TOOLS.md kurali 1), "aciklama" kullaniciya.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from limina.ceviri import t

RISKLER = ("READ", "WRITE_HAFIF", "WRITE", "EXEC", "NETWORK", "DESTRUCTIVE")
YOL_MODLARI = ("oku", "yaz", "ac")   # ac: acma klasoru (open_file)


@dataclass
class AracKaydi:
    ad: str
    fn: Callable[[Any, dict], str]
    paket: str
    risk: str
    baslik: str
    aciklama: str
    modele: str
    sema: dict
    yollar: dict[str, str] = field(default_factory=dict)   # arguman -> "oku" | "yaz" | "ac"
    okuyan: bool = False        # sistem talimati: "yakin eslesmeyi kendin deneyebilirsin" grubu


_KAYIT: dict[str, AracKaydi] = {}


def arac(*, ad: str, paket: str, risk: str, baslik: str, aciklama: str, modele: str,
         sema: dict | None = None, yollar: dict[str, str] | None = None,
         okuyan: bool = False) -> Callable:
    """Dekorator. Fonksiyon imzasi (yol: Path | None, args: dict) -> str."""
    if risk not in RISKLER:
        raise ValueError(f"{ad}: risk {risk!r} gecersiz; {RISKLER}")
    for arg, mod in (yollar or {}).items():
        if mod not in YOL_MODLARI:
            raise ValueError(f"{ad}: yol modu {mod!r} gecersiz ({arg}); {YOL_MODLARI}")

    def sar(fn: Callable) -> Callable:
        if ad in _KAYIT:
            raise ValueError(f"'{ad}' zaten kayitli")
        _KAYIT[ad] = AracKaydi(ad=ad, fn=fn, paket=paket, risk=risk, baslik=baslik,
                               aciklama=aciklama, modele=modele,
                               sema=sema or {"type": "object", "properties": {}},
                               yollar=dict(yollar or {}), okuyan=okuyan)
        return fn
    return sar


def kayitlar() -> dict[str, AracKaydi]:
    return dict(_KAYIT)


def tablo() -> dict[str, Callable]:
    return {ad: k.fn for ad, k in _KAYIT.items()}


def sema_cevir(sema: dict) -> dict:
    """JSON Schema'daki 'description' alanlarini gecerli dile cevirir (kopya).

    Yalnizca description'a dokunur: type/enum/required modelin sozlesmesi,
    dilden bagimsiz. Ic ice properties/items de gezilir. Eklenti kayit
    defteri (limina/eklentiler/registry.py) de ayni fonksiyonu kullanir:
    eklenti araclarinin aciklamalari da tek sozlukten (ceviri.EN) cevrilir.
    """
    cikti = dict(sema)
    if isinstance(cikti.get("description"), str):
        cikti["description"] = t(cikti["description"])
    if isinstance(cikti.get("properties"), dict):
        cikti["properties"] = {ad: sema_cevir(alt) if isinstance(alt, dict) else alt
                               for ad, alt in cikti["properties"].items()}
    if isinstance(cikti.get("items"), dict):
        cikti["items"] = sema_cevir(cikti["items"])
    return cikti


def semalar() -> list[dict]:
    """Modele giden bildirimler. HER CAGRIDA cevrilir (import aninda degil):
    @arac'taki modele= ve sema description'lari kaynak dilde durur, dil
    ayari degisince arac_semalarini_tazele bunu yeniden cagirir.
    tests/ceviri_testi.py @arac bildirimlerini de tarar; sozlukte olmayan
    bir aciklama testi kirar."""
    return [{"name": k.ad, "description": t(k.modele), "parameters": sema_cevir(k.sema)}
            for k in _KAYIT.values()]


def yol_modlari() -> dict[str, dict[str, str]]:
    return {ad: dict(k.yollar) for ad, k in _KAYIT.items() if k.yollar}


def paketler() -> dict[str, dict[str, str]]:
    cikti: dict[str, dict[str, str]] = {}
    for k in _KAYIT.values():
        cikti.setdefault(k.paket, {})[k.ad] = k.risk
    return cikti


def bilgiler() -> dict[str, tuple[str, str]]:
    return {ad: (k.baslik, k.aciklama) for ad, k in _KAYIT.items()}


# Sistem talimatindaki sira: eskiden elle yazilan demetle ayni (list_dir,
# search, read_file, read_document). Sira prompt onbellegini etkiler; kayit
# sirasina bagli kalmasin diye sabit oncelik listesi, kalan okuyanlar sona.
_OKUYAN_SIRA = ("list_dir", "search", "read_file", "read_document")


def okuyanlar() -> tuple[str, ...]:
    okuyan = [ad for ad, k in _KAYIT.items() if k.okuyan]
    return tuple([a for a in _OKUYAN_SIRA if a in okuyan] + [a for a in okuyan if a not in _OKUYAN_SIRA])
