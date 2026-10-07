"""paketler.py — araclarin kullaniciya gorunen gruplari ("paketler").

Bir paket = bir yetenek blogu: tarayici, dosya duzenleme, belge okuma ya da
bir MCP sunucusu. Kullanici paketi bir butun olarak KALDIRABILIR; kaldirilan
paketin araclari policy.toml [araclar]'dan dusurulur (gate.Politika), yani
kapi onlari tanimaz (DENY), modele semalari gitmez, sistem talimatindaki
cumleleri kurulmaz, MCP sunucusu baslatilmaz. Kaynak kod silinmez — paket
"Geri ekle" ile ayni varsayilan risk seviyeleriyle doner.

Cekirdek paket (cekirdek=True) kaldirilamaz: ajanin bir sey OKUYABILMESI
icin gereken asgari kume. Sohbet basina kapatilabilir (Oturum daraltmasi),
politikadan dusurulemez.

Bu modul SAF VERI + saf fonksiyonlardir: gate, vekil_v0 ya da pywebview'e
bagli degildir; gate onu ice aktarir (tersi degil).

Kaldirma kaydi policy.toml'da tutulur:
    [paketler]
    kaldirilan = ["tarayici", "belge"]
Yalnizca DARALTIR: bu liste hicbir araca izin ekleyemez.

MCP paketleri (policy.toml [mcp.<ad>]) burada TANIMLI DEGIL — sunucu adi
paket adidir ("mcp:<ad>"), araclari sunucu kesfedildiginde belli olur ve
[araclar]'da siniflandirildigi kadari modele gider.
"""
from __future__ import annotations

from typing import Any, Iterable

# Insan dilindeki adlar/aciklamalar arayuzde t() ile cevrilir; buradaki
# metinler KAYNAK dil (Turkce) anahtarlaridir.
# Yerlesik paketlerin KIMLIGI burada (ad, ikon, aciklama, cekirdek mi); hangi
# aracin hangi pakete ait oldugu ve varsayilan riski KAYIT DEFTERINDEN gelir
# (pevrai.araclar.kayit — her arac kendi @arac bildiriminde paketini soyler).
# Boylece yeni bir arac eklemek icin buraya dokunulmaz.
from pevrai.araclar import kayit as _kayit

_PAKET_KIMLIK: dict[str, dict[str, Any]] = {
    "cekirdek": {
        "ad": "Temel okuma",
        "ikon": "kalkan",
        "cekirdek": True,
        "aciklama": ("Klasörleri listeler, metin dosyalarını okur, dosya adı ve içeriğinde arar. "
                     "Kaldırılamaz."),
    },
    "belge": {
        "ad": "Belge okuma",
        "ikon": "dosya",
        "cekirdek": False,
        "aciklama": "PDF, DOCX, PPTX, XLSX ve CSV dosyalarından metin çıkarır (OCR yok).",
    },
    "dosya_duzenleme": {
        "ad": "Dosya düzenleme",
        "ikon": "klasor",
        "cekirdek": False,
        "aciklama": ("Dosya oluşturur, düzenler, taşır, yeniden adlandırır ve çöpe taşır. Her "
                     "yazma yedeklenir; kalıcı silme yoktur."),
    },
    "acma": {
        "ad": "Dosya ve uygulama açma",
        "ikon": "disa",
        "cekirdek": False,
        "aciklama": ("Seçtiğin klasördeki dosyaları ilişkili programla, kısayolları hedefleriyle "
                     "açar. Ajan bu klasöre yazamaz; her açma onay ister."),
    },
    "ekip": {
        "ad": "Ekip panosu",
        "ikon": "konusma",
        "cekirdek": False,
        "gizli": True,          # panelde yok: bu araclar yalnizca ekip iscisi politikasinda
        "aciklama": "Ekip görevinde ajanların birbirine mesaj yazdığı pano (ekip_mesaj, ekip_gelen).",
    },
    "ag": {
        "ad": "Düşünce Ağı",
        "ikon": "ag",
        "cekirdek": False,
        "aciklama": ("Baloncuk ve ağırlıklı bağlantılardan oluşan düşünce ağlarını ateşler ve "
                     "düzenler. Dosya baloncukları okuma iznine tabidir."),
    },
    "tarayici": {
        "ad": "Tarayıcı",
        "ikon": "web",
        "cekirdek": False,
        "aciklama": ("Chrome'u ayrı bir profille açar; izinli sitelerde okur, tıklar, form "
                     "doldurur ve indirir. Parola ve kart bilgisi girmez."),
    },
}

YERLESIK: dict[str, dict[str, Any]] = {
    ad: {**kimlik, "araclar": _kayit.paketler().get(ad, {})} for ad, kimlik in _PAKET_KIMLIK.items()
}
# Kayit defterinde bilinmeyen bir pakete kaydedilmis arac varsa (yeni modul,
# kimlik yazilmamis) yine de gorunsun: adiyla, ikonsuz.
for _paket, _araclar in _kayit.paketler().items():
    YERLESIK.setdefault(_paket, {"ad": _paket, "ikon": "araclar", "cekirdek": False,
                                 "aciklama": "", "araclar": _araclar})

# Her aracin insan dilindeki adi ve tek cumlelik aciklamasi — @arac bildiriminden
# (baslik, aciklama). Teknik ad arayuzde ACIKLAMANIN icinde gosterilir.
ARAC_BILGI: dict[str, tuple[str, str]] = _kayit.bilgiler()

RISK_SEVIYELERI = ("READ", "WRITE_HAFIF", "WRITE", "EXEC", "NETWORK", "DESTRUCTIVE")

# MCP aracinin dize argumani yol mu? Ad ipucu (path/src/dst/dir/file/folder ve
# Turkce karsiliklari). Kesin degil; panel secici gosterir, kullanici karar verir.
import re as _re
YOL_ADI = _re.compile(r"(path|src|dst|dir|file|folder|yol|dosya|klasor|kaynak|hedef|root)", _re.I)

# Optional packages provide metadata only here; services and databases load lazily.
try:
    from pevrai.eklentiler.registry import CATALOG as _EKLENTILER, TOOLS as _EKLENTI_ARACLARI
except ImportError:
    _EKLENTILER, _EKLENTI_ARACLARI = {}, {}
YERLESIK.update(_EKLENTILER)

# Eklenti araclarinin adi "nesne_eylem" (course_create): panelde insan dilinde
# baslik bu iki parcadan kurulur, aciklama aracin kendi sema aciklamasi.
_NESNE = {"course": "Ders", "exam": "Sınav", "topic": "Konu", "study_plan": "Çalışma planı",
          "study_session": "Çalışma kaydı", "study": "Çalışma", "focus": "Odak", "note": "Not",
          "workspace": "Proje", "task": "Görev"}
_EYLEM = {"create": "oluşturma", "get": "okuma", "list": "listeleme", "update": "güncelleme",
          "delete": "silme", "log": "kaydetme", "stats": "istatistik", "start": "başlatma",
          "status": "durumu", "pause": "duraklatma", "resume": "sürdürme", "finish": "bitirme",
          "search": "arama", "read": "okuma", "link": "bağlama", "archive": "arşivleme",
          "history": "geçmişi", "restore": "geri yükleme", "context": "bağlamı", "attach": "dosya bağlama",
          "detach": "dosya ayırma", "resolve": "yol doğrulama", "note_link": "not bağlama",
          "log_list": "günlük listeleme"}


def arac_bilgisi(arac: str) -> tuple[str, str]:
    """(baslik, aciklama). Yerlesik araclar ARAC_BILGI'den; eklenti araclari
    addan turetilir + sema aciklamasi; bilinmeyen arac teknik adiyla."""
    if arac in ARAC_BILGI:
        return ARAC_BILGI[arac]
    if arac in _EKLENTI_ARACLARI:
        for nesne in sorted(_NESNE, key=len, reverse=True):
            if arac.startswith(nesne + "_"):
                eylem = arac[len(nesne) + 1:]
                return (f"{_NESNE[nesne]} {_EYLEM.get(eylem, eylem.replace('_', ' '))}",
                        str(_EKLENTI_ARACLARI[arac].get("description") or ""))
        return (arac.replace("_", " ").capitalize(), str(_EKLENTI_ARACLARI[arac].get("description") or ""))
    return (arac, "")

MCP_ONEK = "mcp:"


def yerlesik_araclari(kaldirilan: Iterable[str]) -> set[str]:
    """Kaldirilmis yerlesik paketlerin arac adlari. Cekirdek asla dahil degil."""
    cikti: set[str] = set()
    for ad in kaldirilan:
        p = YERLESIK.get(ad)
        if p and not p["cekirdek"]:
            cikti.update(p["araclar"])
    return cikti


def mcp_adi(paket: str) -> str | None:
    """'mcp:converter' -> 'converter'; yerlesik paket adiysa None."""
    return paket[len(MCP_ONEK):] if paket.startswith(MCP_ONEK) else None


def paket_listesi(politika_araclar: dict[str, str], mcp_sunuculari: Iterable[str],
                  kaldirilan: Iterable[str], kesfedilen: dict[str, Any],
                  durumlar: dict[str, tuple[str, str]], olu: dict[str, str],
                  yol_bildirimleri: dict[str, dict[str, str]] | None = None) -> list[dict]:
    """Arayuzun cizdigi paket kartlari. SAF: hicbir sey okumaz.

    politika_araclar: policy.toml [araclar] (kaldirilanlar DUSURULMUS hali)
    mcp_sunuculari:   policy.toml [mcp] adlari (baslatilanlar)
    kaldirilan:       [paketler] kaldirilan
    kesfedilen:       kesfedilen MCP araclari "sunucu.arac" -> aciklama
    durumlar:         arac -> (durum, sebep) — acik/kapali/gizli/kesfedilmedi
    olu:              cokmus MCP sunuculari -> sebep
    """
    kaldirilan = set(kaldirilan)
    cikti: list[dict] = []

    for ad, p in YERLESIK.items():
        if p.get("gizli"):
            continue            # ekip panosu gibi: yalnizca isci politikasinda, panelde degil
        araclar = []
        for arac, risk in p["araclar"].items():
            baslik, aciklama = arac_bilgisi(arac)
            durum, sebep = durumlar.get(arac, ("kaldirildi", ""))
            araclar.append({"ad": arac, "baslik": baslik, "aciklama": aciklama,
                            "risk": politika_araclar.get(arac, risk),
                            "durum": durum if ad not in kaldirilan else "kaldirildi", "sebep": sebep})
        cikti.append({
            "paket": ad, "tur": "yerlesik", "ad": p["ad"], "ikon": p["ikon"],
            "aciklama": p["aciklama"], "cekirdek": p["cekirdek"],
            # Yeni surumle gelen ama kullanicinin policy.toml'unda satiri olmayan
            # araclar: panel "Eksik araclari ekle" gosterir (paket_geri_ekle yazar).
            "eksik": [a for a in p["araclar"] if a not in politika_araclar] if ad not in kaldirilan else [],
            "kurulu": ad not in kaldirilan and (not p.get("optional") or any(a in politika_araclar for a in p["araclar"])), "araclar": araclar,
        })

    # MCP paketleri: policy'de tanimli sunucular + (policy'den silinmis ama
    # bu oturumda hala bagli) kesfedilenler.
    sunucular = list(mcp_sunuculari)
    for tam_ad in kesfedilen:
        s = tam_ad.partition(".")[0]
        if s not in sunucular:
            sunucular.append(s)
    for s in sunucular:
        araclar = []
        adlar = sorted({a for a in politika_araclar if a.startswith(s + ".")}
                       | {a for a in kesfedilen if a.startswith(s + ".")})
        for tam_ad in adlar:
            arac = tam_ad.partition(".")[2]
            durum, sebep = durumlar.get(tam_ad, ("kesfedilmedi", ""))
            bilgi = kesfedilen.get(tam_ad, "")
            if isinstance(bilgi, dict):
                aciklama, dize_argumanlar = bilgi.get("aciklama", ""), list(bilgi.get("dize_argumanlar", []))
            else:
                aciklama, dize_argumanlar = str(bilgi), []
            araclar.append({"ad": tam_ad, "baslik": arac.replace("_", " ").capitalize(),
                            "aciklama": aciklama,
                            "risk": politika_araclar.get(tam_ad), "durum": durum, "sebep": sebep,
                            # yol bildirimi {arg: oku|yaz}; yol-benzeri dize argumanlari panel secici gosterir
                            "yollar": dict((yol_bildirimleri or {}).get(tam_ad, {})),
                            "yol_adaylari": [a for a in dize_argumanlar if YOL_ADI.search(a)]})
        cikti.append({
            "paket": MCP_ONEK + s, "tur": "mcp", "ad": s, "ikon": "araclar",
            "aciklama": "", "cekirdek": False, "kurulu": True,
            "tanimli": s in list(mcp_sunuculari),      # policy.toml'da [mcp.s] var mi
            "hata": olu.get(s), "araclar": araclar,
        })
    return cikti
