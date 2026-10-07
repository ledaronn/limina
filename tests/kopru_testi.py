"""Kopruyu modelsiz sinar: thread, onay bloklamasi, durdurma, toplu onay.

Calistirma:  python tests/kopru_testi.py
Model cagirmaz, kota harcamaz, dosya sistemine dokunmaz.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

# Testler GERCEK sohbet klasorune (~/.vekil/sohbetler) dokunmamali: hem kullanici
# verisini kirletir hem de testler birbirini etkiler — bir test kaydeder, sonraki
# Kopru onu diskten yukler ve sayimlar tutmaz (yakalandi).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # proje koku -> 'pevrai' paketi
from pevrai import sohbet as _depo
from pevrai import kurulum
from pevrai import ceviri as _ceviri
_ceviri.dil_ayarla("tr")   # metinler kaynak dilde dogrulanir; kisisel arayuz.toml'a bagli kalmasin
kurulum.politikayi_hazirla(sessiz=True)   # temiz klonda policy.toml sablondan
_depo.KOK = Path(tempfile.mkdtemp(prefix="pevrai_test_"))

# Model gecmisi pevrai.model.taban'in sozluk bicimindedir (sohbet.py ayni
# bicimi diske yazar): SDK nesnesi yok, taklit de gerekmiyor.
from pevrai.model.taban import kullanici_mesaji, model_turu, sonuc_mesaji, AracCagrisi

from pevrai.gui_kopru import Kopru
from pevrai.olaylar import (
    Durduruldu,
    Olay,
    OlayTipi,
    OnayCevabi,
    OnayIstegi,
    Oturum,
    onay_iste,
)

HATA_SAYISI = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA_SAYISI
    if kosul:
        print(f"  GECTI  {mesaj}")
    else:
        HATA_SAYISI += 1
        print(f"  KALDI  {mesaj}")


def temiz_kopru(kosucu):
    """Her test kendi TEMIZ sohbet klasoruyle baslar.

    Sohbetler artik diske yaziliyor; onceki testin kaydettigi sohbet, sonraki
    testin Kopru'su tarafindan yukleniyor ve sayimlar tutmuyordu (yakalandi).
    """
    shutil.rmtree(_depo.KOK, ignore_errors=True)
    _depo.KOK.mkdir(parents=True, exist_ok=True)
    TAMPON.clear()
    return Kopru(kosucu=kosucu)


def _istek(arac: str, risk: str, toplu: bool = True, yikici: bool = False) -> OnayIstegi:
    return OnayIstegi(arac=arac, args={"path": "kum/a.txt"}, risk=risk,
                      etki="UZERINE YAZILACAK (yedek alinir)",
                      yikici=yikici, toplu_sunulabilir=toplu)


def sahte_gorev(gorev: str, mod: str | None, oturum: Oturum,
                profil: str | None = None) -> str:
    """Iki write_file + bir trash isteyen sahte bir ajan turu."""
    kararlar: list[bool] = []
    for _ in range(2):
        oturum.kontrol()
        kararlar.append(onay_iste(oturum, _istek("write_file", "WRITE")))
    oturum.kontrol()
    kararlar.append(onay_iste(oturum, _istek("trash", "DESTRUCTIVE", toplu=False)))
    return ",".join("E" if k else "R" for k in kararlar)


TAMPON: list[dict] = []


def olay_bekle(kopru: Kopru, tip: OlayTipi, sn: float = 3.0) -> dict | None:
    """UI thread'inin yaptigi sey: kuyrugu yokla. Eslesmeyenler tamponda kalir."""
    bitis = time.monotonic() + sn
    while True:
        for i, olay in enumerate(TAMPON):
            if olay["tip"] == tip.value:
                return TAMPON.pop(i)
        if time.monotonic() >= bitis:
            return None
        TAMPON.extend(kopru.olaylari_cek())
        time.sleep(0.01)


# ---------------------------------------------------------------------------

def test_toplu_onay_ve_destructive() -> None:
    print("\n1) Toplu onay WRITE'ta gecerli, DESTRUCTIVE'te degil")
    kopru = temiz_kopru(sahte_gorev)
    kopru.gorev_baslat("sahte")

    dogrula(olay_bekle(kopru, OlayTipi.ONAY_GEREKLI) is not None,
            "ilk write_file onay istedi")
    kopru.onay_cevapla("tumu")

    # Ikinci write_file toplu onaydan gecmeli -> yeni ONAY_GEREKLI cikmamali,
    # bir sonraki istek DESTRUCTIVE olmali.
    olay = olay_bekle(kopru, OlayTipi.ONAY_GEREKLI)
    dogrula(olay is not None and olay["veri"]["istek"]["arac"] == "trash",
            "ikinci write_file toplu onaydan gecti, sirada trash var")
    dogrula(olay is not None and olay["veri"]["istek"]["toplu_sunulabilir"] is False,
            "trash icin 'Tumu' sunulabilir degil")

    kopru.onay_cevapla("tumu")   # saglayici yasak secenegi zorluyor
    bitti = olay_bekle(kopru, OlayTipi.GOREV_BITTI)
    dogrula(bitti is not None and bitti["veri"]["metin"] == "E,E,E",
            "yasak TUMU tekile dusuruldu, gorev tamamlandi")
    dogrula("trash" not in kopru.oturum.aktif_toplu_onaylar(),
            "trash toplu onay listesine YAZILMADI")


def test_durdurma() -> None:
    print("\n2) Onay beklerken durdurma")
    kopru = temiz_kopru(sahte_gorev)
    kopru.gorev_baslat("sahte")
    dogrula(olay_bekle(kopru, OlayTipi.ONAY_GEREKLI) is not None, "onay bekleniyor")

    kopru.durdur()
    bitti = olay_bekle(kopru, OlayTipi.GOREV_BITTI)
    dogrula(bitti is not None and bitti["veri"]["durduruldu"] is True,
            "durdurma gorevi bitirdi, cikti traceback degil")
    dogrula(not kopru.calisiyor(), "ajan thread'i kapandi")


def test_kapanma_reddeder() -> None:
    print("\n3) Pencere kapanirsa onay REDDEDILIR")
    kopru = temiz_kopru(sahte_gorev)
    kopru.gorev_baslat("sahte")
    olay_bekle(kopru, OlayTipi.ONAY_GEREKLI)
    kopru.kapat()
    dogrula(not kopru.calisiyor(), "kapat() thread'i 5sn icinde topladi")


def test_bozuk_saglayici() -> None:
    print("\n4) Bozuk/istisna atan saglayici izin kazanmaz")

    def patlayan(istek: OnayIstegi) -> OnayCevabi:
        raise RuntimeError("saglayici coktu")

    oturum = Oturum(onay_saglayici=patlayan)
    dogrula(onay_iste(oturum, _istek("write_file", "WRITE")) is False,
            "istisna -> RED")

    oturum2 = Oturum(onay_saglayici=lambda i: OnayCevabi.RED)
    dogrula(onay_iste(oturum2, _istek("write_file", "WRITE")) is False, "RED -> False")

    # RuntimeError yukarida genel "except Exception" dalini sinar; SECURITY.md'nin
    # "onay alinamazsa reddet" maddesi EOFError/KeyboardInterrupt icin AYRI bir
    # dal iddia ediyor (olaylar.py:210) — o dal hic sinanmamisti.
    def stdin_yok(istek: OnayIstegi) -> OnayCevabi:
        raise EOFError()

    def ctrl_c(istek: OnayIstegi) -> OnayCevabi:
        raise KeyboardInterrupt()

    dogrula(onay_iste(Oturum(onay_saglayici=stdin_yok), _istek("write_file", "WRITE")) is False,
            "EOFError (stdin yok) -> RED")
    dogrula(onay_iste(Oturum(onay_saglayici=ctrl_c), _istek("write_file", "WRITE")) is False,
            "KeyboardInterrupt (Ctrl-C) -> RED")


def test_gorev_hatasi_thread_oldurmez() -> None:
    print("\n5) Gorev icindeki istisna arayuze HATA olarak doner")

    def patlayan_gorev(gorev: str, mod: str | None, oturum: Oturum,
                       profil: str | None = None) -> str:
        raise ValueError("beklenmeyen")

    kopru = temiz_kopru(patlayan_gorev)
    kopru.gorev_baslat("sahte")
    hata = olay_bekle(kopru, OlayTipi.HATA)
    dogrula(hata is not None and "beklenmeyen" in hata["veri"]["mesaj"],
            "HATA olayi yayinlandi")
    dogrula(olay_bekle(kopru, OlayTipi.GOREV_BITTI) is not None,
            "GOREV_BITTI yine de geldi (UI kilitlenmez)")


def test_gecmis() -> None:
    print("\n6) Sohbet gecmisi")
    from pevrai.olaylar import GECMIS_TAVANI

    o = Oturum(onay_saglayici=lambda i: OnayCevabi.EVET)
    # Gorev 1: 3 oge
    o.gorev_basladi(); o.gecmis_al().extend(["g1-soru", "g1-arac", "g1-yanit"])
    # Gorev 2: 2 oge
    o.gorev_basladi(); o.gecmis_al().extend(["g2-soru", "g2-yanit"])
    dogrula(len(o.gecmis_al()) == 5, "gecmis gorevler arasi birikiyor")
    dogrula(o.gecmis_gorev_sayisi() == 2, "iki gorev isaretlendi")

    # Yarim kalan gorev geri alinir (durdurma senaryosu)
    o.gorev_basladi(); o.gecmis_al().extend(["g3-soru", "g3-yarim-cagri"])
    o.gecmis_gorevi_geri_al()
    dogrula(o.gecmis_al() == ["g1-soru", "g1-arac", "g1-yanit", "g2-soru", "g2-yanit"],
            "yarim gorev gecmisten temizlendi")
    dogrula(o.gecmis_gorev_sayisi() == 2, "gorev isareti de geri alindi")

    # Tavan: en eski gorev KOMPLE atilir, parcali degil
    o2 = Oturum(onay_saglayici=lambda i: OnayCevabi.EVET)
    for n in range(6):
        o2.gorev_basladi()
        o2.gecmis_al().extend([f"g{n}-{k}" for k in range(10)])
    o2.gorev_basladi()
    dogrula(len(o2.gecmis_al()) <= GECMIS_TAVANI, f"tavan uygulandi ({len(o2.gecmis_al())})")
    dogrula(o2.gecmis_al()[0].endswith("-0"), "kesme gorev sinirindan yapildi")
    indis = o2._gorev_indisleri
    dogrula(indis[0] == 0 and all(0 <= i <= len(o2.gecmis_al()) for i in indis),
            "gorev indisleri kaydirildi")

    o2.gecmis_sifirla()
    dogrula(o2.gecmis_al() == [] and o2.gecmis_gorev_sayisi() == 0, "sifirlama")


def test_yeni_sohbet() -> None:
    print("\n7) Yeni sohbet")
    kopru = temiz_kopru(sahte_gorev)
    kopru.oturum.toplu_ekle("write_file")
    kopru.oturum.gecmis_al().append("eski")
    eski = kopru.oturum

    dogrula(isinstance(kopru.yeni_sohbet(), str), "yeni sohbet kimlik dondurur")
    dogrula(kopru.oturum is not eski, "yeni Oturum nesnesi")
    dogrula(kopru.oturum.aktif_toplu_onaylar() == [], "toplu onaylar sifirlandi")
    dogrula(kopru.oturum.gecmis_al() == [], "gecmis sifirlandi")
    dogrula(kopru.oturum.gecmis_koru is True, "gecmis ayari korundu")

    kopru.gorev_baslat("sahte")
    olay_bekle(kopru, OlayTipi.ONAY_GEREKLI)
    dogrula(kopru.yeni_sohbet() is None, "gorev calisirken yeni sohbet acilmaz")
    kopru.durdur()


def test_sohbet_gecisi() -> None:
    print("\n8) Sohbetler arasi gecis")
    kopru = temiz_kopru(sahte_gorev)

    kopru.gorev_baslat("birinci gorev")
    # Onay kuyrugu tek slotlu (cift tiklamayi yutar): her onay TEK TEK,
    # bir sonraki istek gelene kadar beklenerek cevaplanir.
    for _ in range(3):
        dogrula(olay_bekle(kopru, OlayTipi.ONAY_GEREKLI) is not None, "onay istendi")
        kopru.onay_cevapla("evet")
    dogrula(olay_bekle(kopru, OlayTipi.GOREV_BITTI) is not None, "gorev bitti")

    liste = kopru.sohbetler()
    dogrula(len(liste) == 1 and liste[0]["baslik"] == "birinci gorev",
            "baslik ilk gorevden turetildi")
    birinci = liste[0]["id"]

    ikinci = kopru.yeni_sohbet()
    dogrula(ikinci != birinci, "yeni sohbet ayri kimlik aldi")
    dogrula(len(kopru.olaylari_cek()) == 0, "yeni sohbette kuyruk bos")

    arsiv = kopru.sohbet_ac(birinci)
    dogrula(arsiv is not None and len(arsiv) > 3, "arsiv geri dondu")
    dogrula(arsiv[0]["tip"] == "gorev_basladi", "arsiv gorev basindan basliyor")
    dogrula([o for o in arsiv if o["tip"] == "onay_gerekli"], "onay olaylari arsivde")
    dogrula(kopru.sohbetler()[0]["aktif"] is True, "birinci sohbet aktif oldu")

    # Arka plandaki sohbetin oturumu ayri: gecmis ve toplu onay karismaz
    kopru.sohbet_ac(ikinci)
    dogrula(kopru.oturum.gecmis_al() == [], "ikinci sohbetin gecmisi bagimsiz")

    dogrula(kopru.sohbet_sil(ikinci) is True, "sohbet silindi")
    dogrula(len(kopru.sohbetler()) == 1, "listede bir sohbet kaldi")


def test_tek_isci_thread() -> None:
    print("\n9) Butun gorevler AYNI thread'de kosar")
    import threading

    thread_adlari: list[int] = []

    def izleyen_gorev(gorev: str, mod: str | None, oturum: Oturum,
                      profil: str | None = None) -> str:
        # Playwright gibi thread'e bagli kutuphaneler icin kritik: gorev basina
        # yeni thread acilirsa ikinci tarayici cagrisi "is parcacigi hatasi" verir.
        thread_adlari.append(threading.get_ident())
        return "bitti"

    TAMPON.clear()
    kopru = temiz_kopru(izleyen_gorev)
    for n in range(3):
        kopru.gorev_baslat(f"gorev {n}")
        dogrula(olay_bekle(kopru, OlayTipi.GOREV_BITTI) is not None, f"gorev {n} bitti")

    dogrula(len(thread_adlari) == 3, "uc gorev de kostu")
    dogrula(len(set(thread_adlari)) == 1,
            f"ucu de AYNI thread'de ({len(set(thread_adlari))} farkli thread)")
    dogrula(threading.get_ident() not in thread_adlari, "ana thread'de kosmadi")

    # Playwright thread'e bagli: kapatma ISCI thread'inde olmali, UI'da degil.
    kapatan: list[int] = []
    kopru._tarayiciyi_kapat = lambda: kapatan.append(threading.get_ident())

    kopru.kapat()
    dogrula(kopru._isci is not None and not kopru._isci.is_alive(), "kapat isciyi durdurdu")
    dogrula(len(kapatan) == 1, "tarayici oturumu kapatildi (EPIPE'in sebebi buydu)")
    dogrula(kapatan and kapatan[0] == thread_adlari[0],
            "kapatma GOREVLERLE AYNI thread'de yapildi")
    dogrula(kapatan and kapatan[0] != threading.get_ident(),
            "UI thread'inden kapatilmadi")


def test_kalicilik() -> None:
    print("\n10) Sohbet diske kaydedilir ve geri yuklenir")

    gorulen: list[int] = []

    def gecmisi_sayan(gorev: str, mod: str | None, oturum: Oturum,
                      profil: str | None = None) -> str:
        # calistir()'in yaptigini taklit eder: gercek Content nesneleri,
        # arasinda bir arac cagrisi + sonucu (zincir dogrulamasi da sinansin).
        gorulen.append(len(oturum.gecmis_al()))
        oturum.gorev_basladi()
        oturum.gecmis_al().extend([
            kullanici_mesaji(gorev),
            model_turu(None, [AracCagrisi(ad="list_dir", args={"path": "kum"}, id="call_1")]),
            sonuc_mesaji([("list_dir", "call_1", "3 dosya")]),
            model_turu(f"{gorev}: tamam", []),
        ])
        return "tamam"

    kopru = temiz_kopru(gecmisi_sayan)
    kopru.gorev_baslat("ilk gorev")
    dogrula(olay_bekle(kopru, OlayTipi.GOREV_BITTI) is not None, "gorev bitti")
    kopru.kapat()

    dosyalar = list(_depo.KOK.glob("*.json"))
    dogrula(len(dosyalar) == 1, "sohbet diske yazildi")

    # --- pencere yeniden aciliyor ---
    yeni = Kopru(kosucu=gecmisi_sayan)
    liste = yeni.sohbetler()

    # Acilista kayitli sohbetler YUKLENIR ama aktif olan YENI VE BOS bir
    # sohbettir. Eski test "son sohbet aktif acilir" varsayiyordu; davranis
    # bilerek degisti (kullanici Pevrai'yi gorev yazmak icin aciyor), test
    # guncellenmemisti. Olculen sey artik: kayitli olan KAYBOLMADI, ama
    # kullanicinin uzerine dusmedi.
    kayitli = [s for s in liste if s["baslik"] == "ilk gorev"]
    dogrula(len(kayitli) == 1, "kayitli sohbet diskten geri yuklendi")
    dogrula(kayitli[0]["aktif"] is False, "kayitli sohbet acilista aktif DEGIL")

    aktif = [s for s in liste if s["aktif"]]
    dogrula(len(aktif) == 1, "tam bir tane aktif sohbet var")
    dogrula(aktif[0]["id"] != kayitli[0]["id"], "aktif olan yeni, bos sohbet")

    # Bos sohbet diske YAZILMAMALI, yoksa her acilis bir cop json birakir
    # ve kenar cubugu zamanla bos girdilerle dolar.
    dogrula(len(list(_depo.KOK.glob("*.json"))) == 1, "bos sohbet diske yazilmadi")

    arsiv = yeni.sohbet_ac(kayitli[0]["id"])
    dogrula(arsiv and arsiv[0]["tip"] == "gorev_basladi", "arsiv geri geldi")
    dogrula(any(o["tip"] == "gorev_bitti" for o in arsiv), "tamamlanmis akis korundu")
    dogrula(yeni.uyarilari_al() == [], "uyari yok, temiz yuklendi")

    print("\n11) Yuklenen sohbette BAGLAM da duruyor")
    yeni.gorev_baslat("ikinci gorev")
    dogrula(olay_bekle(yeni, OlayTipi.GOREV_BITTI) is not None, "ikinci gorev bitti")
    dogrula(len(gorulen) == 2 and gorulen[1] == 4,
            f"ikinci gorev onceki konusmayi gordu (baglamda {gorulen[1]} kayit)")
    ilk = yeni.oturum.gecmis_al()[0]
    dogrula(ilk["parcalar"][0].get("metin") == "ilk gorev",
            "kullanici mesaji diskten aynen dondu")
    cagri_p = yeni.oturum.gecmis_al()[1]["parcalar"][0]
    dogrula(cagri_p.get("tip") == "cagri" and cagri_p.get("ad") == "list_dir" and cagri_p.get("id") == "call_1",
            "arac cagrisi (kimligiyle) diskten aynen dondu")
    sonuc_p = yeni.oturum.gecmis_al()[2]["parcalar"][0]
    dogrula(sonuc_p.get("tip") == "sonuc" and sonuc_p.get("cevap") == {"result": "3 dosya"} and sonuc_p.get("id") == "call_1",
            "arac SONUCU (kimligiyle) diskten aynen dondu")
    yeni.kapat()
    # Hala 1: "ikinci gorev" sohbet_ac ile acilan KAYITLI sohbette calisti
    # (aktif olan oydu), terk edilen bos sohbet hic doldurulmadi. Cakisma
    # riski kalmasin diye burada da _sayac degil id EŞLEŞMESİ dogrulaniyor.
    dogrula(len(list(_depo.KOK.glob("*.json"))) == 1, "bos sohbet kapanista da yazilmadi")

    print("\n12) Sohbet silinince dosya da gider")
    ucuncu = Kopru(kosucu=gecmisi_sayan)
    # [0] artik AKTIF (bos, yeni) sohbet — liste sirali geliyor (bolum 13).
    # Silinecek olan diskteki kayit: aktif olmayani sec.
    kimlik = next(s["id"] for s in ucuncu.sohbetler() if not s["aktif"])
    dogrula(ucuncu.sohbet_sil(kimlik) is True, "silindi")
    dogrula(list(_depo.KOK.glob("*.json")) == [], "dosya diskten de silindi")


def test_sohbet_sirasi() -> None:
    print("\n13) Kenar cubugu sirasi: en yeni ustte, aktif basta, diskten sonra da ayni")
    from datetime import datetime, timedelta
    from pevrai.gui_kopru import sohbet_sirasi

    # --- saf karar fonksiyonu ---
    a = {"id": "a", "guncelleme": "2026-09-14T10:00:00"}
    b = {"id": "b", "guncelleme": "2026-09-14T11:00:00"}
    c = {"id": "c", "guncelleme": "2026-09-14T09:00:00"}
    dogrula([s["id"] for s in sohbet_sirasi([a, b, c], None)] == ["b", "a", "c"],
            "aktif yokken en yeni guncellenen ustte")
    dogrula([s["id"] for s in sohbet_sirasi([a, b, c], c)] == ["c", "b", "a"],
            "aktif sohbet en eski olsa da basta")
    ayni1 = {"id": "e1", "guncelleme": "2026-09-14T12:00:00"}
    ayni2 = {"id": "e2", "guncelleme": "2026-09-14T12:00:00"}
    dogrula([s["id"] for s in sohbet_sirasi([ayni1, ayni2], None)] == ["e2", "e1"],
            "ayni saniyede sonra yaratilan ustte")
    dogrula([s["id"] for s in sohbet_sirasi([a, {"id": "x"}], None)] == ["a", "x"],
            "guncelleme alani eksik sohbet dibe duser, KeyError yok")

    # --- kopru: uc sohbet, uc farkli zaman ---
    def hizli(gorev: str, mod: str | None, oturum: Oturum, profil: str | None = None) -> str:
        return "ok"

    kopru = temiz_kopru(hizli)
    kimlikler: list[str] = []
    for n in range(3):
        kopru.gorev_baslat(f"gorev {n}")
        dogrula(olay_bekle(kopru, OlayTipi.GOREV_BITTI) is not None, f"gorev {n} bitti")
        kimlikler.append(kopru._aktif["id"])
        kopru.yeni_sohbet()
    g0, g1, g2 = kimlikler
    yeni = kopru._aktif["id"]
    dogrula(all("guncelleme" in s for s in kopru.sohbetler()),
            "her sohbette guncelleme alani var (bellekteki, diske yazilmamis dahil)")

    # Zamanlar elle ayristiriliyor: gorevler ayni saniyede bitti, saniye
    # hassasiyetinde beraberlik olculmek istenen sey degil.
    simdi = datetime.now()
    zaman = {g0: simdi - timedelta(hours=3), g1: simdi - timedelta(hours=1),
             g2: simdi - timedelta(hours=2)}
    for s in kopru._sohbetler:
        if s["id"] in zaman:
            s["guncelleme"] = zaman[s["id"]].isoformat(timespec="seconds")

    sira = [s["id"] for s in kopru.sohbetler()]
    dogrula(sira == [yeni, g1, g2, g0],
            f"bos 'Yeni sohbet' aktifken basta, kalanlar en yeni ustte ({sira})")
    dogrula(kopru.sohbetler()[0]["baslik"] == "Yeni sohbet" and kopru.sohbetler()[0]["aktif"],
            "basliksiz aktif sohbet 'Yeni sohbet' adiyla basta")

    kopru.sohbet_ac(g0)
    sira = [s["id"] for s in kopru.sohbetler()]
    dogrula(sira == [g0, yeni, g1, g2],
            f"en eski sohbet aktif yapilinca basa gecti, gerisi degismedi ({sira})")

    # --- kapanis + yeniden acilis: sira diskten de ayni geliyor ---
    kopru.kapat()
    import json
    diskte = json.loads((_depo.KOK / f"{g0}.json").read_text(encoding="utf-8"))
    dogrula(diskte["guncelleme"] == zaman[g0].isoformat(timespec="seconds"),
            "kaydet bellekteki guncelleme'yi AYNEN yazdi, kapanis anini degil")

    yeni_kopru = Kopru(kosucu=hizli)
    liste = yeni_kopru.sohbetler()
    dogrula(liste[0]["aktif"] and liste[0]["baslik"] == "Yeni sohbet",
            "acilista bos yeni sohbet aktif ve basta")
    dogrula([s["id"] for s in liste[1:]] == [g1, g2, g0],
            f"diskten yuklenen sohbetler ayni sirada ({[s['id'] for s in liste[1:]]})")
    yeni_kopru.kapat()


def test_arac_daraltmasi() -> None:
    print("\n14) Arac daraltmasi SOHBET BASINA yasar, gorevde degismez")

    def hizli(gorev: str, mod: str | None, oturum: Oturum, profil: str | None = None) -> str:
        return "ok"

    kopru = temiz_kopru(hizli)
    dogrula(kopru.araclari_daralt(["browser_open"], False) is True, "bos sohbette daraltma yazildi")
    dogrula(kopru.oturum.kapali_araclar() == ["browser_open"] and not kopru.oturum.hepsi_kapali(),
            "Oturum daraltmayi tasiyor")
    # Bos sohbette "yeni sohbet": Oturum YENIDEN kurulmali, daraltma sizmamali
    # (toplu onay icin ayni kural vardi; daraltma icin eksikti, testte yakalandi).
    dogrula(isinstance(kopru.yeni_sohbet(), str) and kopru.oturum.kapali_araclar() == [],
            "bos sohbetten yeni sohbete gecince daraltma sifirlandi")

    kopru.araclari_daralt([], True)
    kopru.gorev_baslat("a")
    dogrula(olay_bekle(kopru, OlayTipi.GOREV_BITTI) is not None, "gorev bitti")
    a = kopru._aktif["id"]
    dogrula(kopru.oturum.hepsi_kapali(), "gorev daraltmayi silmedi (sohbet boyunca kalir)")

    yeni = kopru.yeni_sohbet()
    dogrula(yeni != a and not kopru.oturum.hepsi_kapali() and kopru.oturum.kapali_araclar() == [],
            "yeni sohbet varsayilanla (hepsi acik) basladi")
    kopru.sohbet_ac(a)
    dogrula(kopru.oturum.hepsi_kapali(), "eski sohbete donunce onun daraltmasi geri geldi")

    kopru.gorev_baslat("b")
    olay_bekle(kopru, OlayTipi.GOREV_BASLADI)
    kopru._mesgul = True                     # gorev suruyor gibi
    dogrula(kopru.araclari_daralt([], False) is False, "gorev calisirken daraltma reddedilir")
    kopru._mesgul = False
    olay_bekle(kopru, OlayTipi.GOREV_BITTI)
    kopru.kapat()



def ag_koprusu() -> None:
    """GERCEK kopru metotlari (pencere.Api.ag_*).

    Neden ayri: arayuz testi SAHTE kopru kullaniyor, motor testi kopruyu hic
    cagirmiyor. Bu boslukta ag_atesle, v2'de kaldirilmis olan ag.okuma_metni'yi
    cagirmaya devam ediyordu — uygulamada "Atesle" dugmesi cokuyordu ve hicbir
    test gormuyordu.
    """
    print("\n11) Dusunce Agi koprusu (gercek Api metotlari)")
    import shutil as _sh
    import tempfile as _tf
    from pevrai import ag
    from pevrai.pencere import Api

    kok = Path(_tf.mkdtemp(prefix="pevrai_agkopru_"))
    eski = ag.AG_KOK
    ag.AG_KOK = kok / "aglar"
    try:
        api = Api.__new__(Api)                      # pywebview penceresi gerekmez
        from pevrai import PROJE_KOKU
        from pevrai.gate import Politika as _Politika
        api._politika = _Politika(PROJE_KOKU / "policy.toml")

        r = api.ag_kaydet({"ad": "kopru denemesi", "tetik": "deneme yapilirken",
                           "dugumler": [
                               {"kimlik": "a", "baslik": "Amac", "metin": "Istek: {gorev}",
                                "konum": [0, 0, 0]},
                               {"kimlik": "b", "baslik": "Kural", "tur": "kural", "kapi": "hepsi",
                                "metin": "Kisa yaz.", "konum": [10, 0, 0]}],
                           "baglantilar": [{"kaynak": "a", "hedef": "b"}]})
        dogrula(r["ok"], f"ag_kaydet: {r.get('hata')}")
        dogrula(isinstance(r.get("uyarilar"), list), "kayit statik analiz uyarilarini donuyor")

        liste = api.ag_listesi()
        dogrula(liste["ok"] and liste["aglar"][0]["tetik"] == "deneme yapilirken",
                "ag_listesi tetigi tasiyor (talimata bu yaziliyor)")

        r = api.ag_atesle("kopru denemesi", [], "tam", "bu haftayi ozetle")
        dogrula(r["ok"], f"ag_atesle CALISIYOR: {r.get('hata')}")
        dogrula("Ağ okuması" in r["metin"], "okuma metni geldi")
        dogrula("bu haftayi ozetle" in r["metin"], "{gorev} yer tutucusu o istekle doldu")
        dogrula([x["kimlik"] for x in r["kosu"]["sira"]] == ["a", "b"], "atesleme sirasi dogru")
        dogrula(all(k in r["kosu"] for k in ("sessiz", "engellenen", "uyarilar")),
                "kosu arayuzun bekledigi alanlari tasiyor")

        r = api.ag_atesle("olmayan ag")
        dogrula(not r["ok"] and r["hata"], "olmayan ag: cokmeden hata donuyor")
        r = api.ag_kaydet({"ad": "bozuk", "dugumler": [{"kimlik": "x", "baslik": "x", "tur": "dosya"}]})
        dogrula(not r["ok"] and r["hata"], "bozuk ag: cokmeden sebep donuyor")
        dogrula(api.ag_getir("kopru denemesi")["ok"], "ag_getir")
        dogrula(api.ag_sil("kopru denemesi")["ok"], "ag_sil")
    finally:
        ag.AG_KOK = eski
        _sh.rmtree(kok, ignore_errors=True)


if __name__ == "__main__":
    test_toplu_onay_ve_destructive()
    test_durdurma()
    test_kapanma_reddeder()
    test_bozuk_saglayici()
    test_gorev_hatasi_thread_oldurmez()
    test_gecmis()
    test_yeni_sohbet()
    test_sohbet_gecisi()
    test_tek_isci_thread()
    test_kalicilik()
    test_sohbet_sirasi()
    test_arac_daraltmasi()
    ag_koprusu()
    shutil.rmtree(_depo.KOK, ignore_errors=True)
    print(f"\nSonuc: {'TUM TESTLER GECTI' if HATA_SAYISI == 0 else f'{HATA_SAYISI} test kaldi'}")
    raise SystemExit(1 if HATA_SAYISI else 0)