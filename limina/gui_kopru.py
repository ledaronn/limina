"""Ajan thread'i ile UI thread'i arasindaki kopru.

pywebview'e bagli DEGIL. Sadece thread + kuyruk. HTML/JS tarafi bu sinifin
metotlarini cagirir; hangi arayuz oldugu buradan gorunmez.

Is bolumu:
  - ajan thread'i: calistir() burada doner, onayda BLOKE OLUR
  - UI thread'i   : olaylari_cek() ile kuyrugu bosaltir, onay_cevapla() ile cozer

Gorevler TEK ve KALICI bir isci thread'inde kosar. Gorev basina yeni thread
acilmiyor: Playwright'in senkron API'si kendisini baslatan thread'e baglidir,
her gorevde yeni thread acilinca ikinci tarayici cagrisi "is parcacigi hatasi"
ile dusuyordu (gozlemlendi). Tek isci, tarayici oturumunu da butun tutar.

Sohbetler: birden fazla Oturum ayni anda yasar, biri aktiftir. Her sohbet kendi
olay arsivini tutar; sohbet degistirince arayuz arsivi yeniden oynatarak akisi
geri kurar.

Sohbetler DISKE KAYDEDILIR (~/.vekil/sohbetler/). Bu, kullanicinin bilerek
verdigi bir karar: arsiv ve model gecmisi arac ciktilarini — yani okunan
dosyalarin ve web sayfalarinin tam metnini — icerir. journal.py dosya
iceriklerini gunluge yazmiyor; burasi o kuralin bilincli istisnasi, cunku
"kapatinca sohbet kaybolmasin" istegi baska turlu karsilanamiyor.
Tarayici ekran kareleri kaydedilmez (arsive hic girmiyorlar).

ARAYUZ.md 9/2-3.
"""

from __future__ import annotations

import queue
import threading
import uuid
from datetime import datetime
from typing import Any, Callable

from limina.olaylar import (
    Durduruldu,
    Olay,
    OlayTipi,
    OnayCevabi,
    OnayIstegi,
    Oturum,
    olay_sozluge,
)

# Bellekte tutulan sohbet basina azami olay. Asilirsa en eskiler dusuruluyor:
# arsiv bir kolayliktir, sinirsiz buyumesine izin verilmez.
ARSIV_TAVANI = 400


def _simdi() -> str:
    """Sohbetin `guncelleme` alani icin zaman damgasi. Diskteki bicimle ayni
    (sohbet.kaydet, saniye hassasiyeti) — iki kaynak dizge olarak
    karsilastiriliyor, bicimler ayrisirsa siralama sessizce bozulur."""
    return datetime.now().isoformat(timespec="seconds")


def sohbet_sirasi(sohbetler: list[dict[str, Any]], aktif: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Kenar cubugu sirasi. SAF: liste alir, sirali yeni liste doner.

    Kural: aktif sohbet en basta; kalanlar `guncelleme`ye gore en yeni ustte.
    Berabere kalan zaman damgalarinda (ayni saniye) sonra yaratilan ustte —
    ayni saniyede acilan iki sohbetten yeni olan, kullanicinin son dokundugu.

    `guncelleme` alani her sohbette VAR sayilir (_sohbet_yarat yaziyor);
    eksik olursa "" ile en dibe duser, KeyError ile kenar cubugunu kirmaz.
    """
    def anahtar(ic: tuple[int, dict[str, Any]]) -> tuple[bool, str, int]:
        sira, s = ic
        return (s is aktif, str(s.get("guncelleme") or ""), sira)
    return [s for _, s in sorted(enumerate(sohbetler), key=anahtar, reverse=True)]


def _gecmisi_contente(sozlukler: list[dict]) -> list[Any]:
    """Diskten gelen sozlukler zaten gecmis bicimi (limina.model.taban):
    dogrulanip kopyalanir, SDK'ya bagimlilik yok."""
    if not sozlukler:
        return []
    from limina import sohbet
    return sohbet.sozlukleri_contente(sozlukler)


def _varsayilan_kosucu(gorev: str, mod: str | None, oturum: Oturum,
                       profil: str | None = None, ekip: bool = False) -> str:
    # Tembel import: olaylar.py ve gui_kopru.py, vekil_v0'a bagimli olmasin.
    if ekip:
        # Ekip gorevi: planlayici -> plan onayi -> isci surecleri -> birlestirici (ekip.py)
        # ekip: True (varsayilan alan, tum ajanlar) ya da {"alan", "ajanlar", "proje"}
        from pathlib import Path as _P
        from limina.ekip import ekip_gorevi, tek_ajan_gorevi
        ayar = ekip if isinstance(ekip, dict) else {}
        if ayar.get("tek"):
            # Tek ajana dogrudan gorev (ofis): planlayici yok, ayni isci yolu
            return tek_ajan_gorevi(gorev, str(ayar["tek"]), mod, oturum, profil,
                                   calisma_alani=_P(ayar["alan"]) if ayar.get("alan") else None,
                                   yol=str(ayar.get("yol") or ""), proje=ayar.get("proje"))
        return ekip_gorevi(gorev, mod, oturum, profil,
                           calisma_alani=_P(ayar["alan"]) if ayar.get("alan") else None,
                           secili=ayar.get("ajanlar") or None, proje=ayar.get("proje"))
    from limina.vekil_v0 import calistir
    return calistir(gorev, mod=mod, oturum=oturum, profil=profil)


class Kopru:
    def __init__(self,
                 kosucu: Callable[[str, str | None, Oturum, str | None], str] | None = None) -> None:
        self._kosucu = kosucu or _varsayilan_kosucu
        self._olaylar: queue.Queue[Olay] = queue.Queue()
        self._cevap: queue.Queue[OnayCevabi] = queue.Queue(maxsize=1)
        self._isler: queue.Queue = queue.Queue()
        self._isci: threading.Thread | None = None
        self._kapaniyor = False
        # Mantiksal mesguliyet. thread.is_alive() KULLANILMIYOR: isci thread'i
        # gorevler arasinda da yasiyor, ayrica GOREV_BITTI yayinlandiktan sonra
        # bir an daha calisir gorunuyordu (testte yakalandi).
        self._mesgul = False
        self._sohbetler: list[dict[str, Any]] = []
        self._yuklenen_uyarilar: list[str] = []
        self._diskten_yukle()
        # Acilista HICBIR kayitli sohbet acilmaz: bos bir sohbetle baslanir.
        # Onceki surumde son sohbet aktif yapiliyordu ama arayuz akisi yeniden
        # kurmuyordu — kenar cubugunda o sohbet vurgulu gorunup ekran bos
        # kaliyor, kullanici yazinca araya giriyordu (testte yakalandi).
        self._aktif: dict[str, Any] = self._sohbet_yarat()

    # ------------------------------------------------------------------
    # sohbetler
    # ------------------------------------------------------------------
    def _sohbet_yarat(self, gecmis_koru: bool = True, kimlik: str | None = None) -> dict[str, Any]:
        sohbet: dict[str, Any] = {
            # uuid4: sira sayaci + saniye hassasiyetli zaman damgasi (eski
            # bicim) ayni saniyede baslayan iki Kopru arasinda CAKISABILIYORDU
            # — her ornek kendi sayacini 1'den baslatiyor, "yeniden acildiginda
            # yuklenen sohbet + yeni bos sohbet" tam da bu senaryo (testte
            # yakalandi). Cakisan id ayni dosyayi sessizce ustune yazdirirdi.
            "id": kimlik or f"s-{uuid.uuid4().hex[:12]}",
            "baslik": "",
            "arsiv": [],
            # Son degisiklik ani. Diske sohbet.kaydet yaziyor; bellekteki, henuz
            # yazilmamis sohbette de OLMALI ki sira tek kurala otursun. Karar:
            # bos yeni sohbet icin yaratilis ani; sonra her ARSIVE GIREN olayda
            # tazelenir (_yayinla). Arsiv, sohbetin tek gercek degisim kaynagi —
            # tarayici kareleri arsive girmedigi icin onlar da tazelemez (kare
            # bir goruntudur, sohbete eklenen bir sey degil). Kaydetme ani
            # KULLANILMIYOR: kapanista butun sohbetler arka arkaya yaziliyor,
            # hepsi ayni anda "guncellenmis" gorunurdu.
            "guncelleme": _simdi(),
        }
        sohbet["oturum"] = Oturum(
            onay_saglayici=self._onay_bekle,
            yayinla=lambda olay, s=sohbet: self._yayinla(s, olay),
            gecmis_koru=gecmis_koru,
        )
        self._sohbetler.append(sohbet)
        return sohbet

    def _diskten_yukle(self) -> None:
        """Kayitli sohbetleri geri getirir. Hicbir hata acilisi engellemez."""
        try:
            from limina import sohbet as depo
            kayitlar = depo.yukle_hepsi()
        except Exception as e:
            self._yuklenen_uyarilar.append(
                f"Kayitli sohbetler okunamadi ({type(e).__name__}: {e}).")
            return

        for kayit in kayitlar:
            s = self._sohbet_yarat(kimlik=kayit["id"])
            s["baslik"] = kayit.get("baslik", "")
            s["guncelleme"] = kayit.get("guncelleme") or s["guncelleme"]
            proje = kayit.get("proje_baglami")
            if isinstance(proje, dict) and isinstance(proje.get("id"), str) and isinstance(proje.get("name"), str):
                s["oturum"].proje_baglami = {"id": proje["id"], "name": proje["name"]}
            s["arsiv"] = list(kayit.get("arsiv", []))     # sozluk halinde saklanir
            try:
                s["oturum"].gecmis_al().extend(_gecmisi_contente(kayit.get("gecmis", [])))
                s["oturum"].gorev_basladi()               # yeni gorev icin sinir isareti
            except Exception as e:
                kayit["uyari"] = (f"'{s['baslik']}' sohbetinin baglami yuklenemedi "
                                  f"({type(e).__name__}). Metin acildi, ama buradan devam "
                                  f"edersen ajan onceki konusmayi hatirlamaz.")
            if kayit.get("uyari"):
                self._yuklenen_uyarilar.append(f"{s['baslik'] or s['id']}: {kayit['uyari']}")

    def uyarilari_al(self) -> list[str]:
        """Acilista biriken yukleme uyarilari; arayuz bir kez gosterir."""
        cikti = self._yuklenen_uyarilar
        self._yuklenen_uyarilar = []
        return cikti

    def _kaydet(self, sohbet: dict[str, Any]) -> None:
        """Sohbeti diske yazar. Hata gorevi bozmaz, uyari olarak birikir."""
        try:
            from limina import sohbet as depo
            if (not sohbet["arsiv"] and not sohbet["oturum"].proje_baglami
                    and not (depo.KOK / (sohbet["id"] + ".json")).exists()):
                return
            hata = depo.kaydet(sohbet["id"], sohbet["baslik"] or sohbet["id"],
                               sohbet["arsiv"], sohbet["oturum"].gecmis_al(),
                               guncelleme=sohbet["guncelleme"],
                               proje_baglami=sohbet["oturum"].proje_baglami)
        except Exception as e:
            hata = f"Sohbet kaydedilemedi ({type(e).__name__}: {e})"
        if hata:
            self._yuklenen_uyarilar.append(hata)

    def _yayinla(self, sohbet: dict[str, Any], olay: Olay) -> None:
        """Olayi hem arsive hem (sohbet aktifse) UI kuyruguna yazar.

        Arka planda kalan bir sohbetin olaylari kuyruga girmez; yoksa baska bir
        sohbetin akisi ekrandakine karisirdi.
        """
        # Tarayici kareleri arsive GIRMEZ: kare basina 100+ KB, 400 olaylik bir
        # arsiv onlarca megabayta cikardi. Kare anlik bir gorunum; sohbet
        # gecmisinde saklanmasinin degeri yok, maliyeti buyuk.
        if olay.tip is OlayTipi.TARAYICI:
            if sohbet is self._aktif:
                self._olaylar.put(olay)
            return

        arsiv = sohbet["arsiv"]
        arsiv.append(olay_sozluge(olay))
        sohbet["guncelleme"] = _simdi()
        if len(arsiv) > ARSIV_TAVANI:
            del arsiv[: len(arsiv) - ARSIV_TAVANI]
        if not sohbet["baslik"] and olay.tip is OlayTipi.GOREV_BASLADI:
            ham = str(olay.veri.get("gorev", "")).strip().splitlines()
            sohbet["baslik"] = (ham[0][:48] if ham else "") or "(başlıksız)"
        if sohbet is self._aktif:
            self._olaylar.put(olay)

    @property
    def oturum(self) -> Oturum:
        return self._aktif["oturum"]

    def sohbetler(self) -> list[dict[str, Any]]:
        """Kenar cubugu listesi, SIRALI. Sira burada kurulur, arayuz yalnizca
        gosterir (bkz. sohbet_sirasi). Basliksiz sohbet "Yeni sohbet" adiyla
        gider ve aktifse yine bastadir — kural basliga degil aktiflige bakar."""
        return [{"id": s["id"], "baslik": s["baslik"] or "Yeni sohbet",
                 "aktif": s is self._aktif, "olay": len(s["arsiv"]),
                 "guncelleme": s["guncelleme"]}
                for s in sohbet_sirasi(self._sohbetler, self._aktif)]

    def yeni_sohbet(self) -> str | None:
        """Yeni bir Oturum: konusma ve toplu onaylar sifirdan (ARAYUZ.md 7)."""
        if self.calisiyor():
            return None
        # Bos bir sohbetten yenisine gecmenin anlami yok — AMA "bos" olmak
        # yalnizca arsivin bos olmasi degil: toplu onay ya da konusma gecmisi
        # varsa Oturum'un YENIDEN kurulmasi sart, yoksa "yeni sohbet toplu
        # onaylari sifirlar" kurali sessizce delinirdi (testte yakalandi).
        # Arac daraltmasi da ayni sinifta: bos sohbette araclari kapatip "yeni
        # sohbet" diyen kullanici varsayilani bekler (testte yakalandi).
        o = self.oturum
        if (not self._aktif["arsiv"] and not o.aktif_toplu_onaylar() and not o.gecmis_al()
                and not o.hepsi_kapali() and not o.kapali_araclar() and not o.proje_baglami):
            return self._aktif["id"]
        self._aktif = self._sohbet_yarat(gecmis_koru=self.oturum.gecmis_koru)
        self._bosalt(self._olaylar)
        self._bosalt(self._cevap)
        return self._aktif["id"]

    def sohbet_ac(self, sohbet_id: str) -> list[dict[str, Any]] | None:
        """Sohbeti aktif yapar ve arsivini doner (arayuz akisi yeniden kurar)."""
        if self.calisiyor():
            return None
        for s in self._sohbetler:
            if s["id"] == sohbet_id:
                self._aktif = s
                self._bosalt(self._olaylar)
                self._bosalt(self._cevap)
                return list(s["arsiv"])
        return None

    def sohbet_sil(self, sohbet_id: str) -> bool:
        if self.calisiyor():
            return False
        for s in list(self._sohbetler):
            if s["id"] == sohbet_id:
                try:
                    from limina import sohbet as depo
                    depo.sil(s["id"])       # dosya gercekten silinir
                except Exception:
                    pass
                self._sohbetler.remove(s)
                if s is self._aktif:
                    self._aktif = self._sohbetler[-1] if self._sohbetler else self._sohbet_yarat()
                    self._bosalt(self._olaylar)
                return True
        return False

    def araclari_daralt(self, kapali: list[str], hepsi_kapali: bool) -> bool:
        """Araclar paneli / sohbet anahtari: AKTIF sohbetin daraltmasini yazar.

        Gorev calisirken reddedilir (False): arac listesi gorev basinda
        cozuluyor, ortasinda degisen bir ayar sessizce etkisiz kalirdi.
        Daraltma Oturum'da yasar; yeni sohbet yeni Oturum, sifirdan baslar.
        """
        if self.calisiyor():
            return False
        self.oturum.araclari_daralt(kapali, hepsi_kapali)
        return True

    # ------------------------------------------------------------------
    # UI thread'inden cagrilir
    # ------------------------------------------------------------------
    def calisiyor(self) -> bool:
        return self._mesgul

    def gorev_baslat(self, gorev: str, mod: str | None = None,
                     profil: str | None = None, ekip: bool = False,
                     gosterim: str | None = None) -> None:
        """profil: Faz 7 Asama 5'te eklendi. Arayuzdeki sohbet/gorev anahtari
        'sohbet' profilini secer (araclar = [], saf sohbet). Profil YALNIZCA
        buradan, kullanicinin acik secimiyle geliyor — arayuz kendi basina
        bir profil SECMEZ, cunku profil onceden imzalanmis bir onaydir."""
        if self.calisiyor():
            raise RuntimeError("Zaten calisan bir gorev var (Faz 5: tek gorev, tek pencere).")
        if self._kapaniyor:
            raise RuntimeError("Pencere kapaniyor.")
        self.oturum.durdur_bayragi.clear()
        self._bosalt(self._cevap)
        self._mesgul = True
        self._isci_baslat()
        self._isler.put((gorev, mod, profil, self._aktif, ekip, gosterim))

    def _isci_baslat(self) -> None:
        if self._isci is not None and self._isci.is_alive():
            return
        self._isci = threading.Thread(target=self._isci_dongusu, daemon=True,
                                      name="limina-ajan")
        self._isci.start()

    def _tarayiciyi_kapat(self) -> None:
        """Playwright oturumunu duzgun kapatir. YALNIZCA isci thread'inden.

        Neden isci thread'inde: Playwright'in senkron API'si kendisini baslatan
        thread'e baglidir. kapat() UI thread'inden cagriliyor; oradan
        browser.close() demek az once duzeltilen thread ihlalinin aynisi olurdu.
        Kapatilmazsa surec cikarken Node surucusunun ucu aniden kesiliyor ve
        konsola EPIPE yigin izi dusuyor (gozlemlendi).
        """
        try:
            from limina.vekil_v0 import TARAYICI
            TARAYICI.kapat()
        except Exception:
            pass        # kapanis yolunda hicbir hata pencereyi asmamali

    def _isci_dongusu(self) -> None:
        """Butun gorevler BU thread'de kosar; Playwright oturumu boylece butun kalir."""
        while True:
            is_ = self._isler.get()
            if is_ is None:            # kapanis isareti
                self._tarayiciyi_kapat()
                return
            gorev, mod, profil, sohbet, ekip, gosterim = is_
            try:
                self._kos(gorev, mod, profil, sohbet, ekip, gosterim)
            finally:
                self._mesgul = False
                self._kaydet(sohbet)

    def olaylari_cek(self, azami: int = 100) -> list[dict[str, Any]]:
        """UI dongusu bunu periyodik cagirir. Bloke olmaz."""
        cikti: list[dict[str, Any]] = []
        for _ in range(azami):
            try:
                cikti.append(olay_sozluge(self._olaylar.get_nowait()))
            except queue.Empty:
                break
        return cikti

    def onay_cevapla(self, cevap: str) -> None:
        """Onay kartindaki dugme. cevap: 'evet' | 'red' | 'tumu'."""
        try:
            deger = OnayCevabi(cevap)
        except ValueError:
            deger = OnayCevabi.RED   # taninmayan cevap izin kazanmaz
        try:
            self._cevap.put_nowait(deger)
        except queue.Full:
            pass   # bekleyen istek yok; yinelenen tiklama yutulur

    def durdur(self) -> None:
        """Durdur dugmesi. Calisan arac cagrisini kesmez, sonrakini baslatmaz."""
        self.oturum.durdur()
        try:
            self._cevap.put_nowait(OnayCevabi.RED)   # onayda bekleyeni aninda coz
        except queue.Full:
            pass

    def kapat(self) -> None:
        """Pencere kapaniyor. Onay alinamiyor -> RED (SECURITY.md)."""
        self._kapaniyor = True
        for s in self._sohbetler:
            self._kaydet(s)
        self.durdur()
        self._isler.put(None)
        if self._isci is not None:
            self._isci.join(timeout=5.0)

    # ------------------------------------------------------------------
    # Ajan thread'inden cagrilir
    # ------------------------------------------------------------------
    def _kos(self, gorev: str, mod: str | None, profil: str | None,
             sohbet: dict[str, Any], ekip: bool = False,
             gosterim: str | None = None) -> None:
        oturum = sohbet["oturum"]
        oturum.yayinla(Olay(OlayTipi.GOREV_BASLADI,
                            {"gorev": gosterim if gosterim is not None else gorev,
                             "mod": mod, "profil": profil, "ekip": ekip}))
        try:
            sonuc = (self._kosucu(gorev, mod, oturum, profil, ekip) if ekip
                     else self._kosucu(gorev, mod, oturum, profil))
            oturum.yayinla(Olay(OlayTipi.GOREV_BITTI, {"metin": sonuc, "durduruldu": False}))
        except Durduruldu:
            # Yarim gorev baglamda kalmasin (cevapsiz function_call sonraki turu bozar).
            if oturum.gecmis_koru:
                oturum.gecmis_gorevi_geri_al()
            oturum.yayinla(Olay(OlayTipi.GOREV_BITTI, {
                "metin": "Durduruldu. Yapilan islemler gunlukte, geri almak icin /gecmis",
                "durduruldu": True,
            }))
        except Exception as hata:   # ajan thread'i sessizce olmemeli
            oturum.yayinla(Olay(OlayTipi.HATA, {"mesaj": f"{type(hata).__name__}: {hata}"}))
            oturum.yayinla(Olay(OlayTipi.GOREV_BITTI,
                                {"metin": "Gorev hatayla bitti.", "durduruldu": False}))

    def _onay_bekle(self, istek: OnayIstegi) -> OnayCevabi:
        """Ajan thread'i burada bloke olur. ONAY_GEREKLI olayini onay_iste yayinladi."""
        while True:
            if self.oturum.durdur_bayragi.is_set():
                return OnayCevabi.RED
            try:
                return self._cevap.get(timeout=0.2)
            except queue.Empty:
                continue

    # ------------------------------------------------------------------

    @staticmethod
    def _bosalt(k: queue.Queue) -> None:
        while True:
            try:
                k.get_nowait()
            except queue.Empty:
                return
