# vekil_v0.py — Faz 5a: onay sağlayıcı + olay yayını. Döngü arayüzü bilmez.
import difflib
import json
import os
import re
import shutil
import sys
import threading
import time
import tomllib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable

from limina import model as modelkat
from limina.model import (ModelHatasi, OranSiniri, SunucuHatasi, ZamanAsimi,
                          kullanici_mesaji, sonuc_mesaji)
from limina.model.taban import ardisik_birlestir

from limina import PROJE_KOKU, journal
from limina import model_zinciri
from limina import ofis
from limina import mcp_bridge
from limina import tarayici
from limina.baglam import B
from limina.sonuc import hata as sonuc_hatasi
from limina.ceviri import t
from limina.araclar import kayit
from limina import talimat as _talimat, durum as _durum
# Bolunen moduller; buradaki adlar geriye donuk uyumluluk (testler, pencere).
from limina.talimat import (gosterilen_araclar, sistem_talimati, talimat_cumleleri,   # noqa: F401
                            _persona_bolumleri, _erisim, _Erisim, _kok_isaretleri, OKUYAN_ARACLAR)
from limina.durum import (_durum_dosyasi_yaz, _durum_kalanlar, _sure_metni, ozet_metni,   # noqa: F401
                          _ozet_yaz, _durum_oku, _uzlastirma_satiri, _devam_gorevi_kur)
# Arac fonksiyonlari artik limina.araclar altinda (TEK bildirim: @arac).
# Buradaki adlar geriye donuk uyumluluk: testler ve eski cagiranlar
# vekil_v0.write_file gibi erisiyor.
from limina.araclar.dosya import (list_dir, read_file, search, degisiklik_gecmisi,   # noqa: F401
                                  read_document, write_file, move, rename, trash, edit_file, mkdir)
from limina.araclar.acma import open_file  # noqa: F401
from limina.araclar.tarayici_araclari import (browser_open, browser_read, browser_snapshot,  # noqa: F401
                                              browser_click, browser_fill, browser_download)
from limina.araclar.ortak import (MAX_OUTPUT, MAX_SATIR, kirp as _kirp, bulunamadi as _bulunamadi,  # noqa: F401
                                  journal_yaz as _journal_yaz, hassas_mi as _hassas_mi,
                                  hassas_maskele as _hassas_maskele, args_gizle as _args_gizle)
from limina.gate import (Politika, ASK, DENY, tavan_karari, tur_karari, durum_karari,
                  kok_karari, butce_karari, devam_karari, TUR_TAVANI, ARAC_YOL_MODU)
from limina.olaylar import (Durduruldu, Olay, OlayTipi, OnayIstegi, Oturum,
                     onay_iste, terminal_onayi, terminal_oturumu)


class TavanDoldu(Exception):
    """Gunluk istek tavanina carpildi. Bu bir AG HATASI DEGIL, bizim
    duvarimiz — o yuzden yeniden denenmez, gorev orada kesilir."""

    def __init__(self, rol: str, sayi: int, tavan: int) -> None:
        self.rol, self.sayi, self.tavan = rol, sayi, tavan
        super().__init__(f"{rol}: {sayi}/{tavan}")

# Windows konsolu UTF-8 değilse çıktı yazarken çökebilir. Çökmek yerine ? bassın.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_DENEME = 3
# Projedeki her uzun islemin siniri var (Playwright, MCP koprusu, LibreOffice);
# en sik yapilan cagrinin (model) yoktu. Ag yarida giderse (ENOTFOUND/timeout
# gozlemlendi) client SURESIZ bekler ve gorev GUI'de sonsuza kadar "calisiyor"
# kalirdi. API_DENEME ile carpildigi icin toplam ust sinir bu degerin uc kati.
MODEL_ZAMAN_ASIMI = 90  # saniye

from limina import kurulum as _kurulum
from limina import POLICY_DOSYASI as _POLICY_DOSYASI
if _POLICY_DOSYASI == PROJE_KOKU / "policy.toml":
    _kurulum.politikayi_hazirla()      # ilk acilis: policy.toml yoksa sablondan uretilir
POLICY_PATH = _POLICY_DOSYASI          # ekip iscisinde LIMINA_POLICY ile uretilmis dar politika
B.politika = Politika(POLICY_PATH)

# Yerleşim kontrolü. Giriş noktası ne olursa olsun (CLI, evals.py, pencere.py)
# içe aktarılırken çalışır: kaynak kod yazma köklerinin içindeyse süreç başlamaz.
# Uyarı basıp devam etmek bir koruma değil — ihlal edildiğinde durur.
_yerlesim_hatasi = B.politika.kod_koku_yazilabilir_mi(PROJE_KOKU)
if _yerlesim_hatasi:
    raise SystemExit(f"\n  YERLESIM HATASI\n  {_yerlesim_hatasi}\n")

B.tarayici = tarayici.Tarayici()

B.kopru = mcp_bridge.Kopru()
# MCP sunuculari IMPORT ANINDA BASLATILMAZ (eskiden baslatiliyordu: modulu
# ice aktaran her sey — testler, saf sohbet, ayarlar paneli — iki alt surec
# aciyordu). mcp_baglan() ilk gorevde (dongu) ya da pencere acilirken arka
# planda cagrilir; idempotent ve kilitli.
_mcp_kilit = threading.Lock()
_mcp_baglandi = False


def mcp_baglan(sessiz: bool = False) -> None:
    """policy.toml [mcp] sunucularini baslatir, araclarini kesfeder, semalari
    tazeler. Bir kez calisir (sonraki cagrilar aninda doner); es zamanli
    cagrilar kilitte bekler — arka planda baslatilmis baglanti bitmeden
    gorev basladiysa gorev onu bekler, yarim listeyle calismaz."""
    global _mcp_baglandi
    with _mcp_kilit:
        # Politikada olup henuz baglanmamis (ve cokmemis) sunucular: ilk cagri
        # hepsini, sonraki cagrilar yalnizca panelden YENI eklenenleri baglar —
        # "yeniden baslatinca baglanir" demek zorunda kalmadan.
        yeni = [(ad, cfg) for ad, cfg in B.politika.mcp.items()
                if ad not in B.kopru._istemciler and ad not in B.kopru.olu]
        if _mcp_baglandi and not yeni:
            return
        for ad, cfg in yeni:
            mesaj = B.kopru.bagla(ad, cfg["komut"])
            if not sessiz:
                print(f"  {mesaj}")
        _mcp_baglandi = True
        arac_semalarini_tazele(sessiz=sessiz)


def mcp_arka_planda_baglan() -> None:
    """Pencere acilirken: kullanici ilk gorevi yazana kadar sunucular hazir olsun."""
    threading.Thread(target=mcp_baglan, kwargs={"sessiz": False}, daemon=True, name="mcp-baglan").start()

# Toplu onaya ASLA girmeyen riskler.
# Toplu onayın KENDİSİ artık modül seviyesinde değil, Oturum içinde (olaylar.py):
# "yeni sohbet toplu onayları sıfırlar" kuralı böylece bedava geliyor.
TOPLU_ONAY_YASAK = {"DESTRUCTIVE"}

# Risk seviyesinden BAĞIMSIZ, ada göre toplu onaydan çıkarılan araçlar.
# write_file de WRITE riskiyle toplu onaya açık ama journal.yedekle() ile
# yedekleniyor ve --geri-al ile dönüyor. converter.convert'in yazdığı dosya
# MCP sunucusu tarafında üretiliyor, journal'a hiç girmiyor — yedeği/geri
# alması yok. Toplu onay bu asimetriyi gizler: "Tümü"ye basan kullanıcı,
# ikinci bir dönüşümün üzerine yazdığını hiç görmez. Bkz. DEVIR.md §10.
TOPLU_ONAY_YASAK_ARAC = {"converter.convert"}


def _toplu_sunulabilir_mi(arac: str, risk: str, yikici: bool) -> bool:
    """Bu araç için "Tümü" düğmesi RENDER EDİLEBİLİR mi? Saf karar.

    Faz 7 Aşama 1: kural eskiden `_onay_gerekli_mi` içinde satır arasındaydı
    ve MCP araçlarını ADA göre dışlıyordu (`TOPLU_ONAY_YASAK_ARAC =
    {"converter.convert"}`). Gerekçesi ise ada değil SINIFA aitti: "MCP
    sunucusu tarafında üretilen dosya journal'a hiç girmiyor, yedeği/geri
    alması yok." Bu, converter.convert'e özgü bir durum değil — BÜTÜN MCP
    yazma araçları için geçerli. Ada bağlı liste, sınıflandırılan her yeni
    MCP yazma aracında sessizce delinirdi: kimsenin listeye eklemeyi
    hatırlaması gerekmesin (mcp_bridge.dis_kaynak'ın "istisna listesi
    TUTULMUYOR" kararıyla aynı gerekçe).

    MCP aracı ayrımı ada bakarak yapılır ("sunucu.arac"): köprü araçları bu
    biçimde kaydeder, yerel araçların adında nokta yoktur.
    """
    if yikici or risk in TOPLU_ONAY_YASAK:
        return False
    if arac in TOPLU_ONAY_YASAK_ARAC:
        return False
    return "." not in arac        # MCP araçları toplu onaya HİÇ girmez

# Fark gösteriminde azami satır (ARAYUZ.md 4.5).
FARK_AZAMI_SATIR = 200

# evals.py çağrılan araçları buradan okur.
# OTOMATIK_ONAY bayrağı KALDIRILDI; eval artık kendi onay sağlayıcısını enjekte ediyor.
CAGRILAN_ARACLAR: list[str] = []

# Faz 7 Asama 3: calistir() tarafından görev başında/sonunda ayarlanır
# (bkz. calistir'in dış sarmalayıcısı) — yalnızca journal.yaz'e "profil: <ad>"
# alanını eklemek için (bkz. _journal_yaz). İzin kararına bu global DEĞİL,
# doğrudan parametre olarak giden `profil` kullanılır (gate.Politika.karar).

# Faz 7 Asama 3: kacinci KENDILIGINDEN devam turundayiz (0 = ilk tetikleme).
# B.aktif_profil ile ayni desen ve ayni try/finally'de temizleniyor; yalnizca
# journal kaydina "devam: N" alanini eklemek icin. Devam KARARI bu globali
# kullanmaz — o gate.devam_karari'ya parametre olarak gidiyor.


ARAC_TABLOSU = kayit.tablo()          # ad -> fonksiyon, kayit defterinden

# Arac semalari SAGLAYICIDAN BAGIMSIZ ({"name","description","parameters"}) ve
# KAYIT DEFTERINDEN: her yerel arac kendi modulunde @arac ile bildirildi
# (limina/araclar/*.py). MCP araclari asagida (arac_semalarini_tazele) eklenir.
B.semalar = kayit.semalar()          # dis erisim vekil_v0.ARAC ozelligi uzerinden (asagida)

# durum_yaz BILEREK ARAC listesine EKLENMEDI ve sistem
# talimatinda hic tanitilmiyor (bkz. sistem_talimati() — burada gecmiyor).
# Yalnizca adim tavanina carpilan o TEK zorlanmis cagrida, _durum_kaydet
# icinde, baska hicbir arac sunulmadan ve ANY modda ZORLANARAK kullanilir
# (bkz. Faz 7 DEVIR_FAZ7.md §5.1.1: adim tavanina carpma bir METIN degil bir
# DURUM olmali). "Varsayilan kapali" ilkesinin bu projedeki bir baska
# uygulamasi: normal arac listesinde olsaydi modelin onu KENDI ISTEGIYLE
# cagirmasina guvenmek gerekirdi (bu oturumda dosya ikamesi davranisi
# gozlemlendi — modele guvenilmez), VE her sıradan cagrinin girdi token'ina
# semasi eklenirdi (aynen siniflandirilmamis MCP araclari gibi, asagi bkz.).
def durum_yaz_araci() -> dict:
    """Tavan aninda modele zorlanan tek arac. Her cagrida kurulur: aciklama
    metinleri dil ayarini izler (t), alan ADLARI (hedef/yapilanlar/...) ise
    sozlesme — _durum_kaydet onlari okuyor, cevrilmez."""
    return dict(
        name="durum_yaz",
        description=t(
            "Görev bir tavana ulaştığı için devam edemiyorsun (adım sayısı ya da "
            "araç çağrısı sayısı sınırı — hangisi olduğunu bilmene gerek yok). Bu "
            "SENİN SON çağrındır — başka hiçbir araç çağıramazsın. Şu ana kadar ne "
            "yapıldığını özetle ki bir sonraki çalıştırma kaldığın yerden devam "
            "edebilsin. Ham geçmişi tekrar etme, KISA ve doğrulanabilir ol. "
            "SADECE GERÇEKTEN çalıştırdığın araçların sonucunu yaptın sayarım — "
            "planladığın ama henüz çalıştırmadığın bir adımı 'yapıldı' deme, "
            "'kalanlar'a yaz."),
        parameters={
            "type": "object",
            "properties": {
                "hedef": {
                    "type": "string",
                    "description": t("Görevin bütünü: kullanıcının istediği son hâl, tek-iki cümle."),
                },
                "yapilanlar": {
                    "type": "array", "items": {"type": "string"},
                    "description": t("Şimdiye kadar TAMAMLANMIŞ işler, doğrulanabilir biçimde "
                                     "(örn. 'z3.txt yazıldı', 'fatura_2.pdf dönüştürüldü')."),
                },
                "kalanlar": {
                    "type": "array", "items": {"type": "string"},
                    "description": t("Kalan işler, yapılacakları SIRAYLA."),
                },
                "engel": {
                    "type": "string",
                    "description": t("Varsa tam olarak neye çarpıldığı (adım tavanı, kapı reddi, "
                                     "araç hatası). Yoksa boş bırakılabilir."),
                },
            },
            "required": ["hedef", "yapilanlar", "kalanlar"],
        },
    )

# MCP araclari yerel araclarla ayni listeye girer — dongu acisindan fark yok.
# AMA yalnizca policy.toml [araclar]'da SINIFLANDIRILMIS olanlar modele
# gosterilir. Siniflandirilmamis araci gostermek iki kez kayip: semasi her
# cagrinin girdi token'ina ekleniyor, ve model cagirdiginda kapi zaten DENY
# donduruyor (bkz. "tanimsiz arac reddedilir" testi). Kapi yine son
# savunma — bu filtre onun yerine gecmiyor, onunden gurultuyu aliyor.
_gizlenen: list[str] = []
try:
    from limina.eklentiler.registry import register as _eklentileri_kaydet, sync_schemas as _eklenti_semalari
except ImportError:
    _eklentileri_kaydet = None
if _eklentileri_kaydet:
    _eklentileri_kaydet(ARAC_TABLOSU, B.semalar, lambda: B.politika)


def arac_semalarini_tazele(sessiz: bool = False) -> list[str]:
    """ARAC'taki MCP bildirimlerini B.kopru.araclar ∩ B.politika.araclar'dan
    YENIDEN kurar; siniflandirilmamis olanlarin listesini doner (_gizlenen).

    Import aninda bir kez cagrilir. Sonra da cagrilabilir: Araclar
    panelinden bir MCP araci siniflandirilinca (ayarlar.arac_siniflandir)
    yeniden baslatmadan modele gorunur olsun diye — pencere._politikayi_
    tazele bunu cagirir. B.semalar nesnesi YERINDE degistirilir (yeni nesne
    degil): _gorev_araclari `is B.semalar` karsilastirmasi yapiyor.
    """
    # Yerel semalar kayit defterinden YENIDEN kurulur (suzulmez): aciklamalar
    # dil ayarini izliyor (kayit.semalar her cagrida cevirir), dil degisince
    # pencere bu fonksiyonu cagirir ve modele giden metin de doner.
    B.semalar[:] = kayit.semalar()
    if _eklentileri_kaydet:
        _eklenti_semalari(B.semalar, B.politika)
    gizlenen: list[str] = []
    for tam_ad, bilgi in B.kopru.araclar.items():
        if tam_ad not in B.politika.araclar:
            gizlenen.append(tam_ad)          # sessizce yutma: asagida bildiriliyor
            continue
        B.semalar.append({"name": tam_ad, "description": bilgi["description"],
                     "parameters": bilgi["schema"]})
    _gizlenen[:] = gizlenen
    if gizlenen and not sessiz:
        print(f"  UYARI: {len(gizlenen)} MCP araci policy.toml [araclar] icinde "
              f"siniflandirilmadigi icin modele gosterilmiyor: {', '.join(sorted(gizlenen))}")
    return gizlenen


arac_semalarini_tazele()

def _gorev_araclari(profil: str | None, kapali: Iterable[str] = (),
                    hepsi_kapali: bool = False) -> list[dict] | None:
    """Bu GOREVDE modele gosterilecek arac listesi. None = HIC ARAC YOK.

    kapali / hepsi_kapali: Araclar panelinin (ve sohbet anahtarinin) sohbet
    basina daraltmasi (olaylar.Oturum.araclari_daralt). Profil daraltmasinin
    USTUNE uygulanir, ayni yonde: yalnizca CIKARIR. Paneldeki bir ad ARAC'ta
    yoksa hicbir etkisi olmaz — panel arac ekleyemez. Sonuc bos kalirsa None:
    sohbet modu, profildeki `araclar = []` ile AYNI yol.

    Kapiya dokunmaz: gate.Politika.karar bu kumeyi hic gormez. Model bir
    sekilde kapali bir araci cagirirsa kapi yine kendi kararini verir. Filtre
    kapinin yerine gecmiyor, onunden gurultuyu aliyor (MCP filtresi gibi).

    GOREV BASINDA hesaplanir, import aninda degil — sistem_talimati() ile
    ayni gerekce: profil gorev basina seciliyor ve modul yuklenirken
    sabitlenirse degisiklik yeniden baslatilana kadar SESSIZCE etkisiz
    kalir.

    Uc durum:
      profil yok / profilde `araclar` alani yok -> B.semalar (hepsi, 21 sema)
      araclar = ["write_file", ...]             -> yalnizca o alt kume
      araclar = []                              -> None (SAF SOHBET)

    "Saf sohbet" icin YENI BIR KAVRAM EKLENMEDI: profil zaten arac
    listesini daraltabiliyordu, bos liste bu yetenegin UC HALI. Ayni desen
    MCP filtresinde de var (siniflandirilmamis arac modele hic gosterilmez)
    — orada da kural "gosterilmeyen arac cagrilamaz" degil, "gosterilmeyen
    arac girdi token'ina hic girmez"di. Kapi yine son savunma: sohbet
    modunda model bir arac uydursa bile ARAC_TABLOSU/B.kopru'de karsiligi yok
    ve zaten cagri uretemez.
    """
    if hepsi_kapali:
        return None              # sohbet modu: HIC arac
    # Yalnizca gercekten gosterilen adlar sayilir: policy'de olmayan bir ad
    # (arayuzden gelebilir) listeyi degistirmez, ARAC'in kendisi doner.
    kapali = frozenset(kapali) & gosterilen_araclar(B.semalar)
    # Politikada SINIFLANDIRILMAMIS yerel arac modele gitmez. Bu, kaldirilan
    # paketlerin (policy.toml [paketler] kaldirilan, gate.Politika) yolu:
    # kapi zaten DENY derdi ama sema gonderip modele "var ama yasak" bir arac
    # gostermek hem token hem yanlis vaat. ARAC'in kendisi import aninda
    # kuruluyor; filtre GOREV BASINDA uygulanir ki panelden kaldirma yeniden
    # baslatma gerektirmesin.
    kapali = kapali | (gosterilen_araclar(B.semalar) - frozenset(B.politika.araclar))
    if profil is None:
        kapsam = None
    else:
        kapsam = B.politika.profiller.get(profil, {}).get("araclar")
        if kapsam is not None and not kapsam:
            return None          # BOS LISTE = saf sohbet
    if kapsam is None and not kapali:
        return B.semalar              # ne profil ne panel daraltiyor
    secilen = [fd for fd in B.semalar
               if (kapsam is None or fd["name"] in kapsam) and fd["name"] not in kapali]
    if not secilen:
        return None              # panel her seyi kapatmis = sohbet modu
    return secilen


def _yikici_yazma_mi(arac: str, args: dict, yol: Path | None) -> bool:
    """İçeriği yok eden write_file fiilen silmedir: toplu onayı atlar, ayrı sorulur."""
    if arac != "write_file":
        return False
    hedef = yol or Path(args.get("path", ""))
    if not hedef.exists():
        return False
    yeni = len(str(args.get("content", "")).encode("utf-8"))
    eski = hedef.stat().st_size
    return yeni == 0 or (eski > 0 and yeni < eski * 0.2)


def _etki_cumlesi(arac: str, args: dict, yol: Path | None) -> str:
    """Onay kartındaki tek cümlelik etki. Araca özgü (ARAYUZ.md 4.4)."""
    hedef = yol or Path(args.get("path", ""))
    if arac == "write_file":
        # Boyut SOYLENMELI: onay kartinin isi kullanicinin neye evet dedigini
        # gostermek. "UZERINE YAZILACAK" tek basina 5933 baytlik bir farki da
        # 12 baytlik bir farki da ayni gosteriyordu (gozlemlendi: kum/README.md
        # onaylandi ve icerik sessizce bozuldu, bkz. ROADMAP Faz 5b).
        yeni_bayt = len(str(args.get("content", "")).encode("utf-8"))
        if not hedef.exists():
            return t("yeni dosya oluşturulacak ({bayt} bayt)", bayt=yeni_bayt)
        try:
            eski_bayt = hedef.stat().st_size
        except OSError:
            return t("ÜZERİNE YAZILACAK ({bayt} bayt, yedek alınır)", bayt=yeni_bayt)
        return t("ÜZERİNE YAZILACAK: {eski} bayt -> {yeni} bayt ({fark:+d}, yedek alınır)",
                 eski=eski_bayt, yeni=yeni_bayt, fark=yeni_bayt - eski_bayt)
    if arac == "edit_file":
        eski_p, yeni_p = str(args.get("old_text", "")), str(args.get("new_text", ""))
        sayi = _edit_eslesme(hedef, eski_p)
        if sayi == 0:
            return t("düzenleme UYGULANMAYACAK: old_text bulunamadı (araç hata döndürecek)")
        if sayi != 1:
            return t("düzenleme UYGULANMAYACAK: old_text {sayi} kez geçiyor (araç hata döndürecek)", sayi=sayi)
        return t("yerinde düzenleme: {eski_satir} satır -> {yeni_satir} satır, "
                 "{eski_kr} -> {yeni_kr} karakter (yedek alınır)",
                 eski_satir=eski_p.count("\n") + 1,
                 yeni_satir=(yeni_p.count("\n") + 1) if yeni_p else 0,
                 eski_kr=len(eski_p), yeni_kr=len(yeni_p))
    if arac == "mkdir":
        return t("yeni klasör oluşturulacak (boşken geri alınabilir)")
    if arac == "open_file":
        # Kullanici NEYE evet diyor: kisayolda gercek hedef + argumanlar,
        # .exe'de CALISTIRILACAK. hedef_cozumle reddedecekse kart onu soyler.
        from limina.araclar import acma as _acma
        if hedef.exists():
            tur, aciklama, hata = _acma.hedef_cozumle(hedef, B.politika)
            return hata if hata else aciklama
        return t("'{ad}' açma klasöründe yok (araç hata döndürecek)", ad=hedef.name)
    if arac == "move":
        return t("dosya KAYNAKTAN KAYBOLACAK -> {hedef}", hedef=args.get("dst", "?"))
    if arac == "rename":
        return t("yeni ad: {ad}", ad=args.get("new_name", "?"))
    if arac == "trash":
        return t("çöp klasörüne taşınacak (kalıcı silinmez, geri alınabilir)")
    if arac == "browser_open":
        return t("açılacak adres: {adres}", adres=args.get("url", "?"))
    if arac == "browser_download":
        return t("dosya internetten inecek ({klasor} klasörüne)", klasor=journal.INEN)
    if arac == "browser_click":
        return t("'{ad}' ögesine tıklanacak", ad=args.get("name", "?"))
    if arac == "browser_fill":
        return t("'{ad}' alanına yazılacak", ad=args.get("name", "?"))
    if arac.startswith("converter."):
        # Kaynak adı SÖYLENMELİ: model istediği dosyayı bulamayınca başkasını
        # ikame edip dönüştürebiliyor (gözlemlendi: ornek.md yerine README.md,
        # ve kullanıcı "dönüştürülecek -> kum" kartına bakıp onaylıyor).
        # Üzerine yazma UYARILMALI: MCP sunucusu journal yedeği almıyor,
        # buradaki üzerine yazmanın geri alınması YOK.
        kaynak = Path(str(args.get("src", "?"))).name
        klasor = str(args.get("dst_dir", "?"))
        bicim = str(args.get("target_format", "")).lstrip(".").lower()
        if not bicim.isalnum():
            return t("{kaynak} dönüştürülecek -> {klasor}", kaynak=kaynak, klasor=klasor)
        cikti = Path(klasor) / f"{Path(str(args.get('src', ''))).stem}.{bicim}"
        if cikti.exists():
            if getattr(B.kopru, "geri_alinabilir", lambda _: False)(arac):
                return t("{kaynak} -> {cikti} ({klasor}) — MEVCUT DOSYA YEDEKLENECEK, geri alınabilir", kaynak=kaynak, cikti=cikti.name, klasor=klasor)
            return t("{kaynak} -> {cikti} ({klasor}) — MEVCUT DOSYANIN ÜSTÜNE YAZILACAK, geri alınamaz",
                     kaynak=kaynak, cikti=cikti.name, klasor=klasor)
        return f"{kaynak} -> {cikti.name} ({klasor})"
    return t("{arac} çalıştırılacak", arac=arac)


def _edit_eslesme(hedef: Path, eski_metin: str) -> int:
    """edit_file: old_text dosyada kac kez geciyor (onay karti icin on izleme)."""
    try:
        return hedef.read_text(encoding="utf-8").count(eski_metin) if eski_metin else 0
    except (OSError, UnicodeDecodeError):
        return 0


def _fark_uret(arac: str, args: dict, yol: Path | None) -> str | None:
    """Üzerine yazmada satır bazlı fark. Onayı anlamlı kılan tek şey (ARAYUZ.md 4.5).

    write_file: tam içerik farkı. edit_file: değişiklik uygulanmış hâlin farkı
    (old_text tek eşleşiyorsa; yoksa fark yok, araç zaten reddedecek).
    Terminalde (f) ile açılır, GUI'de onay kartının içinde render edilir.
    """
    if arac not in ("write_file", "edit_file") or yol is None or not yol.exists() or yol.is_dir():
        return None
    try:
        eski_metin = yol.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    eski = eski_metin.splitlines()

    if arac == "edit_file":
        e, y = str(args.get("old_text", "")), str(args.get("new_text", ""))
        if not e or eski_metin.count(e) != 1:
            return None
        yeni = eski_metin.replace(e, y, 1).splitlines()
    else:
        yeni = str(args.get("content", "")).splitlines()
    satirlar = list(difflib.unified_diff(eski, yeni, t("mevcut"), t("yeni"), lineterm="", n=2))
    if not satirlar:
        return t("(içerik aynı)")
    if len(satirlar) > FARK_AZAMI_SATIR:
        kalan = len(satirlar) - FARK_AZAMI_SATIR
        satirlar = satirlar[:FARK_AZAMI_SATIR] + [t("... [fark kırpıldı, {satir} satır daha var]", satir=kalan)]
    return "\n".join(satirlar)


def _onay_gerekli_mi(oturum: Oturum, arac: str, args: dict,
                     risk: str, yol: Path | None) -> bool:
    """Onay isteğini kurar; kararı olaylar.onay_iste verir.

    "Tümü" sunulabilir mi sorusunun cevabı burada hesaplanır, sağlayıcıda değil —
    DESTRUCTIVE ve yıkıcı yazma kuralı tek yerde kalsın diye.
    """
    yikici = _yikici_yazma_mi(arac, args, yol)
    istek = OnayIstegi(
        arac=arac,
        args=_args_gizle(args),
        risk=risk,
        etki=_etki_cumlesi(arac, args, yol),
        yikici=yikici,
        toplu_sunulabilir=_toplu_sunulabilir_mi(arac, risk, yikici),
        fark=_fark_uret(arac, args, yol),
    )
    if arac in B.kopru.araclar and risk not in {"READ"}:
        from dataclasses import replace
        supported = getattr(B.kopru, "geri_alinabilir", lambda _: False)(arac)
        note = t("Bu aracın dosya çıktıları yedeklenir ve geri alınabilir.") if supported else t("Bu dış aracın işlemleri Limina'nın geri alma kapsamına girmez.")
        istek = replace(istek, etki=istek.etki + " " + note)
    return onay_iste(oturum, istek)


def _tarayici_karesi(oturum: Oturum, arac: str) -> None:
    """browser_* çağrısından sonra ekranın anlık karesini arayüze gönderir.

    Kare MODEL BAĞLAMINA GİRMEZ — yalnızca olay olarak arayüze gider. Playwright
    tek işçi thread'ine bağlı olduğu için kare burada, aracın hemen ardından
    alınmalı; arayüz thread'i kendi başına isteyemez.
    """
    if not arac.startswith("browser_"):
        return
    try:
        durum = B.tarayici.durum()
        if not durum.get("acik"):
            return
        kare = B.tarayici.ekran_goruntusu()
    except Exception:
        return          # görüntü bir kolaylık; alınamaması görevi bozmamalı
    if kare:
        oturum.yayinla(Olay(OlayTipi.TARAYICI, {
            "kare": kare, "url": durum.get("url", ""), "baslik": durum.get("baslik", ""),
        }))


def _olcum_yayinla(oturum: Oturum, yanit, adim: int, toplam_cagri: int, son: bool) -> None:
    """Token sayacı: ARAYUZ.md 6'daki bağlam doluluk barının veri kaynağı."""
    girdi, cikti = int(yanit.girdi_token or 0), int(yanit.cikti_token or 0)
    if not girdi and not cikti:
        return
    print(f"  [adim {adim}{' (son)' if son else ''}: {girdi} girdi + {cikti} cikti token]")
    oturum.yayinla(Olay(OlayTipi.OLCUM, {
        "adim": adim, "girdi_token": girdi, "cikti_token": cikti,
        "toplam_cagri": toplam_cagri, "son": son,
    }))


def _model_cagir(saglayici: modelkat.Saglayici, gecmis: list, model: str, rol: str,
                  arac_listesi: list[dict] | None = None,
                  zorla_arac: str | None = None,
                  istek_sayaci: dict | None = None,
                  araclar_kapali: bool = False,
                  gosterilen: Iterable[str] | None = None,
                  oran_bekle: bool = True,
                  oturum: Oturum | None = None) -> modelkat.Yanit:
    """arac_listesi/zorla_arac verilmezse normal davranis (tum ARAC, serbest
    secim). zorla_arac verilirse SADECE o arac sunulur ve ANY modda zorlanir
    (atlanamaz) — _durum_kaydet'in tek musterisi. Tavan/kota/yeniden deneme
    mantigi ikisi icin de AYNI: zorlanmis cagri da gercek bir istek, sayilmali.

    istek_sayaci verilirse GOREV BASINA gonderilen istek sayisi burada
    birikir (bkz. gate.butce_karari). Sayac journal.kota_artir ile TAM AYNI
    noktada artiyor — ikisi de "bir istek gonderildi" olayini sayiyor ve
    ayri yerlerde artsalardi yeniden deneme dallarindan birinde sessizce
    ayrisirlardi. Her DENEME ayri sayilir: 429/503'te yeniden gonderilen
    istek de gercek bir istektir."""
    for deneme in range(API_DENEME):
        if oturum is not None:
            oturum.kontrol()
        # Duvar sayactan ÖNCE ve her denemede ayrı: her deneme ayrı bir istek
        # ve ayrı sayılıyor, o yüzden ayrı kontrol edilmeli.
        # Karar gate.tavan_karari'nda; burada sadece sayaç okunur, istisna atılır.
        # AÇIK: kota.json yazılamazsa sayaç büyümez ve duvar sessizce çalışmaz.
        # Fail-open bilinçli — disk hatası yüzünden Limina'yı kilitlemek orantısız.
        dolu = tavan_karari(rol, journal.kota_sayaclari(), B.politika.gunluk_tavan)
        if dolu:
            raise TavanDoldu(rol, *dolu)
        journal.kota_artir(rol)
        if istek_sayaci is not None:
            # "istek" = BU TURUN sayaci (butce her devam turunda sifirlanir).
            # "toplam" = gorevin BASINDAN beri, hic sifirlanmaz — donus
            # ozetinin "bu gorevde ne harcandi" satiri buradan geliyor.
            istek_sayaci["istek"] = istek_sayaci.get("istek", 0) + 1
            istek_sayaci["toplam"] = istek_sayaci.get("toplam", 0) + 1
        try:
            # araclar_kapali: None — saglayiciya "arac yok" demenin tek yolu;
            # bos liste bile bir sema parcasi tasir. Saglayici farklari
            # (Gemini nokta kodlamasi, OpenAI tool_calls, Anthropic bloklari)
            # limina.model adaptorlerinde; dongu tek bicim gorur.
            return saglayici.uret(
                model, gecmis,
                sistem_talimati(araclar_var=not araclar_kapali, gosterilen=gosterilen),
                None if araclar_kapali else (arac_listesi if arac_listesi is not None else B.semalar),
                zorla_arac)
        except OranSiniri:
            # 429 = hız limiti. Genelde dakikalık pencere, beklersek geçer.
            # oran_bekle=False: model zincirinde sırada başka model var —
            # beklemek yerine hemen ona geçilir (bkz. _calistir_ic).
            if not oran_bekle or deneme == API_DENEME - 1:
                raise
            bekle = 25 * (deneme + 1)
            print(t("  (hız limiti aşıldı, {sn} sn bekleniyor)", sn=bekle))
            _yeniden_deneme_bekle(oturum, bekle, "429")
        except SunucuHatasi:
            if deneme == API_DENEME - 1:
                raise
            bekle = 5 * (deneme + 1)
            print(t("  (sunucu meşgul, {sn} sn sonra tekrar denenecek)", sn=bekle))
            _yeniden_deneme_bekle(oturum, bekle, "503")
        except ZamanAsimi:
            # MODEL_ZAMAN_ASIMI (90 sn) zaten dolmus demek; ustune uzun bir
            # bekleme eklemiyoruz, kisa bir ara yeterli.
            if deneme == API_DENEME - 1:
                raise
            print(t("  (model {sn} sn içinde yanıt vermedi, tekrar denenecek)", sn=MODEL_ZAMAN_ASIMI))
            _yeniden_deneme_bekle(oturum, 5, "timeout")
    raise AssertionError("_model_cagir: deneme dongusu sonuc vermeden bitti")


def _yeniden_deneme_bekle(oturum: Oturum | None, sn: float, sebep: str) -> None:
    if oturum is None:
        time.sleep(sn)
        return
    oturum.kontrol()
    oturum.yayinla(Olay(OlayTipi.BEKLEME, {"sn": sn, "sebep": sebep}))
    oturum.durdur_bayragi.wait(sn)
    oturum.kontrol()


def _halka_kur(halkalar: list, bas: int, oturum: Oturum | None = None, politika=None):
    """halkalar[bas:] icinde saglayicisi KURULABILEN ilk halka -> (indis, istemci).

    Kurulamayan (anahtari olmayan) halka atlanir ve arayuze soylenir: zincirde
    anahtari girilmemis bir baglanti gorevi durdurmasin. Hicbiri kurulamazsa
    (None, ilk hata) — cagiran eski tek-saglayici mesajini verir."""
    ilk_hata = None
    for i in range(bas, len(halkalar)):
        try:
            return i, modelkat.kur(politika or B.politika, MODEL_ZAMAN_ASIMI, ajan=halkalar[i].ajan())
        except ModelHatasi as e:
            ilk_hata = ilk_hata or e
            if oturum is not None and len(halkalar) > 1:
                oturum.yayinla(Olay(OlayTipi.MODEL_GECIS, {
                    "eski": halkalar[i].etiket, "yeni": "", "sebep": "anahtar", "mesaj": e.mesaj}))
    return None, ilk_hata or ModelHatasi(0, t("Kullanılabilir model yok."))


def tavan_olayi(hata: TavanDoldu, adim: int) -> tuple[dict, str]:
    """TavanDoldu -> (HATA olayinin verisi, gorevin donus metni). Saf fonksiyon.

    'kota': True 429 ile AYNI kanal — arayuz ikisini de "limitin doldu" diye
    gosterir. Fark METINDE durur: bu limit BIZIM ve Ayarlar'dan degistirilebilir.
    O cumle silinirse kullanici bizim duvarimizi Google'in kotasi sanir.
    """
    rol_adi = t("güçlü") if hata.rol == "guclu" else t("hızlı")
    veri = {
        "mesaj": t("Günlük istek tavanına ulaşıldı ({kullanilan}/{tavan}, {model} model). "
                   "Yarın sıfırlanır. Ayarlar > Model'den tavanı yükseltebilirsin.",
                   kullanilan=hata.sayi, tavan=hata.tavan, model=rol_adi),
        "kota": True,
    }
    return veri, t("Günlük istek tavanı ({tavan}) doldu, görev {adim}. adımda kesildi. "
                   "Yapılan işlemler günlükte.", tavan=hata.tavan, adim=adim)


def _durum_kaydet(saglayici: modelkat.Saglayici, gecmis: list, model: str, rol: str,
                   gorev: str, mod_ad: str, adim: int, azami_adim: int,
                   baslangic_zamani: str, sinir_aciklamasi: str,
                   istek_sayaci: dict | None = None,
                   onceki_kimlik: str | None = None,
                   devam_sayisi: int = 0,
                   oturum: Oturum | None = None) -> tuple[str, str | None]:
    """Bir tavana carpildi (gate.durum_karari "durum_yaz" dedi — adim sayisi
    ya da arac cagrisi sayisi, sinir_aciklamasi hangisi oldugunu soyler). TEK
    bir zorlanmis cagriyla modelden ozet alir (durum_yaz DISINDA arac
    sunulmaz, ANY modda zorlanir — atlanamaz), ~/.vekil/durum/'a yazar.

    Model cagrisi herhangi bir sebeple basarisiz olsa bile (kota, ag, bos
    yanit) BIR durum dosyasi yine yazilir — sadece dongunun kendi alanlariyla,
    engel alaninda sebep belirtilerek. calistir'in geri kalanindaki her model
    hatasi zaten temiz bir metne cevriliyor (cagirana istisna sizmiyor); bu
    aynen o desenin devami, sessiz kayip yerine.
    """
    kimlik = uuid.uuid4().hex[:12]
    hedef, yapilanlar, kalanlar, engel = "", [], [], ""
    try:
        # Butceye carpilmis olsa bile bu TEK cagri yapilir: aksi halde
        # butceye carpmak durum dosyasi BIRAKMADAN durmak olurdu, yani tam
        # da butcenin onlemeye calistigi "sessiz yarim kalma". Butce
        # kontrolu dongude, bu cagriyi kapsamiyor — ama cagri yine de
        # sayiliyor (gunluk tavan onu gormeli).
        yanit = _model_cagir(saglayici, gecmis, model, rol,
                              arac_listesi=[durum_yaz_araci()],
                              zorla_arac="durum_yaz", istek_sayaci=istek_sayaci, oturum=oturum)
        cagrilar = yanit.cagrilar or []
        if cagrilar:
            args = dict(cagrilar[0].args)
            hedef = str(args.get("hedef") or "")
            yapilanlar = [str(x) for x in (args.get("yapilanlar") or [])]
            kalanlar = [str(x) for x in (args.get("kalanlar") or [])]
            engel = str(args.get("engel") or "")
        else:
            engel = t("(model durum_yaz çağırmadı, özet alınamadı)")
    except Durduruldu:
        raise
    except Exception as e:
        engel = t("(model özeti alınırken hata: {tur}: {mesaj})", tur=type(e).__name__, mesaj=e)

    yazma_kokleri = [str(k) for k in B.politika.yazma]
    dogrulanan_yazmalar = [
        (f"{k['yol']} -> {k.get('yeni_yol', '?')} ({k.get('islem', 'tasindi')})"
         if k.get("tip") == "tasima" else str(k.get("yol")))
        for k in journal.gorev_kayitlari(baslangic_zamani)
    ]
    hata = _durum_dosyasi_yaz(kimlik, gorev, mod_ad, adim, azami_adim, yazma_kokleri,
                               dogrulanan_yazmalar, hedef, yapilanlar, kalanlar, engel,
                               onceki_kimlik=onceki_kimlik, devam_sayisi=devam_sayisi)
    if hata:
        # Kimlik None doner: dosya yoksa KENDILIGINDEN DEVAM da edilemez
        # (devam eden tarafin okuyacagi bir sey yok). Fail-closed.
        return (t("{sinir} doldu VE ilerleme kaydedilemedi: {hata} "
                  "Yapılan işlemler günlükte, --gecmis ile görülebilir.",
                  sinir=sinir_aciklamasi, hata=hata), None)
    yol = _durum.DURUM_KOK / f"{kimlik}.md"
    return (t("{sinir} doldu, görev tamamlanmadı. İlerleme '{kimlik}' kimliğiyle kaydedildi ({yol}).",
              sinir=sinir_aciklamasi, kimlik=kimlik, yol=yol), kimlik)


def calistir(gorev: str, mod: str | None = None, oturum: Oturum | None = None,
             profil: str | None = None) -> str:
    """Faz 7 Asama 3: profil gorevi TANINMAYAN bir profille CAGIRMAYA HIC
    KALKMAZ — fail-closed, model cagrilmadan reddeder. Taninan bir profil
    calisma boyunca B.aktif_profil'e yazilir (yalnizca journal isaretlemesi
    icin; izin kararina profil zaten burada, dogrudan parametre olarak
    gidiyor, global GEREKMEZ) ve gorev bitince/patlasa bile finally'de
    temizlenir — GUI ayni surecte ardisik gorevler calistirdigi icin bir
    profilin bir sonraki (profilsiz) goreve sizmasi kabul edilemez.
    """
    if profil is not None and profil not in B.politika.profiller:
        gecerli = ", ".join(B.politika.profiller) or t("(tanımlı profil yok)")
        return t("Tanınmayan profil: '{profil}'. Tanımlı profiller: {liste}.", profil=profil, liste=gecerli)
    B.aktif_profil = profil
    B.aktif_devam = 0
    try:
        return _gozetimsiz_surdur(gorev, mod, oturum, profil)
    finally:
        B.aktif_profil = None
        B.aktif_devam = 0


def _mod_coz_gorev(mod: str | None, profil: str | None) -> tuple[dict, str]:
    """(sinir demeti, mod adi). Cagiran ACIKCA bir mod secmediyse profilin
    kendi mod'u kullanilir — cagiran her zaman ustun, profil yalnizca
    varsayilani onerir, dayatmaz.

    Ayri bir fonksiyon oldu cunku IKI yerden cagriliyor: dongunun kendisi
    (_calistir_ic) ve kendiliginden devam surucusu (_gozetimsiz_surdur, kota
    kontrolu icin rolu bilmesi gerekiyor). Iki yerde ayri ayri cozulseydi
    birinde profilin mod'u unutulur ve surucu YANLIS ROLUN kotasina bakardi.
    """
    profil_veri = B.politika.profiller.get(profil) if profil else None
    if mod is None and profil_veri and profil_veri.get("mod"):
        mod = profil_veri["mod"]
    return B.politika.mod_coz(mod), (mod or B.politika.varsayilan_mod)


def _devam_durma_metni(karar: str, devam_sayisi: int, azami_devam: int) -> str:
    """devam_karari'nin dort donusunu kullaniciya okunur tek cumleye cevirir.

    Saf. Gozetimsiz modun butun anlami bu cumlede: kullanici dondugunde
    "neden durdu" sorusunun cevabini ARAMAK zorunda kalmamali.
    """
    if karar == "dur_kota":
        return t("[Kendiliğinden devam DURDU: günlük istek tavanı doldu. Tavan en dış "
                 "sınırdır, hiçbir devam onu aşamaz. Yarın sıfırlanır ya da "
                 "Ayarlar > Model'den yükseltilebilir.]")
    if karar == "dur_sinir":
        if azami_devam == 0:
            return t("[Kendiliğinden devam YAPILMADI: bu profilde azami_devam tanımlı "
                     "değil (0 = kapalı). İlerleme durum dosyasında duruyor, "
                     "'--devam <kimlik>' ile elle sürdürülebilir.]")
        return t("[Kendiliğinden devam DURDU: devam turu üst sınırına ulaşıldı "
                 "({tur}/{azami}). İlerleme durum dosyasında duruyor.]",
                 tur=devam_sayisi, azami=azami_devam)
    if karar == "dur_ilerleme_yok":
        return t("[Kendiliğinden devam DURDU: son iki devam turunda GÜNLÜĞE GEÇEN "
                 "hiçbir yeni yazma olmadı ({tur} tur denendi). Görev aynı "
                 "yerde dönüyor olabilir. Bu karar modelin kendi özetine değil "
                 "journal kayıtlarına bakar.]", tur=devam_sayisi)
    return ""


def _gozetimsiz_surdur(gorev: str, mod: str | None, oturum: Oturum | None,
                        profil: str | None) -> str:
    """Gorevi calistirir; PROFIL ETKINSE bir tavana carpip durum dosyasi
    biraktiginda KENDILIGINDEN devam eder.

    YALNIZCA PROFIL ETKINKEN. Profilsiz etkilesimli yol bugunkuyle BIREBIR
    ayni kalir: durum yazilir, kullaniciya kimlik soylenir, devam kararini
    kullanici verir. Gerekce: profil kullanicinin ONCEDEN KAYDEDILMIS
    onayidir; onay olmadan kendi kendine devam etmek o onayi UYDURMAK olur.

    Her devam turu TAZE baglamla kosar (ayri bir Oturum, gecmis_koru=False):
    durum dosyasi deseninin butun anlami bu — biriken konusma gecmisi
    tasinsaydi tur tur buyuyen bir baglam elde ederdik ve adim tavaninin
    sifirlanmasi hicbir sey kazandirmazdi. Durdurma bayragi PAYLASILIYOR:
    kullanici durdurma dugmesine bastiginda devam zinciri de durmali.

    Faz 7 Asama 5: araci olmayan bir profil (saf sohbet) ne devam eder ne
    ozet birakir — ikisinin de karsiligi yok.

    Faz 7 Asama 4: profilli her calisma sonunda bir DONUS OZETI birakir
    (~/.vekil/ozet/<kimlik>.md, MODEL CAGRISI YOK — bkz. ozet_metni).
    Surucunun BUTUN cikislari _ozet_bitir'den geciyor; ozet "bazen"
    uretilen bir sey olsaydi tam da en cok gereken durumda (beklenmedik bir
    dalda durulunca, kota bitince) eksik olurdu.
    """
    demet, mod_ad = _mod_coz_gorev(mod, profil)
    rol = demet["model"]

    # Donus ozeti (Asama 4) icin kayit. Gorevin BASINDAN itibaren dolar ve
    # devam turlari boyunca TASINIR — ozet butun zinciri anlatmali, yalnizca
    # son turu degil.
    baslangic_zamani = datetime.now()
    istek_sayaci: dict = {"istek": 0, "toplam": 0}
    kayit: dict = {"gorev": gorev, "mod": mod_ad, "profil": profil,
                    "baslangic": baslangic_zamani.isoformat(timespec="seconds"),
                    "kapi_reddi": 0, "durum_zinciri": []}
    _journal_baslangici = datetime.now().isoformat(timespec="microseconds")

    metin, kimlik = _calistir_ic(gorev, mod, oturum, profil,
                                  istek_sayaci=istek_sayaci, kayit=kayit)
    if kimlik:
        kayit["durum_zinciri"].append(kimlik)
    if profil is not None and _gorev_araclari(
            profil, oturum.kapali_araclar() if oturum else (),
            oturum.hepsi_kapali() if oturum else False) is None:
        # SAF SOHBET (araclar = [] ya da panel her seyi kapatmis): ne
        # kendiliginden devam, ne ozet.
        # Ozetin isi "kullanici yokken ne oldu"yu anlatmak; bir sohbet
        # mesajinin cevabi zaten ekranda ve hicbir yan etkisi olamaz
        # (arac yok -> yazma yok -> journal bos). Her sohbet mesaji icin
        # dosya birakmak ~/.vekil/ozet/'i cop haline getirirdi.
        return metin
    if profil is None:
        # PROFILSIZ YOL BIREBIR AYNI: ne kendiliginden devam, ne ozet.
        # Etkilesimli kullanimda sohbet penceresinin KENDISI ozettir;
        # ayrica dosya yazmak gurultu olurdu.
        return metin

    p = B.politika.profiller[profil]
    azami_devam = p.get("azami_devam", 0)

    devam_sayisi = 0
    kisir_tur = 0          # ust uste dogrulanmis yazma URETMEYEN tur sayisi
    devam_oturumu: Oturum | None = None
    durma_notu = ""

    if kimlik is None:
        return _ozet_bitir(metin, kayit, kimlik, devam_sayisi, istek_sayaci,
                            rol, baslangic_zamani, _journal_baslangici, "", oturum)

    while True:
        # Kota HER TURDA taze okunuyor: devam zinciri sirasinda baska bir
        # gorev (GUI'de) da istek harcamis olabilir.
        kota_dolu = tavan_karari(rol, journal.kota_sayaclari(),
                                  B.politika.gunluk_tavan) is not None
        karar = devam_karari(devam_sayisi, azami_devam,
                              yeni_yazma_var_mi=(kisir_tur < 2),
                              kota_dolu_mu=kota_dolu)
        if karar != "devam":
            durma_notu = _devam_durma_metni(karar, devam_sayisi, azami_devam)
            return _ozet_bitir(metin, kayit, kimlik, devam_sayisi, istek_sayaci,
                                rol, baslangic_zamani, _journal_baslangici,
                                durma_notu, oturum)

        veri, hata = _durum_oku(kimlik)
        if hata:
            return _ozet_bitir(metin, kayit, kimlik, devam_sayisi, istek_sayaci,
                                rol, baslangic_zamani, _journal_baslangici,
                                t("[Kendiliğinden devam edilemedi: {hata}]", hata=hata), oturum)
        kok_hatasi = kok_karari(veri.get("yazma_kokleri", []),
                                 [str(k) for k in B.politika.yazma])
        if kok_hatasi:
            return _ozet_bitir(metin, kayit, kimlik, devam_sayisi, istek_sayaci,
                                rol, baslangic_zamani, _journal_baslangici,
                                t("[Kendiliğinden devam edilemedi: {hata}]", hata=kok_hatasi),
                                oturum)

        if devam_oturumu is None:
            devam_oturumu = Oturum(
                onay_saglayici=(oturum.onay_saglayici if oturum else terminal_onayi),
                yayinla=(oturum.yayinla if oturum else _sessiz_yayin),
                durdur_bayragi=(oturum.durdur_bayragi if oturum
                                 else threading.Event()),
                gecmis_koru=False,
            )

        devam_sayisi += 1
        B.aktif_devam = devam_sayisi
        # Bu TURUN yazmalarini olcmek icin: journal.gorev_kayitlari bu
        # zamandan SONRAKI kayitlara bakacak. Model ozeti KULLANILMIYOR.
        tur_baslangici = datetime.now().isoformat(timespec="microseconds")
        yeni_gorev = _devam_gorevi_kur(veri, kimlik)
        print(f"  [kendiliginden devam {devam_sayisi}/{azami_devam}, kimlik {kimlik}]")

        metin, yeni_kimlik = _calistir_ic(yeni_gorev, mod or veri.get("mod"),
                                           devam_oturumu, profil,
                                           onceki_kimlik=kimlik,
                                           devam_sayisi=devam_sayisi,
                                           istek_sayaci=istek_sayaci, kayit=kayit)

        yazma_oldu = bool(journal.gorev_kayitlari(tur_baslangici))
        kisir_tur = 0 if yazma_oldu else kisir_tur + 1

        if yeni_kimlik:
            kayit["durum_zinciri"].append(yeni_kimlik)

        if yeni_kimlik is None:
            # kayit["engel"] BURADA SET EDILMIYOR: _ozet_bitir durma_notu'nu
            # zaten engel'e ekliyor, ikisini birden yazmak ayni cumleyi iki
            # kez bastiriyordu (canli kosuda gorundu).
            return _ozet_bitir(metin, kayit, None, devam_sayisi, istek_sayaci,
                                rol, baslangic_zamani, _journal_baslangici,
                                t("[Görev {tur} kendiliğinden devam turunda tamamlandı.]",
                                  tur=devam_sayisi), oturum)
        kimlik = yeni_kimlik


def _ozet_bitir(metin: str, kayit: dict, kimlik: str | None, devam_sayisi: int,
                 istek_sayaci: dict, rol: str, baslangic, journal_baslangici: str,
                 durma_notu: str, oturum: Oturum | None) -> str:
    """Kaydi tamamlar, ozeti yazar, olayi yayinlar, donus metnini kurar.

    Surucunun BUTUN cikislari buradan geciyor — ozet "bazen" uretilen bir
    sey olsaydi tam da en cok gereken durumda (beklenmedik bir dalda
    durulunca) eksik olurdu.
    """
    kayit["bitis"] = datetime.now().isoformat(timespec="seconds")
    kayit["sure_sn"] = (datetime.now() - baslangic).total_seconds()
    kayit["devam_sayisi"] = devam_sayisi
    kayit["istek"] = istek_sayaci.get("toplam", 0)
    kayit["durum_kimligi"] = kimlik
    # Kota MODEL CAGIRMADAN okunuyor: journal.kota_sayaclari diskteki
    # sayaci okur, gate.Politika tavanlari tasir.
    sayaclar = journal.kota_sayaclari()
    kayit["kota"] = {r: (sayaclar.get(r, 0), B.politika.gunluk_tavan.get(r, 0))
                      for r in (rol,)}
    # GUVENILIR yazmalar: modelin iddiasi DEGIL, journal kaydi.
    kayit["yazmalar"] = [
        (f"{k['yol']} -> {k.get('yeni_yol', '?')} ({k.get('islem', 'tasindi')})"
         if k.get("tip") == "tasima" else str(k.get("yol")))
        + (f"  [devam {k['devam']}]" if k.get("devam") else "")
        for k in journal.gorev_kayitlari(journal_baslangici)
    ]
    # Modelin "kalanlar" iddiasi SON durum dosyasindan. Okunamazsa ozet
    # yine uretilir — bu alan bir kolaylik, ozetin sarti degil.
    if kimlik:
        kayit["kalanlar"] = _durum_kalanlar(kimlik)
    # SONUC: gorevin nasil bittigi. Carpilan sinirlar AYRI bir liste
    # (kayit["engeller"]) — "yolda neye carptik" ile "sonunda ne oldu"
    # farkli sorular ve ayni cumlede birlestirilince celisiyorlardi.
    # Yalnizca durma_notu varsa SONUC'u burada belirliyoruz; yoksa bos
    # birakiliyor ve ozet_metni (saf) durustce turetiyor.
    if durma_notu:
        kayit["sonuc"] = durma_notu.strip("[]")

    kayit["kimlik"] = kimlik or f"ozet-{uuid.uuid4().hex[:12]}"
    yol, hata = _ozet_yaz(kayit)
    if oturum is not None and yol:
        oturum.yayinla(Olay(OlayTipi.OZET, {
            "kimlik": kayit["kimlik"], "yol": yol, "metin": ozet_metni(kayit),
        }))
    kuyruk = durma_notu
    if yol:
        kuyruk += "\n\n" + t("[Görev özeti: {ozet}]", ozet=yol)
    elif hata:
        kuyruk += f"\n\n[{hata}]"
    return metin + ("\n\n" + kuyruk.strip() if kuyruk.strip() else "")


def _sessiz_yayin(olay) -> None:
    """Oturum verilmemisse (CLI) devam turlarinin yayincisi."""


def _calistir_ic(gorev: str, mod: str | None, oturum: Oturum | None,
                  profil: str | None, onceki_kimlik: str | None = None,
                  devam_sayisi: int = 0,
                  istek_sayaci: dict | None = None,
                  kayit: dict | None = None) -> tuple[str, str | None]:
    # Oturum verilmezse CLI davranışı: terminal onayı, olay yayını yok.
    # GUI kendi oturumunu verir (gui_kopru.py), evals.py sabit cevaplı olanı.
    oturum = oturum or terminal_oturumu()
    # Profilin KENDI mod'u var ve cagiran ACIKCA bir mod SECMEDIYSE, profilin
    # mod'u kullanilir — cagiran her zaman ustun (profil yalnizca varsayilani
    # oneriyor, dayatmiyor).
    profil_veri = B.politika.profiller.get(profil) if profil else None
    # Mod GOREV BASINDA cozulur, modul yuklenirken degil: ayarlardan
    # degisince yeniden baslatma gerekmez. Gorevin ortasinda degismesin
    # diye de bir kez cozulup yerelde tutuluyor (adim/cagri tavanlari dahil).
    # Cozum _mod_coz_gorev'de: surucu de ayni cozumu kullaniyor (bkz. orasi).
    demet, mod_ad = _mod_coz_gorev(mod, profil)
    rol = demet["model"]              # "varsayilan" | "guclu" — gunluk KOTA bu rolle sayilir
    # Model ZINCIRI (limina/model_zinciri.py): kullanicinin API baglantilari
    # sirasiyla; limiti dolan model bir sure atlanir, musait olanlar onde.
    # Mod MODEL SECMEZ: modeli kullanici sohbet ekranindan secer (oturum.
    # secili_model), secilen basa alinir. [baglantilar] yoksa eski [model]
    # ayarinin iki modeli. Ekip iscisi: ajanin baglantisi, sonra genel zincir.
    halkalar = model_zinciri.sirala(model_zinciri.zincir(
        B.politika, rol, ajan=B.ajan, ajan_adi=B.ajan_adi or "",
        secili="" if B.ajan else getattr(oturum, "secili_model", "")))
    # Saglayici GOREV BASINDA kurulur: Ayarlar > Model'den saglayici/anahtar
    # degisince yeniden baslatma gerekmez. Anahtari olmayan halka atlanir
    # (arayuze soylenir); hicbiri kurulamazsa gorev model cagirmadan, acik bir
    # mesajla biter (istisna sizmaz).
    sira_i, client = _halka_kur(halkalar, 0, oturum)
    if sira_i is None:
        e = client
        mesaj = t("Model sağlayıcısı kurulamadı: {hata}", hata=e.mesaj)
        if kayit is not None:
            kayit.setdefault("engeller", []).append((devam_sayisi, mesaj))
        oturum.yayinla(Olay(OlayTipi.HATA, {"mesaj": mesaj, "anahtar": e.code == 401}))
        return mesaj, None
    halka = halkalar[sira_i]
    model = halka.model
    print(f"  mod: {mod_ad}, model: {halka.etiket}" + (f", profil: {profil}" if profil else "")
          + (f", ajan: {B.ajan_adi}" if B.ajan_adi else "")
          + (f", zincir: {len(halkalar)} model" if len(halkalar) > 1 else ""))
    # Sohbet geçmişi: oturum koruyorsa önceki görevler bağlamda kalır
    # ("şimdi de onları PDF'e çevir" diyebilmek için). Kapalıysa her görev bağımsız.
    if oturum.gecmis_koru:
        oturum.gorev_basladi()
        gecmis = oturum.gecmis_al()      # canlı liste; append doğrudan oturuma yazar
    else:
        gecmis = []
    gecmis.append(kullanici_mesaji(gorev))
    toplam_cagri = 0
    # journal.gorev_kayitlari icin: bu GOREVDEN once yazilan hicbir kayit
    # "dogrulanan_yazmalar"a KARISMASIN diye baslangic zamanini journal.yaz'in
    # urettigi BICIMLE (mikrosaniye) aliyoruz — string karsilastirmasi
    # kronolojik siralamayla ayni sonucu verir.
    _baslangic_zamani = datetime.now().isoformat(timespec="microseconds")

    azami_adim = demet["adim"]
    azami_cagri = demet["cagri"]
    # Gorev basina istek butcesi. Sayac calistir'e YEREL: her gorev kendi
    # butcesiyle baslar, devam_et TAZE bir calistir cagrisi oldugu icin
    # butce orada da sifirlanir (bkz. gate.butce_karari docstring'i).
    # Arac listesi GOREV BASINDA cozulur (import aninda degil, bkz.
    # _gorev_araclari). None = saf sohbet: modele hicbir arac semasi gitmez.
    # Sohbet basina daraltma (Araclar paneli / sohbet anahtari) da burada,
    # profil daraltmasiyla AYNI fonksiyondan gecer.
    mcp_baglan(sessiz=True)           # ilk gorevde (ya da arka plan bitene kadar bekle)
    gorev_araclari = _gorev_araclari(profil, oturum.kapali_araclar(), oturum.hepsi_kapali())
    araclar_kapali = gorev_araclari is None
    # Kismi daraltmada persona bolumleri gosterilen listeye gore suzulur;
    # tam listede None (dokunulmaz) — sistem_talimati'nin eski yolu.
    gosterilen = None if gorev_araclari is B.semalar else gosterilen_araclar(gorev_araclari)
    if araclar_kapali:
        print("  arac listesi: BOS (saf sohbet) — kapi bu turda hic cagrilmayacak")
    elif gorev_araclari is not B.semalar:
        kim = f"profil '{profil}'" if profil else "araclar paneli"
        print(f"  arac listesi: {len(gorev_araclari)} arac ({kim} daraltti)")

    azami_istek = demet["istek"]
    # Sayac SURUCUDEN gelebilir (kendiliginden devam zinciri boyunca
    # "toplam" birikir). "istek" her turda SIFIRLANIR: butce gorev
    # basina, devam turu basina degil (bkz. gate.butce_karari).
    if istek_sayaci is None:
        istek_sayaci = {}
    istek_sayaci["istek"] = 0
    # Profilin KENDI azami_adim'i, mod'un adim tavanini SIKILASTIRABILIR —
    # gozetimsiz calistirmalar icin bilinerek daha dar bir tavan istenebilir.
    # Yalnizca DAHA SIKI yonde: profil hicbir sekilde mod'un tavanindan
    # GENIS bir tavan VEREMEZ, "min" ile garanti ediliyor.
    if profil_veri and profil_veri.get("azami_adim"):
        azami_adim = min(azami_adim, profil_veri["azami_adim"])

    for adim in range(1, azami_adim + 1):
        oturum.kontrol()        # durdurma noktası 1: yeni tur başlamadan
        oturum.yayinla(Olay(OlayTipi.ADIM_BASLADI, {"adim": adim, "azami": azami_adim}))
        # Ekip iscisi: pano mesajlari HER turdan once teslim edilir (kullanici
        # mesaji olarak, <untrusted_content> icinde). Pano yoksa None, hicbir
        # sey eklenmez. Ilk turda gorev metniyle birlesmesin diye adim > 1'de
        # ayri mesaj; adim 1'de goreve eklenir (ardisik iki kullanici mesaji
        # bazi saglayicilarda reddediliyor — ardisik_birlestir bunu cozer).
        if B.ekip_pano:
            from limina.araclar.ekip_pano import tur_notu
            notu = tur_notu()
            if notu:
                gecmis.append(kullanici_mesaji(notu))
                gecmis[:] = ardisik_birlestir(gecmis)
                oturum.yayinla(Olay(OlayTipi.EKIP_MESAJ, {"ajan": B.ajan_adi, "teslim": True,
                                                          "metin": notu[:2000]}))
        try:
            while True:
                try:
                    yanit = _model_cagir(client, gecmis, model, rol,
                                          arac_listesi=gorev_araclari,
                                          istek_sayaci=istek_sayaci,
                                          araclar_kapali=araclar_kapali,
                                          gosterilen=gosterilen,
                                          oran_bekle=sira_i == len(halkalar) - 1,
                                          oturum=oturum)
                    break
                except ModelHatasi as e:
                    # Kullanim doldu: halkayi isaretle, siradakine gec, AYNI
                    # adimi yeniden dene (basarisiz istek gecmise hic girmedi).
                    # Anahtar/model adi hatasi gecis sebebi DEGIL: ayar hatasi,
                    # sessizce atlanmaz — asagidaki genel isleyiciye gider.
                    if isinstance(e, ZamanAsimi) or not model_zinciri.kota_hatasi_mi(e):
                        raise
                    bitis = model_zinciri.dolu_isaretle(halka, e)
                    yeni_i, yeni = _halka_kur(halkalar, sira_i + 1, oturum)
                    if yeni_i is None:
                        raise
                    eski = halka
                    sira_i, client = yeni_i, yeni
                    halka = halkalar[sira_i]
                    model = halka.model
                    print(t("  ({eski} limiti doldu, {yeni} ile devam ediliyor)",
                            eski=eski.etiket, yeni=halka.etiket))
                    oturum.yayinla(Olay(OlayTipi.MODEL_GECIS, {
                        "eski": eski.etiket, "yeni": halka.etiket, "sebep": "limit",
                        "bitis": bitis.isoformat(timespec="minutes")}))
        except TavanDoldu as e:
            veri, metin = tavan_olayi(e, adim)
            if kayit is not None:
                kayit.setdefault("engeller", []).append(
                    (devam_sayisi, t("Günlük istek tavanı doldu ({model}: {kullanilan}/{tavan}), "
                                     "{adim}. adımda kesildi",
                                     model=e.rol, kullanilan=e.sayi, tavan=e.tavan, adim=adim)))
            oturum.yayinla(Olay(OlayTipi.HATA, veri))
            return metin, None
        except ZamanAsimi:
            # Deneme (API_DENEME kez) burada zaten tuketildi.
            mesaj = t("Modelle bağlantı {sn} sn içinde kurulamadı ({deneme} deneme sonunda). "
                      "Ağ bağlantını kontrol et ve tekrar dene.",
                      sn=MODEL_ZAMAN_ASIMI, deneme=API_DENEME)
            if kayit is not None:
                kayit.setdefault("engeller", []).append((devam_sayisi, mesaj))
            oturum.yayinla(Olay(OlayTipi.HATA, {"mesaj": mesaj}))
            return mesaj + t("\n{sayi} araç çağrısı yapılmıştı.", sayi=toplam_cagri), None
        except ModelHatasi as e:
            # Kota/oran sınırı ayrı bir olay olarak bildirilir: arayüz bunu
            # teknik hata gibi değil, "limitin doldu" diye gösterir. Sürekli
            # bir sayaç göstermek yerine sınıra çarpınca söylemek daha dürüst —
            # yerel sayaç zaten gerçek kotayı bilmiyordu.
            kota_doldu = model_zinciri.kota_hatasi_mi(e) and not isinstance(e, ZamanAsimi)
            if kota_doldu:
                model_zinciri.dolu_isaretle(halka, e)     # tek halkada da: Ayarlar'da gorunsun
            oturum.yayinla(Olay(OlayTipi.HATA, {
                "mesaj": f"{e.code}: {e.mesaj}",
                "kota": kota_doldu,
                "zincir": len(halkalar) > 1,
                "anahtar": e.code in (401, 403),
                "model": halka.etiket,
            }))
            if kayit is not None:
                kayit.setdefault("engeller", []).append(
                    (devam_sayisi, t("Model çağrısı başarısız ({tur}): {mesaj}",
                                     tur=e.code, mesaj=e.mesaj)))
            if kota_doldu and len(halkalar) > 1:
                return t("Sıradaki bütün modellerin kullanım limiti doldu. Daha sonra tekrar dene "
                         "ya da Ayarlar > Model'den yeni bir API ekle."), None
            if kota_doldu:
                return t("Bu modelin günlük/dakikalık isteği doldu. Biraz sonra tekrar dene, "
                         "ya da diğer modele geç."), None
            return (t("Model çağrısı başarısız ({tur}): {mesaj}", tur=e.code, mesaj=e.mesaj)
                    + t("\n{sayi} araç çağrısı yapılmıştı.", sayi=toplam_cagri)), None

        cagrilar = yanit.cagrilar
        if not cagrilar:
            _olcum_yayinla(oturum, yanit, adim, toplam_cagri, son=True)
            metin = yanit.metin or t("(model boş yanıt verdi)")
            # Nihai yanıt da geçmişe girer, yoksa sonraki görev ne dediğini bilmez.
            if oturum.gecmis_koru:
                gecmis.append(yanit.icerik)
            oturum.yayinla(Olay(OlayTipi.YANIT_PARCASI, {"metin": metin}))
            # kimlik None: gorev BITTI, surdurulecek bir durum yok.
            return metin, None

        _olcum_yayinla(oturum, yanit, adim, toplam_cagri, son=False)
        gecmis.append(yanit.icerik)
        sonuc_parcalari: list[tuple[str, str | None, str]] = []   # (ad, cagri id, metin)
        tur_sayaci: dict[str, int] = {}

        for c in cagrilar:
            oturum.kontrol()    # durdurma noktası 2: yeni araç çağrısı başlamadan
            toplam_cagri += 1
            if toplam_cagri > azami_cagri:
                # ESKIDEN burada dogrudan return edilirdi — gozetimsiz modda
                # sessizce olen IKINCI bir yoldu (bkz. durum_karari'nin
                # docstring'i, "IKI AYRI CIKIS NOKTASI"). Artik SINIR
                # asilan cagriya da (tur_karari'nin SINIR dalindaki gibi) bir
                # yanit veriyoruz ve dongu asagida durum_karari'ya birlikte
                # bagliyor — gecmis'i yarim birakip donmuyoruz.
                metin = t("Çağrı limiti ({limit}) doldu, bu istek işlenmedi. "
                          "Kalan işi ayrı bir görev olarak iste.", limit=azami_cagri)
                sonuc_parcalari.append((c.ad, c.id, metin))
                continue

            args = dict(c.args)
            gercek_ad = c.ad
            # Konsol ve olay akisi AYNI maskelenmis kopyayi gorur; araca giden
            # `args` maskelenmez (kapi gercek degeri denetlemeli).
            gizli_args = _args_gizle(args)
            ozet = {k: (v if len(str(v)) <= 60 else str(v)[:60] + "...")
                    for k, v in gizli_args.items()}
            print(t("  adım {adim}: {arac} ({karar})",
                    adim=f"{adim}.{toplam_cagri}", arac=gercek_ad, karar=ozet))

            # === Kapı. Araca giden tek yol burası. ===
            # Site profilleri icin kapinin AKTIF ADRESI bilmesi gerekiyor:
            # browser_click/fill/download argumanlarinda adres tasimiyor.
            # Adres her cagrida tarayicidan taze okunuyor — kapida durum
            # tutulsaydi kullanici sekmeyi elle degistirdiginde kapi eski
            # siteyi zanneder ve yanlis profili uygulardi.
            aktif_url = ""
            if gercek_ad.startswith("browser_") and gercek_ad != "browser_open":
                try:
                    aktif_url = str(B.tarayici.durum().get("url", "") or "")
                except Exception:
                    aktif_url = ""      # okunamazsa varsayilan profil uygulanir
            karar = B.politika.karar(gercek_ad, args, aktif_url, profil)
            risk = B.politika.araclar.get(gercek_ad, "?")
            CAGRILAN_ARACLAR.append(gercek_ad)
            # masa: ekip ofisinde ajanin yurudugu yer (yalnizca gosterim, ofis.py)
            oturum.yayinla(Olay(OlayTipi.ARAC_CAGRILDI, ofis.masa_ekle({
                "arac": gercek_ad, "args": gizli_args, "risk": risk,
                "karar": karar.sonuc, "adim": adim, "sira": toplam_cagri,
            })))
            baslangic = time.monotonic()   # DENY/SINIR dallari icin: ~0

            tur_sayaci[risk] = tur_sayaci.get(risk, 0) + 1
            asildi = tur_karari(risk, tur_sayaci, TUR_TAVANI)
            if asildi:
                _, tavan = asildi
                metin = (f"Bu turda {risk} riskli {tavan} islem sinirina ulasildi. "
                         f"Kalan isleri bir sonraki adimda iste; kullanici her partiyi ayri gorur.")
                sonuc_parcalari.append((c.ad, c.id, metin))
                print(f"          [SINIR] {metin[:70]}...")
                oturum.yayinla(Olay(OlayTipi.ARAC_SONUCU, {
                    "arac": gercek_ad, "sonuc": metin, "karar": "SINIR",
                    "sure_sn": round(time.monotonic() - baslangic, 2),
                }))
                continue

            basarili = False
            if karar.sonuc == DENY:
                metin = t("İzin reddedildi: {gerekce}", gerekce=karar.gerekce)
                if kayit is not None:
                    kayit["kapi_reddi"] = kayit.get("kapi_reddi", 0) + 1
            elif karar.sonuc == ASK and not _onay_gerekli_mi(
                    oturum, gercek_ad, args, risk, karar.yol):
                metin = t("Kullanıcı bu işlemi reddetti. Alternatif bir yol dene ya da dur.")
                # Arac calismadi; sayac sifirlanir. OLCULDU: bu sifirlama yokken
                # reddedilen bir write_file'in sure_sn'i 31.32 cikti — kullanicinin
                # onay kartina bakma suresi araca yazilmisti (asagidaki "onay
                # alinmis" dali sifirliyordu, red dali sifirlamiyordu).
                baslangic = time.monotonic()
                if kayit is not None:
                    kayit["kapi_reddi"] = kayit.get("kapi_reddi", 0) + 1
            else:
                # Onay (varsa) burada alinmis oldu. Sure sayaci buradan baslar;
                # kullanicinin onay ekranina bakma suresi araca yazilmaz.
                baslangic = time.monotonic()
                fn = ARAC_TABLOSU.get(gercek_ad)
                if fn is None and gercek_ad in B.kopru.araclar:
                    metin = B.kopru.cagir(gercek_ad, args)
                elif fn is None:
                    metin = sonuc_hatasi(t("Bilinmeyen araç: {arac}", arac=gercek_ad))
                else:
                    try:
                        metin = fn(karar.yol, args)
                    except Exception as e:      # istisna dışarı sızmaz, metne döner
                        metin = sonuc_hatasi(t("{arac} çalışırken hata: {tur}: {mesaj}",
                                  arac=gercek_ad, tur=type(e).__name__, mesaj=e))
                basarili = getattr(metin, "basarili", True)

            print(f"          [{karar.sonuc}] -> {metin.splitlines()[0][:75]}...")
            oturum.yayinla(Olay(OlayTipi.ARAC_SONUCU, {
                "arac": gercek_ad, "sonuc": metin, "karar": karar.sonuc,
                "basarili": basarili,
                "sure_sn": round(time.monotonic() - baslangic, 2),
            }))
            _tarayici_karesi(oturum, gercek_ad)
            sonuc_parcalari.append((c.ad, c.id, metin))

        gecmis.append(sonuc_mesaji(sonuc_parcalari))

        # gate.durum_karari: bu turda cagri geldiyse (cagrilar bos degildi,
        # yoksa "if not cagrilar" dalindan zaten donulurdu) model_bitirdi_mi
        # HER ZAMAN False. IKI AYRI SINIR aynı karara bagliyor: adim ==
        # azami_adim (SON izinli tur) VE toplam_cagri > azami_cagri (bu
        # turda cagri tavanina carpildi mi, yukarideki dongude SINIR yanitiyla
        # devam edilmisti, burda gercekten asilip asilmadigina bakiyoruz).
        # Eski "dongu tukendi" kuyruk kodu KALDIRILDI, artik erisilemezdi.
        cagri_asildi = toplam_cagri > azami_cagri
        # Butce ucuncu bir CIKIS YOLU degil, ucuncu bir PARAMETRE.
        butce_doldu = butce_karari(istek_sayaci["istek"], azami_istek)
        karar = durum_karari(adim, azami_adim,
                              cagri_tavaninda_mi=cagri_asildi,
                              butce_doldu_mu=butce_doldu is not None,
                              model_bitirdi_mi=False)
        if karar == "durum_yaz":
            if cagri_asildi:
                sinir_aciklamasi = t("Çağrı limiti ({limit})", limit=azami_cagri)
            elif butce_doldu:
                sinir_aciklamasi = t("Görev istek bütçesi ({limit}, '{mod}' modu)",
                                     limit=butce_doldu[1], mod=mod_ad)
            else:
                sinir_aciklamasi = t("Adım limiti ({limit})", limit=azami_adim)
            if kayit is not None:
                kayit.setdefault("engeller", []).append(
                    (devam_sayisi, f"{sinir_aciklamasi} doldu"))
            oturum.yayinla(Olay(OlayTipi.HATA, {
                "mesaj": t("{sinir} doldu, ilerleme kaydediliyor. Kalan işi ayrı bir görev "
                           "olarak iste ya da Ayarlar > Model'den ilgili limiti yükselt.",
                           sinir=sinir_aciklamasi),
                "kota": True,       # turuncu kart: teknik hata degil, ayarlanabilir sinir
            }))
            return _durum_kaydet(client, gecmis, model, rol, gorev, mod_ad, adim, azami_adim,
                                  _baslangic_zamani, sinir_aciklamasi,
                                  istek_sayaci=istek_sayaci,
                                  onceki_kimlik=onceki_kimlik,
                                  devam_sayisi=devam_sayisi, oturum=oturum)

    raise AssertionError(
        "calistir: for donguu adim tavanina carpmadan tukendi — durum_karari'nin "
        "range(1, azami_adim+1) ile senkron olmadigini gosterir, kod hatasi.")


# --- Faz 7 Asama 2: durum dosyasindan DEVAM. ------------------------------
# Taze baglamla baslar (eski konusma gecmisi YUKLENMEZ — olcumun curuttugu
# seyin aynisi olurdu, bkz. DEVIR_FAZ7.md §4). devam_et yeni bir calistir()
# cagrisidir, gorev metni durum dosyasindan kurulur.

def devam_et(kimlik: str, mod: str | None = None, oturum: Oturum | None = None,
             profil: str | None = None) -> str:
    """Faz 7 Asama 2: kimlik'i olan durum dosyasindan TAZE bir gorev baslatir.

    "Taze": eski konusma gecmisi (gecmis listesi) YUKLENMEZ, calistir() sifirdan
    baslar — ölçümün doğruladığı şey tam bu (DEVIR_FAZ7.md §4/§8): N adimlik
    tek bir uzun sohbetin maliyeti N^2 ile buyuyor, kisa-ve-taze koşular
    dogrusal kaliyor.

    mod verilmezse durum dosyasindaki mod tekrar kullanilir (ayni sinirlarla
    devam etmek varsayilan davranis).

    profil verilirse (elle: `--devam <kimlik> --profil <ad>`) bu cagri da
    kendiliginden devam surucusune girer — yani bir kez elle tetiklenen bir
    devam, profilin azami_devam'i kadar KENDI KENDINE surebilir. Profil
    verilmezse davranis bugunkuyle ayni: tek tur, sonra durur.
    """
    veri, hata = _durum_oku(kimlik)
    if hata:
        return hata

    kok_hatasi = kok_karari(veri.get("yazma_kokleri", []), [str(k) for k in B.politika.yazma])
    if kok_hatasi:
        return kok_hatasi

    gorev = _devam_gorevi_kur(veri, kimlik)
    return calistir(gorev, mod=mod or veri.get("mod"), oturum=oturum, profil=profil)


def main() -> None:
    """CLI giris noktasi (pyproject: limina-cli); govde limina.cli'de."""
    from limina.cli import main as _main
    _main()


# --- Geriye donuk uyumluluk: vekil_v0.POLITIKA / TARAYICI / KOPRU / AKTIF_* ------
# Tekiller limina.baglam.B'de (araclar da oradan okuyor). Bu adlarla okumak ve
# YAZMAK (pencere._politikayi_tazele, testler) B'ye gider; modul sinifi
# degistirilerek ozellik yapildi — bare-name kullanim icindeki kod zaten B.* okur.
import sys as _sys
import types as _types


def _bagli(alan: str):
    """B.<alan>'a bagli modul ozelligi. Deleter no-op: unittest.mock.patch.object
    geri alirken delattr dener, ozellik silinemez ama hata da vermemeli."""
    return property(lambda self: getattr(B, alan), lambda self, v: setattr(B, alan, v), lambda self: None)


def _modulden(modul, alan: str):
    return property(lambda self: getattr(modul, alan), lambda self, v: setattr(modul, alan, v), lambda self: None)


class _VekilModulu(_types.ModuleType):
    # Bolunen modullerdeki ayarlanabilir sabitler: vekil_v0.DURUM_KOK = ... yazan
    # testler ve eski cagiranlar dogru modulu degistirsin.
    DURUM_KOK = _modulden(_durum, "DURUM_KOK")
    OZET_KOK = _modulden(_durum, "OZET_KOK")
    PERSONA_YOL = _modulden(_talimat, "PERSONA_YOL")
    ARAC = _bagli("semalar")
    POLITIKA = _bagli("politika")
    TARAYICI = _bagli("tarayici")
    KOPRU = _bagli("kopru")
    AKTIF_PROFIL = _bagli("aktif_profil")
    AKTIF_DEVAM = _bagli("aktif_devam")


_sys.modules[__name__].__class__ = _VekilModulu


if __name__ == "__main__":
    main()
