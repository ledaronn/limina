"""Ajan dongusu ile arayuz arasindaki sozlesme.

Bu modul hicbir arayuz kutuphanesi tanimaz: ne terminal, ne pywebview, ne queue.
Sadece iki soruyu tanimlar: "ajan ne bildirir" ve "onay nasil istenir".

Faz 5 mimari parcasi. Gorsel tasarim bu dosyayi hic ilgilendirmez.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Protocol


# --------------------------------------------------------------------------
# Olaylar
# --------------------------------------------------------------------------

class OlayTipi(str, Enum):
    GOREV_BASLADI = "gorev_basladi"    # veri: gorev, mod
    ADIM_BASLADI = "adim_basladi"      # veri: adim, azami
    OLCUM = "olcum"                    # veri: adim, girdi_token, cikti_token, toplam_cagri
    ARAC_CAGRILDI = "arac_cagrildi"    # veri: arac, args, risk, karar, adim, sira
    ONAY_GEREKLI = "onay_gerekli"      # veri: istek (bkz. istek_sozluge)
    ONAY_SONUCU = "onay_sonucu"        # veri: arac, cevap
    ARAC_SONUCU = "arac_sonucu"        # veri: arac, sonuc, sure_sn, karar
    TARAYICI = "tarayici"              # veri: kare (base64 jpeg), url, baslik
    YANIT_PARCASI = "yanit_parcasi"    # veri: metin (su an akis yok, tek parca gelir)
    OZET = "ozet"                      # veri: kimlik, yol, metin (Faz 7 Asama 4)
    GOREV_BITTI = "gorev_bitti"        # veri: metin, durduruldu
    HATA = "hata"                      # veri: mesaj
    EKIP_MESAJ = "ekip_mesaj"          # veri: kimden, kime, metin (pano) | ajan, teslim (iscide teslim)
    MODEL_GECIS = "model_gecis"        # veri: eski, yeni (etiket), sebep ("limit" | "anahtar"), bitis
    BEKLEME = "bekleme"                # veri: sn, sebep (yeniden deneme)


@dataclass(frozen=True)
class Olay:
    tip: OlayTipi
    veri: dict[str, Any] = field(default_factory=dict)


def olay_sozluge(olay: Olay) -> dict[str, Any]:
    """JS tarafina gonderilebilir duz sozluk. Icerik JSON-uyumlu olmali."""
    return {"tip": olay.tip.value, "veri": olay.veri}


# --------------------------------------------------------------------------
# Onay
# --------------------------------------------------------------------------

class OnayCevabi(str, Enum):
    RED = "red"
    EVET = "evet"
    TUMU = "tumu"   # bu arac icin oturum boyunca; oturum disina TASINMAZ


@dataclass(frozen=True)
class OnayIstegi:
    """Onay ekraninin gostermesi gereken her sey.

    Saglayici bunu yorumlamaz, sadece gosterir. Hangi secenegin sunulabilecegine
    cekirdek karar verir (bkz. toplu_sunulabilir).
    """
    arac: str
    args: dict[str, Any]
    risk: str
    etki: str                         # araca ozgu tek cumle
    yikici: bool = False              # yikici yazma; kirmizi uyari seridi
    toplu_sunulabilir: bool = False   # "Tumu" dugmesi render edilebilir mi
    fark: str | None = None           # uzerine yazmada satir bazli fark


def istek_sozluge(istek: OnayIstegi) -> dict[str, Any]:
    return {
        "arac": istek.arac,
        "args": istek.args,
        "risk": istek.risk,
        "etki": istek.etki,
        "yikici": istek.yikici,
        "toplu_sunulabilir": istek.toplu_sunulabilir,
        "fark": istek.fark,
    }


class OnaySaglayici(Protocol):
    def __call__(self, istek: OnayIstegi) -> OnayCevabi: ...


Yayinci = Callable[[Olay], None]


def _sessiz(olay: Olay) -> None:
    """Varsayilan yayinci: hicbir sey yapmaz (CLI ve eval icin)."""


# Gecmiste tutulacak azami oge sayisi. Asilirsa EN ESKI GOREV komple atilir.
# Parca parca kirpmak tehlikeli: Gemini bir function_response'un onunde
# function_call bekliyor; gorev sinirindan kesince zincir hep butun kalir.
GECMIS_TAVANI = 40


class Durduruldu(Exception):
    """Kullanici gorevi durdurdu. Kopru yakalar, cikti temiz kapanir."""


def daraltma_guncelle(mevcut: frozenset[str], kapali: frozenset[str], hepsi_kapali: bool,
                      ad: str, acik: bool) -> tuple[frozenset[str], bool]:
    """Araclar panelinde tek bir aracin acilip kapanmasi. SAF.

    mevcut: modele gosterilebilecek araclarin tamami (policy.toml'da
    siniflandirilmis VE kesfedilmis). Panel bu kumenin DISINA cikamaz: ad
    mevcut degilse durum aynen doner — panel arac EKLEYEMEZ, yalnizca
    cikarabilir (profil kuralinin arayuz karsiligi).

    Sonuc KANONIK: ya hepsi_kapali=True ve bos kume, ya da hepsi_kapali=False
    ve mevcut'un GERCEK bir alt kumesi. Sohbet anahtari ("hepsini kapat") ile
    tek tek kapatarak ayni noktaya gelmek ayni durumu uretir; iki gosterim
    ayrismaz.
    """
    if ad not in mevcut:
        return kapali, hepsi_kapali
    if hepsi_kapali:
        kapali = frozenset(mevcut)
    kapali = (kapali - {ad}) if acik else (kapali | {ad})
    kapali = kapali & mevcut
    if mevcut and kapali >= mevcut:
        return frozenset(), True
    return kapali, False


# --------------------------------------------------------------------------
# Oturum
# --------------------------------------------------------------------------

@dataclass
class Oturum:
    """Bir gorev (ya da bir sohbet penceresi) boyunca yasayan durum.

    Toplu onaylar burada tutulur; yeni bir Oturum yaratmak onlari sifirlar.
    ARAYUZ.md 7: "Yeni sohbet acmak toplu onaylari sifirlar."
    """
    onay_saglayici: OnaySaglayici
    yayinla: Yayinci = _sessiz
    durdur_bayragi: threading.Event = field(default_factory=threading.Event)
    gecmis_koru: bool = True
    _toplu: set[str] = field(default_factory=set)
    _gecmis: list[Any] = field(default_factory=list)
    _gorev_indisleri: list[int] = field(default_factory=list)
    # Araclar paneli: bu SOHBETTE modele gosterilmeyecek araclar. Toplu
    # onaylar gibi Oturum'da yasar — yeni sohbet yeni Oturum, daraltma sifir.
    # policy.toml'a YAZILMAZ: "bu sohbette tarayiciya dokunma" anlik bir
    # ihtiyac; kalici olsaydi kullanici unutur, haftalar sonra "arac neden
    # calismiyor" diye arardi. Diske de yazilmiyor (toplu onaylar da yazilmiyor).
    _kapali_araclar: frozenset[str] = frozenset()
    _hepsi_kapali: bool = False
    # Sohbet ekranindaki model secici: "kimlik/model" (bos = otomatik, zincir
    # sirasi). Gorev bu modelle baslar; limiti dolarsa zincir sirasi izlenir.
    secili_model: str = ""
    proje_baglami: dict[str, str] | None = None

    # --- toplu onay ---
    def toplu_onayli(self, arac: str) -> bool:
        return arac in self._toplu

    def toplu_ekle(self, arac: str) -> None:
        self._toplu.add(arac)

    def toplu_iptal(self, arac: str | None = None) -> None:
        """Kenar cubugundaki 'aktif toplu onaylar' listesinden iptal icin."""
        if arac is None:
            self._toplu.clear()
        else:
            self._toplu.discard(arac)

    def aktif_toplu_onaylar(self) -> list[str]:
        return sorted(self._toplu)

    # --- arac daraltmasi (Araclar paneli / sohbet anahtari) ---
    def kapali_araclar(self) -> list[str]:
        return sorted(self._kapali_araclar)

    def hepsi_kapali(self) -> bool:
        """Sohbet modu: modele HICBIR arac semasi gitmez. Ayri bir kavram
        degil, daraltmanin uc hali (profildeki `araclar = []` gibi)."""
        return self._hepsi_kapali

    def araclari_daralt(self, kapali: Iterable[str], hepsi_kapali: bool) -> None:
        """TEK yazma noktasi. Sohbet anahtari da, paneldeki tek tek dugmeler de
        buraya yazar. Yalnizca DARALTIR: burada yazilan bir ad, modele
        gosterilecek listeden CIKARILIR; listeye bir sey EKLEMENIN yolu yok
        (bkz. vekil_v0._gorev_araclari — kesisim aliyor)."""
        self._kapali_araclar = frozenset() if hepsi_kapali else frozenset(kapali)
        self._hepsi_kapali = bool(hepsi_kapali)

    # --- sohbet gecmisi ---
    # Gecmis burada tutuluyor cunku "oturum" zaten dogru kapsam: yeni bir Oturum
    # hem toplu onaylari hem konusmayi sifirlar. Icerik model kutuphanesine ait
    # nesneler; bu modul onlari acmaz, sadece tasir.
    def gecmis_al(self) -> list[Any]:
        """CANLI liste doner; calistir() dogrudan buna ekler."""
        return self._gecmis

    def gorev_basladi(self) -> None:
        """Yeni gorevin gecmisteki baslangicini isaretler ve tavani uygular."""
        self._gorev_indisleri.append(len(self._gecmis))
        self._budala()

    def _budala(self) -> None:
        while len(self._gecmis) > GECMIS_TAVANI and len(self._gorev_indisleri) > 1:
            kes = self._gorev_indisleri[1]
            del self._gecmis[:kes]
            self._gorev_indisleri = [i - kes for i in self._gorev_indisleri[1:]]

    def gecmis_gorevi_geri_al(self) -> None:
        """Yarim kalan gorevi gecmisten cikarir.

        Durdurma aninda gecmisin sonunda cevapsiz bir function_call kalabilir;
        bir sonraki model cagrisi bunu reddeder. Gorev basindan itibaren silmek
        hem zinciri butun tutar hem de yarim isi baglamda birakmaz.
        """
        if not self._gorev_indisleri:
            return
        del self._gecmis[self._gorev_indisleri[-1]:]
        self._gorev_indisleri.pop()

    def gecmis_sifirla(self) -> None:
        self._gecmis.clear()
        self._gorev_indisleri.clear()

    def gecmis_gorev_sayisi(self) -> int:
        return len(self._gorev_indisleri)

    # --- durdurma ---
    def durdur(self) -> None:
        self.durdur_bayragi.set()

    def kontrol(self) -> None:
        """Dongude guvenli noktalarda cagrilir. Durdurulduysa Durduruldu firlatir.

        Calisan bir arac cagrisini KESMEZ; sadece bir sonrakinin baslamasini onler.
        LibreOffice gibi senkron bir alt surec yarida kesilemez.
        """
        if self.durdur_bayragi.is_set():
            raise Durduruldu()


# --------------------------------------------------------------------------
# Onay akisi (cekirdek karar noktasi)
# --------------------------------------------------------------------------

def onay_iste(oturum: Oturum, istek: OnayIstegi) -> bool:
    """Onay akisinin TEK yolu. Guvenlik kurallari burada, saglayicida degil.

    Saglayici sadece kullaniciya gosterip cevap dondurur; hangi secenegin
    sunulabilir oldugunu ve toplu onayin ne zaman yazildigini burasi bilir.
    """
    if istek.toplu_sunulabilir and oturum.toplu_onayli(istek.arac):
        return True

    oturum.yayinla(Olay(OlayTipi.ONAY_GEREKLI, {"istek": istek_sozluge(istek)}))

    try:
        cevap = oturum.onay_saglayici(istek)
    except (EOFError, KeyboardInterrupt):
        # SECURITY.md: onay alinamazsa REDDET. Asla varsayilan evet.
        cevap = OnayCevabi.RED
    except Exception:
        # Bozuk bir saglayici da izin kazanmaz.
        cevap = OnayCevabi.RED

    # Saglayici yasak oldugu halde TUMU dondurse bile tekile dusurulur.
    if cevap is OnayCevabi.TUMU and not istek.toplu_sunulabilir:
        cevap = OnayCevabi.EVET

    if cevap is OnayCevabi.TUMU:
        oturum.toplu_ekle(istek.arac)

    oturum.yayinla(Olay(OlayTipi.ONAY_SONUCU,
                        {"arac": istek.arac, "cevap": cevap.value}))
    return cevap is not OnayCevabi.RED


# --------------------------------------------------------------------------
# Hazir saglayicilar
# --------------------------------------------------------------------------

def terminal_onayi(istek: OnayIstegi) -> OnayCevabi:
    """CLI onay ekrani. EOF/Ctrl-C onay_iste icinde yakalanir -> RED."""
    print("\n  === ONAY GEREKIYOR ===")
    if istek.yikici:
        print("  !! DIKKAT: bu yazma dosyanin icerigini yok ediyor (fiilen silme).")
        print("  !! Toplu onay bu islemde gecerli degil, tek tek sorulur.")
    print(f"  Arac  : {istek.arac}  (risk: {istek.risk})")
    for anahtar, deger in istek.args.items():
        metin = str(deger)
        gosterim = metin if len(metin) <= 200 else metin[:200] + f"... [{len(metin)} karakter]"
        print(f"  {anahtar:7}: {gosterim}")
    print(f"  Etki  : {istek.etki}")

    secenek = "(e)vet / (h)ayir"
    if istek.fark:
        secenek += " / (f)ark"
    if istek.toplu_sunulabilir:
        secenek += f" / (t)umu - bu oturumda {istek.arac} icin bir daha sorma"

    while True:
        cevap = input(f"  {secenek}: ").strip().lower()
        if cevap in ("e", "evet"):
            return OnayCevabi.EVET
        if cevap in ("f", "fark") and istek.fark:
            print(istek.fark)
            continue
        if cevap in ("t", "tumu", "tümü") and istek.toplu_sunulabilir:
            return OnayCevabi.TUMU
        return OnayCevabi.RED   # taninmayan cevap dahil her sey RED


def sabit_cevap(cevap: str) -> OnaySaglayici:
    """Test/eval icin sabit cevap veren saglayici uretir: 'e' | 'h' | 't'.

    Eskiden vekil_v0.OTOMATIK_ONAY modul bayragiydi; artik acikca enjekte edilir.
    Uretim yolunda kullanilmaz.
    """
    tablo = {"e": OnayCevabi.EVET, "evet": OnayCevabi.EVET,
             "t": OnayCevabi.TUMU, "tumu": OnayCevabi.TUMU}
    deger = tablo.get(cevap.strip().lower(), OnayCevabi.RED)

    def _saglayici(istek: OnayIstegi) -> OnayCevabi:
        return deger
    return _saglayici


def otomatik_red(istek: OnayIstegi) -> OnayCevabi:
    """Gozetimsiz calistirma varsayilani: ASK gerektiren arac calismaz."""
    return OnayCevabi.RED


def terminal_oturumu() -> Oturum:
    return Oturum(onay_saglayici=terminal_onayi)
