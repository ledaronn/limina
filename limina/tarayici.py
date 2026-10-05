# tarayici.py — Playwright uzerinden Chrome oturumuna baglanir.
#
# Baglanti KENDINI ONARIR. Onceki surumde sayfa bir kez acilip sonsuza kadar
# onbellekte tutuluyordu; sekme (ya da Chrome) kapaninca her cagri
# "TargetClosedError: Target page, context or browser has been closed" ile
# dusuyordu ve toparlanma yoktu (gozlemlendi). Artik her islem oncesi canlilik
# kontrol ediliyor, kopmus oturum bir kez yeniden kuruluyor.
from __future__ import annotations
from limina.sonuc import hata as sonuc_hatasi

import base64
import json
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path


from limina import PROJE_KOKU
from limina.ceviri import t

CDP_PORT = 9222
CDP_ADRES = f"http://localhost:{CDP_PORT}"
MAX_METIN = 12000
PROFIL = PROJE_KOKU / "chrome-profil"
CHROME_ADAYLARI = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def _port_acik(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def ayni_oturum_mu(aktif_port_metni: str, surum_json: str, port: int = CDP_PORT) -> bool:
    """Portta dinleyen Chrome, BIZIM profil klasorumuzle acilan Chrome mu? Saf.

    Chrome her acilista <user-data-dir>/DevToolsActivePort dosyasina iki
    satir yazar: dinledigi port ve benzersiz (GUID'li) WebSocket yolu.
    /json/version'in dondurdugu webSocketDebuggerUrl ayni yolu tasir. Ikisi
    eslesiyorsa port bizim profilimize ait; eslesmiyorsa (ya da dosya yoksa)
    portta BASKA bir Chrome var — kullanicinin kendi tarayicisi olabilir.

    Neden onemli: eski kod "port acik mi" diye bakip acik olana baglaniyordu.
    Kullanici kendi Chrome'unu --remote-debugging-port=9222 ile acmissa ajan
    onun giris yapilmis oturumuna (cerezler, hesaplar) baglanir ve
    browser_read ilk acik sekmesini okurdu. Ayri profil (chrome-profil/)
    tam bunu onlemek icin vardi; port kontrolu onu deliyordu.
    """
    satirlar = [x.strip() for x in aktif_port_metni.splitlines() if x.strip()]
    if len(satirlar) < 2 or satirlar[0] != str(port):
        return False
    try:
        ws = json.loads(surum_json).get("webSocketDebuggerUrl", "")
    except (ValueError, AttributeError):
        return False
    yol = satirlar[1] if satirlar[1].startswith("/") else "/" + satirlar[1]
    return bool(ws) and ws.endswith(yol)


def _dinleyen_pid(port: int) -> int | None:
    """Portta LISTENING durumundaki surecin PID'i (Windows: netstat -ano)."""
    try:
        cikti = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                               timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except Exception:
        return None
    for satir in cikti.splitlines():
        parcalar = satir.split()
        if len(parcalar) >= 5 and parcalar[0] == "TCP" and parcalar[1].endswith(f":{port}")                 and parcalar[3].upper() == "LISTENING":
            try:
                return int(parcalar[4])
            except ValueError:
                return None
    return None


def _surec_komutu(pid: int) -> str:
    """PID'in komut satiri (Windows: CIM). Alinamazsa bos dize."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}').CommandLine"],
            capture_output=True, text=True, timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return (r.stdout or "").strip()
    except Exception:
        return ""


def komut_bizim_profilde_mi(komut: str, profil: Path = PROFIL) -> bool:
    """Chrome komut satirinda --user-data-dir=<bizim profil> var mi? Saf."""
    if not komut:
        return False
    k = komut.lower().replace("/", "\\")
    hedef = str(profil).lower().replace("/", "\\").rstrip("\\")
    return (f"--user-data-dir={hedef}" in k) or (f'--user-data-dir="{hedef}"' in k)


def _bizim_chrome_mu() -> bool:
    """Acik porttaki Chrome'un sahibini dogrular. Iki kanit yolu:

    1) <profil>/DevToolsActivePort <-> /json/version ws yolu (eski Chrome'lar yazar)
    2) Portta dinleyen surecin komut satirinda --user-data-dir=<bizim profil>
       (Chrome 152'de DevToolsActivePort artik yazilmiyor — olculdu; yalnizca
       1'e guvenmek kendi Chrome'umuzu reddediyordu)
    Ikisi de tutmazsa BAGLANILMAZ.
    """
    try:
        metin = (PROFIL / "DevToolsActivePort").read_text(encoding="utf-8")
        with urllib.request.urlopen(f"{CDP_ADRES}/json/version", timeout=2) as y:
            if ayni_oturum_mu(metin, y.read().decode("utf-8", errors="replace")):
                return True
    except Exception:
        pass
    pid = _dinleyen_pid(CDP_PORT)
    if pid is None:
        return False
    return komut_bizim_profilde_mi(_surec_komutu(pid))


def _chrome_yolu() -> str | None:
    for aday in CHROME_ADAYLARI:
        if Path(aday).exists():
            return aday
    return shutil.which("chrome")


class Tarayici:
    """Tek bir Playwright oturumu tutar. Ilk kullanimda baglanir."""

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._sayfa = None
        self._surec = None

    def _chrome_baslat(self) -> str | None:
        """Debug portu kapaliysa Chrome'u kendi profilimizle baslatir.

        Port ACIKSA once sahibine bakilir: bizim profilimizle acilmis Chrome
        degilse (bkz. ayni_oturum_mu) BAGLANMAYIZ — kullanicinin kendi
        oturumuna girmek yerine acik bir hata metni doner.
        """
        if _port_acik(CDP_PORT):
            if _bizim_chrome_mu():
                return None
            return sonuc_hatasi(t("{port} portunda Limina'nın başlatmadığı bir Chrome var; güvenlik gereği ona "
                     "bağlanılmıyor (kullanıcının kendi oturumu olabilir). O Chrome'u kapat ya da "
                     "--remote-debugging-port olmadan aç; Limina kendi profiliyle yenisini başlatır.",
                     port=CDP_PORT))

        yol = _chrome_yolu()
        if yol is None:
            return sonuc_hatasi(t("Chrome bulunamadı. Beklenen konumlar: {liste}. Kurulu değilse tarayıcı "
                     "araçları kullanılamaz.", liste=", ".join(CHROME_ADAYLARI)))

        PROFIL.mkdir(parents=True, exist_ok=True)
        try:
            # Liste arguman, shell=True yok. Ayri profil: ana Chrome oturumlarina dokunmaz.
            self._surec = subprocess.Popen(
                [yol,
                 f"--remote-debugging-port={CDP_PORT}",
                 f"--user-data-dir={PROFIL}",
                 "--allow-file-access-from-files",
                 "--no-first-run",
                 "--no-default-browser-check"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            return sonuc_hatasi(t("Chrome başlatılamadı: {hata}", hata=e))

        for _ in range(20):          # en fazla 10 saniye bekle
            if _port_acik(CDP_PORT):
                return None
            time.sleep(0.5)
        return sonuc_hatasi(t("Chrome başlatıldı ama {port} portu 10 saniyede açılmadı.", port=CDP_PORT))

    # ------------------------------------------------------------------
    # Baglanti yasam dongusu
    # ------------------------------------------------------------------
    def _sayfa_canli(self) -> bool:
        try:
            return self._sayfa is not None and not self._sayfa.is_closed()
        except Exception:
            return False

    def _browser_canli(self) -> bool:
        try:
            return self._browser is not None and self._browser.is_connected()
        except Exception:
            return False

    def _temizle(self, tam: bool) -> None:
        """Sayfayi (tam=False) ya da butun Playwright oturumunu (tam=True) birakir."""
        self._sayfa = None
        if not tam:
            return
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._pw = self._browser = None

    def _sayfa_tazele(self) -> str | None:
        """Baglanti ayakta ama sekme kapanmis: acik bir sekme bul, yoksa yenisini ac."""
        try:
            ctx = (self._browser.contexts[0] if self._browser.contexts
                   else self._browser.new_context())
            for sayfa in ctx.pages:
                if not sayfa.is_closed():
                    self._sayfa = sayfa
                    return None
            self._sayfa = ctx.new_page()
            return None
        except Exception as e:
            self._temizle(tam=True)
            return sonuc_hatasi(t("Yeni sekme açılamadı ({tur}: {hata}).", tur=type(e).__name__, hata=e))

    def _baglan(self) -> str | None:
        """Calisir bir sayfa garantiler. Hata varsa metin dondurur, yoksa None."""
        if self._browser_canli() and self._sayfa_canli():
            return None

        # Baglanti duruyorsa Chrome'u yeniden baslatmaya gerek yok: sadece sekme olmus.
        if self._browser_canli():
            hata = self._sayfa_tazele()
            if hata is None:
                return None

        self._temizle(tam=True)
        hata = self._chrome_baslat()
        if hata:
            return hata
        try:
            # Playwright TEMBEL: paket yalnizca tarayici gercekten kullanilinca
            # gerekir. pip install -e .[tarayici] kurulmadan da Limina acilir;
            # tarayici araci cagrilinca anlasilir bir metin doner.
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                return sonuc_hatasi(t("Tarayıcı araçları için Playwright kurulu değil: pip install -e .[tarayici] "
                         "(python -m playwright install chromium gerekmez, sistem Chrome'u kullanılır). "
                         "Bu araç şu an kullanılamaz."))
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.connect_over_cdp(CDP_ADRES)
            ctx = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
            acik = [s for s in ctx.pages if not s.is_closed()]
            self._sayfa = acik[0] if acik else ctx.new_page()
            return None
        except Exception as e:
            self._temizle(tam=True)
            return sonuc_hatasi(t("Tarayıcıya bağlanılamadı ({tur}: {hata}). Chrome'un --remote-debugging-port=9222 "
                     "ile açık olduğundan emin ol. Bu araç şu an kullanılamaz, başka bir yol dene.",
                     tur=type(e).__name__, hata=e))

    @staticmethod
    def _oturum_koptu(e: Exception) -> bool:
        """Hata 'sayfa/tarayici kapandi' turunden mi? Oyleyse yeniden denemeye deger."""
        imza = f"{type(e).__name__}: {e}".lower()
        return any(k in imza for k in (
            "targetclosed", "target page", "has been closed", "connection closed",
            "browser has been closed", "websocket", "target crashed",
        ))

    def _yurut(self, hata_onu: str, gorev):
        """Islemi calistirir; oturum koptuysa BIR KEZ yeniden baglanip tekrar dener.

        Tek deneme bilincli: kalici bir sorunda modeli sonsuz dongude tutmak
        yerine acik bir hata metni donmek daha iyi — model alternatif arar.
        """
        hata = self._baglan()
        if hata:
            return hata
        try:
            return gorev()
        except Exception as e:
            if not self._oturum_koptu(e):
                return sonuc_hatasi(t("{onek} ({tur}: {hata}).", onek=hata_onu, tur=type(e).__name__, hata=e))
            self._temizle(tam=False)
            hata = self._baglan()
            if hata:
                return hata
            try:
                return gorev()
            except Exception as e2:
                return sonuc_hatasi(t("{onek} ({tur}: {hata}). Oturum yeniden kuruldu ama işlem yine başarısız oldu.",
                         onek=hata_onu, tur=type(e2).__name__, hata=e2))

    def ekran_goruntusu(self, kalite: int = 55) -> str | None:
        """Gorunur alanin JPEG karesi, base64. Basarisizsa None.

        Model baglamina GIRMEZ, yalnizca arayuze gider — kare basina 100+ KB
        baglam butcesini bir adimda tuketirdi. JPEG secildi: PNG'nin birkac
        kati kucuk ve arayuzde fark edilmiyor.
        """
        if not (self._browser_canli() and self._sayfa_canli()):
            return None
        try:
            ham = self._sayfa.screenshot(type="jpeg", quality=kalite, full_page=False,
                                         timeout=5000)
            return base64.b64encode(ham).decode("ascii")
        except Exception:
            return None

    def durum(self) -> dict:
        """Arayuzun tarayici panelinde gosterecegi anlik durum."""
        if not (self._browser_canli() and self._sayfa_canli()):
            return {"acik": False}
        try:
            return {"acik": True, "url": self._sayfa.url, "baslik": self._sayfa.title()}
        except Exception:
            return {"acik": False}

    def ac(self, url: str) -> str:
        def git():
            self._sayfa.goto(url, wait_until="domcontentloaded", timeout=30000)
            return t("Sayfa açıldı: {baslik} ({url})", baslik=self._sayfa.title(), url=self._sayfa.url)
        return self._yurut(t("'{url}' açılamadı", url=url), git)

    def oku(self) -> str:
        def topla():
            # innerText: gorunur metin. Gizli/beyaz-uzerine-beyaz metni de icerebilir,
            # bu yuzden cikti her durumda untrusted olarak isaretlenir.
            return (self._sayfa.evaluate("() => document.body.innerText"),
                    self._sayfa.url, self._sayfa.title())

        sonuc = self._yurut(t("Sayfa okunamadı"), topla)
        if isinstance(sonuc, str):
            return sonuc
        metin, url, baslik = sonuc

        metin = (metin or "").strip()
        if not metin:
            return t("'{url}' sayfasında okunabilir metin yok (JS ile yüklenen bir sayfa olabilir).", url=url)

        kirpildi = ""
        if len(metin) > MAX_METIN:
            metin = metin[:MAX_METIN]
            kirpildi = "\n" + t("[... sayfa metni kırpıldı, ilk {n} karakter gösteriliyor]", n=MAX_METIN)

        # Sayfa kendi kapanis etiketini yazip sarmaldan CIKAMASIN (bkz.
        # mcp_bridge.dis_kaynak — ayni acik, ayni duzeltme).
        metin = metin.replace("</untrusted_content>", "<\\/untrusted_content>")

        return (
            f"<untrusted_content source=\"{url}\" title=\"{baslik}\">\n"
            f"{metin}{kirpildi}\n"
            f"</untrusted_content>"
        )

    def anlik_goruntu(self) -> str:
        """Sayfanin ARIA agacini dondurur. Etkilesimli ogeler rol+ad ile gorunur."""
        def topla():
            return (self._sayfa.locator("body").aria_snapshot(), self._sayfa.url)

        sonuc = self._yurut(t("Anlık görüntü alınamadı"), topla)
        if isinstance(sonuc, str):
            return sonuc
        agac, url = sonuc

        agac = (agac or "").strip()
        if not agac:
            return t("'{url}' sayfasında erişilebilir öge bulunamadı.", url=url)
        if len(agac) > MAX_METIN:
            agac = agac[:MAX_METIN] + "\n" + t("[... ağaç kırpıldı, ilk {n} karakter]", n=MAX_METIN)

        agac = agac.replace("</untrusted_content>", "<\\/untrusted_content>")

        return (f"<untrusted_content source=\"{url}\" type=\"aria_snapshot\">\n"
                f"{agac}\n</untrusted_content>")

    ADAY_AZAMI = 10

    def _adaylar(self, konum, sayi: int) -> list[str]:
        """Belirsiz bir eslesmenin adaylarinin ERISILEBILIR ADLARI (aria-label >
        gorunur metin > title), en fazla ADAY_AZAMI. Okunamayan aday '(ad
        okunamadi)' olarak girer — liste yalan soylemesin diye."""
        adlar: list[str] = []
        for i in range(min(sayi, self.ADAY_AZAMI)):
            try:
                ham = konum.nth(i).evaluate(
                    "e => (e.getAttribute('aria-label') || e.innerText || "
                    "e.getAttribute('title') || '').trim()")
                ad = " ".join(str(ham).split())[:80] or "(bos ad)"
            except Exception:
                ad = "(ad okunamadi)"
            adlar.append(ad)
        return adlar

    def _oge(self, rol: str, ad: str):
        """Rol ve ada gore TEK bir oge bulur. Bulamazsa ya da birden fazlaysa
        None + sebep — ve sebep, modelin ikinci cagrida DOGRU SECIM yapmasina
        yetecek veriyi tasir.

        Iki asamali esleme:
          1. exact=True  — verilen ad bir ogenin TAM erisilebilir adiysa ve tek
             ise onu al. Model bir onceki hatadan gelen aday listesinden tam
             ad secip tekrar cagirdiginda buradan gecer.
          2. exact=False — alt dize. Tek eslesme varsa al; birden fazlaysa
             TIKLAMA, ADAYLARI LISTELE.

        Faz 7 olcumunde (DEVIR_FAZ7.md §9, M4 yan bulgusu) bir Wikipedia
        makalesinde 'Bitki' 17, 'Kloroplast' 6 ogeyle eslesti ve arac "belirsiz,
        daha ayirt edici bir ad kullan" diyordu — dogru davranis (belirsizken
        tiklamamak) ama modelin elinde SECEBILECEGI hicbir sey yoktu, her
        belirsizlikte bir adim kaybediyordu. Bu, read_file'in "yol bulunamadi ->
        klasordeki komsu adlar" deseninin aynisi: hata mesaji modelin
        duzeltebilecegi bilgiyi TASIMALI.
        """
        try:
            tam = self._sayfa.get_by_role(rol, name=ad, exact=True)
            if tam.count() == 1:
                return tam.first, None
            konum = self._sayfa.get_by_role(rol, name=ad, exact=False)
            sayi = konum.count()
        except Exception as e:
            return None, t("'{rol}' geçerli bir rol değil ({hata}). Rolleri browser_snapshot çıktısından al.",
                           rol=rol, hata=e)

        if sayi == 0:
            return None, t("'{rol}' rolünde '{ad}' adlı öge bulunamadı. Sayfa değişmiş olabilir — "
                           "browser_snapshot ile güncel ağacı al.", rol=rol, ad=ad)
        if sayi > 1:
            adlar = self._adaylar(konum, sayi)
            tekrar = sum(1 for a in adlar if adlar.count(a) > 1)
            liste = "; ".join(f"[{i}] {a}" for i, a in enumerate(adlar, 1))
            kuyruk = (" " + t("(ilk {n} gösterildi)", n=self.ADAY_AZAMI)) if sayi > self.ADAY_AZAMI else ""
            uyari = (" " + t("DİKKAT: bazı adayların adı AYNI, tam ad da ayırt etmez — "
                             "browser_snapshot ile bağlamına bak.")) if tekrar else ""
            return None, (t("'{rol}' rolünde '{ad}' adıyla {sayi} öge var, TIKLANMADI. "
                            "Adaylar (tam ad): {liste}{kuyruk}. Birini TAM ADIYLA tekrar çağır.",
                            rol=rol, ad=ad, sayi=sayi, liste=liste, kuyruk=kuyruk) + uyari)
        return konum.first, None

    def tikla(self, rol: str, ad: str) -> str:
        hata = self._baglan()   # _yurut kullanilmiyor: oge arama sayfaya bagli,
                                # kopan oturumda yeniden aranmasi gerekir
        if hata:
            return hata
        oge, sebep = self._oge(rol, ad)
        if oge is None:
            return sebep
        try:
            oge.click(timeout=10000)
            self._sayfa.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception as e:
            return sonuc_hatasi(t("Tıklanamadı ({tur}: {hata}). Öge görünür ve etkin mi?", tur=type(e).__name__, hata=e))
        return t("'{ad}' tıklandı. Sayfa: {baslik} ({url}). Yeni durumu görmek için browser_snapshot çağır.",
                 ad=ad, baslik=self._sayfa.title(), url=self._sayfa.url)

    def doldur(self, rol: str, ad: str, metin: str) -> str:
        hata = self._baglan()
        if hata:
            return hata
        oge, sebep = self._oge(rol, ad)
        if oge is None:
            return sebep

        # Parola alanina asla yazilmaz — model isterse bile.
        try:
            tip = (oge.get_attribute("type") or "").lower()
            oge_adi = ((oge.get_attribute("name") or "") + (oge.get_attribute("id") or "")).lower()
        except Exception:
            tip, oge_adi = "", ""

        if tip == "password" or any(k in oge_adi for k in ("password", "passwd", "sifre", "parola")):
            return sonuc_hatasi(t("Bu bir parola alanı. Ajan parola girmez — bu kural aşılamaz. "
                     "Giriş yapılması gerekiyorsa kullanıcı kendisi yapmalı."))
        if tip in ("hidden",):
            return sonuc_hatasi(t("Gizli bir alana yazılamaz."))

        try:
            oge.fill(metin, timeout=10000)
        except Exception as e:
            return sonuc_hatasi(t("Yazılamadı ({tur}: {hata}).", tur=type(e).__name__, hata=e))
        return t("'{ad}' alanına yazıldı ({n} karakter). Göndermek için kullanıcı onayı gerekir.",
                 ad=ad, n=len(metin))

    def indir(self, rol: str, ad: str, hedef_dir: Path, izinli_uzantilar: set[str]) -> str:
        """Bir link/butona tiklar ve indirmeyi bekler. Dosya ara klasore iner."""
        hata = self._baglan()
        if hata:
            return hata
        oge, sebep = self._oge(rol, ad)
        if oge is None:
            return sebep

        hedef_dir.mkdir(parents=True, exist_ok=True)
        try:
            with self._sayfa.expect_download(timeout=60000) as bekleyen:
                oge.click(timeout=10000)
            indirme = bekleyen.value
        except Exception as e:
            return sonuc_hatasi(t("İndirme başlamadı ({tur}: {hata}). Bu öge bir dosya indirme bağlantısı "
                     "olmayabilir; normal gezinme için browser_click kullan.", tur=type(e).__name__, hata=e))

        onerilen = Path(indirme.suggested_filename or "indirilen")
        uzanti = onerilen.suffix.lower()

        if uzanti not in izinli_uzantilar:
            indirme.cancel()
            return sonuc_hatasi(t("İndirme iptal edildi: '{ad}' uzantısı ({uzanti}) izinli listede değil. "
                     "İzinli: {liste}. Çalıştırılabilir dosyalar hiçbir koşulda indirilmez.",
                     ad=onerilen.name, uzanti=uzanti or t("yok"), liste=", ".join(sorted(izinli_uzantilar))))

        hedef = hedef_dir / onerilen.name
        sayac = 1
        while hedef.exists():
            hedef = hedef_dir / f"{onerilen.stem}_{sayac}{onerilen.suffix}"
            sayac += 1

        try:
            indirme.save_as(str(hedef))
        except Exception as e:
            return sonuc_hatasi(t("Dosya kaydedilemedi ({tur}: {hata}).", tur=type(e).__name__, hata=e))

        boyut = hedef.stat().st_size
        return t("İndirildi: {hedef} ({bayt} bayt). Bu bir ARA klasördür — kalıcı yerine taşımak "
                 "için move kullan. İçeriğini okumak için read_document kullan.", hedef=hedef, bayt=boyut)

    def kapat(self) -> None:
        """Oturumu birakir. YALNIZCA baglantiyi kuran thread'den cagrilmali.

        _temizle kullaniliyor: nesneler de None'a cekilsin. Aksi halde kapanmis
        bir tarayiciya is_connected() sorulup yeni bir hata uretilebiliyordu.
        """
        self._temizle(tam=True)