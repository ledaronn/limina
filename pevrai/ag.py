"""ag.py — Düşünce Ağı: depo, izin köprüsü, arayüz/araç uyarlayıcısı.

Yayılımın kendisi `pevrai/ag_motoru.py` içindedir ve pevrai'dan bağımsızdır.
Bu modül üç işi yapar:

  1. DEPO. Ağlar ~/.vekil/aglar/<ad>.json altında durur — ajanın yazma kökünde
     DEĞİL: ajan write_file ile bir ağı ya da bir dosya düğümünün yolunu
     değiştiremez. Kaydetmeden önce motorla doğrulanır; bozuksa diske HİÇ
     yazılmaz (fail-closed). Her kayıtta eski hal .gecmis/ altına kopyalanır.
  2. İZİN KÖPRÜSÜ. Motor kapı kararı vermez; `izin_fn` Pevrai'nın kendi
     `yol_dogrula`'sını çağırır. ALLOW değilse düğüm ateşlemez (ASK de değil:
     yayılımın ortasında onay sorulmaz). İçerik okunurken yol YENİDEN
     doğrulanır ve çözülmüş yoldan okunur (ateşleme ile okuma arasında yolun
     değişmesi işe yaramasın).
  3. UYARLAYICI. Arayüz ve araçlar için düz sözlük biçimi (animasyon tik
     damgaları, sessiz/engellenen sebepleriyle).
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from pevrai import ag_motoru as motor
from pevrai import journal as _journal
from pevrai.ag_motoru import AgHatasi, KAPILAR, KAPI_ADLARI, TURLER  # noqa: F401  (dışarıya)
from pevrai.ceviri import t

AG_KOK = _journal.KOK / "aglar"
GECMIS_TAVANI = 20
AD_KALIBI = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,47}$")


# ---------------------------------------------------------------------------
# Dogrulama ve depo
# ---------------------------------------------------------------------------

def dogrula(ham: dict) -> tuple[dict | None, str | None]:
    """(temiz ham sözlük, hata). Motor şemayı doğrular; konum/etiket gibi
    arayüze ait alanlar ham sözlükte OLDUĞU GİBİ kalır (motor onları taşımaz)."""
    if not isinstance(ham, dict):
        return None, t("ağ bir JSON nesnesi olmalı")
    ad = str(ham.get("ad") or "").strip()
    if not AD_KALIBI.match(ad):
        return None, t("Ağ adı geçersiz: harf/rakam ile başlar, en fazla 48 karakter.")
    try:
        motor.ag_yukle(ham)
    except AgHatasi as e:
        return None, str(e)
    temiz = {"ad": ad, "aciklama": str(ham.get("aciklama") or "")[:500],
             # Tetik: "bu ag ne zaman atesLENMELI" — tek cumle. Talimata yazilir
             # ki ajan dogru agi ARAC CAGIRMADAN secebilsin.
             "tetik": " ".join(str(ham.get("tetik") or "").split())[:200],
             "dugumler": [_dugum_temizle(d) for d in ham["dugumler"]],
             "baglantilar": [{"kaynak": b["kaynak"], "hedef": b["hedef"],
                              "agirlik": float(b.get("agirlik", 1.0)),
                              "gecikme": int(b.get("gecikme", 1))} for b in ham.get("baglantilar", [])],
             "guncelleme": datetime.now().isoformat(timespec="seconds")}
    return temiz, None


def _dugum_temizle(d: dict) -> dict:
    """Depoya yazılan biçim. Boş alanlar da yazılır (arayüz onları bekliyor);
    motor boş değeri "alan yok" sayar."""
    kapi = KAPI_ADLARI.get(d.get("kapi") or "herhangi", "herhangi")
    konum = d.get("konum") or [0.0, 0.0, 0.0]
    return {"kimlik": d["kimlik"], "tur": d.get("tur") or "fikir",
            "baslik": d.get("baslik") or "", "metin": d.get("metin") or "",
            "yol": d.get("yol") or "", "kapi": kapi,
            "esik": d.get("esik") if kapi == "esik" else None,
            "k": d.get("k") if kapi == "en_az" else None,
            "yanlilik": float(d.get("yanlilik") or 0) if kapi == "esik" else 0,
            "sira": d.get("sira"), "kaynak": d.get("kaynak") or "kullanici",
            "renk": _renk(d.get("renk")), "konum": [float(c) for c in konum],
            "etiketler": [str(e)[:32] for e in (d.get("etiketler") or [])][:10]}


def _renk(deger) -> str:
    """Baloncugun kullanici rengi. Yalnizca #rrggbb; bos = turun rengi.
    Kapali kume: tuvale rastgele dize gitmesin."""
    s = str(deger or "").strip().lower()
    return s if re.fullmatch(r"#[0-9a-f]{6}", s) else ""


def tasi(ham: dict) -> tuple[dict, list[str]]:
    """v1 ağını v2 şemasına taşır. (ham, yapılan değişiklikler)

    İki uyumsuzluk var: (a) 'esik' artık yalnızca kapi='esik' ile kabul ediliyor,
    (b) döngü içindeki engelleyici bağlantı reddediliyor. Kullanıcının ağını
    sessizce bozmak yerine taşıyıp ne yaptığımızı söylüyoruz."""
    notlar: list[str] = []
    for d in ham.get("dugumler", []):
        kapi = KAPI_ADLARI.get(d.get("kapi") or "herhangi", "herhangi")
        d["kapi"] = kapi
        if kapi != "esik" and d.get("esik") is not None:
            notlar.append(t("'{k}': eşik değeri kaldırıldı ('{kapi}' kapısı eşik kullanmaz).",
                            k=d.get("kimlik"), kapi=kapi))
            d["esik"] = None
        if kapi != "esik" and d.get("yanlilik"):
            notlar.append(t("'{k}': yanlılık kaldırıldı (yalnızca eşik kapısında anlamlı).", k=d.get("kimlik")))
            d["yanlilik"] = 0
        if d.get("tur") != "dosya" and d.get("yol"):
            notlar.append(t("'{k}': yol kaldırıldı (dosya düğümü değil).", k=d.get("kimlik")))
            d["yol"] = ""
    # Dongu ici engelleyiciler: motor reddediyor. Tek tek cikarip haber ver.
    while True:
        try:
            motor.ag_yukle(ham)
            break
        except AgHatasi as e:
            eslesme = re.search(r"'([^']+)' -> '([^']+)'", str(e))
            if not eslesme:
                break
            ka, he = eslesme.group(1), eslesme.group(2)
            onceki = len(ham.get("baglantilar", []))
            ham["baglantilar"] = [b for b in ham.get("baglantilar", [])
                                  if not (b.get("kaynak") == ka and b.get("hedef") == he)]
            if len(ham["baglantilar"]) == onceki:
                break
            notlar.append(t("{ka} → {he} bağlantısı kaldırıldı: döngü içinde engelleme/olumsuzlama "
                            "sonucu sıraya bağlı yapardı.", ka=ka, he=he))
    return ham, notlar


def ag_yolu(ad: str) -> Path:
    return AG_KOK / (re.sub(r"[^A-Za-z0-9_-]+", "-", ad.strip()).strip("-").lower() + ".json")


def aglar() -> list[dict]:
    cikti = []
    if not AG_KOK.exists():
        return cikti
    for y in sorted(AG_KOK.glob("*.json")):
        try:
            veri = json.loads(y.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(veri, dict) or not veri.get("ad"):
            continue
        dugumler = veri.get("dugumler") or []
        cikti.append({"ad": veri["ad"], "dosya": y.name, "aciklama": veri.get("aciklama", ""),
                      "tetik": veri.get("tetik", ""),
                      "dugum": len(dugumler), "baglanti": len(veri.get("baglantilar") or []),
                      # Tamami ajan yazmissa listede rozet: kullanici neyin kendisine
                      # ait oldugunu bir bakista gorsun.
                      "ajan": bool(dugumler) and all(d.get("kaynak") == "ajan" for d in dugumler),
                      "guncelleme": veri.get("guncelleme", "")})
    return cikti


def oku(ad: str) -> tuple[dict | None, str | None]:
    y = ag_yolu(ad)
    if not y.is_file():
        return None, t("'{ad}' adlı ağ yok.", ad=ad)
    try:
        veri = json.loads(y.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, t("'{ad}' okunamadı: {hata}", ad=ad, hata=e)
    temiz, hata = dogrula(veri)
    if hata:                      # v1'den kalma ag olabilir: tasimayi dene
        tasinan, notlar = tasi(veri)
        temiz, hata2 = dogrula(tasinan)
        if temiz:
            yaz(temiz)
            temiz["tasima_notlari"] = notlar
            return temiz, None
        return None, hata2 or hata
    return temiz, None


def _gecmise_al(y: Path) -> None:
    """Kayıttan önceki hal .gecmis/<ad>/<zaman>.json. Ajan da ağa yazabildiği
    için "ağın dünkü hali"ne dönebilmek ucuz bir sigorta."""
    if not y.is_file():
        return
    try:
        klasor = AG_KOK / ".gecmis" / y.stem
        klasor.mkdir(parents=True, exist_ok=True)
        shutil.copy2(y, klasor / (datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"))
        for eski in sorted(klasor.glob("*.json"))[:-GECMIS_TAVANI]:
            eski.unlink(missing_ok=True)
    except OSError:
        pass


def yaz(ham: dict) -> str | None:
    temiz, hata = dogrula(ham)
    if hata:
        return hata
    try:
        AG_KOK.mkdir(parents=True, exist_ok=True)
        y = ag_yolu(temiz["ad"])
        _gecmise_al(y)
        y.write_text(json.dumps(temiz, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as e:
        return t("Ağ kaydedilemedi: {hata}", hata=e)
    return None


def sil(ad: str) -> str | None:
    y = ag_yolu(ad)
    if not y.is_file():
        return t("'{ad}' adlı ağ yok.", ad=ad)
    try:
        _gecmise_al(y)
        y.unlink()
    except OSError as e:
        return t("Ağ silinemedi: {hata}", hata=e)
    return None


# ---------------------------------------------------------------------------
# Izin koprusu: kapi kararini Pevrai verir, motor degil
# ---------------------------------------------------------------------------

def izin_fn(politika):
    """Motorun çağıracağı karar fonksiyonu. Politika yoksa her şey DENY."""
    def karar(yol: str):
        if politika is None:
            return ("DENY", t("politika verilmedi"))
        k = politika.yol_dogrula(yol, "oku")
        if k.sonuc != "ALLOW":
            return (k.sonuc, k.gerekce)
        if k.yol is None or not k.yol.is_file():
            return ("DENY", t("dosya yok: {yol}", yol=yol))
        return ("ALLOW", "")
    return karar


def dosya_oku_fn(politika):
    """İçerik okuyucu. Yolu YENİDEN doğrular ve çözülmüş yoldan okur:
    ateşleme ile okuma arasında yol değişmişse eski karar geçerli olmasın."""
    def oku_(yol: str) -> str:
        if politika is None:
            return t("[okuma izni yok]")
        k = politika.yol_dogrula(yol, "oku")
        if k.sonuc != "ALLOW" or k.yol is None or not k.yol.is_file():
            return t("[okuma izni yok]")
        return k.yol.read_text(encoding="utf-8", errors="replace")
    return oku_


# ---------------------------------------------------------------------------
# Uyarlayici: arayuz/arac sozlugu
# ---------------------------------------------------------------------------

def _gorev_yerlestir(ham: dict, gorev: str) -> dict:
    """Düğüm metnindeki {gorev} yerine o anki isteği koyar.

    Ağ böylece sabit bir blok değil ŞABLON olur: aynı ağ "bu haftayı özetle"
    ile "geçen ayla karşılaştır" için farklı bağlam üretir. Yalnızca düğüm
    METNİNDE geçer — dosya içeriğine dokunulmaz."""
    istek = " ".join(str(gorev or "").split())[:2000]
    if not istek or "{gorev}" not in json.dumps(ham.get("dugumler") or [], ensure_ascii=False):
        return ham
    return {**ham, "dugumler": [{**d, "metin": str(d.get("metin") or "").replace("{gorev}", istek)}
                                for d in ham["dugumler"]]}


def analiz(ham: dict) -> list[str]:
    """Kayıt sonrası uyarılar (ölü düğüm, etkisiz baskılayıcı, ulaşılmaz...)."""
    try:
        return motor.analiz(motor.ag_yukle(ham))
    except AgHatasi:
        return []


def ates(ham: dict, uyaran: list[str] | None = None, politika=None, kip: str = "tam",
         gorev: str = "") -> dict:
    """Ağı ateşler; arayüzün ve araçların beklediği düz sözlüğü döner.

    'sira' okuma sırasıdır (tik damgalarıyla — animasyon bunu oynatır),
    'sessiz' ve 'engellenen' ateşlemeyenleri SEBEBİYLE listeler."""
    a = motor.ag_yukle(_gorev_yerlestir(ham, gorev))
    istenen = [u for u in (uyaran or []) if u in a.dugumler] or None
    bilinmeyen = [u for u in (uyaran or []) if u not in a.dugumler]
    kosu = motor.atesle(a, istenen, izin_fn(politika))
    metin = motor.okuma_metni(a, kosu, kip if kip in motor.KIPLER else "tam", dosya_oku_fn(politika))
    d = a.dugumler
    return {
        "ad": a.ad, "uyaran": kosu.uyaran, "bilinmeyen_uyaran": bilinmeyen,
        "sira": [{"sira": i + 1, "tik": kosu.tik[k], "kimlik": k, "tur": d[k].tur,
                  "baslik": d[k].baslik, "yol": d[k].yol or "", "kapi": d[k].kapi,
                  "kaynak": d[k].kaynak} for i, k in enumerate(kosu.sira)],
        "sessiz": [{"kimlik": k, "baslik": d[k].baslik, "tur": d[k].tur, "neden": g}
                   for k, g in kosu.sessiz.items()],
        "engellenen": [{"kimlik": k, "baslik": d[k].baslik, "gerekce": g}
                       for k, g in kosu.engellenen.items()],
        "uyarilar": kosu.uyarilar, "metin": metin,
    }
