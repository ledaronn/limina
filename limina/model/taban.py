"""model/taban.py — saglayicidan bagimsiz mesaj/yanit bicimi ve Saglayici sozlesmesi.

Dongu (vekil_v0) yalnizca BU bicimi bilir; Gemini/OpenAI/Anthropic farklari
adaptorlerde kalir. Gecmis, sohbet.py'nin zaten diske yazdigi sozluk bicimidir
— yani bellek, disk ve saglayici arasinda tek bicim:

    {"rol": "user"|"model", "parcalar": [
        {"tip": "metin", "metin": "..."},
        {"tip": "cagri", "ad": "list_dir", "args": {...}, "id": "..."},
        {"tip": "sonuc", "ad": "list_dir", "cevap": {"result": "..."}, "id": "..."},
    ]}

Arac semasi da saglayicidan bagimsiz: {"name", "description", "parameters"}
(parameters = JSON Schema). Adaptor kendi bicimine cevirir (Gemini
FunctionDeclaration, OpenAI function, Anthropic input_schema).

Hatalar: dongu yeniden deneme kararini bu siniflara gore verir —
OranSiniri (429: bekle-tekrar), SunucuHatasi (5xx: kisa bekle-tekrar),
ZamanAsimi (kisa bekle-tekrar), ModelHatasi (digerleri: yeniden deneme yok).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Mesaj bicimi yardimcilari (saf)
# ---------------------------------------------------------------------------

def kullanici_mesaji(metin: str) -> dict:
    return {"rol": "user", "parcalar": [{"tip": "metin", "metin": metin}]}


def sonuc_mesaji(sonuclar: list[tuple[str, str | None, str]]) -> dict:
    """[(arac_adi, cagri_id, metin), ...] -> tek 'user' turu. Ayni turdaki
    butun sonuclar TEK mesajda gider (paralel cagri sozlesmesi)."""
    return {"rol": "user", "parcalar": [
        {"tip": "sonuc", "ad": ad, "cevap": {"result": metin}, "id": kimlik}
        for ad, kimlik, metin in sonuclar]}


# Arac adi: MCP araclari "sunucu.arac" adini tasir. Gemini, OpenAI(-uyumlu)
# ve Anthropic API'leri adda yalnizca [a-zA-Z0-9_-] kabul eder (nokta 400
# doner: "Function ... has an invalid name"). Adaptor saglayiciya giderken
# kodlar, donen cagrida cozer; dongu ve gecmis GERCEK adi tasir.
def arac_adi_kodla(ad: str) -> str:
    return ad.replace(".", "__")


def arac_adi_coz(ad: str) -> str:
    return ad.replace("__", ".")


def yeni_cagri_kimligi() -> str:
    return "call_" + uuid.uuid4().hex[:16]


@dataclass
class AracCagrisi:
    ad: str
    args: dict
    id: str
    # Saglayiciya ozgu OPAK ek veri; gecmise "ek" olarak yazilir ve ayni
    # saglayiciya aynen geri verilir. Ornek: Gemini 3'un thought_signature'i
    # (function_call parcasinda zorunlu; eksikse 400). Dongu bunu okumaz.
    ek: dict = field(default_factory=dict)


@dataclass
class Yanit:
    metin: str | None
    cagrilar: list[AracCagrisi]
    icerik: dict                     # gecmise eklenecek "model" turu (yukaridaki bicim)
    girdi_token: int = 0
    cikti_token: int = 0


# ---------------------------------------------------------------------------
# Hatalar
# ---------------------------------------------------------------------------

class ModelHatasi(Exception):
    """Saglayici istegi basarisiz. code: HTTP kodu ya da 0."""

    def __init__(self, code: int, mesaj: str) -> None:
        self.code, self.mesaj = code, mesaj
        super().__init__(f"{code}: {mesaj}" if code else mesaj)


class OranSiniri(ModelHatasi):
    """429 — kota/oran siniri. Dongu bekleyip yeniden dener."""


class SunucuHatasi(ModelHatasi):
    """5xx — saglayici tarafinda gecici hata."""


class ZamanAsimi(ModelHatasi):
    """Yanit MODEL_ZAMAN_ASIMI icinde gelmedi."""

    def __init__(self, mesaj: str = "zaman asimi") -> None:
        super().__init__(0, mesaj)


# ---------------------------------------------------------------------------
# Saglayici sozlesmesi
# ---------------------------------------------------------------------------

class Saglayici:
    """Her adaptor bunu uygular. Yalnizca IKI is: uret ve modeller."""

    ad: str = "?"

    def uret(self, model: str, gecmis: list[dict], sistem: str,
             araclar: list[dict] | None, zorla_arac: str | None = None) -> Yanit:
        """Tek model istegi. araclar None ise hic arac semasi gitmez; zorla_arac
        verilirse yalnizca o arac sunulur ve cagrisi ZORLANIR."""
        raise NotImplementedError

    def modeller(self) -> list[str]:
        """Hesabin erisebildigi model adlari (ag cagrisi). Desteklenmiyorsa []."""
        return []


def model_turu(metin: str | None, cagrilar: list[AracCagrisi], metin_ek: dict | None = None) -> dict:
    """Yanittan gecmise girecek 'model' turunu kurar. metin_ek: metin
    parcasina iliskin saglayici verisi (Gemini imzasi olabilir)."""
    parcalar: list[dict] = []
    if metin:
        parca = {"tip": "metin", "metin": metin}
        if metin_ek:
            parca["ek"] = dict(metin_ek)
        parcalar.append(parca)
    for c in cagrilar:
        parca = {"tip": "cagri", "ad": c.ad, "args": dict(c.args), "id": c.id}
        if c.ek:
            parca["ek"] = dict(c.ek)
        parcalar.append(parca)
    return {"rol": "model", "parcalar": parcalar}


def kimlikleri_tamamla(gecmis: list[dict]) -> list[dict]:
    """Kimliksiz cagri/sonuc parcalarina tutarli kimlik verir (KOPYA doner).

    Eski sohbet dosyalari (Gemini doneminden) cagri kimligi tasimiyor; OpenAI
    ve Anthropic tool_call_id/tool_use_id eslesmesi ister. Bir model turundaki
    kimliksiz cagrilar, izleyen user turundaki ayni adli kimliksiz sonuclarla
    SIRAYLA eslenir. Ad uyusmayan sonuc kendi kimligini alir (eslesmez ama
    istek de bozulmaz).
    """
    cikti: list[dict] = []
    bekleyen: dict[str, list[str]] = {}       # ad -> sirali kimlik kuyrugu (sonuc bekleyen cagrilar)
    for m in gecmis:
        parcalar = []
        if m.get("rol") == "model":
            bekleyen = {}
        for p in m.get("parcalar", []):
            p = dict(p)
            if p.get("tip") == "cagri" and not p.get("id"):
                p["id"] = yeni_cagri_kimligi()
                bekleyen.setdefault(p.get("ad", ""), []).append(p["id"])
            elif p.get("tip") == "sonuc" and not p.get("id"):
                kuyruk = bekleyen.get(p.get("ad", ""))
                p["id"] = kuyruk.pop(0) if kuyruk else yeni_cagri_kimligi()
            parcalar.append(p)
        cikti.append({"rol": m.get("rol", "user"), "parcalar": parcalar})
    return cikti


def ardisik_birlestir(gecmis: list[dict]) -> list[dict]:
    """Ayni rolde ardisik turlari tek turda birlestirir. Anthropic ve bazi
    OpenAI-uyumlu sunucular kesin sirali user/assistant ister; bir gorev
    model hatasiyla kesilince gecmis iki 'user' turuyla bitebilir."""
    cikti: list[dict] = []
    for m in gecmis:
        if cikti and cikti[-1]["rol"] == m["rol"]:
            cikti[-1] = {"rol": m["rol"], "parcalar": cikti[-1]["parcalar"] + m["parcalar"]}
        else:
            cikti.append({"rol": m["rol"], "parcalar": list(m["parcalar"])})
    return cikti
