"""Sohbetlerin diske kaydi.

Bicim BIZIM: model kutuphanesinin nesneleri oldugu gibi yazilmaz, kendi
sozluk bicimimize cevrilir (A2 karari). Gerekcesi: SDK surumu degisince eski
sohbet dosyalari okunamaz hale gelmesin.

Bedeli: arac cagrisi/sonuc zincirini yeniden kurmak bize kaliyor ve orada
yapilacak bir hata modele BOZUK bir gecmis verirdi. Bu yuzden yuklerken zincir
dogrulaniyor: eslesmeyen bir cagri/sonuc gorulurse gecmis o noktadan KESILIR
ve kullaniciya soylenir. Sessizce bozuk baglam yuklemektense acikca kaybetmek.

NE KAYDEDILIR: kullanici mesajlari, ajan yanitlari, arac cagrilari ve arac
SONUCLARI — yani okunan dosyalarin ve web sayfalarinin tam metni. Kullanici
bunu bilerek secti (bkz. arayuzdeki kenar cubugu notu). Dosyalar ~/.vekil
altinda, journal yedekleriyle ayni yerde.

NE KAYDEDILMEZ: tarayici ekran kareleri (gui_kopru arsive hic koymuyor).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pevrai import journal
KOK = journal.KOK / "sohbetler"
BICIM_SURUMU = 1
AD_KALIBI = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def _hazirla() -> None:
    KOK.mkdir(parents=True, exist_ok=True)


def _yol(kimlik: str) -> Path | None:
    """Kimlik dosya adina cevrilir. Yol enjeksiyonuna kapali: sadece basit adlar."""
    if not AD_KALIBI.match(kimlik or ""):
        return None
    return KOK / f"{kimlik}.json"


# ---------------------------------------------------------------------------
# Model gecmisi <-> sozluk
# ---------------------------------------------------------------------------

def _parca_sozluge(parca: Any) -> dict | None:
    """Tek bir Part -> sozluk. Taninmayan parca None doner ve atlanir."""
    metin = getattr(parca, "text", None)
    if metin:
        return {"tip": "metin", "metin": metin}

    cagri = getattr(parca, "function_call", None)
    if cagri is not None:
        return {"tip": "cagri",
                "ad": getattr(cagri, "name", "") or "",
                "args": dict(getattr(cagri, "args", None) or {}),
                "id": getattr(cagri, "id", None)}

    cevap = getattr(parca, "function_response", None)
    if cevap is not None:
        return {"tip": "sonuc",
                "ad": getattr(cevap, "name", "") or "",
                "cevap": dict(getattr(cevap, "response", None) or {}),
                "id": getattr(cevap, "id", None)}
    return None


def _content_sozluge(icerik: Any) -> dict:
    # Gecmis artik BIZIM bicimde (pevrai.model.taban): sozluk gelirse aynen.
    # SDK nesnesi (eski yol) gelirse cevrilir — geriye donuk uyumluluk.
    if isinstance(icerik, dict):
        return {"rol": icerik.get("rol", "user") or "user",
                "parcalar": [dict(p) for p in icerik.get("parcalar", []) if isinstance(p, dict)]}
    parcalar = []
    for parca in (getattr(icerik, "parts", None) or []):
        d = _parca_sozluge(parca)
        if d is not None:
            parcalar.append(d)
    return {"rol": getattr(icerik, "role", "") or "user", "parcalar": parcalar}


def _sozluk_contente(d: dict, types: Any) -> Any:
    parcalar = []
    for p in d.get("parcalar", []):
        tip = p.get("tip")
        if tip == "metin":
            parcalar.append(types.Part.from_text(text=p.get("metin", "")))
        elif tip == "cagri":
            cagri = types.FunctionCall(name=p.get("ad", ""), args=p.get("args") or {})
            if p.get("id"):
                cagri.id = p["id"]
            parcalar.append(types.Part(function_call=cagri))
        elif tip == "sonuc":
            parcalar.append(types.Part.from_function_response(
                name=p.get("ad", ""), response=p.get("cevap") or {}))
    return types.Content(role=d.get("rol", "user"), parts=parcalar)


def zinciri_dogrula(sozlukler: list[dict]) -> tuple[list[dict], str | None]:
    """Cagri/sonuc zincirini dogrular; bozuk kuyrugu keser.

    Kural: model bir tur icinde n arac cagirir, sonraki icerik(ler) o n sonucu
    tasimak zorundadir. Sonuclari eksik bir tur baglamda kalirsa bir sonraki
    model cagrisi hata verir. Bu yuzden "butun" oldugu bilinen SON noktaya
    kadar kesiyoruz.
    """
    if not sozlukler:
        return [], None

    # Bas: ilk kullanici metniyle baslamali (yarim bir turla baslayan gecmis gecersiz).
    bas = 0
    for i, d in enumerate(sozlukler):
        if d.get("rol") == "user" and any(p.get("tip") == "metin" for p in d.get("parcalar", [])):
            bas = i
            break
    else:
        return [], "Gecmiste kullanici mesaji bulunamadi, baglam yuklenmedi."

    calisan = sozlukler[bas:]

    bekleyen = 0
    guvenli = 0          # zincirin butun oldugu son indis (dahil)
    for i, d in enumerate(calisan):
        for p in d.get("parcalar", []):
            if p.get("tip") == "cagri":
                bekleyen += 1
            elif p.get("tip") == "sonuc":
                bekleyen -= 1
        if bekleyen <= 0:
            bekleyen = 0
            guvenli = i + 1

    atilan = (bas) + (len(calisan) - guvenli)
    kirpik = calisan[:guvenli]
    if not kirpik:
        return [], "Gecmisin tamami yarim kalmis, baglam yuklenmedi."
    if atilan:
        return kirpik, (f"Gecmisin sonundaki {atilan} kayit yarim kalmisti "
                        f"(arac cagrisinin sonucu eksik), baglamdan cikarildi.")
    return kirpik, None


# ---------------------------------------------------------------------------
# Disk
# ---------------------------------------------------------------------------

def kaydet(kimlik: str, baslik: str, arsiv: list[dict], gecmis: list[Any],
           guncelleme: str | None = None,
           proje_baglami: dict | None = None) -> str | None:
    """Sohbeti diske yazar. Hata varsa metin dondurur (gorevi bozmaz).

    guncelleme: cagiranin (gui_kopru) belleginde tuttugu son degisiklik ani.
    Verilmezse yazma ani yazilir. Verilmesi onemli: kapanista butun sohbetler
    arka arkaya kaydediliyor; hepsine "simdi" yazilsaydi hepsi ayni anda
    guncellenmis gorunur ve kenar cubugundaki sira her kapanista bozulurdu.
    """
    yol = _yol(kimlik)
    if yol is None:
        return f"Gecersiz sohbet kimligi: {kimlik!r}"
    try:
        _hazirla()
        veri = {
            "surum": BICIM_SURUMU,
            "id": kimlik,
            "baslik": baslik,
            "guncelleme": guncelleme or datetime.now().isoformat(timespec="seconds"),
            "arsiv": arsiv,
            "gecmis": [_content_sozluge(c) for c in gecmis],
            "proje_baglami": proje_baglami,
        }
        gecici = yol.with_suffix(".json.yeni")
        gecici.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        gecici.replace(yol)     # atomik: yarim yazilmis dosya birakmaz
        return None
    except Exception as e:
        return f"Sohbet kaydedilemedi ({type(e).__name__}: {e})"


def yukle_hepsi() -> list[dict]:
    """Kayitli sohbetleri okur. Dosya sirasiyla doner; SIRALAMA BURADA DEGIL,
    gui_kopru.sohbet_sirasi'nda (tek kaynak — arayuz yalnizca gosterir).

    Her ogede: id, baslik, guncelleme, arsiv, gecmis (sozluk halinde), uyari.
    guncelleme dosyadan gelir; okunamayan/eski bicimli dosyada dosyanin
    degisiklik zamani kullanilir — sirada bir yere oturmasi gerekiyor.
    Content'e cevirme cagirana birakildi — bu modul model kutuphanesini
    ice aktarmak zorunda kalmasin diye.
    """
    if not KOK.exists():
        return []
    cikti = []
    for yol in sorted(KOK.glob("*.json"), key=lambda p: p.stat().st_mtime):
        dosya_zamani = datetime.fromtimestamp(yol.stat().st_mtime).isoformat(timespec="seconds")
        try:
            veri = json.loads(yol.read_text(encoding="utf-8"))
        except Exception as e:
            cikti.append({"id": yol.stem, "baslik": yol.stem, "guncelleme": dosya_zamani,
                          "arsiv": [], "gecmis": [],
                          "uyari": f"Sohbet dosyasi okunamadi ({type(e).__name__}), "
                                   f"bos acildi."})
            continue
        guncelleme = veri.get("guncelleme") or dosya_zamani
        if veri.get("surum") != BICIM_SURUMU:
            cikti.append({"id": veri.get("id", yol.stem), "baslik": veri.get("baslik", ""),
                          "guncelleme": guncelleme,
                          "arsiv": veri.get("arsiv", []), "gecmis": [],
                          "uyari": "Sohbet dosyasi eski bir bicimde. Metin acildi ama "
                                   "baglam yuklenmedi: buradan devam edersen ajan "
                                   "onceki konusmayi hatirlamaz."})
            continue
        gecmis, uyari = zinciri_dogrula(veri.get("gecmis", []))
        cikti.append({"id": veri.get("id", yol.stem), "baslik": veri.get("baslik", ""),
                      "guncelleme": guncelleme,
                      "arsiv": veri.get("arsiv", []), "gecmis": gecmis, "uyari": uyari,
                      "proje_baglami": veri.get("proje_baglami")})
    return cikti


def sozlukleri_contente(sozlukler: list[dict], types: Any = None) -> list[Any]:
    """types verilirse SDK nesnelerine cevirir (eski yol); verilmezse gecmis
    zaten sozluk bicimi — kopyalanip doner (pevrai.model bu bicimi konusur)."""
    if types is None:
        return [_content_sozluge(d) for d in sozlukler]
    return [_sozluk_contente(d, types) for d in sozlukler]


def sil(kimlik: str) -> bool:
    """Sohbet dosyasini GERCEKTEN siler (cop kutusuna tasimaz).

    Bilincli istisna: cop kutusu kurali kullanicinin dosyalari icin. Bu dosya
    ajanin urettigi bir kayit ve icinde hassas icerik olabilir; "sil" dedigi
    yerde diskte kalmasi kotu olurdu.
    """
    yol = _yol(kimlik)
    if yol is None or not yol.exists():
        return False
    try:
        yol.unlink()
        return True
    except OSError:
        return False
