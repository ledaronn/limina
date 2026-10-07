# gate.py — izin kapısı. Yürütücüye giden TEK yol burasıdır.
from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from pevrai.ceviri import t

ALLOW, ASK, DENY = "ALLOW", "ASK", "DENY"

# Risk seviyesi -> varsayılan karar. Politika bunu sıkılaştırabilir, gevşetemez.
#
# Gevşetme, seviye ATAMASI ile yapılır: bir araç daha düşük bir seviyeye
# taşınırsa onaysız çalışır. Bu bilinçli — karar policy.toml'da görünür bir
# satır olarak durur, kodun içinde gizli bir istisna olarak değil.
#
# WRITE_HAFIF neden ALLOW: geri alınabilir, içerik yok etmez, günlüğe yazılır.
# Her adımda onay istemek güvenlik eklemiyordu, sadece kullanıcıyı yoruyordu —
# yorulan kullanıcı da okumadan onaylıyor (gözlemlendi: kum/README.md, 5933
# baytlık bir fark "onayla"ya basılarak geçti ve içerik sessizce bozuldu).
# İçeriği yok eden işlemler (WRITE, DESTRUCTIVE) ASK olarak kaldı.
#
# NETWORK neden ALLOW: asıl duvar site beyaz listesi. Listeye alınmış bir
# adrese her girişte tekrar sormak yeni bir sınır çizmiyor. Liste dışı adres
# zaten DENY.
RISK_VARSAYILAN = {
    "READ": ALLOW,
    "WRITE_HAFIF": ALLOW,     # move, rename, browser_click, browser_fill
    "WRITE": ASK,             # write_file — içeriği değiştirir/yok eder
    "EXEC": ASK,
    "NETWORK": ALLOW,         # beyaz listeye karşı ayrıca doğrulanır
    "DESTRUCTIVE": ASK,       # trash, browser_download
}

# Tıklama kalıpları, EYLEM KATEGORİSİNE göre ikiye ayrılır. Aynı araç
# (browser_click) düğmenin adına göre farklı kategoriye düşer: "İleri" sıradan
# bir tıklama, "Ödemeyi tamamla" bambaşka bir şey.
# "=" ile baslayan kalip TAM KELIME eslesir, on ek olarak degil. Gerekcesi:
# "pay" on eki "paylas" kelimesini, "ode" on eki "odev" kelimesini yakaliyordu
# ve "Paylas" dugmesi odeme sayiliyordu (testte cikti).
ODEME_KALIPLARI = [
    "satin al", "satın al", "buy", "purchase", "sepete", "checkout",
    "siparis", "sipariş", "odeme", "ödeme", "payment",
    "=ode", "=öde", "=pay", "=odemeler", "=ödemeler",
    "transfer", "havale", "=eft", "abonelik",
]
GONDERIM_KALIPLARI = [
    "gonder", "gönder", "submit", "send",
    "paylas", "paylaş", "share", "yayinla", "yayınla", "post", "tweet",
    "abone", "subscribe", "kaydol", "sign up", "uye ol", "üye ol",
    "onayla", "confirm", "kabul et", "accept",
    "sil", "delete", "remove", "kaldir", "kaldır",
]

# Araç -> eylem kategorisi. browser_click ayrı ele alınır (yukarıdaki kalıplar).
EYLEM_ARAC = {
    "browser_open": "gezinme",
    "browser_read": "okuma",
    "browser_snapshot": "okuma",
    "browser_fill": "form",
    "browser_download": "indirme",
}
EYLEMLER = ["gezinme", "okuma", "tiklama", "form", "indirme", "gonderim", "odeme"]

# Ayar dosyası hiçbir şey söylemezse geçerli olan taban. Ödeme varsayılan olarak
# YASAK: ajanın kullanıcı adına ödeme tamamlaması için meşru bir sebep yok,
# istenirse bilinçli olarak açılır. "Onayı kaldırmak yerine riski düşür" ilkesi.
EYLEM_TABAN = {
    "gezinme": "izin", "okuma": "izin", "tiklama": "izin", "form": "izin",
    "indirme": "sor", "gonderim": "sor", "odeme": "yasak",
}
IZIN_KARAR = {"izin": ALLOW, "sor": ASK, "yasak": DENY}


def _pozitif(kaynak: dict, anahtar: str, varsayilan: int, ust: int) -> int:
    """Sayisal sinirlari okur. Bozuk deger SESSIZCE sinirsiza donusmemeli:
    harcama duvarinin varsayilani 'duvar yok' olamaz, o yuzden burada patlar
    ve surec baslamaz. _guvenli_yaz da ayni kontrolu yeniden yukleme adiminda
    yakalar, yani panelden bozuk deger yazilamaz."""
    ham = kaynak.get(anahtar, varsayilan)
    if isinstance(ham, bool) or not isinstance(ham, int) or ham < 0 or ham > ust:
        raise ValueError(f"policy.toml: {anahtar} 0 ile {ust} arasinda tam sayi olmali "
                         f"(verilen: {ham!r}).")
    return ham


def _kalip_var(ad: str, kaliplar: list[str]) -> str | None:
    """Tek kelimelik kalıplar KELİME BAŞINDAN eşleşir, alt dize olarak değil.

    "ode" kalıbı "model" kelimesinin içinde geçiyordu ve "Model seç" düğmesi
    boş yere onay istiyordu. "ödeme" yine yakalanır: kelime o kalıpla başlıyor.
    """
    kucuk = (ad or "").casefold()
    if not kucuk:
        return None
    kelimeler = [k for k in re.split(r"[^\w]+", kucuk, flags=re.UNICODE) if k]
    for kalip in kaliplar:
        if kalip.startswith("="):
            tam = kalip[1:]
            if tam in kelimeler:        # TAM kelime: "pay" evet, "paylas" hayir
                return tam
        elif " " in kalip:
            if kalip in kucuk:          # cok kelimeli kalip: butun metinde ara
                return kalip
        elif any(k.startswith(kalip) for k in kelimeler):
            return kalip
    return None


def eylem_kategorisi(arac: str, args: dict) -> str | None:
    """Araç çağrısı hangi eylem kategorisine giriyor? Tarayıcı dışı araçta None."""
    if arac == "browser_click":
        ad = str((args or {}).get("name", ""))
        if _kalip_var(ad, ODEME_KALIPLARI):
            return "odeme"
        if _kalip_var(ad, GONDERIM_KALIPLARI):
            return "gonderim"
        return "tiklama"
    return EYLEM_ARAC.get(arac)


# Hangi aracın HANGİ argümanı yol ve hangi izne tabi: {arac: {arguman: "oku"|"yaz"}}.
# Yerel araçlar bunu kayıt defterinden (pevrai.araclar.kayit, @arac yollar=...)
# bildirir; MCP araçları policy.toml'da tablo biçimiyle bildirir:
#     "okuma.import_pdf" = { risk = "WRITE", yollar = { path = "oku" } }
# Bildirimi olmayan aracın yol argümanı DENETLENMEZ — o yüzden MCP aracını
# sınıflandırırken yol argümanı varsa yollar da yazılmalı (Araçlar paneli sorar).
# Eskiden bu tablo ada bağlıydı ("move" ve "converter.convert" kodda özel dal);
# şimdi her araç kaç yol argümanı olursa olsun aynı döngüden geçer.
YOL_BILDIRIMLERI: dict[str, dict[str, str]] = {
    # Yerleşik olmayan ama sablonla gelen MCP sunucusu: eski policy.toml'lar
    # düz satır ("converter.convert" = "WRITE") taşıyor, bildirim burada durur.
    "converter.convert": {"src": "oku", "dst_dir": "yaz"},
}
try:
    from pevrai.araclar import kayit as _kayit
    YOL_BILDIRIMLERI.update(_kayit.yol_modlari())
except ImportError:      # araclar paketi yoksa (kırpılmış kurulum) kapı yine çalışır
    pass

# Geriye dönük görünüm: aracın BİRİNCİL yol argümanının modu (ilk bildirim).
# vekil_v0._erisim ("okuyan araç açık mı") ve testler bunu okur.
ARAC_YOL_MODU: dict[str, str] = {ad: next(iter(y.values())) for ad, y in YOL_BILDIRIMLERI.items() if y}


def yol_bildir(arac: str, yollar: dict[str, str]) -> None:
    """Çalışma zamanında bildirim ekler (eklentiler, panelden sınıflandırma)."""
    YOL_BILDIRIMLERI[arac] = dict(yollar)
    if yollar:
        ARAC_YOL_MODU[arac] = next(iter(yollar.values()))


@dataclass
class Karar:
    sonuc: str                 # ALLOW / ASK / DENY
    gerekce: str
    yol: Path | None = None    # çözülmüş ve doğrulanmış yol; araca bu verilir


def windows_ad_tuzagi(yol: Path) -> str | None:
    """Bu cozulmus yol, Windows'un BASKA bir dosyaya cevirecegi bir ad tasiyor mu?
    Tasiyorsa sebep, temizse None. Saf: diske dokunmaz, Politika'ya bagli degil.

    KAPIYI KIRAN VAKA (Faz 7 Asama 1'de olculdu, teoriyle degil deneyle):
    'kum\\gizli.pem.' yolu kapidan ALLOW aliyordu. Sebep sirali:
      1. resolve() VAR OLMAYAN bir dosyada sondaki noktayi KORUR
         ('gizli.pem.' olarak kalir; var OLAN dosyada dosya sistemi cozer ve
         nokta duser — bu yuzden '.env.' zaten DENY aliyordu, tesadufen).
      2. Kara liste fnmatch ile ada bakar: 'gizli.pem.' ifadesi '*.pem'
         kalibina UYMAZ.
      3. Ama Win32 dosyayi ACARKEN sondaki noktayi/boslugu YUTAR — yazma
         gercekte 'gizli.pem' dosyasina iner. Deneyle dogrulandi: '_probe.txt.'
         yoluna yazilan icerik '_probe.txt' dosyasinda cikti.
    Yani kapi BIR adi denetleyip dosya sistemi BASKA bir adi kullaniyordu —
    tam olarak "once realpath, sonra kontrol" kuralinin engellemek icin var
    oldugu hata sinifi, sadece ayirici karakter '..' degil '.'.

    Gomulu NUL ayni sinifta: kara liste '.env\x00.txt' adini '.env' kalibina
    uydurmaz. Bugun zararsiz (Python'un open()'i ValueError atiyor, dosyaya
    hic inilmiyor) ama kapinin ALLOW demesi yine de YANLIS cevap — NUL'da
    kesen bir C API'sine giden yeni bir yol acilirsa aciga donusur.

    NORMALLESTIRME DEGIL REDDETME: Windows'ta normal API ile sonu nokta ya da
    bosluk olan bir dosya adi ZATEN olusturulamaz, yani hicbir mesru cagri bu
    yollari kullanmaz. Reddetmek fail-closed, ve hata metni modelin kendini
    duzeltebilecegi bilgiyi tasiyor.
    """
    for parca in yol.parts:
        if "\x00" in parca:
            return "yol gomulu NUL bayti iceriyor"
        # Surucu koku ('D:\\') haric: onun kendisi zaten '\\' ile biter.
        if len(parca) > 1 and parca.rstrip(". ") != parca and not parca.endswith(":\\"):
            return (f"'{parca}' adi nokta ya da bosluk ile bitiyor; Windows bunu "
                    f"acarken yutar ve BASKA bir dosyaya ({parca.rstrip('. ')}) iner")
    return None


def acma_klasoru_ihlali(klasor: Path, yazma_kokleri: Iterable[Path], proje_koku: Path) -> str | None:
    """Acma klasoru ajanin yazabildigi bir yerle kesisiyor mu? Kesisiyorsa neden.

    Uc kesisim de yasak: klasor bir yazma kokunun ICINDE (ajan oraya kisayol
    yazar), bir yazma koku klasorun ICINDE (ayni sey, alt klasorden), ya da
    esit. Kod koku da ayni sebeple: kurulum klasorundeki bir seyi "acilabilir"
    ilan etmek anlamsiz ve dondurulmus surumde tehlikeli. Politika'ya bagli
    DEGIL: panel klasoru yazmadan once ayni kuralla reddeder.
    """
    for w in yazma_kokleri:
        if klasor == w or w in klasor.parents or klasor in w.parents:
            return t("Açma klasörü ({klasor}) ajanın yazabildiği bir yerle kesişiyor ({yazma}). "
                     "Ajan oraya kısayol yazıp açabilirdi; ayrı bir klasör seç.", klasor=klasor, yazma=w)
    # Kod ve config: acma klasoru oralarda olamaz (kaynaktan calisirken proje
    # kokunun KENDISI degil — kullanici kokun yaninda "Kisayollar" acabilir;
    # ajan oraya zaten yazamaz). Dondurulmus surumde kurulum klasoru de korunur.
    from pevrai import DONMUS, KAYNAK_KOK, PAKET
    korunan = [PAKET, Path(proje_koku) / "config"] + ([KAYNAK_KOK] if DONMUS else [])
    for k in korunan:
        if klasor == k or k in klasor.parents:
            return t("Açma klasörü ({klasor}) Pevrai'nın kendi klasörünün içinde olamaz.", klasor=klasor)
    return None


def kod_kokleri(proje_koku: Path) -> list[Path]:
    """Korunacak kokler. Kaynaktan calisirken kod ve config ayni yerde (tek kok).
    Dondurulmus surumde kod Program Files'ta (KAYNAK_KOK), kisisel dosyalar
    %LOCALAPPDATA%/Pevrai'da (PROJE_KOKU): ikisi de korunur — kullanici
    kurulum klasorunu yazma koku yapsa kapi yine reddeder."""
    from pevrai import DONMUS, KAYNAK_KOK
    kokler = [Path(proje_koku)]
    if DONMUS:
        try:
            kokler.append(KAYNAK_KOK.resolve())
        except OSError:
            pass
    return kokler


def korunan_yol_ihlali(yazma_kokleri: Iterable[Path], kod_koku: Path) -> str | None:
    """Bu yazma koku listesi ajanin kendi davranisini degistirmesine izin veriyor mu?

    Politika'ya bagli DEGIL: henuz yazilmamis bir ADAY liste uzerinde de
    calisir. Panel yazmadan once bunu cagirir, _guvenli_yaz yazdiktan sonra
    ayni kurali yeniden dogrular — tek kural, iki uygulama noktasi.

    config/ ayri sayilir cunku persona.md sistem talimatina giriyor: orayi
    yazabilen ajan kapiya hic dokunmadan kendi talimatini degistirir.

    Iki taraf da realpath ile cozulur: Windows 8.3 kisa adi (RUNNER~1)
    ile uzun adi ayni klasoru gosterir ama Path esitligi tutmaz; cozulmemis
    bir girdi korumayi sessizce delerdi (temiz CI makinesinde yakalandi).
    """
    def coz(y: Path) -> Path:
        try:
            return Path(os.path.realpath(y))
        except (OSError, ValueError):
            return Path(y)
    kod_koku = coz(Path(kod_koku))
    yazma_kokleri = [coz(Path(y)) for y in yazma_kokleri]
    korunan = {"kaynak kodu": kod_koku, "config klasoru": kod_koku / "config"}
    for etiket, hedef in korunan.items():
        for yazilabilir in yazma_kokleri:
            if hedef == yazilabilir or yazilabilir in hedef.parents:
                return (f"Pevrai'nin {etiket} ({hedef}) yazma kokunun ICINDE: "
                        f"{yazilabilir}. Bu yerlesimde ajan kendi izin kapisini ya da "
                        f"kendi sistem talimatini degistirebilir.")
    return None


def tavan_karari(rol: str,
                 sayaclar: Mapping[str, int],
                 tavanlar: Mapping[str, int]) -> tuple[int, int] | None:
    """Bu rol icin gunluk istek tavani doldu mu? Doldiysa (sayi, tavan), yoksa None.

    KARAR verir; istisna atmaz, diske dokunmaz, sayaci artirmaz. Cagiran taraf
    sayaclari nereden okudugunu ve ne atacagini kendi bilir.

    Politika'ya bagli DEGIL (bkz. korunan_yol_ihlali): aday sayilar uzerinde de
    calisir, bu yuzden model kutuphanesi olmadan test edilebilir.

    tavan 0 = tavan yok. Karsilastirma > degil >= cunku sayac cagridan ONCE
    artiyor: N tavaninda N istek gecer, N+1. istek duvara carpar.

    TANINMAYAN ROL = TAVAN YOK. Bilincli: journal.kota_artir de taninmayan rolu
    saymiyor, yani sayac hic buyumez ve bir tavan zorlamak "0/450" ile
    karsilastirmak olurdu. Bedeli su: rol adinda bir yazim hatasi duvari
    SESSIZCE devre disi birakir. Faz 6'da efor modlari gelirken mod->rol
    eslemesi Politika yuklenirken dogrulanmali (orada fail-closed olmali,
    burada degil — yukleme zamaninda patlamak gorev ortasinda patlamaktan iyi).
    """
    tavan = tavanlar.get(rol, 0)
    if not tavan:
        return None
    sayi = sayaclar.get(rol, 0)
    return (sayi, tavan) if sayi >= tavan else None


# Tur basina, risk seviyesine gore azami cagri sayisi. Yuksek riskli araclarda
# model tek turda yigin islem yapamaz. vekil_v0'da yasardi; buraya tasindi ki
# tur_karari modelsiz test edilebilsin (asagidaki fonksiyon).
TUR_TAVANI = {"READ": 12, "WRITE": 5, "EXEC": 3, "NETWORK": 3, "DESTRUCTIVE": 2}

# Faz 7 Asama 3: bir profilin sahip olabilecegi KAPALI alan listesi. Profil
# ADLARI kullanici tanimli, ama alanlari degil — bilinmeyen bir alan acilista
# reddedilir (bkz. Politika.__init__).
PROFIL_ALANLARI = {"araclar", "yazma_koklari", "mod", "azami_adim", "azami_devam"}
# [ajanlar.<ad>]: ekip gorevlerinde (ekip paketi) bir isciyi tanimlar. Anahtarin
# kendisi burada DEGIL — anahtar_yuvasi anahtar.py'deki adli yuvayi gosterir.
AJAN_ALANLARI = {"saglayici", "model", "anahtar_yuvasi", "rol", "taban_url", "baglanti", "renk", "gorunum"}
# Eski tek-saglayici [model] ayarinin baglanti kimligi (ayarlar.ESKI_BAGLANTI ile ayni).
ESKI_BAGLANTI_KIMLIGI = "ana"
AJAN_AD_KALIBI = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
# [baglantilar.<kimlik>]: kullanicinin API baglantilari (bkz. pevrai/model_zinciri.py).
BAGLANTI_ALANLARI = {"ad", "saglayici", "taban_url", "modeller", "anahtar_yuvasi"}
BAGLANTI_KALIBI = re.compile(r"^[a-z0-9][a-z0-9_-]{0,19}$")


def tur_karari(risk: str,
               tur_sayaci: Mapping[str, int],
               tur_tavani: Mapping[str, int] = TUR_TAVANI) -> tuple[int, int] | None:
    """Bu TURDA bu risk seviyesinden yapilan cagri sinira carpti mi?
    Carptiysa (sayi, tavan), carpmadiysa None.

    tavan_karari'nin gunluk/rol karsiligi ama olcek FARKLI: o gun boyunca
    birikir, bu TEK TUR icinde birikir ve her turun basinda modelin kendisi
    (vekil_v0.calistir icinde tur_sayaci = {} ile) sifirlanir — sifirlama
    burada DEGIL, cagiran tarafta, cunku "yeni tur" kavrami bu fonksiyonun
    bilmedigi bir dongu detayi.

    Karsilastirma > (tavan_karari'nin >= degil): sayac CAGRIDAN SONRA
    artiyor, yani tavan=5 iken 5 cagri gecer, 6. cagri sinira carpar.
    Taninmayan risk icin varsayilan tavan 5 (vekil_v0'daki eski `.get(risk, 5)`
    ile ayni, cagiran tarafin unutup sinirsiz birakmasindan iyi).
    """
    tavan = tur_tavani.get(risk, 5)
    sayi = tur_sayaci.get(risk, 0)
    return (sayi, tavan) if sayi > tavan else None


def butce_karari(harcanan: int, butce: int) -> tuple[int, int] | None:
    """Bu GOREV icin istek butcesi doldu mu? Dolduysa (harcanan, butce), yoksa None.

    tavan_karari'nin birebir deseni: KARAR verir, istisna atmaz, diske
    dokunmaz, sayaci artirmaz. Politika'ya bagli DEGIL — aday sayilar
    uzerinde de calisir, model kutuphanesi olmadan test edilebilir.

    butce 0 = BUTCE YOK (tavan_karari'nin "tavan 0 = tavan yok"u ile ayni
    sozlesme). Karsilastirma > degil >= cunku sayac cagridan ONCE artiyor:
    N butcesinde N istek gecer, N+1. istek duvara carpar.

    NEDEN ADIM TAVANI YETMIYOR — bu fonksiyonun var olma sebebi:
    adim tavani model TURLARINI sayar, gonderilen ISTEKLERI degil. Bir tur
    icinde _model_cagir 429/503/zaman asiminda API_DENEME (3) kez yeniden
    deniyor ve her deneme AYRI bir istek, ayrica journal.kota_artir'a AYRI
    sayiliyor. Yani adim tavani 8 olan bir gorev en kotu durumda 8*3+3 = 27
    istek gonderebilir. Gunluk tavan (guclu rolunde 18) bunu tek bir yanlis
    anlasilmis gorevde tuketebilir — kullanici evden ciktiktan yirmi dakika
    sonra hem is yarim hem gunun hakki bitmis olur. Gozetimsiz mod bu riski
    dogrudan buyutuyor.

    KAPSAM: "gorev basina". devam_et() TAZE bir calistir() cagrisidir, yani
    butce her devam turunda SIFIRLANIR. Bu bilincli: devam turlarinin sayisi
    profilin azami_devam'i ile ayrica sinirli, ve en dis sinir her zaman
    gunluk tavan — butce onun yerine gecmez, onun ONUNDE durur.
    """
    if not butce:
        return None
    return (harcanan, butce) if harcanan >= butce else None


def durum_karari(adim: int, azami_adim: int, *,
                  cagri_tavaninda_mi: bool = False,
                  butce_doldu_mu: bool = False,
                  model_bitirdi_mi: bool) -> str:
    """Bu turdan sonra dongu ne yapmali: devam mi, durumu dosyaya yazip mi
    dursun, yoksa gorev zaten mi bitti?

    "devam" | "durum_yaz" | "bitti" doner. Saf: diske dokunmaz, model
    cagirmaz, istisna atmaz — vekil_v0.calistir icindeki asil yazma/cagirma
    islerinden ayri, tavan_karari/tur_karari/mod_coz deseninin dorduncu
    musterisi.

    Etkilesimli modda "adim limiti asildi" bir metin mesaji, zararsiz —
    kullanici okur, "devam et" der. Gozetimsiz modda okuyan kimse yok; ayni
    mesaj sessiz bir yarim kalma olur (bkz. DEVIR_FAZ7.md §4). Bu yuzden
    tavana carpma bir DURUMA donusmeli: cagiran taraf "durum_yaz" gorunce
    modelden TEK bir zorlanmis cagriyla ozet alip diske yazar.

    UC AYRI SINIR ayni karara baglanir: calistir'de dongu uc farkli sinirla
    bitebilir — adim sayisi (asagida), tur icindeki toplam arac cagrisi
    (cagri_tavaninda_mi) ve gorev basina istek butcesi (butce_doldu_mu,
    bkz. butce_karari). Ucunu de cagiran taraf hesaplayip veriyor.

    Ilk surumde yalnizca adim sinanmisti; cagri siniri kendi basina donup
    gozetimsiz modda sessizce olen IKINCI bir yol birakiyordu. Butce
    eklenirken ayni hata TEKRARLANMADI: ayri bir return yolu ACILMADI,
    ucuncu sinir de buraya baglandi. Uc sinir, tek karar, tek cikis —
    her yeni sinir bu fonksiyona bir parametre olarak gelmeli, calistir'e
    bir return olarak degil.

    Karsilastirma >= (tur_karari'nin > degil): tavan_karari/tur_karari
    CAGRIDAN SONRA sayiyor ve tavani asinca durduruyor; burada adim
    NUMARASI (1'den baslar, azami_adim'e kadar) ile azami_adim'in KENDISI
    karsilastiriliyor — dongu zaten `range(1, azami_adim + 1)` ile
    calisiyor, yani adim == azami_adim SON izinli turdur. Esitlikte "devam"
    denirse bir sonraki tur hic yasanmadan sinira carpilir; azami_adim=1
    gibi kucuk degerlerde bu kilitlenme demek olurdu.

    Parametreler KEYWORD-ONLY (adim/azami_adim haric): iki bool'un sirasini
    karistirip yanlis pozisyonel deger vermek (orn. cagri_tavaninda_mi yerine
    model_bitirdi_mi) sessizce yanlis davranir, cagiranin patlamasini
    istiyoruz.
    """
    if model_bitirdi_mi:
        return "bitti"
    if cagri_tavaninda_mi or butce_doldu_mu or adim >= azami_adim:
        return "durum_yaz"
    return "devam"


def devam_karari(devam_sayisi: int, azami_devam: int, *,
                 yeni_yazma_var_mi: bool, kota_dolu_mu: bool) -> str:
    """Bir tavana carpip durum dosyasi birakmis gorev KENDILIGINDEN devam
    etmeli mi? "devam" | "dur_ilerleme_yok" | "dur_kota" | "dur_sinir" doner.

    Saf: diske dokunmaz, model cagirmaz, istisna atmaz — tavan_karari /
    tur_karari / mod_coz / durum_karari / butce_karari ailesinin altinci
    uyesi. Uc girdisini de cagiran taraf hesaplayip veriyor.

    KARARLARIN SIRASI BIR ONCELIK SIRASIDIR, keyfi degil:

    1. kota_dolu_mu -> "dur_kota". Gunluk tavan EN DIS sinir; hicbir devam
       onu asamaz. Ilk sirada olmasi sart: kota doluyken "devam" demek bir
       sonraki turda TavanDoldu ile patlamak olurdu ve sebep kullaniciya
       "ilerleme yok" diye yanlis raporlanabilirdi.
    2. devam_sayisi >= azami_devam -> "dur_sinir". Ust sinir FAIL-CLOSED ve
       profilde tanimli; sonsuz devam diye bir sey yok. azami_devam
       tanimlanmamis bir profilde 0'dir ve 0 >= 0 oldugu icin ILK kontrolde
       durur — yani kendiliginden devam "varsayilan kapali" dogar, listeye
       eklenmeyi hatirlamak gerekmez.
    3. not yeni_yazma_var_mi -> "dur_ilerleme_yok". Kendi kendine devam eden
       bir gorevin EN KOTU hali basarisizlik degil, ayni yerde donmesidir:
       kimse izlemiyorken kota bitene kadar ayni turu tekrarlayabilir.
       Zemin gercegi elimizde — journal.gorev_kayitlari. MODELIN OZETI BU
       KARARDA KULLANILMAZ: modelin yapmadigi isi "yapildi" diye bildirdigi
       olculdu (DEVIR_FAZ7.md §8, Asama 1 "beklenmedik bulgu"), yani
       ilerlemeyi modele sormak tam da bu duvarin delinmesi olurdu.
    4. Aksi halde "devam".

    PENCERE CAGIRANIN ISI: `yeni_yazma_var_mi` "su ana kadarki son N turda
    dogrulanmis bir yazma oldu mu" sorusunun cevabidir, N'i bu fonksiyon
    bilmez. Cagiran taraf su an iki tur tolerans veriyor (tek bir kisir tur
    mesru olabilir: model o turu planlama/okuma ile gecirmis olabilir; iki
    tur ust uste kisirsa donuyor demektir). "Yeni tur" kavraminin cagirana
    ait olmasi tur_karari'nin sifirlama kararindaki ayni ayrim.
    """
    if kota_dolu_mu:
        return "dur_kota"
    if devam_sayisi >= azami_devam:
        return "dur_sinir"
    if not yeni_yazma_var_mi:
        return "dur_ilerleme_yok"
    return "devam"


def kok_karari(durum_kokleri: Iterable[str], guncel_kokleri: Iterable[str]) -> str | None:
    """Faz 7 Asama 2: bir durum dosyasindan DEVAM etmek guvenli mi?

    Durum dosyasi yazilirken gecerli olan yazma kokleri (`policy.toml`'un o
    anki hali) ile SIMDIKI kokler AYNI mi (kume esitligi, sira onemsiz)?
    Degilse devam GUVENLI DEGIL — sebep metnini doner, ayniysa None.

    Saf: diske dokunmaz, model cagirmaz. Fail-closed, `Politika.__init__`'in
    mod rolu dogrulamasiyla ayni desen: herhangi bir fark (daralma,
    genisleme, tamamen degisme) reddedilir — "hangi yonde degisti" onemli
    degil, durum dosyasi farkli bir izin siniriyla yazilmis olabilir ve
    devam eden gorev o eski sinira gore "tamamlandi" sanabilir.
    """
    durum_kume, guncel_kume = set(durum_kokleri), set(guncel_kokleri)
    if durum_kume != guncel_kume:
        return (f"Yazma kökleri değişmiş: durum dosyası {sorted(durum_kume)} "
                f"köküyle yazılmıştı, şu an {sorted(guncel_kume)}. Devam güvenli "
                f"değil — görevi baştan başlat.")
    return None


class Politika:
    def __init__(self, dosya: Path) -> None:
        with open(dosya, "rb") as f:
            ham = tomllib.load(f)

        fs = ham.get("filesystem", {})
        self.okuma = [Path(p).expanduser().resolve() for p in fs.get("okuma_koklari", [])]
        self.yazma = [Path(p).expanduser().resolve() for p in fs.get("yazma_koklari", [])]
        self.yasak = fs.get("yasak_kaliplar", [])
        # [acma] klasor: kullanicinin "acilabilir" olarak isaretledigi TEK klasor.
        # Icine ne koyarsa (belge, kisayol, .exe) open_file ile acilabilir; ajan
        # oraya YAZAMAZ. Bu iki cumle birbirine bagli: yazabilseydi kendi
        # kisayolunu koyup acardi. Kesisim varsa klasor YOK sayilir (acma_hatasi).
        self.acma_klasoru: Path | None = None
        self.acma_hatasi: str | None = None
        ham_acma = str((ham.get("acma") or {}).get("klasor") or "").strip()
        if ham_acma:
            try:
                aday = Path(ham_acma).expanduser().resolve()
            except (OSError, ValueError):
                aday = None
            if aday is None:
                self.acma_hatasi = t("Açma klasörü çözülemedi: '{yol}'", yol=ham_acma)
            else:
                self.acma_hatasi = acma_klasoru_ihlali(aday, self.yazma, dosya.parent)
                if self.acma_hatasi is None:
                    self.acma_klasoru = aday
        # [araclar]: düz satır ("x" = "READ") ya da tablo ("x" = { risk = "WRITE",
        # yollar = { path = "oku" } }). Tablo biçimi MCP araçlarının yol
        # argümanlarını kapıya bildirir (bkz. YOL_BILDIRIMLERI).
        self.araclar: dict[str, str] = {}
        self.yol_bildirimleri: dict[str, dict[str, str]] = {}
        for ad, deger in ham.get("araclar", {}).items():
            if isinstance(deger, dict):
                self.araclar[ad] = str(deger.get("risk", ""))
                yollar = deger.get("yollar") or {}
                if not isinstance(yollar, dict) or any(m not in ("oku", "yaz", "ac") for m in yollar.values()):
                    raise ValueError(f"policy.toml [araclar] {ad!r}: yollar {{arguman = \"oku\"|\"yaz\"|\"ac\"}} olmalı.")
                self.yol_bildirimleri[ad] = {str(k): str(v) for k, v in yollar.items()}
            else:
                self.araclar[ad] = str(deger)
        self.mcp = dict(ham.get("mcp", {}))

        # --- Kaldirilan paketler (pevrai.paketler) --------------------------
        # [paketler] kaldirilan = ["tarayici", ...] YALNIZCA DARALTIR: listedeki
        # yerlesik paketin araclari [araclar]'dan dusurulur, yani kapi onlari
        # "tanimsiz arac" diye reddeder ve vekil_v0 semalarini modele hic
        # gondermez. Cekirdek paket listede olsa bile dusurulmez (paketler.
        # yerlesik_araclari onu atlar) — ajan okuma yetenegini kaybedemez.
        # Bilinmeyen ad sessizce yutulmaz: uyari basilir, dosya yine yuklenir
        # (kaldirma bir daraltma, yanlis ad hicbir sey acmaz).
        from pevrai import paketler as _paketler
        ham_paketler = ham.get("paketler", {})
        self.kaldirilan = [str(x) for x in (ham_paketler.get("kaldirilan") or [])]
        for ad in self.kaldirilan:
            if ad not in _paketler.YERLESIK:
                print(f"  UYARI: [paketler] kaldirilan icinde taninmayan paket: {ad!r}")
            elif _paketler.YERLESIK[ad]["cekirdek"]:
                print(f"  UYARI: [paketler] kaldirilan icinde cekirdek paket {ad!r} — yok sayildi")
        self.kaldirilan_araclar = _paketler.yerlesik_araclari(self.kaldirilan)
        for arac in self.kaldirilan_araclar:
            self.araclar.pop(arac, None)

        tarayici = ham.get("browser", {})
        self.izinli_alanlar = [a.lower().lstrip(".") for a in tarayici.get("izinli_alanlar", [])]
        self._eylem_ayarlarini_yukle(tarayici)
        self.izinli_yerel = [Path(p).expanduser().resolve() for p in tarayici.get("izinli_yerel_kokler", [])]
        self.indirilebilir = {u.lower() for u in tarayici.get("indirilebilir_uzantilar", [])}

        model = ham.get("model", {})
        self.model_varsayilan = model.get("varsayilan")
        self.model_guclu = model.get("guclu", self.model_varsayilan)
        if not self.model_varsayilan:
            raise ValueError("policy.toml içinde [model] varsayilan tanımlı değil.")
        # Saglayici (pevrai.model): gemini | openai | anthropic. Anahtar burada
        # DEGIL (anahtar.py: ortam degiskeni / keyring / credentials.json) —
        # policy.toml depo disi olsa da bir yedegi (policy.toml.yedek) var ve
        # panelden yeniden yazilan bir dosyada gizli tutulmamali.
        self.saglayici = str(model.get("saglayici", "gemini") or "gemini").lower()
        if self.saglayici not in ("gemini", "openai", "anthropic"):
            raise ValueError(f"policy.toml [model] saglayici = {self.saglayici!r} taninmiyor. "
                             f"Gecerli: gemini, openai, anthropic.")
        self.taban_url = str(model.get("taban_url", "") or "")

        # [baglantilar.<kimlik>]: kullanicinin API baglantilari (saglayici, sunucu
        # adresi, SIRALI model listesi; anahtar anahtar.py'de adli yuvada) ve
        # [model] zincir = sira. Bos ise eski tek-saglayici [model] ayari kullanilir
        # (pevrai/model_zinciri.py). Fail-closed: bozuk tanim acilista patlar.
        self.baglantilar: dict[str, dict] = {}
        for kimlik, b in (ham.get("baglantilar") or {}).items():
            yer = f"policy.toml [baglantilar.{kimlik}]"
            if not isinstance(b, dict):
                raise ValueError(f"{yer} bir tablo olmali.")
            if not BAGLANTI_KALIBI.match(str(kimlik)):
                raise ValueError(f"{yer}: kimlik 1-20 karakter, kucuk harf/rakam/_/- olmali.")
            bilinmeyen = set(b.keys()) - BAGLANTI_ALANLARI
            if bilinmeyen:
                raise ValueError(f"{yer} bilinmeyen alan(lar): {sorted(bilinmeyen)}. Izinli: {sorted(BAGLANTI_ALANLARI)}.")
            saglayici = str(b.get("saglayici") or "").lower()
            if saglayici not in ("gemini", "openai", "anthropic"):
                raise ValueError(f"{yer} saglayici = {saglayici!r} taninmiyor.")
            modeller = b.get("modeller") or []
            if (not isinstance(modeller, list) or not modeller or len(modeller) > 20
                    or not all(isinstance(m, str) and re.match(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{1,127}$", m)
                               for m in modeller)):
                raise ValueError(f"{yer} modeller: 1-20 gecerli model adi olmali.")
            taban = str(b.get("taban_url") or "").strip()
            if taban and not re.match(r"^https?://[^\s\"']{1,300}$", taban):
                raise ValueError(f"{yer} taban_url gecersiz.")
            yuva = str(b.get("anahtar_yuvasi") or "").strip()
            if yuva and not re.match(r"^[A-Za-z0-9_-]{1,32}$", yuva):
                raise ValueError(f"{yer} anahtar_yuvasi = {yuva!r} gecersiz.")
            self.baglantilar[str(kimlik)] = {
                "ad": str(b.get("ad") or kimlik).strip()[:40] or str(kimlik),
                "saglayici": saglayici, "taban_url": taban, "anahtar_yuvasi": yuva,
                "modeller": list(dict.fromkeys(modeller)),      # tekrar edeni at, sira korunur
            }
        sira = [str(k) for k in (model.get("zincir") or []) if str(k) in self.baglantilar]
        self.zincir = list(dict.fromkeys(sira)) + [k for k in self.baglantilar if k not in sira]

        # [ajanlar.<ad>]: ekip isci tanimlari. Fail-closed: bilinmeyen alan,
        # taninmayan saglayici ya da bozuk model adi acilista patlar (mod ve
        # profil dogrulamasiyla ayni desen). Tanim YOKSA ekip ozelligi yalnizca
        # varsayilan modeli tek isci olarak kullanabilir.
        # Iki bicim: YENI = baglanti (+ model): ajan bir API baglantisina bagli,
        # saglayici/adres/yuva baglantidan gelir. ESKI = saglayici, anahtar_yuvasi,
        # taban_url alanlari (okunmaya devam eder). Baglantilardan SONRA okunur:
        # baglanti kimligi var olan bir baglantiyi gostermeli.
        self.ajanlar: dict[str, dict] = {}
        for ad, a in (ham.get("ajanlar") or {}).items():
            if not isinstance(a, dict):
                raise ValueError(f"policy.toml [ajanlar.{ad}] bir tablo olmali.")
            if not AJAN_AD_KALIBI.match(str(ad)):
                raise ValueError(f"policy.toml [ajanlar.{ad}]: ad 1-32 karakter, harf/rakam/_/- olmali.")
            bilinmeyen = set(a.keys()) - AJAN_ALANLARI
            if bilinmeyen:
                raise ValueError(f"policy.toml [ajanlar.{ad}] bilinmeyen alan(lar): {sorted(bilinmeyen)}. "
                                 f"Izinli: {sorted(AJAN_ALANLARI)}.")
            model_adi = str(a.get("model") or "").strip()
            if model_adi and not re.match(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{1,127}$", model_adi):
                raise ValueError(f"policy.toml [ajanlar.{ad}] model = {model_adi!r} gecersiz.")
            renk = str(a.get("renk") or "").strip()
            if renk and not re.match(r"^#[0-9a-fA-F]{6}$", renk):
                raise ValueError(f"policy.toml [ajanlar.{ad}] renk = {renk!r} gecersiz (#rrggbb).")
            gorunum = a.get("gorunum")
            if gorunum is not None and (not isinstance(gorunum, int) or isinstance(gorunum, bool)
                                        or not 0 <= gorunum < 8):
                raise ValueError(f"policy.toml [ajanlar.{ad}] gorunum 0-7 arasi bir tamsayi olmali.")
            baglanti = str(a.get("baglanti") or "").strip()
            if baglanti:
                eski = {"saglayici", "anahtar_yuvasi", "taban_url"} & set(a.keys())
                if eski:
                    raise ValueError(f"policy.toml [ajanlar.{ad}] baglanti ile birlikte {sorted(eski)} "
                                     f"yazilamaz; bunlar baglantidan gelir.")
                if baglanti == ESKI_BAGLANTI_KIMLIGI and not self.baglantilar:
                    # [baglantilar] henuz yok: eski [model] ayari 'ana' baglantisidir.
                    b = {"ad": baglanti, "saglayici": self.saglayici,
                         "taban_url": self.taban_url if self.saglayici == "openai" else "",
                         "anahtar_yuvasi": "", "modeller": [m for m in dict.fromkeys(
                             [self.model_varsayilan, self.model_guclu]) if m]}
                elif baglanti in self.baglantilar:
                    b = self.baglantilar[baglanti]
                else:
                    raise ValueError(f"policy.toml [ajanlar.{ad}] baglanti = {baglanti!r} tanimli degil. "
                                     f"Ajani baska bir baglantiya bagla ya da sil.")
                saglayici, yuva, taban = b["saglayici"], b["anahtar_yuvasi"], b["taban_url"]
                model_adi = model_adi or (b["modeller"][0] if b["modeller"] else "")
            else:
                saglayici = str(a.get("saglayici") or self.saglayici).lower()
                if saglayici not in ("gemini", "openai", "anthropic"):
                    raise ValueError(f"policy.toml [ajanlar.{ad}] saglayici = {saglayici!r} taninmiyor.")
                yuva = str(a.get("anahtar_yuvasi") or "").strip()
                if yuva and not re.match(r"^[A-Za-z0-9_-]{1,32}$", yuva):
                    raise ValueError(f"policy.toml [ajanlar.{ad}] anahtar_yuvasi = {yuva!r} gecersiz.")
                taban = str(a.get("taban_url") or "").strip()
            self.ajanlar[str(ad)] = {
                "saglayici": saglayici,
                "model": model_adi,                       # bos = [model] varsayilan (eski bicim)
                "anahtar_yuvasi": yuva,                   # bos = varsayilan yuva
                "rol": str(a.get("rol") or "").strip()[:200],
                "taban_url": taban,
                "baglanti": baglanti,                     # bos = eski tek-saglayici tanimi
                "renk": renk.lower(),
                "gorunum": gorunum,
            }

        # Dayatilan gunluk istek tavanlari. ROL basina sayilir, model adi basina
        # degil: varsayilan ve guclu ayni modeli gosterebiliyor ve ad basina
        # saymak iki rolu tek kovaya birlestirirdi.
        # 0 = tavan yok. Bu bizim duvarimiz, saglayicinin kotasinin vekili DEGIL.
        self.gunluk_tavan = {
            "varsayilan": _pozitif(model, "gunluk_tavan_varsayilan", 0, 100_000),
            "guclu": _pozitif(model, "gunluk_tavan_guclu", 0, 100_000),
        }
        self.persona_acik = bool(model.get("persona_acik", True))

        # --- Efor modlari ------------------------------------------------
        # Mod bir SINIR DEMETIDIR: model rolu + adim tavani + cagri tavani
        # birlikte. Mod IZIN GEVSETMEZ — "azami" odemeyi acmaz, onay kartini
        # atlamaz. Efor "ne kadar hesap harcayacagim"dir, "ne kadar izin
        # alacagim" degil. Bu ayrim yazili degilse ilerde "azami modda niye
        # hala soruyor" diye gevsetilir.
        # "istek" = GOREV BASINA azami model istegi (bkz. butce_karari).
        # Taban degerler adim tavanindan TUREDI, keyfi degil:
        #   istek ~= adim + 1 (tavana carpinca zorlanan durum_yaz cagrisi)
        #                     + yeniden deneme payi
        # Alt sinir neden adim+1'in altina inemez: butce adim tavanindan
        # KUCUK olursa adim tavani OLU koda doner — gorev her zaman once
        # butceye carpar ve "adim" ayari hicbir sey ifade etmez.
        # Ust sinir neden cok comert degil: butcenin isi bir yanlis
        # anlasilmis gorevin gunun hakkini tuketmesini onlemek; payi
        # buyutmek onu yeniden gunluk tavana havale etmek olurdu.
        # Modlarin ruhu ve sirasi korunuyor: 8 < 14 < 20 < 32.
        MOD_TABAN = {
            "hizli":   {"model": "varsayilan", "adim": 4,  "cagri": 10, "istek": 8},
            "dengeli": {"model": "varsayilan", "adim": 8,  "cagri": 20, "istek": 14},
            "derin":   {"model": "guclu",      "adim": 12, "cagri": 30, "istek": 20},
            "azami":   {"model": "guclu",      "adim": 20, "cagri": 50, "istek": 32},
        }
        ham_modlar = ham.get("modlar", {})
        self.modlar: dict[str, dict] = {}
        for ad, taban in MOD_TABAN.items():
            m = ham_modlar.get(ad, {})
            rol = m.get("model", taban["model"])
            # ROL DOGRULAMASI YUKLEME ZAMANINDA ve FAIL-CLOSED. Gorev ortasinda
            # patlamaktansa acilista patlamak yeglenir. Asil sebep: taninmayan
            # rol gunluk tavan duvarini SESSIZCE devre disi birakir
            # (bkz. tavan_karari docstring'i) — bir yazim hatasi kotayi kapatir.
            if rol not in ("varsayilan", "guclu"):
                raise ValueError(
                    f"policy.toml [modlar.{ad}] model = {rol!r} taninmiyor. "
                    f"Gecerli degerler: 'varsayilan', 'guclu'.")
            self.modlar[ad] = {
                "model": rol,
                "adim":  _pozitif(m, "adim",  taban["adim"],  50),
                "cagri": _pozitif(m, "cagri", taban["cagri"], 200),
                # 0 = butce yok (butce_karari'nin sozlesmesi). Ust sinir 200,
                # cagri ile ayni: ikisi de "kac kere" sayiyor.
                "istek": _pozitif(m, "istek", taban["istek"], 200),
            }

        self.varsayilan_mod = ham_modlar.get("varsayilan_mod", "dengeli")
        if self.varsayilan_mod not in self.modlar:
            raise ValueError(
                f"policy.toml [modlar] varsayilan_mod = {self.varsayilan_mod!r} "
                f"taninmiyor. Gecerli: {', '.join(self.modlar)}.")

        # --- Faz 7 Asama 3: gorev profilleri ------------------------------
        # Profil ADLARI kullanici tanimli (mod gibi kapali dort isim degil),
        # ama ALANLARI kapali. Yukleme zamaninda FAIL-CLOSED dogrulanir —
        # mod rolu dogrulamasiyla AYNI desen: gorev ortasinda degil, acilista
        # patla. Profil ASLA izin GEVSETMEZ (kapida uygulanir, bkz.
        # eylem_izni/karar) — burada yalnizca profilin KAPSAMI (hangi
        # araclar, hangi yazma kokleri) taninmis mi diye bakiliyor.
        self.profiller: dict[str, dict] = {}
        for ad, p in (ham.get("profiller") or {}).items():
            if not isinstance(p, dict):
                raise ValueError(f"policy.toml [profiller.{ad}] bir tablo olmali.")
            bilinmeyen = set(p.keys()) - PROFIL_ALANLARI
            if bilinmeyen:
                raise ValueError(
                    f"policy.toml [profiller.{ad}] bilinmeyen alan(lar): "
                    f"{sorted(bilinmeyen)}. Izinli alanlar: {sorted(PROFIL_ALANLARI)}.")

            # araclar: MEVCUT (siniflandirilmis) araclarin ALT KUMESI olmali.
            # Profil yeni bir arac EKLEYEMEZ — kapali listenin disina cikmaya
            # calisan bir profil, izin kapisinin kendisini genisletmis olurdu.
            #
            # ALAN YOK ile BOS LISTE FARKLI SEYLER (Faz 7 Asama 5):
            #   alan yok    -> None -> profil arac listesini DARALTMIYOR
            #                  (model butun araclari gorur, hicbiri onceden
            #                  onayli degil)
            #   araclar = [] -> bos kume -> HICBIR ARAC. Modele hic arac
            #                  semasi gonderilmez: "saf sohbet" bu.
            # Onceki surumde ikisi `or []` ile ayni yere dusuyordu; bos liste
            # yazan bir profil sessizce "daraltma yok" anlamina geliyordu —
            # tam tersi. Ayrim burada korunuyor, tuketen taraflar (kapi karari
            # ve vekil_v0._gorev_araclari) ikisini ayri ele aliyor.
            profil_araclari = None if p.get("araclar") is None else set(p["araclar"])
            # Kaldirilan bir paketin araci profilde aniliyorsa profil PATLAMAZ,
            # arac profilden dusurulur: kaldirma her katmanda ayni yonde
            # (daraltma) islemeli; kullanici tarayiciyi kaldirinca eski bir
            # profil yuzunden Pevrai acilmaz hale gelmemeli.
            if profil_araclari:
                dusen = profil_araclari & self.kaldirilan_araclar
                if dusen:
                    print(f"  UYARI: [profiller.{ad}] kaldirilmis paket araclari dusuruldu: {sorted(dusen)}")
                    profil_araclari = profil_araclari - dusen
            taninmayan_araclar = (profil_araclari or set()) - set(self.araclar)
            if taninmayan_araclar:
                raise ValueError(
                    f"policy.toml [profiller.{ad}] araclar: taninmayan/siniflandirilmamis "
                    f"arac(lar) {sorted(taninmayan_araclar)}. Profil yalnizca [araclar]'da "
                    f"zaten siniflandirilmis araclarin alt kumesini secebilir.")

            # yazma_koklari: policy.toml'un yazma koklerinin ALT KUMESI olmali
            # (esit ya da bir yazma kokunun altinda) — yol_dogrula'daki AYNI
            # "esit ya da parents icinde" kontrolu. Profil kok GENISLETEMEZ;
            # etkilesimli oturumun zaten yazamadigi bir yere yazma izni bir
            # profilden asla cikmamali.
            # Kapsam disindaki kok PROFILI PATLATMAZ, profilden dusurulur
            # (kaldirilan paket araclariyla ayni yon: daraltma). Kullanici
            # Ayarlar'dan bir yazma kokunu cikarinca, o koku anan eski bir
            # profil yuzunden yazim geri alinmamali — yoksa sablondaki
            # calisma klasoru fiilen zorunlu olurdu. Dusen kok hicbir sey
            # acmaz: bos liste = profil hicbir yolu onceden onaylamaz.
            profil_kokleri = []
            for k in (Path(k).expanduser().resolve() for k in (p.get("yazma_koklari") or [])):
                if any(k == y or y in k.parents for y in self.yazma):
                    profil_kokleri.append(k)
                else:
                    print(f"  UYARI: [profiller.{ad}] yazma_koklari: '{k}' yazma koklerinin alt "
                          f"kumesi degil, profilden dusuruldu (profil daha genis kok goremez).")

            profil_mod = p.get("mod")
            if profil_mod is not None and profil_mod not in self.modlar:
                raise ValueError(
                    f"policy.toml [profiller.{ad}] mod = {profil_mod!r} taninmiyor. "
                    f"Gecerli: {', '.join(self.modlar)}.")

            # azami_devam: kendiliginden devam turu ust siniri. TANIMSIZ = 0 =
            # KAPALI. "Varsayilan kapali" ilkesi: gozetimsiz devam bir profile
            # ACIKCA yazilmadikca dogmaz — mevcut profillerin hicbiri bir gun
            # sessizce kendi kendine devam etmeye baslamaz.
            profil_azami_devam = p.get("azami_devam", 0)
            if (isinstance(profil_azami_devam, bool)
                    or not isinstance(profil_azami_devam, int)
                    or not (0 <= profil_azami_devam <= 20)):
                raise ValueError(
                    f"policy.toml [profiller.{ad}] azami_devam 0 ile 20 arasinda "
                    f"tam sayi olmali (0 = kendiliginden devam kapali; "
                    f"verilen: {profil_azami_devam!r}).")

            profil_azami_adim = p.get("azami_adim")
            if profil_azami_adim is not None:
                # 50 ust siniri _pozitif'in mod adim ust siniriyla AYNI — bu
                # keyfi bir sayi degil, gate.py'nin zaten kabul ettigi araligin
                # disina cikmiyor.
                if (isinstance(profil_azami_adim, bool)
                        or not isinstance(profil_azami_adim, int)
                        or not (1 <= profil_azami_adim <= 50)):
                    raise ValueError(
                        f"policy.toml [profiller.{ad}] azami_adim 1 ile 50 arasinda "
                        f"tam sayi olmali (verilen: {profil_azami_adim!r}).")

            self.profiller[ad] = {
                "araclar": profil_araclari,
                "yazma_koklari": profil_kokleri,
                "mod": profil_mod,
                "azami_adim": profil_azami_adim,
                "azami_devam": profil_azami_devam,
            }

        for k in self.okuma + self.yazma:
            if not k.exists():
                print(f"  UYARI: politikadaki klasör diskte yok: {k}")

    def mod_coz(self, ad: str | None) -> dict:
        """Mod adini sinir demetine cevirir; bilinmeyen ad varsayilana duser.

        KOTA ROL BAZINDA sayilir, mod bazinda DEGIL: dort mod iki kovaya
        dusuyor (hizli+dengeli -> varsayilan, derin+azami -> guclu). Sayaci
        mod adiyla tutmak iki rolu dort kovaya bolerdi ve tavan duvari
        gercek kullanimin yarisini gormezdi.
        """
        return self.modlar.get(ad or self.varsayilan_mod,
                               self.modlar[self.varsayilan_mod])

    def _yasakli_mi(self, yol: Path) -> str | None:
        """Yolun herhangi bir parçası kara listeye uyuyorsa sebebi döndürür."""
        for parca in yol.parts:
            for kalip in self.yasak:
                if fnmatch(parca.lower(), kalip.lower()):
                    return kalip
        return None

    def yol_dogrula(self, istenen: str, mod: str) -> Karar:
        """Önce gerçek yola çözer, SONRA kontrol eder.
        Sıra önemli: kısayol/junction ile dışarı çıkma ancak böyle yakalanır."""
        if mod == "ac":
            if self.acma_klasoru is None:
                return Karar(DENY, self.acma_hatasi or t("Açma klasörü ayarlanmamış. Ayarlar > Dosyalar > "
                                                          "Açma klasörü'nden bir klasör seç; içine koyduğun "
                                                          "dosya ve kısayollar açılabilir olur."))
            # Model klasordeki ogeyi ADIYLA ister ("rapor.pdf"); goreli ad acma
            # klasorune gore cozulur, cwd'ye gore degil. Surucu-goreli ("C:x.txt")
            # ne ad ne tam yol: klasore eklenince surucu harfi klasoru yutar
            # (Path("D:/k") / "C:x" == "C:x"), o yuzden burada acikca reddedilir.
            ham_yol = Path(str(istenen)).expanduser()
            if ham_yol.drive and not ham_yol.is_absolute():
                return Karar(DENY, t("'{yol}' geçerli bir yol değil.", yol=istenen))
            if not ham_yol.is_absolute():
                istenen = str(self.acma_klasoru / str(istenen))
        try:
            yol = Path(istenen).expanduser().resolve()
        except (OSError, ValueError):
            return Karar(DENY, t("'{yol}' geçerli bir yol değil.", yol=istenen))

        # Kara listeden ONCE: kara liste ADA bakiyor, Windows ise dosyayi
        # acarken adi degistirebiliyor. Once "bu ad gercekten bu dosya mi"
        # sorusu cevaplanmali, sonra "bu dosyaya dokunulabilir mi".
        tuzak = windows_ad_tuzagi(yol)
        if tuzak:
            return Karar(DENY, t("'{yol}' reddedildi: {sebep}. Adı düzelt ve tekrar dene.",
                                 yol=istenen, sebep=tuzak))

        kalip = self._yasakli_mi(yol)
        if kalip:
            return Karar(DENY, t("'{yol}' kara listede ('{kalip}' kalıbı). Bu dosyaya erişilemez.",
                                 yol=istenen, kalip=kalip))

        kokler = {"oku": self.okuma, "yaz": self.yazma, "ac": [self.acma_klasoru]}[mod]
        if not any(yol == k or k in yol.parents for k in kokler):
            liste = ", ".join(str(k) for k in kokler)
            # "okuma"/"yazma"/"açma" ayri anahtar: ekleme "{mod}ma" gibi dilbilgisi
            # numaralari cevrilemez (Ingilizce'de "readma" cikardi).
            return Karar(DENY, t("'{yol}' izinli {mod} klasörlerinin dışında. İzinli olanlar: {liste}",
                                 yol=yol, mod={"oku": t("okuma"), "yaz": t("yazma"), "ac": t("açma")}[mod],
                                 liste=liste))

        return Karar(ALLOW, t("izinli"), yol)

    # ------------------------------------------------------------------
    # Eylem izinleri (site profilleri)
    # ------------------------------------------------------------------
    def _eylem_ayarlarini_yukle(self, tarayici: dict) -> None:
        """[browser.eylemler] varsayilanlari + [browser.profiller] istisnalari."""
        self.eylem_varsayilan = dict(EYLEM_TABAN)
        for k, v in (tarayici.get("eylemler") or {}).items():
            if k in EYLEM_TABAN and v in IZIN_KARAR:
                self.eylem_varsayilan[k] = v

        self.site_profilleri: dict[str, dict[str, str]] = {}
        for alan, ayar in (tarayici.get("profiller") or {}).items():
            if not isinstance(ayar, dict):
                continue
            temiz = {k: v for k, v in ayar.items() if k in EYLEM_TABAN and v in IZIN_KARAR}
            if temiz:
                self.site_profilleri[str(alan).lower().lstrip(".")] = temiz

    @staticmethod
    def _alan(url: str) -> str:
        from urllib.parse import urlparse
        try:
            return (urlparse(url or "").hostname or "").lower()
        except ValueError:
            return ""

    def eylem_izni(self, kategori: str, url: str) -> tuple[str, str]:
        """(izin|sor|yasak, gerekce kaynagi) dondurur.

        Adres okunamiyorsa varsayilan profil uygulanir — bilinmeyen konum
        guvenli sayilmaz, site istisnalari yalnizca adi bilinen siteye isler.
        """
        alan = self._alan(url)
        if alan:
            for site, ayar in self.site_profilleri.items():
                if alan == site or alan.endswith("." + site):
                    if kategori in ayar:
                        return ayar[kategori], site
        return self.eylem_varsayilan.get(kategori, EYLEM_TABAN.get(kategori, "sor")), "varsayilan"

    def url_dogrula(self, url: str) -> Karar:
        """Adresi beyaz listeye karsi kontrol eder. Liste disi = DENY."""
        from urllib.parse import urlparse, unquote

        try:
            p = urlparse(url)
        except ValueError:
            return Karar(DENY, f"'{url}' cozumlenemeyen bir adres.")

        if p.scheme == "file":
            # file:///D:/... -> D:\...
            ham_yol = unquote(p.path).lstrip("/")
            yerel = self.yol_dogrula(ham_yol, "oku")
            if yerel.sonuc == DENY:
                return Karar(DENY, f"Yerel dosya reddedildi: {yerel.gerekce}")
            if not any(yerel.yol == k or k in yerel.yol.parents for k in self.izinli_yerel):
                liste = ", ".join(str(k) for k in self.izinli_yerel)
                return Karar(DENY, f"'{ham_yol}' tarayicida acilabilir kokler disinda. Izinli: {liste}")
            return Karar(ALLOW, "izinli yerel dosya")

        if p.scheme not in ("http", "https"):
            return Karar(DENY, f"'{p.scheme}' protokolu desteklenmiyor. Sadece http, https, file.")

        alan = (p.hostname or "").lower()
        if not alan:
            return Karar(DENY, f"'{url}' icinde alan adi yok.")

        # tam eslesme veya alt alan: docs.example.com, example.com listesindeyse gecer
        if not any(alan == a or alan.endswith("." + a) for a in self.izinli_alanlar):
            liste = ", ".join(self.izinli_alanlar) or "(liste bos)"
            return Karar(DENY,
                f"'{alan}' izinli site listesinde degil. Izinli alanlar: {liste}. "
                f"Kullanici bu siteyi policy.toml icine eklemeden acilamaz.")

        return Karar(ALLOW, f"izinli site: {alan}")

    def kod_koku_yazilabilir_mi(self, kod_koku: Path) -> str | None:
        """Ajan kendi kaynak kodunu degistirebiliyor mu? Ihlal varsa sebep dondurur.

        Kapi, kapiyi acan tarafindan duzenlenemez. Bu kuralin dosya sistemi
        karsiligi: Pevrai'nin .py dosyalari yazma koklerinin ICINDE olmamali.
        Icinde olsalardi write_file ile onay mekanizmasini degistirmek kapidan
        ALLOW alirdi — kapi yolun izinli olup olmadigina bakar, dosyanin ne
        oldugunu bilmez.

        Kontrol yalnizca .py dosyalarini degil, sistem talimatini besleyen
        config/ klasorunu de kapsar.
        """
        try:
            kok = Path(kod_koku).expanduser().resolve()
        except (OSError, ValueError):
            return f"Kaynak kod dizini cozulemedi: {kod_koku}"

        for aday in kod_kokleri(kok):
            ihlal = korunan_yol_ihlali(self.yazma, aday)
            if ihlal:
                return ihlal + (" policy.toml'daki yazma_koklari listesini daralt "
                                "ya da kodu disari tasi.")
        return None

    @property
    def calisma(self) -> Path | None:
        """Calisma klasoru: tarayici indirme klasoru olmayan ilk yazma koku.
        None = kullanici calisma klasoru secmedi (zorunlu degil)."""
        from pevrai.journal import INEN
        inen = INEN.expanduser().resolve()
        return next((y for y in self.yazma if y != inen), None)

    def karar(self, arac: str, args: dict, aktif_url: str = "", profil: str | None = None) -> Karar:
        """Izin kapisinin tek giris noktasi. profil verilirse ve temel karar
        ASK ise, profilin KAPSAMI (araclar + yazma_koklari) araci kapsiyorsa
        ALLOW'a gevsetilir — DENY'e ASLA dokunulmaz, ASK olmayan bir karara
        da dokunulmaz. Profil onceden imzalanmis bir onaydir, yeni bir
        yetki degil (bkz. DEVIR_FAZ7.md §5.1).
        """
        temel = self._temel_karar(arac, args, aktif_url)
        if profil is None or temel.sonuc != ASK:
            return temel
        p = self.profiller.get(profil)
        if p is None:
            return temel   # taninmayan profil -> hicbir sey GEVSEMEZ (guvenli varsayilan)
        if not p["araclar"] or arac not in p["araclar"]:
            # Hem "araclar alani yok" (None) hem "araclar = []" (bos) burada
            # ayni sonucu veriyor: HICBIR SEY GEVSEMEZ. Ikisi arac
            # GORUNURLUGUNDE ayrisiyor, izin GEVSETMEDE degil — bir profil
            # hicbir bicimde izin genisletemez.
            return temel   # profil bu araci kapsamiyor -> normal ASK kalir
        if temel.yol is not None and not any(
                temel.yol == k or k in temel.yol.parents for k in p["yazma_koklari"]):
            return temel   # yol profilin yazma_koklari KAPSAMI DISINDA -> ASK kalir
        return Karar(ALLOW,
                     f"'{arac}' profil '{profil}' kapsaminda onceden onayli (ASK -> ALLOW)",
                     temel.yol)

    def _temel_karar(self, arac: str, args: dict, aktif_url: str = "") -> Karar:
        risk = self.araclar.get(arac)
        if risk is None:
            return Karar(DENY, t("'{arac}' aracı politikada tanımlı değil. "
                                 "policy.toml'a eklenmeden çalışmaz.", arac=arac))

        varsayilan = RISK_VARSAYILAN.get(risk)
        if varsayilan is None:
            return Karar(DENY, t("'{arac}' için bilinmeyen risk seviyesi: {risk}", arac=arac, risk=risk))

        if arac == "browser_open":
            url_karari = self.url_dogrula(args.get("url", ""))
            if url_karari.sonuc == DENY:
                return url_karari

        # Tarayıcı eylemleri: kategori + site profiline göre karar.
        # Bu katman risk seviyesinin ÜSTÜNDE çalışır ve hem sıkılaştırabilir
        # hem gevşetebilir — çünkü kural artık politikada görünür bir tabloda,
        # kodun içinde gizli bir istisna değil.
        kategori = eylem_kategorisi(arac, args)
        if kategori:
            # browser_open'da hedef adres, diğerlerinde açık olan sayfa esas alınır.
            olculen = args.get("url", "") if arac == "browser_open" else aktif_url
            izin, kaynak = self.eylem_izni(kategori, olculen)
            alan = self._alan(olculen) or t("bilinmeyen adres")
            if izin == "yasak":
                return Karar(DENY, t("'{kategori}' bu ayarlarda yasak ({alan}, kural: {kaynak}). "
                                     "Ayarlar > Tarayıcı bölümünden değiştirilebilir.",
                                     kategori=kategori, alan=alan, kaynak=kaynak))
            if izin == "sor":
                return Karar(ASK, t("'{kategori}' onay istiyor ({alan}, kural: {kaynak}).",
                                    kategori=kategori, alan=alan, kaynak=kaynak))
            return Karar(ALLOW, t("'{kategori}' serbest ({alan}, kural: {kaynak})",
                                  kategori=kategori, alan=alan, kaynak=kaynak))

        bildirim = self.yol_bildirimleri.get(arac) or YOL_BILDIRIMLERI.get(arac)
        if bildirim:
            # Her yol argümanı kendi moduyla doğrulanır; ilk argüman aracın
            # "birincil" yolu (karar.yol olarak araca gider), diğerleri de
            # DENY'de bütün çağrıyı düşürür. move (path+dst), converter.convert
            # (src+dst_dir) ve herhangi bir MCP aracı aynı döngü.
            birincil = None
            for i, (arg, mod) in enumerate(bildirim.items()):
                yol_karari = self.yol_dogrula(args.get(arg, ""), mod)
                if yol_karari.sonuc == DENY:
                    if i == 0:
                        return yol_karari
                    return Karar(DENY, f"'{arg}' reddedildi: {yol_karari.gerekce}")
                if birincil is None:
                    birincil = yol_karari.yol
            return Karar(varsayilan, f"{arac} ({risk})", birincil)

        return Karar(varsayilan, f"{arac} ({risk})")