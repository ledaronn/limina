"""ofis.py — Ekip ofisinin (3B gorunum) Python tarafi: masalar ve ajan gorunusu.

Masa = bir yetenek kumesi. Bir arac cagrisi hangi masaya aitse ajan o masaya
yurur. Esleme YALNIZCA burada tanimlidir; arayuz ayni tabloyu kopyalamaz,
masa bilgisi olayin icinde gelir (arac_cagrildi {masa}). Masalarin sahnedeki
KONUMU burada degil (sunum karari, ofis/sahne.js).

Saf fonksiyonlar: model, ag, dosya cagrisi yok (tests/ofis_testi.py).
Ofis HICBIR izin vermez: buradaki esleme yalnizca gosterim icindir, kapi
kararina hic girmez.
"""
from __future__ import annotations

import re


def masalar() -> list[dict[str, str]]:
    """Masalar (docs/OFIS_TASARIM.md 3.1), o anki dilde. Metinler sabit t()
    cagrilari: ceviri_testi anahtarlari kaynaktan tarar."""
    from limina.ceviri import t
    return [
        {"kod": "kod", "ad": t("Kod masası"), "aciklama": t("Kod dosyalarını okur ve yazar; kod çalıştırmaz.")},
        {"kod": "dosya", "ad": t("Dosya masası"), "aciklama": t("Belge ve metin dosyası yazar, düzenler, klasör açar.")},
        {"kod": "arsiv", "ad": t("Arşiv"), "aciklama": t("Okuma, arama, belge çıkarma ve değişiklik geçmişi.")},
        {"kod": "istisare", "ad": t("İstişare masası"), "aciklama": t("Ajanlar arası mesajlar, planlama ve birleştirme.")},
        {"kod": "ag", "ad": t("Düşünce Ağı köşesi"), "aciklama": t("Düşünce ağlarını okur ve ateşler.")},
        {"kod": "web", "ad": t("Web masası"), "aciklama": t("Tarayıcı işleri.")},
        {"kod": "kapi", "ad": t("Onay kapısı"), "aciklama": t("Kullanıcı onayı beklenirken burada durulur.")},
        {"kod": "bekleme", "ad": t("Dinlenme alanı"), "aciklama": t("Görevi olmayan ajanların yeri.")},
    ]


# 'yerinde': masa degil, "ajan oldugu yerde kalsin" (hazirlik adimi; bkz. masa_bul).
MASA_KODLARI = frozenset({"kod", "dosya", "arsiv", "istisare", "ag", "web", "kapi", "bekleme", "diger", "yerinde"})

# Kod sayilan uzantilar. Tek yerde: kod/dosya ayrimi yalnizca buna bakar.
KOD_UZANTILARI = frozenset({
    ".py", ".pyw", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".htm", ".css",
    ".scss", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".xml", ".sql", ".sh", ".bat",
    ".ps1", ".c", ".h", ".cpp", ".hpp", ".cc", ".cs", ".java", ".kt", ".go", ".rs", ".rb",
    ".php", ".swift", ".lua", ".r", ".vue", ".svelte",
})

_OKUMA = {"list_dir": "arsiv", "search": "arsiv", "read_document": "arsiv", "degisiklik_gecmisi": "arsiv"}
_PANO = {"ekip_mesaj": "istisare", "ekip_gelen": "istisare"}
_YOL_ALANLARI = ("path", "yol", "dosya", "file", "hedef")
_OKUMA_RISKI = {"READ"}
_YAZMA_RISKI = {"WRITE", "WRITE_HAFIF", "DESTRUCTIVE"}


def _yol(args) -> str:
    """Arac argumanlarindan dosya yolu. Isciden aktarilan eski olaylarda
    args duz metin olabilir; o zaman yol bilinmez."""
    if not isinstance(args, dict):
        return ""
    for k in _YOL_ALANLARI:
        v = args.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def kod_mu(yol: str) -> bool:
    m = re.search(r"(\.[A-Za-z0-9]+)$", str(yol or "").replace("\\", "/").rsplit("/", 1)[-1])
    return bool(m) and m.group(1).lower() in KOD_UZANTILARI


def masa_bul(arac: str, args=None, risk: str | None = None) -> str:
    """Arac cagrisi -> masa kodu. Bilinmeyen arac sessizce kaybolmaz: risk
    biliniyorsa okuma -> arsiv, yazma -> dosya; o da yoksa 'diger' (karakter
    yerinde calisir)."""
    arac = str(arac or "")
    if arac in ("write_file", "edit_file", "read_file"):
        if kod_mu(_yol(args)):
            return "kod"
        return "arsiv" if arac == "read_file" else "dosya"
    if arac == "mkdir":
        # Klasor acmak bir HAZIRLIK adimi: ajan yerinden oynamaz, sonraki gercek
        # yazma masasina yurur. (Kullanici denemesi: "test kodu yaz" diyen ajan
        # once mkdir yuzunden dosya masasina gidiyordu, sonra kod masasina.)
        return "yerinde"
    if arac in _OKUMA:
        return _OKUMA[arac]
    if arac in _PANO:
        return _PANO[arac]
    if arac == "ekip_isci":
        return "bekleme"
    if arac.startswith("ag_"):
        return "ag"
    if arac.startswith("browser_"):
        return "web"
    r = str(risk or "").upper()
    if r in _OKUMA_RISKI:
        return "arsiv"
    if r in _YAZMA_RISKI:
        return "dosya"
    return "diger"


def masa_ekle(veri: dict) -> dict:
    """arac_cagrildi olay verisine 'masa' alani ekler (varsa dokunmaz).
    Ana surecte de isci aktariminda da TEK yol budur."""
    if isinstance(veri, dict) and "masa" not in veri and veri.get("arac"):
        veri["masa"] = masa_bul(veri.get("arac"), veri.get("args"), veri.get("risk"))
    return veri


# ---------------------------------------------------------------------------
# Ajan gorunusu: ayni ajan her acilista ayni gorunur (addan belirlenimli).
# ---------------------------------------------------------------------------

# ekip.js RENKLER ile ayni sira: kart gorunumu ile ofis ayni rengi kullanir.
RENKLER = ["#dcaa65", "#79b9a0", "#91a9e8", "#c4a0d9", "#e08f8f", "#8fd0e0"]
GORUNUM_SAYISI = 8          # sac/aksesuar varyanti (sahne.js yorumlar)
RENK_KALIBI = re.compile(r"^#[0-9a-fA-F]{6}$")


def _ozet(ad: str) -> int:
    """ekip.js renk() ile ayni: h = h*31 + kod, 32 bit."""
    h = 0
    for c in str(ad):
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return h


def ajan_gorunumu(ad: str, tanim: dict | None = None) -> dict:
    """{renk, gorunum}. Tanimda renk/gorunum varsa o, yoksa addan."""
    tanim = tanim or {}
    h = _ozet(ad)
    renk = str(tanim.get("renk") or "")
    if not RENK_KALIBI.match(renk):
        renk = RENKLER[h % len(RENKLER)]
    g = tanim.get("gorunum")
    if not isinstance(g, int) or isinstance(g, bool) or not 0 <= g < GORUNUM_SAYISI:
        g = (h // len(RENKLER)) % GORUNUM_SAYISI
    return {"renk": renk.lower(), "gorunum": g}


def duzen(politika) -> dict:
    """Kopru icin (pencere.ofis_duzeni): masa kodlari/adlari ve ajanlar.
    Anahtar tasimaz."""
    baglantilar = getattr(politika, "baglantilar", {}) or {}
    ajanlar = []
    for ad, a in (getattr(politika, "ajanlar", {}) or {}).items():
        b = baglantilar.get(a.get("baglanti") or "")
        ajanlar.append({"ad": ad, **ajan_gorunumu(ad, a), "baglanti": a.get("baglanti") or "",
                        "baglanti_ad": (b or {}).get("ad", ""), "model": a.get("model") or "",
                        "rol": a.get("rol") or ""})
    return {"masalar": masalar(), "ajanlar": ajanlar}
