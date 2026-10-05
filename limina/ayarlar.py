"""Ayarlarin okunmasi ve yazilmasi. Arayuz kodu icermez.

Iki ayri hedef var ve ikisine ayni sekilde davranilmaz:

  config/arayuz.toml  Zararsiz gorunum/davranis ayarlari. Bu dosya bize ait,
                      dogrudan yazilir, bozulursa varsayilanlara dusulur.

  policy.toml         GUVENLIK SINIRI. Yedekle-yaz-geri oku-yeniden yukle
                      protokolunden gecer, ve yalnizca KAPALI bir alan
                      listesine yazilabilir.

Iki kural pazarlik dısı:

1. Modelin kendisi bu fonksiyonlari cagiramaz. Buradaki hicbir sey ARAC_TABLOSU'na
   ya da ARAC semalarina eklenmez; cagri yolu yalnizca pencere.Api, yani kullanici
   arayuzu. "Kapi, kapiyi acan tarafindan duzenlenemez."

2. policy.toml'un tamami yeniden uretilmez. Yalnizca hedef anahtar degistirilir,
   yorumlar ve elle yazilmis duzen korunur. Sebep olculdu: model bir dosyayi
   yeniden uretirken icerigi sessizce bozabiliyor (kum/README.md, iki kelime).
   Guvenlik sinirinin oldugu dosyada bu risk kabul edilemez.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tomllib
from pathlib import Path
from typing import Any

from limina import PROJE_KOKU
from limina.ceviri import t

KOK = PROJE_KOKU        # policy.toml ve config/ proje kokunde, pakette degil
POLICY = KOK / "policy.toml"
POLICY_YEDEK = KOK / "policy.toml.yedek"
ARAYUZ_YOL = KOK / "config" / "arayuz.toml"
PERSONA_YOL = KOK / "config" / "persona.md"
PERSONA_AZAMI = 6000       # karakter

# Yazilabilecek eylem kategorileri ve degerleri. Bu listeler KAPALI:
# baska bir anahtar/deger gelirse istek reddedilir.
EYLEMLER = ["gezinme", "okuma", "tiklama", "form", "indirme", "gonderim", "odeme"]
DEGERLER = ("izin", "sor", "yasak")
VARSAYILANA_DON = "varsayilan"

_ALAN_KALIBI = re.compile(r"^(?=.{1,253}$)[a-z0-9]([a-z0-9-]*[a-z0-9])?"
                          r"(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")

# Model adi bicimi. Google'in ad semasi: kucuk harf, rakam, tire, nokta.
# Adin hesapta GERCEKTEN VAR OLDUGU burada dogrulanmaz — o kontrol aga bagli
# ve bu ayarin var olma sebebi tam da ag/hesap tarafinda bir seyin degismesi.
# Ag yokken model adini duzeltememek, yanlis ad yazabilmekten daha kotu.
# Saglayiciya gore ad bicimi degisir: Gemini "gemini-2.5-flash", OpenRouter
# "openai/gpt-4o", Ollama "llama3.1:8b", Anthropic "claude-opus-5". Tirnak ve
# bosluk yine yasak (TOML'a tirnak icinde giriyor).
_MODEL_KALIBI = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{1,127}$")
SAGLAYICILAR = ("gemini", "openai", "anthropic")
_URL_KALIBI = re.compile(r"^https?://[^\s\"']{1,300}$")
MODEL_ETIKETLERI = ("varsayilan", "guclu")

# policy.toml'a SAYI ile yazilabilen kapali alan listesi: (bolum, anahtar) -> (alt, ust).
# Ust sinirlar keyfi degil kaza duvari: panelde fazladan bir sifir, gece boyu
# donen bir dongu demek. gate._pozitif ayni araliklari yeniden yukleme adiminda
# dogruluyor, yani buradaki kontrol atlansa bile dosya bozulmaz.
SAYI_ALANLARI: dict[tuple[str, str], tuple[int, int]] = {
    ("model", "gunluk_tavan_varsayilan"): (0, 100_000),
    ("model", "gunluk_tavan_guclu"): (0, 100_000),
    ("dongu", "azami_adim"): (1, 50),
    ("dongu", "azami_cagri"): (1, 200),
}

KOK_ANAHTARLARI = {"okuma": "okuma_koklari", "yazma": "yazma_koklari"}

# policy.toml'a true/false ile yazilabilen kapali alan listesi.
BAYRAK_ALANLARI = {("model", "persona_acik")}

# Mod ADLARI kapali: gate.Politika yalnizca gate.MOD_TABAN'daki bu dort adi okur
# (bkz. gate.py Politika.__init__), baska bir ad policy.toml'a yazilsa bile hic
# okunmaz. Panelden yeni mod EKLENEMEZ, yalnizca var olan dordu duzenlenir.
MOD_ADLARI = ("hizli", "dengeli", "derin", "azami")
MOD_ALANLARI = ("model", "adim", "cagri", "istek")
MOD_ROLLER = ("varsayilan", "guclu")
# adim/cagri ust sinirlari gate._pozitif'in kendi ust sinirlariyla AYNI (50, 200) —
# panel daha gevsek bir sinir yazarsa yeniden yukleme adiminda zaten patlar, burada
# ayni sinir tekrarlanarak kullaniciya erken ve anlasilir bir hata verilir. Alt sinir
# 1: sifir adim/cagri gorevi ilk turda "limit asildi" ile bitirir, sessiz bir
# kilitlenme (SAYI_ALANLARI'ndaki dongu.azami_adim/azami_cagri ile ayni gerekce).
# Alt sinir 1: 0 gate.butce_karari icin "butce yok" demek ve panelden
# yanlislikla sinirsiza cekilmesi, butcenin var olma sebebini ortadan
# kaldirirdi. Butceyi kapatmak isteyen policy.toml'u ELLE duzenler —
# bir guvenlik/harcama duvarini kapatmak iki tikla olmamali
# (gate._pozitif'in "bozuk deger sessizce sinirsiza donusmemeli"
# ilkesinin panel tarafindaki karsiligi).
MOD_SAYI_ALANLARI: dict[str, tuple[int, int]] = {
    "adim": (1, 50), "cagri": (1, 200), "istek": (1, 200)}

# ---------------------------------------------------------------------------
# config/arayuz.toml — bizim dosyamiz, dogrudan yazilir
# ---------------------------------------------------------------------------

ARAYUZ_VARSAYILAN: dict[str, dict[str, Any]] = {
    # dil: arayuz VE Python tarafinin (onay karti, hatalar, ozet, sistem
    # talimati, arac bildirimleri/ciktilari — limina/ceviri.py) dili.
    # VARSAYILAN INGILIZCE (acik kaynak dagitim). Kaynak dil kodda Turkce.
    # gelismis_ayarlar: Ayarlar'da ikinci katman (tavanlar, efor modlari, kara
    # liste, izin tablosu...) gorunsun mu. Varsayilan KAPALI: ilk kurulumda
    # gereken 2-3 ayar disinda hicbir sey gosterilmez.
    # kurulum_tamam: ilk kurulum ekrani (dil, klasorler, eklentiler) bitti mi.
    # Dosya yoksa False -> arayuz ilk acilista kurulum ekranini gosterir.
    "genel": {"dil": "en", "gelismis_ayarlar": False, "kurulum_tamam": False},
    "gorunum": {"tema": "koyu", "animasyon": "tam", "mesaj_genisligi": "dengeli", "ekip_gorunumu": "ofis"},
    "sohbet": {"gecmis_koru": True, "otomatik_kaydirma": True},
    "gelismis": {"teknik_ayrinti_acik": False, "test_modu": False},
}
ARAYUZ_SECENEK: dict[tuple[str, str], tuple[Any, ...]] = {
    ("genel", "dil"): ("tr", "en"),
    ("genel", "gelismis_ayarlar"): (True, False),
    ("genel", "kurulum_tamam"): (True, False),
    ("gorunum", "tema"): ("koyu", "acik"),
    ("gorunum", "animasyon"): ("tam", "azaltilmis", "kapali"),
    ("gorunum", "mesaj_genisligi"): ("dar", "dengeli", "genis"),
    ("gorunum", "ekip_gorunumu"): ("ofis", "kart"),
    ("sohbet", "gecmis_koru"): (True, False),
    ("sohbet", "otomatik_kaydirma"): (True, False),
    ("gelismis", "teknik_ayrinti_acik"): (True, False),
    ("gelismis", "test_modu"): (True, False),
}


def arayuz_oku() -> dict[str, dict[str, Any]]:
    """Arayuz ayarlarini doner. Dosya yoksa ya da BOZUKSA varsayilanlar.

    Bozuk bir ayar dosyasi yuzunden uygulama acilmamali; sessizce varsayilana
    dusmek burada dogru davranis.
    """
    sonuc = {b: dict(a) for b, a in ARAYUZ_VARSAYILAN.items()}
    try:
        if not ARAYUZ_YOL.exists():
            return sonuc
        ham = tomllib.loads(ARAYUZ_YOL.read_text(encoding="utf-8"))
    except Exception:
        return sonuc
    for bolum, alanlar in sonuc.items():
        gelen = ham.get(bolum)
        if not isinstance(gelen, dict):
            continue
        for anahtar in list(alanlar):
            deger = gelen.get(anahtar)
            if deger is not None and deger in ARAYUZ_SECENEK.get((bolum, anahtar), ()):
                alanlar[anahtar] = deger
    return sonuc


def arayuz_yaz(bolum: str, anahtar: str, deger: Any) -> str | None:
    """Tek bir arayuz ayarini yazar. Hata varsa metin doner, yoksa None."""
    if (bolum, anahtar) not in ARAYUZ_SECENEK:
        return f"Taninmayan ayar: {bolum}.{anahtar}"
    if deger not in ARAYUZ_SECENEK[(bolum, anahtar)]:
        izinli = ", ".join(str(x) for x in ARAYUZ_SECENEK[(bolum, anahtar)])
        return f"'{deger}' gecersiz. Izinli: {izinli}"

    mevcut = arayuz_oku()
    mevcut[bolum][anahtar] = deger
    satirlar = ["# arayuz.toml — Limina arayuz ayarlari.",
                "# Bu dosya arayuzden yazilir; elle de duzenlenebilir.",
                "# Bozulursa varsayilanlara dusulur, uygulama acilmaya devam eder.", ""]
    for b, alanlar in mevcut.items():
        satirlar.append(f"[{b}]")
        for a, d in alanlar.items():
            satirlar.append(f"{a} = {_toml_deger(d)}")
        satirlar.append("")
    try:
        ARAYUZ_YOL.parent.mkdir(parents=True, exist_ok=True)
        _atomik_yaz(ARAYUZ_YOL, "\n".join(satirlar))
    except OSError as e:
        return f"Yazilamadi: {e}"
    return None


def _toml_deger(d: Any) -> str:
    if isinstance(d, bool):
        return "true" if d else "false"
    if isinstance(d, (int, float)):
        return str(d)
    return '"' + str(d).replace('"', '\\"') + '"'


def _atomik_yaz(yol: Path, metin: str) -> None:
    """Gecici dosyaya yaz, sonra yerine koy. Yarim yazilmis dosya birakmaz."""
    gecici = yol.with_name(yol.name + ".yeni")
    gecici.write_text(metin, encoding="utf-8")
    gecici.replace(yol)


# ---------------------------------------------------------------------------
# policy.toml — satir bazli, korumali
# ---------------------------------------------------------------------------

def alan_gecerli(alan: str) -> bool:
    """Alan adi bicimi. Yol enjeksiyonu ve bosluklu girdiler burada durur."""
    return bool(_ALAN_KALIBI.match((alan or "").strip().lower()))


def _bolum_araligi(satirlar: list[str], bolum: str) -> tuple[int, int] | None:
    """[bolum] basliginin ve bloğun bittigi yerin indisleri. Yoksa None."""
    hedef = "[" + bolum + "]"
    for i, s in enumerate(satirlar):
        if s.strip() == hedef:
            j = i + 1
            while j < len(satirlar) and not satirlar[j].lstrip().startswith("["):
                j += 1
            return i, j
    return None


def _anahtar_yaz(metin: str, bolum: str, anahtar: str, deger_metni: str) -> str:
    """Bolumdeki anahtari degistirir; bolum ya da anahtar yoksa ekler.

    Dosyanin geri kalanina DOKUNMAZ — yorumlar ve siralama korunur.
    """
    satirlar = metin.splitlines()
    aralik = _bolum_araligi(satirlar, bolum)
    yeni_satir = f"{anahtar} = {deger_metni}"

    if aralik is None:
        if satirlar and satirlar[-1].strip():
            satirlar.append("")
        satirlar += [f"[{bolum}]", yeni_satir, ""]
        return "\n".join(satirlar) + "\n"

    bas, son = aralik
    kalip = re.compile(r"^\s*" + re.escape(anahtar) + r"\s*=")
    for i in range(bas + 1, son):
        if kalip.match(satirlar[i]):
            satirlar[i] = yeni_satir
            return "\n".join(satirlar) + "\n"

    # Anahtar yok: bolumun sonundaki bos satirlardan once ekle
    ekle = son
    while ekle - 1 > bas and not satirlar[ekle - 1].strip():
        ekle -= 1
    satirlar.insert(ekle, yeni_satir)
    return "\n".join(satirlar) + "\n"


def _anahtar_sil(metin: str, bolum: str, anahtar: str) -> str:
    """Anahtari siler; bolum bosaldiysa bolumu de siler."""
    satirlar = metin.splitlines()
    aralik = _bolum_araligi(satirlar, bolum)
    if aralik is None:
        return metin
    bas, son = aralik
    kalip = re.compile(r"^\s*" + re.escape(anahtar) + r"\s*=")
    kalan = [s for s in satirlar[bas + 1:son] if not kalip.match(s)]
    if any(s.strip() and not s.lstrip().startswith("#") for s in kalan):
        satirlar[bas + 1:son] = kalan
    else:
        satirlar[bas:son] = []          # bolum bosaldi, basligi da goturur
    return "\n".join(satirlar) + "\n"


def _dizi_araligi(satirlar: list[str], bolum: str, anahtar: str) -> tuple[int, int] | None:
    """TOML dizisinin (baslangic, kapanis) satir indeksleri. Tek satirlik
    dizide ikisi ayni. Dizi kapanmamissa None — bozuk dosyaya dokunmayiz.

    SINIR: '#' yorum baslangici sayiliyor. Deger icinde '#' gecen bir dizi
    (yol ya da alan adinda pratikte olmuyor) yanlis ayristirilir.
    """
    aralik = _bolum_araligi(satirlar, bolum)
    if aralik is None:
        return None
    bas, son = aralik
    kalip = re.compile(r"^\s*" + re.escape(anahtar) + r"\s*=\s*\[")
    for i in range(bas + 1, son):
        if kalip.match(satirlar[i]):
            derinlik = 0
            for j in range(i, son):
                govde = satirlar[j].split("#", 1)[0]
                derinlik += govde.count("[") - govde.count("]")
                if derinlik <= 0:
                    return (i, j)
            return None
    return None


def _dizi_oge_ekle(metin: str, bolum: str, anahtar: str, deger: str) -> str | None:
    """Diziye tek satir ekler; dizinin geri kalanina ve YORUMLARA dokunmaz.

    Diziyi bastan uretmiyoruz: policy.toml'da "kapi testi bunu bekliyor,
    dokunma" gibi satirlar var ve bastan uretim onlari siler.
    """
    satirlar = metin.splitlines()
    yer = _dizi_araligi(satirlar, bolum, anahtar)
    if yer is None:
        return None
    bas, kapanis = yer
    if bas == kapanis:                       # tek satirlik dizi
        govde = satirlar[bas]
        kapa = govde.rindex("]")
        ic = govde[govde.index("[") + 1:kapa].strip()
        ayirac = "" if not ic or ic.endswith(",") else ", "
        satirlar[bas] = govde[:kapa] + ayirac + json.dumps(deger) + govde[kapa:]
    else:
        satirlar.insert(kapanis, f"    {json.dumps(deger)},")
    return "\n".join(satirlar) + "\n"


def _dizi_oge_sil(metin: str, bolum: str, anahtar: str, deger: str) -> str | None:
    """Diziden bir ogeyi siler. Cok satirli dizide oge KENDI SATIRINDA olmali.

    Ayni satirda iki oge varsa (policy.toml'da var: '"claude.ai", "anthropic.com",')
    None doner. Tahmin yurutup guvenlik dosyasini bozmaktansa kullaniciya
    "bu satiri elle duzenle" demek dogrusu.
    """
    satirlar = metin.splitlines()
    yer = _dizi_araligi(satirlar, bolum, anahtar)
    if yer is None:
        return None
    bas, kapanis = yer
    hedef = json.dumps(deger)
    if bas == kapanis:
        govde = satirlar[bas]
        ac, kapa = govde.index("["), govde.rindex("]")
        ogeler = [p.strip() for p in govde[ac + 1:kapa].split(",") if p.strip()]
        if hedef not in ogeler:
            return None
        ogeler.remove(hedef)
        satirlar[bas] = govde[:ac + 1] + ", ".join(ogeler) + govde[kapa:]
        return "\n".join(satirlar) + "\n"
    for i in range(bas + 1, kapanis):
        if satirlar[i].split("#", 1)[0].strip().rstrip(",").strip() == hedef:
            del satirlar[i]
            return "\n".join(satirlar) + "\n"
    return None


def _guvenli_yaz(yeni_metin: str) -> str | None:
    """policy.toml yazma protokolu. Basarisizsa yedek geri yuklenir.

    Bes adim: yedekle, atomik yaz, geri oku, Politika ile yeniden yukle,
    DEGISMEZI dogrula. Dorduncu adim onemli — dosya gecerli TOML olabilir
    ama Politika'nin bekledigi alanlar bozulmus olabilir; sadece
    ayristirmayi dogrulamak yetmez.
    """
    if not POLICY.exists():
        return f"{POLICY} bulunamadi."
    try:
        shutil.copy2(POLICY, POLICY_YEDEK)
    except OSError as e:
        return f"Yedek alinamadi, hicbir sey yazilmadi: {e}"

    def geri_yukle() -> None:
        try:
            shutil.copy2(POLICY_YEDEK, POLICY)
        except OSError:
            pass

    try:
        _atomik_yaz(POLICY, yeni_metin)
    except OSError as e:
        geri_yukle()
        return f"Yazilamadi, eski hal geri yuklendi: {e}"

    try:
        tomllib.loads(POLICY.read_text(encoding="utf-8"))
    except Exception as e:
        geri_yukle()
        return f"Yazilan dosya gecerli TOML degil, eski hal geri yuklendi: {e}"

    try:
        from limina.gate import Politika
        pol = Politika(POLICY)
    except Exception as e:
        geri_yukle()
        return (f"Politika yuklenemedi ({type(e).__name__}: {e}), eski hal geri yuklendi.")

    # DEGISMEZ: hicbir ayar yazimi, ajanin kendi kapisini duzenleyebilecegi bir
    # yerlesim birakamaz. Bu bir GIRDI dogrulamasi degil, yazma protokolunun
    # kurali — ileride policy.toml'a yazan baska bir alan eklenirse (kokler,
    # model adlari, tavan) o da buradan gecer ve ayni korumayi bedava alir.
    ihlal = pol.kod_koku_yazilabilir_mi(KOK)
    if ihlal:
        geri_yukle()
        return f"Degisiklik reddedildi, eski hal geri yuklendi. {ihlal}"
    return None


def eylem_yaz(alan: str, kategori: str, deger: str) -> str | None:
    """Eylem iznini yazar.

    alan boşsa varsayilan tablo ([browser.eylemler]), doluysa o sitenin
    profili. deger "varsayilan" ise istisna SILINIR.
    """
    if kategori not in EYLEMLER:
        return f"Taninmayan eylem: {kategori}"
    if deger != VARSAYILANA_DON and deger not in DEGERLER:
        return f"'{deger}' gecersiz. Izinli: {', '.join(DEGERLER)}"

    alan = (alan or "").strip().lower()
    if alan:
        if not alan_gecerli(alan):
            return f"'{alan}' gecerli bir alan adi degil."
        bolum = f'browser.profiller."{alan}"'
    else:
        if deger == VARSAYILANA_DON:
            return "Varsayilan tabloda 'varsayilan' secilemez, bir deger gerekir."
        bolum = "browser.eylemler"

    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"

    yeni = (_anahtar_sil(metin, bolum, kategori) if deger == VARSAYILANA_DON
            else _anahtar_yaz(metin, bolum, kategori, f'"{deger}"'))
    return _guvenli_yaz(yeni)


def site_ekle(alan: str) -> str | None:
    """Alan adini izinli_alanlar listesine ekler."""
    alan = (alan or "").strip().lower().lstrip(".")
    if not alan_gecerli(alan):
        return f"'{alan}' gecerli bir alan adi degil."
    try:
        metin = POLICY.read_text(encoding="utf-8")
        mevcut = tomllib.loads(metin).get("browser", {}).get("izinli_alanlar", [])
    except Exception as e:
        return f"policy.toml okunamadi: {e}"
    liste = [str(a).lower().lstrip(".") for a in mevcut]
    if alan in liste:
        return None                     # zaten var, sessizce basarili
    yeni = _dizi_oge_ekle(metin, "browser", "izinli_alanlar", alan)
    if yeni is None:
        return ("policy.toml'daki izinli_alanlar dizisi cozulemedi. "
                "Alani dosyaya elle ekleyip Limina'yi yeniden baslat.")
    return _guvenli_yaz(yeni)


def site_sil(alan: str) -> str | None:
    """Alan adini listeden ve varsa profilinden cikarir."""
    alan = (alan or "").strip().lower().lstrip(".")
    try:
        metin = POLICY.read_text(encoding="utf-8")
        mevcut = tomllib.loads(metin).get("browser", {}).get("izinli_alanlar", [])
    except Exception as e:
        return f"policy.toml okunamadi: {e}"
    liste = [str(a).lower().lstrip(".") for a in mevcut]
    if alan not in liste:
        return None                     # zaten yok, sessizce basarili
    yeni = _dizi_oge_sil(metin, "browser", "izinli_alanlar", alan)
    if yeni is None:
        return (f"'{alan}' silinemedi: dizide kendi satirinda degil ya da bulunamadi. "
                f"policy.toml'da o satiri elle duzenle.")
    # Profil bolumu de gitmeli: listede olmayan site icin istisna tutmanin anlami yok
    satirlar = yeni.splitlines()
    aralik = _bolum_araligi(satirlar, f'browser.profiller."{alan}"')
    if aralik:
        satirlar[aralik[0]:aralik[1]] = []
        yeni = "\n".join(satirlar) + "\n"
    return _guvenli_yaz(yeni)


# ---------------------------------------------------------------------------
# Paketler (limina.paketler): kaldir / geri ekle, MCP sunucusu ekle / sil,
# MCP aracini siniflandir. Hepsi policy.toml'a ayni yedekli protokolle yazar.
# ---------------------------------------------------------------------------

_MCP_AD_KALIBI = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_ARAC_AD_KALIBI = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def _policy_metin() -> tuple[str | None, dict | None, str | None]:
    try:
        metin = POLICY.read_text(encoding="utf-8")
        return metin, tomllib.loads(metin), None
    except Exception as e:
        return None, None, f"policy.toml okunamadi: {e}"


def paket_kaldir(ad: str) -> str | None:
    """Yerlesik bir paketi [paketler] kaldirilan listesine yazar.

    Cekirdek reddedilir: ajanin okuma yetenegi politikadan dusurulemez.
    Yalnizca DARALTIR (gate.Politika kaldirilan araclari [araclar]'dan
    dusurur); [araclar] satirlari dokunulmadan kalir ki "Geri ekle" ayni
    risk seviyeleriyle donsun ve kullanicinin elle degistirdigi seviye
    kaybolmasin.
    """
    from limina import paketler
    ad = str(ad or "").strip()
    p = paketler.YERLESIK.get(ad)
    if p is None:
        return f"'{ad}' yerlesik bir paket degil. MCP sunuculari 'mcp_sunucu_sil' ile silinir."
    if p["cekirdek"]:
        return f"'{p['ad']}' cekirdek pakettir, kaldirilamaz; sohbet basina kapatilabilir."
    metin, ham, hata = _policy_metin()
    if hata:
        return hata
    mevcut = [str(x) for x in (ham.get("paketler", {}).get("kaldirilan") or [])]
    if ad in mevcut:
        return None
    yeni = _dizi_oge_ekle(metin, "paketler", "kaldirilan", ad)
    if yeni is None:                                   # bolum/dizi henuz yok
        yeni = _anahtar_yaz(metin, "paketler", "kaldirilan", json.dumps([ad]))
    return _guvenli_yaz(yeni)


def paket_geri_ekle(ad: str) -> str | None:
    """Yerlesik paketi kaldirilan listesinden cikarir; [araclar]'da satiri
    olmayan araclari varsayilan risk seviyesiyle yeniden yazar."""
    from limina import paketler
    ad = str(ad or "").strip()
    p = paketler.YERLESIK.get(ad)
    if p is None:
        return f"'{ad}' yerlesik bir paket degil."
    metin, ham, hata = _policy_metin()
    if hata:
        return hata
    mevcut = [str(x) for x in (ham.get("paketler", {}).get("kaldirilan") or [])]
    if ad in mevcut:
        yeni = _dizi_oge_sil(metin, "paketler", "kaldirilan", ad)
        if yeni is None:
            return (f"'{ad}' kaldirilan listesinden cikarilamadi; policy.toml [paketler] "
                    f"bolumunu elle duzenle.")
        metin = yeni
    araclar = ham.get("araclar", {})
    for arac, risk in p["araclar"].items():
        if arac not in araclar:
            metin = _anahtar_yaz(metin, "araclar", arac, f'"{risk}"')
    return _guvenli_yaz(metin)


_ARG_AD_KALIBI = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def arac_siniflandir(tam_ad: str, risk: str, yollar: dict | None = None) -> str | None:
    """Bir MCP aracini [araclar]'a risk seviyesiyle yazar (modele gorunur olur).

    yollar: {arguman: "oku"|"yaz"} — aracin yol alan argumanlari. Verilirse
    tablo bicimi yazilir ("x.y" = { risk = "WRITE", yollar = { path = "oku" } })
    ve kapi o argumanlari koklere karsi DOGRULAR. Verilmezse duz satir: yol
    argumani olan bir MCP aracinda bu bir bosluk birakir (kapi denetlemez) —
    Araclar paneli yol-benzeri argumanlar icin secici gosterir.

    Yerlesik araclar buradan siniflandirilmaz: onlarin seviyeleri kayit
    defterinden gelir ve "Geri ekle" ile yazilir. Risk kapali listeden.
    """
    from limina import paketler
    tam_ad = str(tam_ad or "").strip()
    risk = str(risk or "").strip().upper()
    if "." not in tam_ad or not _ARAC_AD_KALIBI.match(tam_ad):
        return f"'{tam_ad}' bir MCP araci adi degil (sunucu.arac bekleniyor)."
    if risk not in paketler.RISK_SEVIYELERI:
        return f"'{risk}' gecerli bir risk seviyesi degil. Gecerli: {', '.join(paketler.RISK_SEVIYELERI)}"
    yollar = {str(k): str(v) for k, v in (yollar or {}).items() if v}
    for arg, mod in yollar.items():
        if not _ARG_AD_KALIBI.match(arg):
            return f"'{arg}' gecerli bir arguman adi degil."
        if mod not in ("oku", "yaz"):
            return f"'{arg}' icin yol modu 'oku' ya da 'yaz' olmali (verilen: {mod!r})."
    metin, ham, hata = _policy_metin()
    if hata:
        return hata
    sunucu = tam_ad.partition(".")[0]
    if sunucu not in ham.get("mcp", {}):
        return f"'{sunucu}' policy.toml [mcp] altinda tanimli degil; once sunucuyu ekle."
    if yollar:
        ic = ", ".join(f'{arg} = "{mod}"' for arg, mod in yollar.items())
        deger = "{ risk = \"" + risk + "\", yollar = { " + ic + " } }"
    else:
        deger = f'"{risk}"'
    return _guvenli_yaz(_anahtar_yaz(metin, "araclar", f'"{tam_ad}"', deger))


def arac_sinif_sil(tam_ad: str) -> str | None:
    """MCP aracinin siniflandirmasini kaldirir: modele gorunmez, kapi DENY der."""
    tam_ad = str(tam_ad or "").strip()
    if "." not in tam_ad or not _ARAC_AD_KALIBI.match(tam_ad):
        return f"'{tam_ad}' bir MCP araci adi degil."
    metin, ham, hata = _policy_metin()
    if hata:
        return hata
    if tam_ad not in ham.get("araclar", {}):
        return None
    return _guvenli_yaz(_anahtar_sil(metin, "araclar", f'"{tam_ad}"'))


def mcp_sunucu_ekle(ad: str, komut: list[str]) -> str | None:
    """policy.toml'a [mcp.<ad>] komut = [...] yazar. Sunucu pencere acikken
    hemen arka planda baglanir (vekil_v0.mcp_baglan eksik sunuculari
    tamamlar); araclari siniflandirilana kadar modele GORUNMEZ
    (varsayilan reddet — yeni sunucu otomatik yetki kazanmaz).

    komut liste olarak alinir, kabuk dizesi degil: shell=True yok, ilk oge
    program, kalanlar argumanlar. "python" sys.executable'a mcp_bridge'de
    cevrilir.
    """
    ad = str(ad or "").strip().lower()
    if not _MCP_AD_KALIBI.match(ad):
        return "Sunucu adi kucuk harf, rakam ve alt cizgi icermeli, harfle baslamali (orn. 'notlar')."
    if not isinstance(komut, list) or not komut or not all(isinstance(x, str) and x.strip() for x in komut):
        return "Komut bos olamaz: program ve argumanlari ayri ayri ver (orn. python, sunucu.py)."
    komut = [x.strip() for x in komut]
    metin, ham, hata = _policy_metin()
    if hata:
        return hata
    if ad in ham.get("mcp", {}):
        return f"'{ad}' zaten tanimli."
    from limina import paketler
    if ad in paketler.YERLESIK:
        return f"'{ad}' yerlesik bir paket adi, MCP sunucusu icin baska ad sec."
    return _guvenli_yaz(_anahtar_yaz(metin, f"mcp.{ad}", "komut", json.dumps(komut, ensure_ascii=False)))


def mcp_sunucu_sil(ad: str) -> str | None:
    """[mcp.<ad>] bolumunu ve o sunucunun butun [araclar] satirlarini siler.
    Profillerde anilan araclari da dusurur ki politika yeniden yuklenebilsin."""
    ad = str(ad or "").strip().lower()
    metin, ham, hata = _policy_metin()
    if hata:
        return hata
    if ad not in ham.get("mcp", {}):
        return f"'{ad}' policy.toml [mcp] altinda tanimli degil."
    satirlar = metin.splitlines()
    aralik = _bolum_araligi(satirlar, f"mcp.{ad}")
    if aralik is None:
        return f"[mcp.{ad}] bolumu bulunamadi; dosyayi elle duzenle."
    bas, son = aralik
    # Bir sonraki basligin HEMEN ustundeki yorum/bos satirlar o basligin
    # aciklamasidir, bu bolumun degil — onlar kalir.
    while son - 1 > bas and (not satirlar[son - 1].strip()
                             or satirlar[son - 1].lstrip().startswith("#")):
        son -= 1
    satirlar[bas:son] = []
    metin = "\n".join(satirlar) + "\n"
    for tam_ad in list(ham.get("araclar", {})):
        if tam_ad.startswith(ad + "."):
            metin = _anahtar_sil(metin, "araclar", f'"{tam_ad}"')
    for profil, p in (ham.get("profiller") or {}).items():
        for tam_ad in (p.get("araclar") or []):
            if str(tam_ad).startswith(ad + "."):
                yeni = _dizi_oge_sil(metin, f"profiller.{profil}", "araclar", str(tam_ad))
                if yeni is None:
                    return (f"'{tam_ad}' [profiller.{profil}] araclar listesinden cikarilamadi; "
                            f"once o satiri elle duzenle.")
                metin = yeni
    return _guvenli_yaz(metin)


def _bolum_sil(metin: str, bolum: str) -> str | None:
    """[bolum] basligini ve govdesini siler; sonraki basligin ustundeki
    yorum/bos satirlar (onun aciklamasi) kalir. Bulunamazsa None."""
    satirlar = metin.splitlines()
    aralik = _bolum_araligi(satirlar, bolum)
    if aralik is None:
        return None
    bas, son = aralik
    while son - 1 > bas and (not satirlar[son - 1].strip()
                             or satirlar[son - 1].lstrip().startswith("#")):
        son -= 1
    satirlar[bas:son] = []
    return "\n".join(satirlar) + "\n"


def ajan_yaz(ad: str, saglayici: str = "", model: str = "", anahtar_yuvasi: str = "",
             rol: str = "", taban_url: str = "", baglanti: str = "", renk: str = "",
             gorunum: int | None = None) -> str | None:
    """[ajanlar.<ad>] tanimini yazar/gunceller (ekip paketi isci tanimi).

    Iki bicim. baglanti doluysa YENI bicim: ajan bir API baglantisina bagli
    (Ayarlar > Model), saglayici/adres/yuva oradan gelir; eski alanlar
    silinir. Bos ise ESKI bicim: saglayici + anahtar_yuvasi + taban_url.

    Anahtarin kendisi buraya YAZILMAZ: yuva anahtar.py'deki adli yuvayi
    gosterir; baglantinin anahtari baglantinin kendi yuvasindadir.
    """
    from limina.gate import AJAN_AD_KALIBI
    from limina import anahtar as _anahtar
    from limina.model import SAGLAYICILAR
    ad = str(ad or "").strip()
    if not AJAN_AD_KALIBI.match(ad):
        return "Ajan adi 1-32 karakter, harf/rakam/_/- olmali (ornek: yazar, arastirmaci)."
    model = model_temizle(model)
    if model and not model_gecerli(model):
        return f"'{model}' gecerli bir model adi degil."
    rol = " ".join(str(rol or "").split())[:200]
    renk = str(renk or "").strip().lower()
    if renk and not re.match(r"^#[0-9a-f]{6}$", renk):
        return "Renk #rrggbb biciminde olmali."
    if gorunum is not None and (not isinstance(gorunum, int) or isinstance(gorunum, bool) or not 0 <= gorunum < 8):
        return "Gorunum 0-7 arasi olmali."
    baglanti = str(baglanti or "").strip()
    metin, ham, hata = _policy_metin()
    if hata:
        return hata
    bolum = f"ajanlar.{ad}"
    if baglanti:
        mevcut = ham.get("baglantilar") or {}
        if baglanti not in mevcut and not (baglanti == ESKI_BAGLANTI and not mevcut):
            return t("'{k}' adlı bir bağlantı yok.", k=baglanti)
        degerler = (("baglanti", baglanti), ("model", model), ("rol", rol), ("renk", renk))
        for eski in ("saglayici", "anahtar_yuvasi", "taban_url"):
            metin = _anahtar_sil(metin, bolum, eski)
    else:
        saglayici = str(saglayici or "").strip().lower()
        if saglayici not in SAGLAYICILAR:
            return f"Taninmayan saglayici: {saglayici}. Gecerli: {', '.join(SAGLAYICILAR)}"
        anahtar_yuvasi = str(anahtar_yuvasi or "").strip()
        if anahtar_yuvasi and not _anahtar.YUVA_KALIBI.match(anahtar_yuvasi):
            return "Yuva adi gecersiz: 1-32 karakter, harf/rakam/_/-."
        if anahtar_yuvasi and anahtar_yuvasi not in _anahtar.yuvalar(saglayici):
            return (f"'{saglayici}' icin '{anahtar_yuvasi}' adli bir anahtar yuvasi yok. Once Ayarlar > "
                    f"Model > Anahtarlar'dan o yuvaya anahtar gir.")
        taban_url = str(taban_url or "").strip()
        if taban_url and not taban_url.startswith(("http://", "https://")):
            return "Sunucu adresi http:// ya da https:// ile baslamali."
        metin = _anahtar_yaz(metin, bolum, "saglayici", f'"{saglayici}"')
        metin = _anahtar_sil(metin, bolum, "baglanti")
        degerler = (("model", model), ("anahtar_yuvasi", anahtar_yuvasi), ("rol", rol), ("taban_url", taban_url),
                    ("renk", renk))
    for anahtar, deger in degerler:
        if deger:
            metin = _anahtar_yaz(metin, bolum, anahtar, _toml_deger(deger))
        else:
            metin = _anahtar_sil(metin, bolum, anahtar)
    if gorunum is not None:
        metin = _anahtar_yaz(metin, bolum, "gorunum", _toml_deger(gorunum))
    return _guvenli_yaz(metin)


def ajan_sil(ad: str) -> str | None:
    ad = str(ad or "").strip()
    metin, ham, hata = _policy_metin()
    if hata:
        return hata
    if ad not in (ham.get("ajanlar") or {}):
        return f"'{ad}' [ajanlar] altinda tanimli degil."
    yeni = _bolum_sil(metin, f"ajanlar.{ad}")
    if yeni is None:
        return f"[ajanlar.{ad}] bolumu bulunamadi; dosyayi elle duzenle."
    return _guvenli_yaz(yeni)


def ajanlar_oku() -> list[dict]:
    """Panel icin: tanimlar + her birinin anahtar durumu (maskeli, anahtar yok)."""
    from limina import anahtar as _anahtar
    from limina.gate import Politika
    try:
        pol = Politika(POLICY)
    except Exception:
        return []
    from limina import ofis
    from limina.model import yerel_adres_mi
    cikti = []
    for ad, a in pol.ajanlar.items():
        kaynak = _anahtar.kaynak(a["saglayici"], a["anahtar_yuvasi"])
        b = pol.baglantilar.get(a["baglanti"]) if a["baglanti"] else None
        # Yerel OpenAI-uyumlu sunucu (Ollama, LM Studio) anahtarsiz calisir.
        anahtarsiz = a["saglayici"] == "openai" and bool(a["taban_url"]) and yerel_adres_mi(a["taban_url"])
        cikti.append({"ad": ad, **a, **ofis.ajan_gorunumu(ad, a),
                      "anahtar_var": kaynak != "yok" or anahtarsiz, "anahtar_kaynak": kaynak,
                      "baglanti_ad": (b or {}).get("ad", "") if a["baglanti"] else "",
                      "etkin_model": a["model"] or getattr(pol, "model_varsayilan", "")})
    return cikti


# ---------------------------------------------------------------------------
# API baglantilari ve model zinciri ([baglantilar.<kimlik>], [model] zincir)
# ---------------------------------------------------------------------------
BAGLANTI_YUVA_ONEKI = "api-"        # anahtar.py yuvasi: "api-<kimlik>" (ekip yuvalariyla karismaz)
ESKI_BAGLANTI = "ana"               # eski tek-saglayici ayarindan uretilen ilk baglanti
_BAGLANTI_AD_YASAK = re.compile(r'["\\\x00-\x1f\x7f]')


def _toml_dizi(ogeler: list[str]) -> str:
    return "[" + ", ".join(json.dumps(str(x), ensure_ascii=False) for x in ogeler) + "]"


def _kimlik_uret(ad: str, mevcut: set[str]) -> str:
    """Addan dosya/TOML dostu kimlik: 'DeepSeek (iş)' -> 'deepseek-is'."""
    cevir = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    taban = re.sub(r"[^a-z0-9]+", "-", ad.translate(cevir).lower()).strip("-")[:16] or "api"
    kimlik, n = taban, 2
    while kimlik in mevcut:
        kimlik = f"{taban[:16]}-{n}"
        n += 1
    return kimlik


def _eski_baglantiyi_olustur(metin: str, ham: dict) -> str:
    """[baglantilar] hic yoksa, eski [model] ayarini ilk baglanti olarak yazar.

    Anahtar yuvasi BOS (varsayilan yuva): kullanicinin zaten kayitli anahtari
    ve ortam degiskeni aynen calismaya devam eder, yeniden girmek gerekmez.
    Derin model varsayilandan farkliysa zincirde ikinci model olur."""
    if ham.get("baglantilar"):
        return metin
    from limina.model_zinciri import SAGLAYICI_KISA_AD
    m = ham.get("model", {}) or {}
    saglayici = str(m.get("saglayici") or "gemini").lower()
    varsayilan = str(m.get("varsayilan") or "").strip()
    guclu = str(m.get("guclu") or "").strip()
    modeller = [x for x in dict.fromkeys([varsayilan, guclu]) if x]
    bolum = f"baglantilar.{ESKI_BAGLANTI}"
    metin = _anahtar_yaz(metin, bolum, "ad", _toml_deger(SAGLAYICI_KISA_AD.get(saglayici, saglayici)))
    metin = _anahtar_yaz(metin, bolum, "saglayici", _toml_deger(saglayici))
    taban = str(m.get("taban_url") or "").strip()
    if taban and saglayici == "openai":
        metin = _anahtar_yaz(metin, bolum, "taban_url", json.dumps(taban))
    metin = _anahtar_yaz(metin, bolum, "modeller", _toml_dizi(modeller))
    metin = _anahtar_yaz(metin, "model", "zincir", _toml_dizi([ESKI_BAGLANTI]))
    return metin


def _baglanti_hazirla() -> tuple[str | None, dict | None, str | None]:
    """policy metni + ayristirilmis hali; eski ayar gerekiyorsa baglantiya
    cevrilmis olarak (henuz YAZILMADI — cagiran tek _guvenli_yaz ile yazar)."""
    metin, ham, hata = _policy_metin()
    if hata:
        return None, None, hata
    metin = _eski_baglantiyi_olustur(metin, ham)
    # Onceki surumun [model] derin'i (Derin mod modeli): model artik sohbet
    # ekranindan seciliyor, bu anahtar okunmuyor — kalintiyi temizle.
    metin = _anahtar_sil(metin, "model", "derin")
    return metin, tomllib.loads(metin), None


def baglanti_yaz(kimlik: str, ad: str, saglayici: str, taban_url: str,
                 modeller: list[str]) -> tuple[str | None, str]:
    """Baglanti ekler (kimlik bos) ya da gunceller. (hata, kimlik) doner.

    Anahtar BURAYA YAZILMAZ: yeni baglantinin yuvasi 'api-<kimlik>', anahtari
    kopru anahtar.py'ye yazar. Saglayici sonradan degistirilemez: anahtar
    saglayici adiyla saklaniyor, degisirse eski anahtar sahipsiz kalirdi."""
    ad = " ".join(str(ad or "").split())
    if not ad or len(ad) > 40 or _BAGLANTI_AD_YASAK.search(ad):
        return t("Bağlantı adı 1-40 karakter olmalı, tırnak ve ters bölü içermemeli."), ""
    saglayici = str(saglayici or "").strip().lower()
    if saglayici not in SAGLAYICILAR:
        return t("Tanınmayan sağlayıcı: {s}. Geçerli: {g}", s=saglayici, g=", ".join(SAGLAYICILAR)), ""
    taban_url = str(taban_url or "").strip().rstrip("/") if saglayici == "openai" else ""
    if taban_url and not _URL_KALIBI.match(taban_url):
        return t("Sunucu adresi http:// ya da https:// ile başlamalı, boşluk içermemeli."), ""
    temiz: list[str] = []
    for m in modeller or []:
        m = model_temizle(str(m))
        if not m:
            continue
        if not model_gecerli(m):
            return t("'{m}' geçerli bir model adı değil.", m=m), ""
        if m not in temiz:
            temiz.append(m)
    if not temiz:
        return t("En az bir model adı yaz."), ""
    if len(temiz) > 20:
        return t("Bir bağlantıda en fazla 20 model olabilir."), ""
    metin, ham, hata = _baglanti_hazirla()
    if hata:
        return hata, ""
    mevcut = ham.get("baglantilar") or {}
    kimlik = str(kimlik or "").strip()
    if kimlik:
        if kimlik not in mevcut:
            return t("'{k}' adlı bir bağlantı yok.", k=kimlik), ""
        if str(mevcut[kimlik].get("saglayici") or "").lower() != saglayici:
            return t("Bağlantının sağlayıcısı değiştirilemez; yeni bir bağlantı ekle."), ""
    else:
        kimlik = _kimlik_uret(ad, set(mevcut))
    bolum = f"baglantilar.{kimlik}"
    metin = _anahtar_yaz(metin, bolum, "ad", _toml_deger(ad))
    metin = _anahtar_yaz(metin, bolum, "saglayici", _toml_deger(saglayici))
    metin = (_anahtar_yaz(metin, bolum, "taban_url", json.dumps(taban_url)) if taban_url
             else _anahtar_sil(metin, bolum, "taban_url"))
    metin = _anahtar_yaz(metin, bolum, "modeller", _toml_dizi(temiz))
    if kimlik not in mevcut:
        metin = _anahtar_yaz(metin, bolum, "anahtar_yuvasi", _toml_deger(BAGLANTI_YUVA_ONEKI + kimlik))
    m = tomllib.loads(metin).get("model", {}) or {}
    zincir = [str(x) for x in (m.get("zincir") or [])]
    if kimlik not in zincir:
        metin = _anahtar_yaz(metin, "model", "zincir", _toml_dizi(zincir + [kimlik]))
    return _guvenli_yaz(metin), kimlik


def baglanti_sil(kimlik: str) -> tuple[str | None, dict]:
    """Baglantiyi siler. (hata, {saglayici, yuva}) — kopru anahtari da siler."""
    kimlik = str(kimlik or "").strip()
    metin, ham, hata = _baglanti_hazirla()
    if hata:
        return hata, {}
    mevcut = ham.get("baglantilar") or {}
    if kimlik not in mevcut:
        return t("'{k}' adlı bir bağlantı yok.", k=kimlik), {}
    # Baglantiya bagli ajan sahipsiz kalirsa politika yuklenmez (fail-closed);
    # ham bir yukleme hatasi yerine sebebi soyle.
    kullanan = sorted(ad for ad, a in (ham.get("ajanlar") or {}).items()
                      if isinstance(a, dict) and str(a.get("baglanti") or "") == kimlik)
    if kullanan:
        return t("Bu bağlantıyı kullanan ajanlar var: {liste}. Önce onları başka bir bağlantıya bağla.",
                 liste=", ".join(kullanan)), {}
    bilgi = {"saglayici": str(mevcut[kimlik].get("saglayici") or ""),
             "yuva": str(mevcut[kimlik].get("anahtar_yuvasi") or "")}
    yeni = _bolum_sil(metin, f"baglantilar.{kimlik}")
    if yeni is None:
        return t("[baglantilar.{k}] bölümü bulunamadı; dosyayı elle düzenle.", k=kimlik), {}
    m = tomllib.loads(yeni).get("model", {}) or {}
    zincir = [str(x) for x in (m.get("zincir") or []) if str(x) != kimlik]
    yeni = (_anahtar_yaz(yeni, "model", "zincir", _toml_dizi(zincir)) if zincir
            else _anahtar_sil(yeni, "model", "zincir"))
    return _guvenli_yaz(yeni), bilgi


def zincir_yaz(sira: list[str]) -> str | None:
    """Baglantilarin kullanim sirasi. Mevcut baglantilarin tam bir permutasyonu olmali."""
    sira = [str(x) for x in (sira or [])]
    metin, ham, hata = _baglanti_hazirla()
    if hata:
        return hata
    mevcut = list((ham.get("baglantilar") or {}).keys())
    if sorted(sira) != sorted(mevcut) or len(set(sira)) != len(sira):
        return t("Sıralama mevcut bağlantılarla uyuşmuyor; sayfayı yenile.")
    return _guvenli_yaz(_anahtar_yaz(metin, "model", "zincir", _toml_dizi(sira)))


def model_temizle(ad: str) -> str:
    """Yapistirmadan gelen gurultuyu atar: bosluk ve 'models/' oneki. Buyuk/kucuk
    harf KORUNUR: bazi saglayicilarda ad buyuk harf tasiyabilir."""
    return (ad or "").strip().removeprefix("models/")


def saglayici_yaz(ad: str) -> str | None:
    """[model] saglayici = gemini | openai | anthropic."""
    ad = str(ad or "").strip().lower()
    if ad not in SAGLAYICILAR:
        return f"'{ad}' gecerli bir saglayici degil. Gecerli: {', '.join(SAGLAYICILAR)}"
    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"
    return _guvenli_yaz(_anahtar_yaz(metin, "model", "saglayici", f'"{ad}"'))


def taban_url_yaz(url: str) -> str | None:
    """[model] taban_url — OpenAI-uyumlu sunucu adresi. Bos = varsayilan (api.openai.com)."""
    url = str(url or "").strip().rstrip("/")
    if url and not _URL_KALIBI.match(url):
        return "Adres http:// ya da https:// ile baslamali, bosluk icermemeli."
    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"
    yeni = _anahtar_sil(metin, "model", "taban_url") if not url else _anahtar_yaz(metin, "model", "taban_url", json.dumps(url))
    return _guvenli_yaz(yeni)


def model_gecerli(ad: str) -> bool:
    return bool(_MODEL_KALIBI.match(model_temizle(ad)))


def model_yaz(etiket: str, ad: str) -> str | None:
    """[model] altindaki 'varsayilan' ya da 'guclu' adini degistirir.

    Yalnizca BICIM dogrulanir. Yanlis ama bicimce gecerli bir ad yazilirsa ilk
    gorevde API hata doner ve kullanici buradan geri alir — kalici bir hasar yok.
    Tirnak ve bosluk kalipta reddediliyor; deger TOML'a tirnak icinde girdigi
    icin bu kontrol bicimsel degil, zorunlu.
    """
    if etiket not in MODEL_ETIKETLERI:
        return f"Taninmayan model etiketi: {etiket}. Beklenen: varsayilan, guclu"
    temiz = model_temizle(ad)
    if not model_gecerli(temiz):
        return (f"'{ad}' model adi gibi gorunmuyor. Kucuk harf, rakam, tire ve "
                f"nokta kullanilir, en az 3 karakter. Ornek: gemini-3.5-flash-lite")
    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"
    return _guvenli_yaz(_anahtar_yaz(metin, "model", etiket, f'"{temiz}"'))


def sayi_yaz(bolum: str, anahtar: str, deger: Any) -> str | None:
    """policy.toml'daki sayisal bir siniri degistirir.

    Tavanlarda 0 'tavan yok' demektir. Adim/cagri sinirinda 0 anlamsiz oldugu
    icin alt sinir 1 — sifir adimli bir ajan hata degil, sessiz bir kilitlenme.
    """
    aralik = SAYI_ALANLARI.get((bolum, anahtar))
    if aralik is None:
        return f"Taninmayan sayisal ayar: {bolum}.{anahtar}"
    try:
        sayi = int(str(deger).strip())
    except (TypeError, ValueError):
        return f"'{deger}' tam sayi degil."
    alt, ust = aralik
    if not (alt <= sayi <= ust):
        return f"{anahtar} {alt} ile {ust} arasinda olmali ({sayi} verildi)."
    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"
    return _guvenli_yaz(_anahtar_yaz(metin, bolum, anahtar, str(sayi)))


def mod_yaz(mod: str, alan: str, deger: Any) -> str | None:
    """policy.toml [modlar.<mod>]'daki 'model'/'adim'/'cagri'/'istek' alanini
    degistirir.

    Mod izin gevsetmez (bkz. ARCHITECTURE.md) — burada yazilan uc alan da yalnizca
    "ne kadar hesap harcanacagi"ni belirler, gate.karar()'in verdigi ALLOW/ASK/DENY'e
    dokunmaz.
    """
    if mod not in MOD_ADLARI:
        return f"Taninmayan mod: {mod}. Beklenen: {', '.join(MOD_ADLARI)}"
    if alan not in MOD_ALANLARI:
        return f"Taninmayan mod alani: {alan}. Beklenen: {', '.join(MOD_ALANLARI)}"

    if alan == "model":
        if deger not in MOD_ROLLER:
            return f"'{deger}' gecersiz. Izinli: {', '.join(MOD_ROLLER)}"
        deger_metni = f'"{deger}"'
    else:
        try:
            sayi = int(str(deger).strip())
        except (TypeError, ValueError):
            return f"'{deger}' tam sayi degil."
        alt, ust = MOD_SAYI_ALANLARI[alan]
        if not (alt <= sayi <= ust):
            return f"{alan} {alt} ile {ust} arasinda olmali ({sayi} verildi)."
        deger_metni = str(sayi)

    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"
    return _guvenli_yaz(_anahtar_yaz(metin, f"modlar.{mod}", alan, deger_metni))


def varsayilan_mod_yaz(mod: str) -> str | None:
    """[modlar] varsayilan_mod anahtarini degistirir — mod verilmeden calistirilan
    gorevlerin hangi demeti (model + adim/cagri tavani) kullanacagi."""
    if mod not in MOD_ADLARI:
        return f"Taninmayan mod: {mod}. Beklenen: {', '.join(MOD_ADLARI)}"
    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"
    return _guvenli_yaz(_anahtar_yaz(metin, "modlar", "varsayilan_mod", f'"{mod}"'))


def bayrak_yaz(bolum: str, anahtar: str, deger: Any) -> str | None:
    """policy.toml'daki mantiksal bir ayari degistirir. Alan listesi KAPALI."""
    if (bolum, anahtar) not in BAYRAK_ALANLARI:
        return f"Taninmayan bayrak: {bolum}.{anahtar}"
    if not isinstance(deger, bool):
        return f"'{deger}' true/false degil."
    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"
    return _guvenli_yaz(_anahtar_yaz(metin, bolum, anahtar, "true" if deger else "false"))


def _kok_coz(yol: str) -> tuple[Path | None, str | None]:
    """Kullanicidan gelen yolu realpath ile cozer, klasor oldugunu dogrular.

    realpath sembolik baglantiyi da cozer: 'kum/link -> C:\\' diye bir baglanti
    kok olarak eklenirse gercek hedefe gore degerlendirilir.
    """
    ham = (yol or "").strip().strip('"')
    if not ham:
        return None, "Klasor yolu bos."
    try:
        aday = Path(os.path.realpath(Path(ham).expanduser()))
    except (OSError, ValueError) as e:
        return None, f"'{ham}' cozulemedi: {e}"
    if not aday.exists():
        # Modelin/kullanicinin duzeltebilmesi icin komsu klasorleri say.
        try:
            komsu = sorted(k.name for k in aday.parent.iterdir() if k.is_dir())[:8]
        except OSError:
            komsu = []
        ek = f" '{aday.parent}' icindeki klasorler: {', '.join(komsu)}" if komsu else ""
        return None, f"'{aday}' diskte yok.{ek}"
    if not aday.is_dir():
        return None, f"'{aday}' bir klasor degil. Kokler klasor olmali."
    return aday, None


def kok_ekle(tur: str, yol: str) -> str | None:
    """Okuma ya da yazma kokleri listesine bir klasor ekler.

    Yazma kokunde korunan yol kontrolu YAZMADAN ONCE yapilir: _guvenli_yaz
    ayni kontrolu yazdiktan sonra da yapiyor ve geri aliyor, ama kullaniciya
    "reddedildi ve geri alindi" yerine "neden olmaz" demek daha iyi.
    """
    anahtar = KOK_ANAHTARLARI.get(tur)
    if anahtar is None:
        return f"Taninmayan kok turu: {tur}. Beklenen: okuma, yazma"
    aday, hata = _kok_coz(yol)
    if hata:
        return hata

    try:
        from limina.gate import Politika, kod_kokleri, korunan_yol_ihlali
        pol = Politika(POLICY)
    except Exception as e:
        return f"policy.toml okunamadi: {e}"

    mevcut = pol.yazma if tur == "yazma" else pol.okuma
    if aday in mevcut:
        return f"'{aday}' zaten {tur} koklerinde."
    for k in mevcut:
        if k in aday.parents:
            return f"'{aday}' zaten '{k}' kokunun altinda, ayrica eklemeye gerek yok."

    if tur == "yazma":
        ihlal = next((h for k in kod_kokleri(KOK) if (h := korunan_yol_ihlali([aday], k))), None)
        if ihlal:
            return ihlal + " Bu klasor yazma koku olamaz."

    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"
    yeni = _dizi_oge_ekle(metin, "filesystem", anahtar, str(aday))
    if yeni is None:
        return f"policy.toml'daki {anahtar} dizisi cozulemedi, elle duzenle."
    return _guvenli_yaz(yeni)


def acma_klasoru_yaz(yol: str) -> str | None:
    """[acma] klasor = "<yol>" yazar. Bos yol = ozelligi kapatir.

    Yazmadan once gate.acma_klasoru_ihlali: klasor ajanin yazabildigi bir
    yerle kesisemez. Kural kapida da var (kesisirse klasor yok sayilir) ama
    kullaniciya "neden olmaz"i secim aninda soylemek daha iyi.
    """
    ham = (yol or "").strip().strip('"')
    if not ham:
        try:
            metin = POLICY.read_text(encoding="utf-8")
        except OSError as e:
            return f"policy.toml okunamadi: {e}"
        return _guvenli_yaz(_anahtar_yaz(metin, "acma", "klasor", '""'))
    aday, hata = _kok_coz(ham)
    if hata:
        return hata
    try:
        from limina.gate import Politika, acma_klasoru_ihlali
        pol = Politika(POLICY)
    except Exception as e:
        return f"policy.toml okunamadi: {e}"
    ihlal = acma_klasoru_ihlali(aday, pol.yazma, KOK)
    if ihlal:
        return ihlal
    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"
    # Ileri egik cizgi: TOML temel dizesinde ters egik cizgi kacis karakteri.
    return _guvenli_yaz(_anahtar_yaz(metin, "acma", "klasor", f'"{aday.as_posix()}"'))


def kok_sil(tur: str, yol: str) -> str | None:
    """Kok listesinden bir klasor cikarir.

    Son yazma kokunun silinmesine IZIN VERILIR: ajani yazamaz hale getirmek
    mesru bir tercih ve geri alinabilir. Daraltmak hicbir zaman guvenlik
    riski degildir, o yuzden burada korunan yol kontrolu yok.
    """
    anahtar = KOK_ANAHTARLARI.get(tur)
    if anahtar is None:
        return f"Taninmayan kok turu: {tur}. Beklenen: okuma, yazma"
    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"
    aday, _ = _kok_coz(yol)
    # Silmede diskte VARLIK ARANMAZ: silinmis bir klasorun kokunu temizleyebilmeliyiz.
    # Once dosyada yazili haliyle, sonra cozulmus haliyle denenir; ileri egik
    # cizgili hali de (sablon kokleri "C:/Users/..." diye yazar, panel ise
    # Windows bicimini gonderir).
    ham = str(yol).strip()
    for aday_metin in [ham, str(aday) if aday else None, ham.replace("\\", "/"),
                       aday.as_posix() if aday else None]:
        if not aday_metin:
            continue
        yeni = _dizi_oge_sil(metin, "filesystem", anahtar, aday_metin)
        if yeni is not None:
            return _guvenli_yaz(yeni)
    return (f"'{yol}' {anahtar} listesinde kendi satirinda bulunamadi. "
            f"policy.toml'da o satiri elle sil.")


# ---------------------------------------------------------------------------
# Calisma klasoru: ajanin hem okuyup hem yazdigi ana klasor (ilk yazma koku).
# Zorunlu DEGIL: kullanici baska bir klasor secebilir ya da hic secmeyebilir.
# ---------------------------------------------------------------------------

CALISMA_VARSAYILAN = Path.home() / "Limina"
_DIZE = re.compile(r'"(?:[^"\\]|\\.)*"|\'[^\']*\'')


def calisma_klasoru() -> Path | None:
    """Gecerli calisma klasoru (gate.Politika.calisma; Ekip de bunu varsayilan alir)."""
    try:
        from limina.gate import Politika
        pol = Politika(POLICY)
    except Exception:
        return None
    return pol.calisma


def _yol_ogelerini_degistir(metin: str, eski: Path, yeni: Path | None) -> tuple[str, int]:
    """policy.toml metninde eski klasoru gosteren her dize ogesini yeni ile
    degistirir (yeni None ise dizi ogesi silinir). Yorumlar ve duzen korunur.
    Yalnizca TAM ESLESEN yollar: alt klasorler (eski/alt) dokunulmaz.
    Doner: (yeni metin, degisen oge sayisi)."""
    sayi = 0
    cikis: list[str] = []
    for satir in metin.splitlines():
        kod, yorum = satir, ""
        if satir.lstrip().startswith("#"):
            cikis.append(satir)
            continue
        if "#" in satir:
            # dize icindeki # yorum degildir; dizelerden sonra gelen ilk # yorumdur
            son = 0
            for m in _DIZE.finditer(satir):
                son = m.end()
            i = satir.find("#", son)
            if i >= 0:
                kod, yorum = satir[:i], satir[i:]

        def esles(m: re.Match) -> bool:
            ham = m.group(0)
            try:
                deger = json.loads(ham) if ham.startswith('"') else ham[1:-1]
                return bool(deger) and Path(deger).expanduser().resolve() == eski
            except (ValueError, OSError):
                return False

        eslesenler = [m for m in _DIZE.finditer(kod) if esles(m)]
        if not eslesenler:
            cikis.append(satir)
            continue
        sayi += len(eslesenler)
        if yeni is not None:
            for m in reversed(eslesenler):
                kod = kod[:m.start()] + json.dumps(str(yeni)) + kod[m.end():]
            cikis.append(kod + yorum)
            continue
        # Silme: dizi ogesi kendi satirindaysa satir gider; tek satirlik
        # dizideyse oge ve virgulu cikar.
        if kod.strip().rstrip(",").strip() == eslesenler[0].group(0) and len(eslesenler) == 1:
            continue
        for m in reversed(eslesenler):
            bas, son = m.start(), m.end()
            sag = kod[son:]
            if sag.lstrip().startswith(","):
                son += len(sag) - len(sag.lstrip()) + 1
                sag = kod[son:]
                son += len(sag) - len(sag.lstrip())
            else:
                sol = kod[:bas].rstrip()
                if sol.endswith(","):
                    bas = len(sol) - 1
            kod = kod[:bas] + kod[son:]
        cikis.append(kod + yorum)
    return "\n".join(cikis) + "\n", sayi


def calisma_klasoru_degistir(yol: str) -> str | None:
    """Calisma klasorunu degistirir: eski klasorun gectigi HER yer (okuma,
    yazma, yerel dosya kokleri, gorev profilleri) yeni klasore tasinir.
    Bos yol = calisma klasoru yok (ajan dosya yazamaz; sonra eklenebilir).
    Hata varsa metin doner, yoksa None. Eski klasorun DOSYALARINA dokunulmaz."""
    ham = (yol or "").strip().strip('"')
    eski = calisma_klasoru()
    try:
        metin = POLICY.read_text(encoding="utf-8")
    except OSError as e:
        return f"policy.toml okunamadi: {e}"
    if not ham:
        if eski is None:
            return None
        yeni_metin, sayi = _yol_ogelerini_degistir(metin, eski, None)
        return _guvenli_yaz(yeni_metin) if sayi else None
    aday, hata = _kok_coz(ham)
    if hata:
        return hata
    if eski is not None and aday == eski:
        return None
    from limina.gate import Politika, kod_kokleri, korunan_yol_ihlali
    ihlal = next((h for k in kod_kokleri(KOK) if (h := korunan_yol_ihlali([aday], k))), None)
    if ihlal:
        return ihlal + " Bu klasor calisma klasoru olamaz."
    if eski is not None:
        try:
            if aday in Politika(POLICY).yazma:
                return f"'{aday}' zaten bir yazma koku."
        except Exception as e:
            return f"policy.toml okunamadi: {e}"
        yeni_metin, sayi = _yol_ogelerini_degistir(metin, eski, aday)
        if sayi:
            return _guvenli_yaz(yeni_metin)
    # Calisma klasoru yoktu (ya da metinde bulunamadi): okuma + yazma koku olarak ekle.
    hata = kok_ekle("yazma", str(aday))
    if hata:
        return hata
    hata = kok_ekle("okuma", str(aday))
    return None if hata is None or "zaten" in hata else hata


def persona_oku() -> str:
    try:
        return PERSONA_YOL.read_text(encoding="utf-8")
    except OSError:
        return ""


def persona_yaz(metin: str) -> str | None:
    """config/persona.md dosyasini degistirir.

    Boyut siniri var cunku bu metin HER ISTEKTE gonderiliyor: uzun bir persona
    her gorevi kaliciken pahalilastirir. policy.toml protokolunden gecmez —
    persona bir izin sinirini degistirmiyor, modele verilen bir tercih metni.
    """
    yeni = (metin or "").strip()
    if len(yeni) > PERSONA_AZAMI:
        return (f"Hafiza {len(yeni)} karakter, sinir {PERSONA_AZAMI}. "
                f"Bu metin her istekte gonderiliyor; kisalt.")
    try:
        PERSONA_YOL.parent.mkdir(parents=True, exist_ok=True)
        _atomik_yaz(PERSONA_YOL, yeni + ("\n" if yeni else ""))
    except OSError as e:
        return f"persona.md yazilamadi: {e}"
    return None


def _acma_ogeleri(pol) -> list[str]:
    try:
        from limina.araclar.acma import acilabilir_ogeler
        return acilabilir_ogeler(pol)
    except Exception:
        return []


def policy_oku() -> dict[str, Any]:
    """Panelin gosterecegi salt-okunur ozet + duzenlenebilir tablolar."""
    try:
        from limina.gate import EYLEM_TABAN, Politika
        pol = Politika(POLICY)
    except Exception as e:
        return {"ok": False, "hata": f"policy.toml okunamadi: {e}"}
    return {
        "ok": True,
        "eylemler": dict(getattr(pol, "eylem_varsayilan", EYLEM_TABAN)),
        "profiller": {k: dict(v) for k, v in getattr(pol, "site_profilleri", {}).items()},
        "izinli_alanlar": list(pol.izinli_alanlar),
        "okuma_koklari": [str(k) for k in pol.okuma],
        "yazma_koklari": [str(k) for k in pol.yazma],
        "calisma_klasoru": str(pol.calisma) if pol.calisma else "",
        # Acma klasoru: politika dosyasindaki ham deger + kapinin kabul ettigi hali
        # (kesisim varsa None) + reddin nedeni. Panel ucunu de gosterir.
        "acma_klasoru": str(pol.acma_klasoru) if pol.acma_klasoru else "",
        "acma_hatasi": pol.acma_hatasi or "",
        "acma_ogeleri": _acma_ogeleri(pol),
        "yasak_kaliplar": list(pol.yasak),
        "araclar": dict(pol.araclar),
        "model_varsayilan": getattr(pol, "model_varsayilan", ""),
        "model_guclu": getattr(pol, "model_guclu", ""),
        "gunluk_tavan": dict(getattr(pol, "gunluk_tavan", {})),
        "azami_adim": getattr(pol, "azami_adim", 0),
        "azami_cagri": getattr(pol, "azami_cagri", 0),
        "modlar": {ad: dict(demet) for ad, demet in getattr(pol, "modlar", {}).items()},
        "varsayilan_mod": getattr(pol, "varsayilan_mod", ""),
        "persona_acik": getattr(pol, "persona_acik", True),
        "kod_koku_guvenli": pol.kod_koku_yazilabilir_mi(KOK) is None,
    }


# ---------------------------------------------------------------------------
# Ilk kurulum ekrani: dil, klasorler, eklentiler, gorunum. Her adimin bir
# varsayilani var; ekran "Varsayilanlarla devam" ile tek tikla gecilebilir.
# Yazmalar mevcut korumali yollardan gecer (kok_ekle/kok_sil, paket_*).
# ---------------------------------------------------------------------------

EK_KLASORLER = (("Downloads", "İndirilenler"), ("Desktop", "Masaüstü"), ("Documents", "Belgeler"))


def _ev() -> Path:
    """Ev klasoru (testler gecici klasore yonlendirir)."""
    return Path.home()


def kurulum_gerekli() -> bool:
    return not arayuz_oku()["genel"]["kurulum_tamam"]


def _secilebilir_paketler(pol) -> list[dict[str, Any]]:
    from limina import paketler
    try:
        from limina.eklentiler import registry
    except ImportError:
        registry = None
    sonuc = []
    for ad, p in paketler.YERLESIK.items():
        if p.get("cekirdek") or p.get("gizli"):
            continue
        if registry is not None and ad in registry.CATALOG:
            if not registry.available(ad):
                continue
            acik = registry.enabled(ad, pol)
        else:
            acik = ad not in getattr(pol, "kaldirilan", [])
        sonuc.append({"ad": ad, "baslik": p.get("ad", ad), "aciklama": p.get("aciklama", ""),
                      "ikon": p.get("ikon", "araclar"), "acik": acik})
    return sonuc


def kurulum_durumu() -> dict[str, Any]:
    """Kurulum ekraninin baslangic hali: gecerli ayarlar = ekranin varsayilanlari."""
    try:
        from limina.gate import Politika
        pol = Politika(POLICY)
    except Exception as e:
        return {"ok": False, "hata": f"policy.toml okunamadi: {e}"}
    a = arayuz_oku()
    calisma = pol.calisma
    return {
        "ok": True,
        "gerekli": not a["genel"]["kurulum_tamam"],
        "dil": a["genel"]["dil"],
        "tema": a["gorunum"]["tema"],
        "ekip_gorunumu": a["gorunum"]["ekip_gorunumu"],
        "calisma": str(calisma) if calisma else "",
        "calisma_varsayilan": str(CALISMA_VARSAYILAN),
        "ek_klasorler": [{"ad": ad, "baslik": baslik, "yol": str(_ev() / ad),
                          "var": (_ev() / ad).is_dir(),
                          "secili": (_ev() / ad).resolve() in pol.okuma}
                         for ad, baslik in EK_KLASORLER],
        "paketler": _secilebilir_paketler(pol),
    }


def kurulum_uygula(veri: dict[str, Any]) -> list[str]:
    """Kurulum ekranindaki secimleri yazar. Doner: hata metinleri (bos = tamam).
    Bir adim basarisiz olsa da digerleri denenir; kurulum yine TAMAM sayilir
    ki kullanici ekranda kilitli kalmasin — hatalar ona gosterilir ve hepsi
    Ayarlar'dan duzeltilebilir.

    veri: {dil, tema, ekip_gorunumu,
           calisma: {"tur": "varsayilan"|"ozel"|"yok", "yol": str},
           ek_klasorler: {"Downloads": bool, ...}, paketler: {ad: bool}}"""
    hatalar: list[str] = []

    def not_et(h: str | None) -> None:
        if h:
            hatalar.append(h)

    for bolum, anahtar in (("genel", "dil"), ("gorunum", "tema"), ("gorunum", "ekip_gorunumu")):
        if veri.get(anahtar) is not None:
            not_et(arayuz_yaz(bolum, anahtar, veri[anahtar]))

    secim = veri.get("calisma") or {}
    tur = secim.get("tur")
    eski = calisma_klasoru()
    if tur == "varsayilan":
        try:
            CALISMA_VARSAYILAN.mkdir(parents=True, exist_ok=True)
            not_et(calisma_klasoru_degistir(str(CALISMA_VARSAYILAN)))
        except OSError as e:
            hatalar.append(f"{CALISMA_VARSAYILAN} acilamadi: {e}")
    elif tur == "ozel":
        not_et(calisma_klasoru_degistir(str(secim.get("yol") or "")) if secim.get("yol")
               else "Calisma klasoru secilmedi.")
    elif tur == "yok":
        not_et(calisma_klasoru_degistir(""))
    # Varsayilan klasor kullanilmadiysa ve BOSSA kaldirilir (ilk acilista
    # kendiliginden acilmisti; kullanicinin diskinde iz birakmasin).
    yeni = calisma_klasoru()
    varsayilan = CALISMA_VARSAYILAN.resolve()
    if eski == varsayilan and yeni != varsayilan:
        try:
            varsayilan.rmdir()          # bos degilse OSError: dokunulmaz
        except OSError:
            pass

    try:
        from limina.gate import Politika
        okuma = Politika(POLICY).okuma
    except Exception:
        okuma = []
    for ad, istenen in (veri.get("ek_klasorler") or {}).items():
        if ad not in dict(EK_KLASORLER):
            continue
        yol = _ev() / ad
        if bool(istenen) and yol.is_dir() and yol.resolve() not in okuma:
            h = kok_ekle("okuma", str(yol))
            not_et(None if h and "zaten" in h else h)      # zaten kapsanmis: sorun degil
        elif not istenen and yol.resolve() in okuma:
            not_et(kok_sil("okuma", str(yol)))

    try:
        from limina.gate import Politika
        mevcut = {p["ad"]: p["acik"] for p in _secilebilir_paketler(Politika(POLICY))}
    except Exception:
        mevcut = {}
    for ad, istenen in (veri.get("paketler") or {}).items():
        if ad in mevcut and bool(istenen) != mevcut[ad]:
            not_et(paket_geri_ekle(ad) if istenen else paket_kaldir(ad))

    not_et(arayuz_yaz("genel", "kurulum_tamam", True))
    return hatalar
