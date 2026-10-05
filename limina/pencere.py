# pencere.py — Faz 5b/5c. pywebview penceresi ve JS'e acilan tek yuzey.
#
# Ajan dongusunu dogrudan cagirmaz; her sey gui_kopru.Kopru uzerinden gecer.
from __future__ import annotations

import sys
import threading
from datetime import datetime
import tomllib
from pathlib import Path
from typing import Any

import webview

from limina import PAKET, PROJE_KOKU, ayarlar, ceviri, journal
from limina.gate import Politika
from limina.gui_kopru import Kopru
from limina.olaylar import daraltma_guncelle

KOK = PROJE_KOKU                       # policy.toml, config/
ARAYUZ = PAKET / "arayuz" / "index.html"
# Pencere/baslik cubugu ikonu. Verilmezse pywebview (WinForms) ikonu calisan
# yorumlayicinin exe'sinden cikarir — baslik cubugunda Python logosu gorunur
# ve uygulama "bir Python programi" gibi durur. webview.start(icon=...) docs'ta
# "GTK/QT" dese de winforms.py 6.2.1'de dosya varsa self.Icon'a yukluyor
# (dogrulandi: platforms/winforms.py, "Application icon" blogu).
IKON = PAKET / "arayuz" / "limina.ico"

# Baglam doluluk barinin paydasi. Simdilik sabit; Faz 6'da policy.toml'a tasinir.
BAGLAM_PENCERESI = 1_000_000


def _pano_dosyalari() -> list[str]:
    """Windows panosundaki dosya yollarini okur (Explorer'da 'Kopyala' ile
    konan CF_HDROP). Tarayici clipboard API'si bunu vermez — DnD icin
    kullandigimiz pywebviewFullPath da yalnizca surukle-birakta gelir, Ctrl+V
    icin ayri bir yol gerekir. Windows disinda ya da panoda dosya yoksa bos liste."""
    if sys.platform != "win32":
        return []
    import ctypes

    user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
    CF_HDROP = 15
    yollar: list[str] = []
    try:
        if not user32.OpenClipboard(None):
            return []
        try:
            h_drop = user32.GetClipboardData(CF_HDROP)
            if h_drop:
                adet = shell32.DragQueryFileW(h_drop, 0xFFFFFFFF, None, 0)
                for i in range(adet):
                    uzunluk = shell32.DragQueryFileW(h_drop, i, None, 0)
                    arabellek = ctypes.create_unicode_buffer(uzunluk + 1)
                    shell32.DragQueryFileW(h_drop, i, arabellek, uzunluk + 1)
                    if arabellek.value:
                        yollar.append(arabellek.value)
        finally:
            user32.CloseClipboard()
    except Exception:
        return []
    return yollar


class Api:
    """JS'in cagirabildigi tek yuzey. pywebview her metodu js_api olarak acar.

    Butun metotlar UI thread'inden cagrilir ve ASLA bloke olmaz — ajan arka
    plandaki thread'inde bekler, buradaki cagrilar sadece kuyruga dokunur.
    """

    # JS'in gormesi gerekmeyen HER alan alt cizgiyle baslar. pywebview, js_api
    # nesnesinin acik alanlarini tarayarak JS'e acar; buraya bir pencere/kontrol
    # nesnesi konursa WinForms agacina dalip sonsuz ozyinelemeye giriyor
    # (gozlemlendi: "maximum recursion depth exceeded").
    def __init__(self, politika: Politika) -> None:
        self._kopru = Kopru()
        self._politika = politika
        self._pencere = None          # webview penceresi, main() icinde atanir
        self._surukle_destegi = False
        self._ekler: list[str] = []  # goreve iliştirilmis dosya yollari
        self._model_listesi: dict | None = None   # arka plandan gelen liste
        self._model_cekiliyor = False
        from limina.okuma import ReaderLink
        self._okuma = ReaderLink()
        self._okuma_kilit = threading.Lock()

    # ------------------------------------------------------------------
    # gorev
    # ------------------------------------------------------------------
    def eklenti_katalog(self) -> dict:
        try:
            from limina.eklentiler.registry import catalog
            return {"ok": True, "plugins": catalog(self._politika)}
        except ImportError:
            return {"ok": True, "plugins": []}

    def not_taslaklari(self) -> dict:
        from limina import taslak
        try:
            return {"ok": True, "taslaklar": taslak.oku()}
        except Exception as exc:
            return {"ok": False, "hata": str(exc)}

    def not_taslak_yaz(self, kimlik: str, veri=None) -> dict:
        from limina import taslak
        try:
            taslak.yaz(str(kimlik), veri)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "hata": str(exc)}

    def sohbet_projesi(self, kimlik=None) -> dict:
        from limina.eklentiler.registry import invoke
        try:
            proje = None
            if kimlik:
                row = invoke("workspace_get", {"id": str(kimlik)}, self._politika)
                proje = {"id": row["id"], "name": row["name"]}
            self._kopru.oturum.proje_baglami = proje
            self._kopru._kaydet(self._kopru._aktif)
            return {"ok": True, "proje_baglami": proje}
        except Exception as exc:
            return {"ok": False, "hata": str(exc)}

    def eklenti_cagir(self, ad: str, args: dict) -> dict:
        """Direct user actions use the same validators/services without a model call."""
        try:
            from limina.eklentiler.registry import invoke
            return {"ok": True, "result": invoke(ad, args, self._politika, actor="user")}
        except Exception as exc:
            return {"ok": False, "hata": str(exc)}

    def eklenti_ayarla(self, ad: str, enabled: bool) -> dict:
        from limina.eklentiler.registry import CATALOG, available
        if ad not in CATALOG or not available(ad):
            return {"ok": False, "hata": ceviri.t("Eklenti dosyaları bulunamadı.")}
        if self._kopru.calisiyor():
            return {"ok": False, "hata": ceviri.t("Önce çalışan görevi durdur.")}
        hata = ayarlar.paket_geri_ekle(ad) if enabled else ayarlar.paket_kaldir(ad)
        if hata is None:
            self._politika = Politika(KOK / "policy.toml")
            # Do not import/start the agent or MCP servers just to use local panels.
            vekil = sys.modules.get("limina.vekil_v0")
            if vekil is not None:
                vekil.POLITIKA = self._politika
                vekil.arac_semalarini_tazele(sessiz=True)
        return {"ok": hata is None, "hata": hata}

    def gorev_baslat(self, gorev: str, mod: str | None = None, ekip=False, model: str = "",
                     gosterim: str | None = None) -> dict:
        """Sohbet modu artik AYRI bir parametre DEGIL: arayuzdeki anahtar
        Araclar panelinin "hepsini kapat" durumunu kuruyor (araclar_hepsi) ve
        gorev o daraltmayla kosuyor. Eski yol (sohbet_modu bayragi -> 'sohbet'
        profili) kaldirildi: iki mekanizma iki yerde ayni seyi yapiyordu."""
        gorev = (gorev or "").strip()
        if not gorev:
            return {"ok": False, "hata": ceviri.t("Görev boş.")}

        # Eklenen dosyalar goreve TAM YOL olarak yazilir; dosya yerinde kalir,
        # kopyalanmaz (ARAYUZ.md 5). Ajan bunlari normal araclarla okur, yani
        # izin kapisi yine devrede — ek eklemek izin vermek degildir.
        ekler = list(self._ekler)
        if ekler:
            satirlar = "\n".join(f"- {y}" for y in ekler)
            gorev = f"{gorev}\n\nIlgili dosyalar:\n{satirlar}"
            if isinstance(gosterim, str):
                gosterim = f"{gosterim}\n\nIlgili dosyalar:\n{satirlar}"

        try:
            # Sohbet ekranindaki model secici ("kimlik/model", bos = otomatik).
            # Zincirde olmayan bir deger yok sayilir (model_zinciri.zincir).
            if not self._kopru.calisiyor():
                self._kopru.oturum.secili_model = str(model or "")[:200]
            # Profil YOK: arayuz profil secemez (profil onceden imzalanmis bir
            # onaydir, JS tarafi policy.toml'daki adlari bilmemeli).
            opts = {"gosterim": gosterim} if isinstance(gosterim, str) else {}
            self._kopru.gorev_baslat(gorev, mod=mod, ekip=ekip if isinstance(ekip, dict) else bool(ekip), **opts)
        except RuntimeError as e:
            return {"ok": False, "hata": str(e)}
        self._ekler = [y for y in self._ekler if y not in ekler]
        return {"ok": True}

    def durdur(self) -> dict:
        self._kopru.durdur()
        return {"ok": True}

    # ------------------------------------------------------------------
    # olay akisi
    # ------------------------------------------------------------------
    def olaylari_cek(self) -> dict:
        """JS bunu periyodik cagirir. Push yerine cekme: pywebview'de arka plan
        thread'inden evaluate_js cagirmak platforma gore guvenilir degil."""
        with self._okuma_kilit:
            olaylar = self._kopru.olaylari_cek()
            try:
                self._okuma.tick(self, olaylar)
            except Exception as exc:
                # Optional reader integration must not break the main event loop.
                if not getattr(self, '_okuma_uyarildi', False):
                    olaylar.append({'tip':'hata','veri':{'mesaj':'Okuma Atölyesi bağlantısı: '+str(exc)}})
                    self._okuma_uyarildi = True
        # Onay olayi kuyruktan BIR KEZ gectigi icin bu da bir kez tetiklenir.
        if any(o.get("tip") == "onay_gerekli" for o in olaylar):
            self._one_al()
        return {
            "olaylar": olaylar,
            "calisiyor": self._kopru.calisiyor(),
            "toplu_onaylar": self._kopru.oturum.aktif_toplu_onaylar(),
            "baglam_penceresi": BAGLAM_PENCERESI,
            "surukle_destegi": self._surukle_destegi,
            "gecmis_koru": self._kopru.oturum.gecmis_koru,
            "sohbet_id": self._kopru._aktif["id"],
            "proje_baglami": self._kopru.oturum.proje_baglami,
            "gecmis_gorev": self._kopru.oturum.gecmis_gorev_sayisi(),
            "kota": self._kota_satirlari(),
            "sohbetler": self._kopru.sohbetler(),
            # Aktif sohbetin arac daraltmasi: sohbet anahtari ve Araclar paneli
            # bunu gosterir. Sohbet degisince kendiliginden dogru degere doner.
            "kapali_araclar": self._kopru.oturum.kapali_araclar(),
            "hepsi_kapali": self._kopru.oturum.hepsi_kapali(),
            # Acilista/kaydetmede biriken uyarilar. Bir kez okunur, sonra silinir.
            "uyarilar": self._kopru.uyarilari_al(),
        }

    # ------------------------------------------------------------------
    # onay
    # ------------------------------------------------------------------
    def onay_cevapla(self, cevap: str) -> dict:
        self._kopru.onay_cevapla(cevap)
        return {"ok": True}

    def okuma_kaynak_ac(self, uri: str) -> dict:
        """Explicit source-link click; only the configured reader can be launched."""
        try:
            return self._okuma.open_source(uri, self._politika)
        except Exception as exc:
            return {'ok':False,'hata':str(exc)}

    def toplu_iptal(self, arac: str | None = None) -> dict:
        self._kopru.oturum.toplu_iptal(arac)
        return {"ok": True}

    # ------------------------------------------------------------------
    # sohbet
    # ------------------------------------------------------------------
    def yeni_sohbet(self) -> dict:
        """Konusmayi ve toplu onaylari sifirlar. Calisan gorev varken reddeder."""
        kimlik = self._kopru.yeni_sohbet()
        if kimlik is None:
            return {"ok": False, "hata": ceviri.t("Önce çalışan görevi durdur: bir görev çalışırken başka sohbete geçilemez.")}
        return {"ok": True, "id": kimlik}

    def sohbetler(self) -> dict:
        return {"ok": True, "sohbetler": self._kopru.sohbetler()}

    def sohbet_ac(self, sohbet_id: str) -> dict:
        """Sohbeti aktif yapar ve arsivini doner; arayuz akisi yeniden kurar."""
        arsiv = self._kopru.sohbet_ac(sohbet_id)
        if arsiv is None:
            return {"ok": False, "hata": ceviri.t("Önce çalışan görevi durdur: bir görev çalışırken başka sohbete geçilemez.")}
        return {"ok": True, "olaylar": arsiv, "proje_baglami": self._kopru.oturum.proje_baglami}

    def sohbet_sil(self, sohbet_id: str) -> dict:
        if not self._kopru.sohbet_sil(sohbet_id):
            return {"ok": False, "hata": ceviri.t("Silinemedi.")}
        return {"ok": True}

    def gecmis_ayari(self, acik: bool) -> dict:
        """Gecmis kapaliyken her gorev bagimsiz bir oturum (CLI davranisi)."""
        self._kopru.oturum.gecmis_koru = bool(acik)
        return {"ok": True, "acik": self._kopru.oturum.gecmis_koru}

    # ------------------------------------------------------------------
    # slash komutlari / bilgi
    # ------------------------------------------------------------------
    def komutlar(self) -> dict:
        """config/komutlar.toml'dan okunur. Sablonlar kod degil, duz metindir."""
        yol = KOK / "config" / "komutlar.toml"
        if not yol.exists():
            return {"ok": True, "komutlar": []}
        try:
            veri = tomllib.loads(yol.read_text(encoding="utf-8"))
        except Exception as e:
            return {"ok": False, "hata": f"komutlar.toml okunamadi: {e}"}
        return {"ok": True, "komutlar": veri.get("komut", [])}

    def karsilama_onerileri(self) -> dict:
        pol = self._politika
        removed = set(getattr(pol, "kaldirilan", []))
        oturum = self._kopru.oturum
        closed = set(oturum.kapali_araclar())
        def enabled(name):
            return name in pol.araclar and name not in closed and not oturum.hepsi_kapali()
        result = []
        if "tarayici" not in removed and pol.izinli_alanlar and enabled("browser_open"):
            result.append(["web", "Web'de ara", "Güncel bilgileri bul", ceviri.t("internette şu konuyu araştır: ")])
        if pol.okuma and enabled("list_dir"):
            result.append(["klasor", "Dosyalarla çalış", "Oku, düzenle, oluştur", ceviri.t("Şu klasördeki dosyaları listele: {yol}", yol=pol.okuma[0])])
        if "dosya_duzenleme" not in removed and pol.calisma and enabled("rename") and enabled("list_dir"):
            result.append(["bilgisayar", "Bilgisayarını kontrol et", "Taşı, dönüştür, adlandır", ceviri.t("Şu yazılabilir klasördeki dosyaları düzenle: {yol}", yol=pol.calisma)])
        result.append(["fikir", "Fikir geliştir", "Planla, analiz et", ceviri.t("bana şu konuda yardım et: ")])
        return {"ok": True, "oneriler": result}

    def siteler(self) -> dict:
        """Tarayicinin acabilecegi alan adlari. SALT OKUNUR — buradan degistirilemez;
        policy.toml'a yazan bir yol arayuze bilincli olarak acilmadi."""
        alanlar = list(getattr(self._politika, "izinli_alanlar", []) or [])
        return {"ok": True, "alanlar": alanlar}

    def modeller(self) -> dict:
        return {
            "ok": True,
            "varsayilan": getattr(self._politika, "model_varsayilan", "?"),
            "guclu": getattr(self._politika, "model_guclu", "?"),
        }

    def _mevcut_araclar(self) -> frozenset[str]:
        """Modele gosterilebilecek araclar: policy.toml'da siniflandirilmis VE
        kesfedilmis (ARAC'ta semasi var). Panelin daraltabilecegi kume budur;
        disina cikilamaz."""
        from limina import vekil_v0
        # Politikada olmayan yerel arac (kaldirilmis paket) panelden acilamaz.
        return vekil_v0.gosterilen_araclar(vekil_v0.ARAC) & frozenset(self._politika.araclar)

    # ------------------------------------------------------------------
    # paketler: kullaniciya gorunen arac gruplari (limina.paketler)
    # ------------------------------------------------------------------
    def paketler(self) -> dict:
        """Araclar panelinin kartlari: yerlesik paketler + MCP sunuculari, her
        aracin insan dilindeki adi/aciklamasi, bu sohbetteki durumu, risk."""
        from limina import paketler, vekil_v0
        vekil_v0.mcp_baglan(sessiz=True)     # kesif icin; arka planda basladiysa bekler
        a = self.araclar()
        if not a.get("ok"):
            return a
        durumlar = {x["ad"]: (x["durum"], x["sebep"]) for x in a["araclar"]}
        # Aciklama + dize tipli arguman adlari: panel yol-benzeri argumanlar
        # icin "oku/yaz" secici gosterir (kapiya yol bildirimi).
        kesfedilen = {}
        for tam_ad, b in getattr(vekil_v0.KOPRU, "araclar", {}).items():
            ozellikler = ((b.get("schema") or {}).get("properties") or {})
            kesfedilen[tam_ad] = {
                "aciklama": str(b.get("description") or "").strip(),
                "dize_argumanlar": [ad for ad, o in ozellikler.items()
                                    if isinstance(o, dict) and o.get("type") == "string"],
            }
        liste = paketler.paket_listesi(
            dict(self._politika.araclar), list(self._politika.mcp),
            list(getattr(self._politika, "kaldirilan", [])), kesfedilen, durumlar,
            dict(getattr(vekil_v0.KOPRU, "olu", {})),
            yol_bildirimleri=dict(getattr(self._politika, "yol_bildirimleri", {})))
        return {"ok": True, "paketler": liste, "hepsi_kapali": a["hepsi_kapali"],
                "calisiyor": a["calisiyor"], "risk_seviyeleri": list(paketler.RISK_SEVIYELERI)}

    def _politika_yaz(self, hata: str | None) -> dict:
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    def paket_kaldir(self, ad: str) -> dict:
        if self._kopru.calisiyor():
            return {"ok": False, "hata": ceviri.t("Önce çalışan görevi durdur.")}
        return self._politika_yaz(ayarlar.paket_kaldir(str(ad)))

    def paket_geri_ekle(self, ad: str) -> dict:
        return self._politika_yaz(ayarlar.paket_geri_ekle(str(ad)))

    def mcp_ekle(self, ad: str, komut) -> dict:
        """komut: dize listesi ya da bosluklarla ayrilmis tek dize (arayuz)."""
        if isinstance(komut, str):
            import shlex
            try:
                komut = shlex.split(komut, posix=False)
            except ValueError as e:
                return {"ok": False, "hata": f"Komut ayrıştırılamadı: {e}"}
            komut = [x.strip('"') for x in komut]
        return self._politika_yaz(ayarlar.mcp_sunucu_ekle(str(ad), list(komut or [])))

    def mcp_sil(self, ad: str) -> dict:
        if self._kopru.calisiyor():
            return {"ok": False, "hata": ceviri.t("Önce çalışan görevi durdur.")}
        return self._politika_yaz(ayarlar.mcp_sunucu_sil(str(ad)))

    def arac_siniflandir(self, tam_ad: str, risk: str, yollar=None) -> dict:
        yollar = dict(yollar) if isinstance(yollar, dict) else {}
        return self._politika_yaz(ayarlar.arac_siniflandir(str(tam_ad), str(risk), yollar))

    def arac_sinif_sil(self, tam_ad: str) -> dict:
        return self._politika_yaz(ayarlar.arac_sinif_sil(str(tam_ad)))

    def araclar(self) -> dict:
        """Ajanin elindeki butun araclar: ad, risk, aciklama, ve bu sohbetteki
        DURUMU. Liste KAYITTAN uretiliyor, elle yazilmiyor — yeni bir arac
        eklendiginde arayuzde kendiliginden gorunur.

        durum:
          acik         modele gosteriliyor
          kapali       kullanici bu sohbette kapatti (Araclar paneli / anahtar)
          gizli        MCP sunucusu sundu ama policy.toml [araclar]'da
                       siniflandirilmadi -> modele HIC gosterilmiyor. Bu bilgi
                       eskiden yalnizca acilis uyarisinda vardi, kimse gormuyordu.
          kesfedilmedi policy.toml'da siniflandirilmis ama sunucu sunmadi
                       (sunucu ayakta degil / araci kaldirmis) -> gosterilemez.
                       Bunu "acik" diye gostermek yalan olurdu.
        """
        try:
            from limina import vekil_v0
        except Exception as e:
            return {"ok": False, "hata": f"Arac listesi okunamadi: {e}"}

        aciklama: dict[str, str] = {}
        try:
            for bildirim in (vekil_v0.ARAC.function_declarations or []):
                aciklama[bildirim.name.replace("__", ".")] = (bildirim.description or "").strip()
        except Exception:
            pass
        for tam_ad, bilgi in getattr(vekil_v0.KOPRU, "araclar", {}).items():
            aciklama.setdefault(tam_ad, str(bilgi.get("description") or "").strip())

        mevcut = self._mevcut_araclar()
        gizli = set(getattr(vekil_v0, "_gizlenen", []))
        oturum = self._kopru.oturum
        kapali = set(oturum.kapali_araclar())
        hepsi_kapali = oturum.hepsi_kapali()

        cikti = []
        for ad in sorted(set(self._politika.araclar) | mevcut | gizli):
            if ad in gizli:
                durum, sebep = "gizli", "policy.toml [araclar] içinde sınıflandırılmadı"
            elif ad not in mevcut:
                durum, sebep = "kesfedilmedi", "sunucu bu aracı sunmadı (MCP ayakta değil?)"
            elif hepsi_kapali or ad in kapali:
                durum, sebep = "kapali", ("sohbet modu: bütün araçlar kapalı" if hepsi_kapali
                                          else "bu sohbette kullanıcı kapattı")
            else:
                durum, sebep = "acik", ""
            cikti.append({
                "ad": ad,
                "risk": self._politika.araclar.get(ad, "?"),
                "aciklama": aciklama.get(ad, ""),
                "kaynak": "MCP" if "." in ad else "yerel",
                "durum": durum,
                "sebep": sebep,
            })
        return {"ok": True, "araclar": cikti, "hepsi_kapali": hepsi_kapali,
                "calisiyor": self._kopru.calisiyor()}

    # Daraltma yolu. policy.toml'a YAZMAZ, kapiya DOKUNMAZ; yalnizca aktif
    # sohbetin Oturum'unda "modele gosterilmeyecekler" kumesini degistirir.
    # Genisletme yok: daraltma_guncelle mevcut kumenin disina cikamaz.
    def arac_ayarla(self, ad: str, acik: bool) -> dict:
        try:
            mevcut = self._mevcut_araclar()
        except Exception as e:
            return {"ok": False, "hata": f"Arac listesi okunamadi: {e}"}
        ad = str(ad)
        if ad not in mevcut:
            return {"ok": False, "hata": f"'{ad}' panelden açılabilir bir araç değil "
                                         f"(policy.toml'da sınıflandırılmamış ya da keşfedilmemiş)."}
        o = self._kopru.oturum
        kapali, hepsi = daraltma_guncelle(mevcut, frozenset(o.kapali_araclar()),
                                          o.hepsi_kapali(), ad, bool(acik))
        if not self._kopru.araclari_daralt(sorted(kapali), hepsi):
            return {"ok": False, "hata": ceviri.t("Önce çalışan görevi durdur.")}
        return {"ok": True, "kapali_araclar": sorted(kapali), "hepsi_kapali": hepsi}

    def araclar_hepsi(self, acik: bool) -> dict:
        """Sohbet/gorev anahtari: hepsini kapat (sohbet modu) ya da hepsini ac.
        Panelin "Hepsini kapat/ac" dugmeleri de buraya gelir — tek yol."""
        if not self._kopru.araclari_daralt([], not bool(acik)):
            return {"ok": False, "hata": ceviri.t("Önce çalışan görevi durdur.")}
        return {"ok": True, "kapali_araclar": [], "hepsi_kapali": not bool(acik)}

    def disa_aktar(self, metin: str, onerilen_ad: str = "sohbet.md") -> dict:
        """Sohbeti kullanicinin sectigi yere metin dosyasi olarak yazar.

        Kaydetme yeri kullanicinin sectigi yerdir; yol hapishanesi burada
        gecerli DEGIL cunku islemi ajan degil kullanici yapiyor.
        """
        if self._pencere is None:
            return {"ok": False, "hata": ceviri.t("Pencere hazır değil.")}
        try:
            hedef = self._pencere.create_file_dialog(
                webview.SAVE_DIALOG, save_filename=onerilen_ad)
        except Exception as e:
            return {"ok": False, "hata": f"Kaydetme penceresi acilamadi: {e}"}
        if not hedef:
            return {"ok": True, "iptal": True}
        yol = hedef if isinstance(hedef, str) else hedef[0]
        try:
            Path(yol).write_text(str(metin), encoding="utf-8")
        except OSError as e:
            return {"ok": False, "hata": f"Yazilamadi: {e}"}
        return {"ok": True, "yol": yol}

    # ------------------------------------------------------------------
    # ayarlar
    # ------------------------------------------------------------------
    # DIKKAT: bu metotlar policy.toml'a yazabiliyor. ARAC_TABLOSU'na
    # EKLENMEZLER ve ARAC semalarinda yer ALMAZLAR — cagri yolu yalnizca
    # kullanici arayuzu. "Kapi, kapiyi acan tarafindan duzenlenemez."
    def arayuz_ayarlari(self) -> dict:
        """Yalnizca config/arayuz.toml (dil, animasyon...). Acilista JS bunu
        cagirir: ayarlar_oku policy.toml'u da okuyor, ilk boyama icin agir."""
        return {"ok": True, "arayuz": ayarlar.arayuz_oku()}

    def ayarlar_oku(self) -> dict:
        veri = ayarlar.policy_oku()
        veri["arayuz"] = ayarlar.arayuz_oku()
        veri["durum"] = {
            "model": getattr(self._politika, "model_varsayilan", "?"),
            "calisiyor": self._kopru.calisiyor(),
            "sohbet_sayisi": len(self._kopru.sohbetler()),
            "surukle_destegi": self._surukle_destegi,
            "kod_koku_guvenli": veri.get("kod_koku_guvenli", False),
        }
        return veri

    def _politikayi_tazele(self) -> None:
        """Ayar degisikligini KAPIYA da isle.

        Ajan dongusu vekil_v0.POLITIKA'yi kullaniyor; yalnizca Api'nin kendi
        kopyasini tazelemek yetmez — o durumda ayar degisir ama kapi eski
        politikayla karar vermeye devam ederdi. Degisiklik bir sonraki arac
        cagrisinda gecerli olur.
        """
        yeni = Politika(KOK / "policy.toml")
        self._politika = yeni
        try:
            from limina import vekil_v0
            vekil_v0.POLITIKA = yeni
            # MCP semalari politikaya gore yeniden kurulur: panelden
            # siniflandirilan arac yeniden baslatmadan modele gorunur.
            vekil_v0.arac_semalarini_tazele(sessiz=True)
            # Panelden eklenen yeni MCP sunucusu da aninda baglanir (arka planda;
            # bitince paketler() kesfi gorur).
            if getattr(vekil_v0, "_mcp_baglandi", False):
                vekil_v0.mcp_arka_planda_baglan()
        except Exception:
            pass

    def arayuz_ayari_yaz(self, bolum: str, anahtar: str, deger) -> dict:
        hata = ayarlar.arayuz_yaz(str(bolum), str(anahtar), deger)
        # Dil degistiyse Python tarafi da HEMEN donsun. Arayuz kendi metinlerini
        # dilAyarla() ile aninda degistiriyor; onay karti etki cumlesi, hata
        # seridi ve donus ozeti bir sonraki acilisa kadar eski dilde kalsaydi
        # ayni ekranda iki dil gorunurdu (ceviri.dil() aksi halde onbellekli).
        if hata is None and (bolum, anahtar) == ("genel", "dil"):
            ceviri.dil_ayarla(str(deger))
            # Modele giden arac aciklamalari da dil ayarini izliyor; semalar
            # yeniden kurulmazsa bir sonraki gorev eski dilde bildirim tasir.
            vekil = sys.modules.get("limina.vekil_v0")
            if vekil is not None:
                vekil.arac_semalarini_tazele(sessiz=True)
        return {"ok": hata is None, "hata": hata}

    def eylem_ayari_yaz(self, alan: str, kategori: str, deger: str) -> dict:
        hata = ayarlar.eylem_yaz(str(alan or ""), str(kategori), str(deger))
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    def site_ekle(self, alan: str) -> dict:
        hata = ayarlar.site_ekle(str(alan))
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    def site_sil(self, alan: str) -> dict:
        hata = ayarlar.site_sil(str(alan))
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    # --- saglayici ve API anahtari (limina.model / limina.anahtar) ---
    def saglayici_bilgisi(self) -> dict:
        """Ayarlar > Model'in ust bolumu: secili saglayici, taban adres, anahtar
        durumu (MASKELI — anahtarin kendisi arayuze hic gitmez)."""
        from limina import anahtar, model
        pol = self._politika
        ad = getattr(pol, "saglayici", "gemini")
        return {"ok": True, "saglayici": ad, "saglayicilar": list(model.SAGLAYICILAR),
                "adlar": dict(model.SAGLAYICI_ADI), "taban_url": getattr(pol, "taban_url", ""),
                # Karsilama seridi icin: zincirde KULLANILABILIR bir baglanti var mi
                # (anahtari kayitli ya da anahtar gerektirmeyen yerel sunucu).
                "anahtar_var": any(b["anahtar_var"] or b["anahtarsiz_olabilir"]
                                   for b in self._baglanti_satirlari()),
                "anahtar_maske": anahtar.maskele(anahtar.oku(ad)),
                "anahtar_kaynak": anahtar.kaynak(ad), "ortam_degiskeni": anahtar.ORTAM_DEGISKENI.get(ad, ""),
                "keyring": anahtar._keyring() is not None}

    def saglayici_yaz(self, ad: str) -> dict:
        return self._politika_yaz(ayarlar.saglayici_yaz(str(ad)))

    def taban_url_yaz(self, url: str) -> dict:
        return self._politika_yaz(ayarlar.taban_url_yaz(str(url or "")))

    def anahtar_yaz(self, saglayici: str, deger: str, yuva: str = "") -> dict:
        """Anahtar policy.toml'a DEGIL anahtar.py deposuna yazilir; olay
        akisina, journal'a ve sohbete hic girmez. yuva: adli yuva (ekip
        ajanlari icin ikinci/ucuncu anahtar), bos = varsayilan."""
        from limina import anahtar
        hata = anahtar.yaz(str(saglayici), str(deger or ""), str(yuva or ""))
        return {"ok": hata is None, "hata": hata}

    def anahtar_yuvalari(self) -> dict:
        """Her saglayicinin adli yuvalari + durumu (maskeli; anahtar gitmez)."""
        from limina import anahtar, model
        cikti = {}
        for s in model.SAGLAYICILAR:
            cikti[s] = [{"yuva": y, "kaynak": anahtar.kaynak(s, y), "maske": anahtar.maskele(anahtar.oku(s, y))}
                        for y in anahtar.yuvalar(s)]
        return {"ok": True, "yuvalar": cikti}

    # ------------------------------------------------------------------
    # API baglantilari ve model zinciri (limina/model_zinciri.py)
    # ------------------------------------------------------------------
    def _baglanti_satirlari(self) -> list[dict]:
        """Sirali baglantilar + anahtar durumu (MASKELI) + dolu modeller.
        [baglantilar] yoksa eski [model] ayari tek, 'sanal' bir baglanti olarak
        gosterilir; ilk degisiklikte gercek baglantiya cevrilir (ayarlar.py)."""
        from limina import anahtar, model, model_zinciri
        pol = self._politika
        if pol.baglantilar:
            kaynaklar = [(k, pol.baglantilar[k], False) for k in pol.zincir]
        else:
            m = [x for x in dict.fromkeys([pol.model_varsayilan, pol.model_guclu]) if x]
            kaynaklar = [(ayarlar.ESKI_BAGLANTI, {
                "ad": model_zinciri.SAGLAYICI_KISA_AD.get(pol.saglayici, pol.saglayici),
                "saglayici": pol.saglayici, "taban_url": pol.taban_url if pol.saglayici == "openai" else "",
                "anahtar_yuvasi": "", "modeller": m}, True)]
        simdi = datetime.now()
        satirlar = []
        for kimlik, b, sanal in kaynaklar:
            yuva = b["anahtar_yuvasi"]
            kayitli = anahtar.oku(b["saglayici"], yuva)
            dolu = {}
            for mod in b["modeller"]:
                bitis = model_zinciri.dolu_bitis(model_zinciri.Halka(kimlik, b["ad"], b["saglayici"],
                                                                     b["taban_url"], yuva, mod), simdi)
                if bitis:
                    dolu[mod] = bitis.isoformat(timespec="minutes")
            satirlar.append({
                "kimlik": kimlik, "ad": b["ad"], "saglayici": b["saglayici"], "taban_url": b["taban_url"],
                "modeller": list(b["modeller"]), "sanal": sanal,
                "anahtar_var": bool(kayitli), "anahtar_maske": anahtar.maskele(kayitli),
                "anahtar_kaynak": anahtar.kaynak(b["saglayici"], yuva),
                "anahtarsiz_olabilir": b["saglayici"] == "openai" and model.yerel_adres_mi(b["taban_url"]),
                "dolu": dolu})
        return satirlar

    def baglantilar(self) -> dict:
        from limina import anahtar, model_zinciri
        pol = self._politika
        return {"ok": True, "baglantilar": self._baglanti_satirlari(),
                "hazirlar": model_zinciri.HAZIRLAR, "keyring": anahtar._keyring() is not None,
                "saglayici_adlari": {"gemini": "Google Gemini", "openai": ceviri.t("OpenAI-uyumlu"),
                                     "anthropic": "Anthropic Claude"}}

    def baglanti_kaydet(self, kimlik: str, ad: str, saglayici: str, taban_url: str,
                        modeller, anahtar_metni: str = "") -> dict:
        """Ekle (kimlik bos) ya da guncelle. Anahtar policy.toml'a DEGIL anahtar
        deposuna, baglantinin kendi yuvasina yazilir; bos = dokunma."""
        from limina import anahtar
        if isinstance(modeller, str):
            modeller = modeller.replace(",", "\n").splitlines()
        hata, kimlik = ayarlar.baglanti_yaz(str(kimlik or ""), str(ad or ""), str(saglayici or ""),
                                            str(taban_url or ""), [str(m) for m in (modeller or [])])
        sonuc = self._politika_yaz(hata)
        if not sonuc["ok"]:
            return sonuc
        sonuc["kimlik"] = kimlik
        anahtar_metni = str(anahtar_metni or "").strip()
        if anahtar_metni:
            b = self._politika.baglantilar.get(kimlik) or {}
            h = anahtar.yaz(b.get("saglayici", saglayici), anahtar_metni, b.get("anahtar_yuvasi", ""))
            if h:
                return {"ok": False, "kimlik": kimlik,
                        "hata": ceviri.t("Bağlantı kaydedildi ama anahtar yazılamadı: {h}", h=h)}
        return sonuc

    def _baglanti_tanimi(self, kimlik: str) -> dict | None:
        """Kayitli baglanti ya da (henuz cevrilmemis) eski ayarin sanal 'ana' baglantisi."""
        kimlik = str(kimlik or "")
        for satir in self._baglanti_satirlari():
            if satir["kimlik"] == kimlik:
                b = self._politika.baglantilar.get(kimlik)
                return {**satir, "anahtar_yuvasi": b["anahtar_yuvasi"] if b else ""}
        return None

    def baglanti_anahtar_sil(self, kimlik: str) -> dict:
        from limina import anahtar
        b = self._baglanti_tanimi(kimlik)
        if not b:
            return {"ok": False, "hata": ceviri.t("Bağlantı bulunamadı.")}
        h = anahtar.yaz(b["saglayici"], "", b["anahtar_yuvasi"])
        return {"ok": h is None, "hata": h}

    def baglanti_sil(self, kimlik: str) -> dict:
        from limina import anahtar, model_zinciri
        if self._kopru.calisiyor():
            return {"ok": False, "hata": ceviri.t("Önce çalışan görevi durdur.")}
        hata, bilgi = ayarlar.baglanti_sil(str(kimlik or ""))
        sonuc = self._politika_yaz(hata)
        # Anahtar yalnizca baglantiya OZEL yuvadaysa silinir; varsayilan yuva
        # (eski tek-anahtar) baska yerlerde (ekip, ortam) kullaniliyor olabilir.
        if sonuc["ok"] and str(bilgi.get("yuva", "")).startswith(ayarlar.BAGLANTI_YUVA_ONEKI):
            anahtar.yaz(bilgi["saglayici"], "", bilgi["yuva"])
        if sonuc["ok"]:
            model_zinciri.sifirla(str(kimlik))
        return sonuc

    def zincir_yaz(self, sira) -> dict:
        return self._politika_yaz(ayarlar.zincir_yaz([str(x) for x in (sira or [])]))

    def baglanti_sifirla(self, kimlik: str = "") -> dict:
        """'Limit doldu' isaretlerini kaldirir: model zincirde yeniden denenir."""
        from limina import model_zinciri
        model_zinciri.sifirla(str(kimlik) if kimlik else None)
        return {"ok": True}

    def baglanti_modelleri_getir(self, kimlik: str) -> dict:
        """Baglantinin hesabindaki model adlari — arka planda (ag cagrisi).
        Sonuc model_listesi_al ile alinir (tek model listesi yuvasi)."""
        from limina import model, model_zinciri
        b = self._baglanti_tanimi(kimlik)
        if not b:
            return {"ok": False, "hata": ceviri.t("Önce bağlantıyı kaydet.")}
        if self._model_cekiliyor:
            return {"ok": True, "basladi": True}
        self._model_cekiliyor = True
        self._model_listesi = None
        halka = model_zinciri.Halka(str(kimlik), b["ad"], b["saglayici"], b["taban_url"],
                                    b["anahtar_yuvasi"], b["modeller"][0])

        def cek() -> None:
            try:
                s = model.kur(self._politika, 30.0, ajan=halka.ajan())
                self._model_listesi = {"ok": True, "modeller": sorted(s.modeller())}
            except Exception as e:
                self._model_listesi = {"ok": False, "hata": ceviri.t("Liste alınamadı: {h}",
                                                                     h=f"{type(e).__name__}: {e}")}
            finally:
                self._model_cekiliyor = False

        threading.Thread(target=cek, daemon=True).start()
        return {"ok": True, "basladi": True}

    def ajanlar(self) -> dict:
        return {"ok": True, "ajanlar": ayarlar.ajanlar_oku()}

    def ajan_yaz(self, ad: str, saglayici: str = "", model: str = "", anahtar_yuvasi: str = "",
                 rol: str = "", taban_url: str = "", baglanti: str = "", renk: str = "",
                 gorunum=None) -> dict:
        """baglanti doluysa ajan o API baglantisina baglanir (saglayici/yuva/adres
        oradan); bossa eski bicim (saglayici + yuva + adres)."""
        try:
            gorunum = None if gorunum in (None, "") else int(gorunum)
        except (TypeError, ValueError):
            return {"ok": False, "hata": ceviri.t("Görünüm geçersiz.")}
        return self._politika_yaz(ayarlar.ajan_yaz(str(ad), str(saglayici or ""), str(model or ""),
                                                   str(anahtar_yuvasi or ""), str(rol or ""), str(taban_url or ""),
                                                   str(baglanti or ""), str(renk or ""), gorunum))

    def ofis_duzeni(self) -> dict:
        """Ekip ofisi: masa kodlari/adlari ve ajanlarin gorunusu (limina/ofis.py).
        Anahtar tasimaz; masalarin sahnedeki konumu arayuzde."""
        from limina import ofis
        return {"ok": True, **ofis.duzen(self._politika)}

    def ajan_sil(self, ad: str) -> dict:
        return self._politika_yaz(ayarlar.ajan_sil(str(ad)))

    # --- Ekip alani ---------------------------------------------------------
    def ekip_projeler(self) -> dict:
        from limina import projeler
        try:
            return {"ok": True, "projeler": projeler.liste(self._politika)}
        except Exception as exc:
            return {"ok": False, "hata": str(exc), "projeler": []}

    def ekip_proje_yaz(self, ad: str, klasor: str, aciklama: str = "", kimlik: str | None = None) -> dict:
        from limina import projeler
        try:
            return {"ok": True, "proje": projeler.yaz(self._politika, str(ad), str(klasor), str(aciklama or ""), kimlik or None)}
        except Exception as exc:
            return {"ok": False, "hata": str(exc)}

    def ekip_proje_sil(self, kimlik: str) -> dict:
        from limina import projeler
        try:
            projeler.sil(self._politika, str(kimlik))
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "hata": str(exc)}

    def ekip_kosular(self, proje: str | None = None) -> dict:
        from limina import ekip
        return {"ok": True, "kosular": ekip.kosular(proje or None)}

    def ekip_kosu(self, kimlik: str) -> dict:
        from limina import ekip
        veri = ekip.kosu(str(kimlik))
        return {"ok": veri is not None, "kosu": veri, "hata": None if veri else "Koşu bulunamadı."}

    def ofis_ajan_karti(self, ad: str, isci: str = "", kimlik: str = "") -> dict:
        """Ofisteki ajan karti: baglanti · model, limit durumu (model zinciri,
        ilk 4 halka) ve bu kosuda GUNLUGE yazilmis dosyalari (isci etiketiyle;
        modelin "yazdim" demesi degil). Yalnizca okur, anahtar tasimaz."""
        import re as _re
        from limina import ekip, journal, model_zinciri
        pol = self._politika
        cikti = {"ok": True, "ad": str(ad), "rol": "", "baglanti_ad": "", "model": "", "zincir": [], "yazdiklari": []}
        a = pol.ajanlar.get(str(ad))
        if a:
            simdi = datetime.now()
            halkalar = model_zinciri.zincir(pol, ajan=a, ajan_adi=str(ad))
            cikti.update(rol=a.get("rol", ""), baglanti_ad=halkalar[0].ad if halkalar else "",
                         model=halkalar[0].model if halkalar else "")
            for h in halkalar[:4]:
                bitis = model_zinciri.dolu_bitis(h, simdi)
                cikti["zincir"].append({"etiket": h.etiket, "dolu_bitis": bitis.isoformat(timespec="minutes") if bitis else ""})
        isci, kimlik = str(isci or ""), str(kimlik or "")
        if isci and _re.match(r"^[0-9]{8}-[0-9]{6}$", kimlik):
            kosu = ekip.kosu(kimlik) or {}
            bas = str(kosu.get("baslangic") or "")
            if bas:
                yollar = [k.get("yol") for k in journal.gorev_kayitlari(bas) if k.get("ajan") == isci and k.get("yol")]
                cikti["yazdiklari"] = list(dict.fromkeys(yollar))[:30]
        return cikti

    def ekip_tek_gorev_baslat(self, gorev: str, proje: str | None, ajan: str, yol: str = "", mod: str | None = None) -> dict:
        """Ofisteki ajan kartindan: yalnizca bu ajana gorev (planlayici yok).
        Yazma yolu (proje icinde goreli) plan onay kartinda gorunur; plan_dogrula
        ve dar isci politikasi ekip goreviyle ayni."""
        from limina import ekip
        if str(ajan or "") not in self._politika.ajanlar:
            return {"ok": False, "hata": ceviri.t("Ajan tanımlı değil: {ajan}", ajan=ajan)}
        alan = None
        if proje:
            p = next((x for x in self.ekip_projeler().get("projeler", []) if x["kimlik"] == proje), None)
            if p is None:
                return {"ok": False, "hata": ceviri.t("Proje bulunamadı.")}
            alan = p["klasor"]
        return self.gorev_baslat(gorev, mod, ekip={"alan": alan, "ajanlar": [str(ajan)], "proje": proje,
                                                   "tek": str(ajan), "yol": str(yol or "")})

    def ekip_kosu_olaylari(self, kimlik: str) -> dict:
        """Ofiste gecmis oynatma: kosunun olay kaydi. Yalnizca okur."""
        from limina import ekip
        return {"ok": True, "olaylar": ekip.kosu_olaylari(str(kimlik or ""))}

    def ekip_gorev_baslat(self, gorev: str, proje: str | None, ajanlar: list | None, mod: str | None = None) -> dict:
        """Ekip alanindan: proje (klasor) + secili ajanlar + gorev."""
        from limina import ekip
        alan = None
        if proje:
            p = next((x for x in self.ekip_projeler().get("projeler", []) if x["kimlik"] == proje), None)
            if p is None:
                return {"ok": False, "hata": ceviri.t("Proje bulunamadı.")}
            alan = p["klasor"]
        return self.gorev_baslat(gorev, mod, ekip={"alan": alan, "ajanlar": [str(a) for a in (ajanlar or [])],
                                                   "proje": proje})

    # --- Dusunce Agi (ag.py) ------------------------------------------
    # Arayuz agi cizer ve atesler; izin karari yine kapida: 'dosya' dugumu
    # okuma karari ALLOW degilse ateslemez (bkz. ag.ates -> _icerik).

    def ag_listesi(self) -> dict:
        from limina import ag
        return {"ok": True, "aglar": ag.aglar()}

    def ag_getir(self, ad: str) -> dict:
        from limina import ag
        veri, hata = ag.oku(str(ad))
        return {"ok": hata is None, "ag": veri, "hata": hata}

    def ag_kaydet(self, veri) -> dict:
        """Arayuzden gelen ag (dugumler + baglantilar + konumlar). Dogrulama
        ag.yaz icinde; bozuksa DISKE HIC YAZILMAZ, sebep geri doner.

        'uyarilar': statik analiz (olu dugum, hem besleyip hem engelleyen
        dugum, ulasilmaz alt ag). Hata degil; kullanici atesLEMEDEN once
        gorsun diye."""
        from limina import ag
        if not isinstance(veri, dict):
            return {"ok": False, "hata": ceviri.t("ağ bir JSON nesnesi olmalı")}
        from limina import journal
        with journal._gunluk_kilidi():          # ekip iscileri de ayni aga yazabilir
            hata = ag.yaz(veri)
        return {"ok": hata is None, "hata": hata, "uyarilar": [] if hata else ag.analiz(veri)}

    def ag_sil(self, ad: str) -> dict:
        from limina import ag
        hata = ag.sil(str(ad))
        return {"ok": hata is None, "hata": hata}

    def ag_atesle(self, ad: str, uyaran: list | None = None, kip: str = "tam", gorev: str = "") -> dict:
        """Agi atesler. Donus hem ANIMASYON icin (sira: tik damgalari, kimlik)
        hem de OKUMA icin (metin). Model cagrilmaz: saf hesap.

        gorev: o anki istek — agdaki {gorev} yer tutucularini doldurur."""
        from limina import ag
        veri, hata = ag.oku(str(ad))
        if hata:
            return {"ok": False, "hata": hata}
        try:
            kosu = ag.ates(veri, [str(u) for u in (uyaran or [])], self._politika,
                           str(kip or "tam"), gorev=str(gorev or ""))
        except ag.AgHatasi as e:
            return {"ok": False, "hata": str(e)}
        return {"ok": True, "kosu": kosu, "metin": kosu["metin"]}

    def ag_gorev_baslat(self, ad: str, uyaran: list | None = None, gorev: str = "", kip: str = "tam") -> dict:
        """Ag okumasini bir goreve baglam olarak gonderir. Okuma metni goreve
        EKLENIR; dosya icerikleri ve ajan notlari zaten <untrusted_content>
        sarmalinda."""
        from limina import ag
        istek = (gorev or "").strip()
        if not istek:
            return {"ok": False, "hata": ceviri.t("Görev boş.")}
        veri, hata = ag.oku(str(ad))
        if hata:
            return {"ok": False, "hata": hata}
        try:
            # Goreve gonderirken {gorev} yer tutuculari o istekle dolar.
            kosu = ag.ates(veri, [str(u) for u in (uyaran or [])], self._politika, str(kip or "tam"),
                           gorev=istek)
        except ag.AgHatasi as e:
            return {"ok": False, "hata": str(e)}
        return self.gorev_baslat(istek + "\n\n" + kosu["metin"])

    def ekip_pano_yaz(self, metin: str, kime: str = "herkes") -> dict:
        """Kullanici, calisan ekip gorevinin panosuna yazar ("kullanici" imzasiyla).
        Isciler bir sonraki turlarinda gorur. Kosu yoksa hata."""
        from limina.baglam import B
        from limina.araclar import ekip_pano
        pano = getattr(B, "ekip_pano", None)
        if not pano:
            return {"ok": False, "hata": ceviri.t("Çalışan bir ekip görevi yok.")}
        metin = str(metin or "").strip()
        if not metin:
            return {"ok": False, "hata": ceviri.t("Mesaj boş.")}
        k = ekip_pano.yaz(Path(pano), "kullanici", str(kime or "herkes"), metin)
        return {"ok": True, "sira": k["sira"]}

    def model_yaz(self, etiket: str, ad: str) -> dict:
        """Model adini policy.toml'a yazar. Yeniden baslatma gerekmez:
        ajan dongusu modeli her gorevde POLITIKA'dan taze okuyor."""
        hata = ayarlar.model_yaz(str(etiket), str(ad))
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    def sayi_yaz(self, bolum: str, anahtar: str, deger: Any) -> dict:
        hata = ayarlar.sayi_yaz(str(bolum), str(anahtar), deger)
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    def mod_yaz(self, mod: str, alan: str, deger: Any) -> dict:
        """Bir efor modunun (hizli/dengeli/derin/azami) model/adim/cagri/istek
        alanini yazar. Mod izin gevsetmez — burada duzenlenen sadece hesap harcama
        tavani, onay kartlarina veya ALLOW/ASK/DENY kararina dokunmaz."""
        hata = ayarlar.mod_yaz(str(mod), str(alan), deger)
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    def varsayilan_mod_yaz(self, mod: str) -> dict:
        hata = ayarlar.varsayilan_mod_yaz(str(mod))
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    def klasor_sec(self) -> dict:
        """Isletim sisteminin klasor secicisi. Elle yol yazmak yerine bunu
        kullaniyoruz: yazim hatasi olmaz ve gelen yol gercekten var."""
        if self._pencere is None:
            return {"ok": False, "hata": ceviri.t("Pencere hazır değil.")}
        try:
            secim = self._pencere.create_file_dialog(webview.FOLDER_DIALOG)
        except Exception as e:
            return {"ok": False, "hata": f"Klasor secici acilamadi: {e}"}
        if not secim:
            return {"ok": True, "yol": ""}
        return {"ok": True, "yol": secim[0] if isinstance(secim, (list, tuple)) else str(secim)}

    # ------------------------------------------------------------------
    # ilk kurulum ekrani (ayarlar.kurulum_*)
    # ------------------------------------------------------------------
    def kurulum_durumu(self) -> dict:
        return ayarlar.kurulum_durumu()

    def kurulum_uygula(self, veri) -> dict:
        if self._kopru.calisiyor():
            return {"ok": False, "hatalar": [ceviri.t("Önce çalışan görevi durdur.")]}
        veri = veri if isinstance(veri, dict) else {}
        hatalar = ayarlar.kurulum_uygula(veri)
        if veri.get("dil") in ("tr", "en"):
            ceviri.dil_ayarla(str(veri["dil"]))
        self._politikayi_tazele()
        return {"ok": not hatalar, "hatalar": hatalar}

    def calisma_klasoru_yaz(self, yol: str) -> dict:
        hata = ayarlar.calisma_klasoru_degistir(str(yol or ""))
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    def kok_ekle(self, tur: str, yol: str) -> dict:
        hata = ayarlar.kok_ekle(str(tur), str(yol))
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    def kok_sil(self, tur: str, yol: str) -> dict:
        hata = ayarlar.kok_sil(str(tur), str(yol))
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    def acma_klasoru_yaz(self, yol: str) -> dict:
        """[acma] klasor. Bos = kapat. Kesisim reddi ayarlar.acma_klasoru_yaz'da."""
        hata = ayarlar.acma_klasoru_yaz(str(yol or ""))
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    def persona_oku(self) -> dict:
        return {"ok": True, "metin": ayarlar.persona_oku(),
                "azami": ayarlar.PERSONA_AZAMI}

    def persona_yaz(self, metin: str) -> dict:
        hata = ayarlar.persona_yaz(str(metin))
        return {"ok": hata is None, "hata": hata}

    def bayrak_yaz(self, bolum: str, anahtar: str, deger: bool) -> dict:
        hata = ayarlar.bayrak_yaz(str(bolum), str(anahtar), bool(deger))
        if hata is None:
            self._politikayi_tazele()
        return {"ok": hata is None, "hata": hata}

    # Model listesi AG'DAN gelir ve saniyeler surebilir. Api metotlari bloke
    # olmamali (JS 120 ms'de bir olay yokluyor), o yuzden cekme arka planda
    # yapilir, JS sonucu ayri bir cagriyla toplar — birakilan_ekleri_al deseni.
    def model_listesi_getir(self) -> dict:
        if self._model_cekiliyor:
            return {"ok": True, "basladi": True}
        self._model_cekiliyor = True
        self._model_listesi = None

        def cek() -> None:
            try:
                from limina import modeller
                self._model_listesi = {"ok": True, "modeller": modeller.mevcut_modeller(self._politika)}
            except Exception as e:
                self._model_listesi = {"ok": False,
                                       "hata": f"Liste alinamadi: {type(e).__name__}: {e}"}
            finally:
                self._model_cekiliyor = False

        threading.Thread(target=cek, daemon=True).start()
        return {"ok": True, "basladi": True}

    def model_listesi_al(self) -> dict:
        """Hazirsa sonucu doner ve tuketir; degilse bekliyor der."""
        sonuc = self._model_listesi
        if sonuc is None:
            return {"ok": True, "bekliyor": True}
        self._model_listesi = None
        return sonuc

    def _kota_satirlari(self) -> list[dict]:
        """Rol basina bugunku kullanim. Sayi journal'dan, tavan ve model adi
        POLITIKA'dan — journal artik policy.toml okumuyor."""
        from limina import model_zinciri
        sayaclar = journal.kota_sayaclari()
        pol = self._politika
        adlar = {r: (model_zinciri.sirala(model_zinciri.zincir(pol, r)) or [None])[0] for r in ("varsayilan", "guclu")}
        adlar = {r: (h.etiket if h else "?") for r, h in adlar.items()}
        return [{"rol": rol, "model": adlar[rol], "istek": sayaclar.get(rol, 0),
                 "tavan": pol.gunluk_tavan.get(rol, 0)}
                for rol in ("varsayilan", "guclu")]

    def _one_al(self) -> None:
        """Onay bekleniyorsa Limina'yi one getirir.

        Playwright'in actigi Chrome penceresi Limina'nin ustune firliyor ve
        onay karti gorunmez kaliyor; kullanici gorevi DONMUS saniyor
        (gozlemlendi). Ajan sayfayla Playwright API'si uzerinden konusuyor,
        gercek tiklamayla degil — yani Limina'yi one almak ajanin isini
        bozmaz, sadece soruyu gorunur kilar.

        NEDEN pencere.on_top DEGIL: pywebview'in set_on_top'u WinForms
        formunun TopMost'unu CAGIRAN thread'den (burasi bir js_api thread'i)
        dogrudan yaziyor, Invoke etmiyor. Windows bunu arayuz thread'ine
        senkron SendMessage'a ceviriyor; arayuz thread'i o anda bir js_api
        cagrisi icin Thread.start() yapip GIL bekliyorsa (pythonnet ozellik
        atamasinda GIL'i birakmiyor) iki taraf birbirini bekler — pencere
        "yanit vermiyor". 2026-09-15'te onay kartinin cikacagi her gorevde
        yasandi; takilma.log/py-spy dokumu: Thread-N set_on_top, Dummy
        (arayuz) Thread.start -> wait. BeginInvoke: is arayuz thread'inin
        kuyruguna girer, burasi HIC beklemez.
        """
        if self._pencere is None:
            return
        try:
            from System import Func, Type
            from webview.platforms.winforms import BrowserView

            form = BrowserView.instances.get(self._pencere.uid)
            if form is None:
                return

            def _one_getir() -> None:
                form.TopMost = True
                form.TopMost = False

            form.BeginInvoke(Func[Type](_one_getir))
        except Exception:
            pass        # one alamamak gorevi bozmamali

    def kota(self) -> dict:
        """Bugun yapilan istek sayilari. YEREL sayim: kesin kota degil, tahmin."""
        return {"ok": True, "satirlar": self._kota_satirlari()}

    def mod_kotasi(self, mod: str | None = None) -> dict:
        """Secili modun bugunku durumu — gorev BASLAMADAN once gosterilir.

        ROL bazinda: dort mod iki kovaya dusuyor (hizli+dengeli -> varsayilan,
        derin+azami -> guclu), sayac rol tutuyor.

        Sayilan sey ISTEK, gorev DEGIL. Bir gorev modun adim tavanina kadar
        istek harcayabilir; "kac gorev kaldi" demiyoruz cunku o boleni
        uydurmak olurdu. Onun yerine yarida kesilme riskini soyluyoruz —
        tavana carpan gorev ORTASINDA kesilir (DEVIR_FAZ6.md 2.9).
        """
        pol = self._politika
        d = pol.mod_coz(mod)
        rol = d["model"]
        tavan = pol.gunluk_tavan.get(rol, 0)          # 0 = tavan yok
        kalan = max(0, tavan - journal.kota_sayaclari().get(rol, 0)) if tavan else None
        return {
            "ok": True,
            "mod": mod or pol.varsayilan_mod,
            "model": self._kota_satirlari()[0 if rol == "varsayilan" else 1]["model"],
            "tavan": tavan,
            "kalan": kalan,                            # None = tavan yok
            "adim_tavani": d["adim"],
            # Uyari YAPISAL degil GUNLUK olmali. azami'nin adim tavani (20)
            # guclu'nun gunluk tavanindan (18) buyuk; sayac sifirken bile
            # kalan < adim_tavani cikiyordu ve uyari hic sonmuyordu. Sonmeyen
            # uyari okunmaz. Yapisal durum modun ozelligi, gunun haberi degil.
            "kesilebilir": (kalan is not None and tavan >= d["adim"]
                            and 0 < kalan < d["adim"]),
            "tavana_sigmiyor": tavan != 0 and tavan < d["adim"],
            "dolu": kalan == 0,
        }

    # ------------------------------------------------------------------
    # dosya ekleme
    # ------------------------------------------------------------------
    def _ek_kaydet(self, yollar) -> dict:
        """Yollari dogrular ve ek listesine ekler. Kapiyi ATLAMAZ — burada yapilan
        kontrol yalnizca kullaniciyi erken uyarmak icin; asil karar arac cagrisinda
        gate.karar() tarafindan verilir."""
        eklenen, uyarilar = [], []
        for ham in (yollar or []):
            yol = Path(str(ham))
            if not yol.exists():
                uyarilar.append(f"{yol.name}: dosya bulunamadi")
                continue
            karar = self._politika.yol_dogrula(str(yol), "oku")
            if karar.sonuc == "DENY":
                # ARAYUZ.md 5: izinli koklerin disindaysa arayuz bunu HEMEN soyler.
                uyarilar.append(f"{yol.name}: {karar.gerekce}")
                continue
            tam = str(karar.yol)
            if tam not in self._ekler:
                self._ekler.append(tam)
            eklenen.append({"ad": yol.name, "yol": tam})
        return {"ok": True, "ekler": eklenen, "uyarilar": uyarilar}

    def dosya_sec(self) -> dict:
        """Isletim sisteminin dosya secicisi. Tam yol yalnizca buradan gelir."""
        if self._pencere is None:
            return {"ok": False, "hata": ceviri.t("Pencere hazır değil.")}
        try:
            secim = self._pencere.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
        except Exception as e:
            return {"ok": False, "hata": f"Dosya secici acilamadi: {e}"}
        if not secim:
            return {"ok": True, "ekler": [], "uyarilar": []}
        return self._ek_kaydet(secim)

    def dosya_goster(self, yol: str) -> dict:
        """Sohbetteki bir yola tiklaninca Explorer'da o dosyayi secili acar.

        Yalnizca GOSTERIR: dosyayi yurutmez, acmaz — explorer.exe'ye
        /select ile veriliyor, liste arguman, shell yok. Kapiyi atlamaz cunku
        kapiya girecek bir sey yok: ajan degil kullanici tikliyor ve Explorer
        kullanicinin zaten yapabildigi bir sey.

        Iki ret: (1) UNC yolu (\\\\sunucu\\...) — Explorer'da acmak SMB baglantisi
        kurar, kimlik bilgisi sizabilir; modelin urettigi metne tek tikla o
        riski almayiz. Bu yuzden exists() cagrilmadan ONCE reddedilir, var mi
        diye bakmak bile baglanti demek. (2) Olmayan yol. Arayuz ayni
        yerel-yol kuralini uyguluyor (YEREL_YOL); burasi ikinci uygulama noktasi.
        """
        import re
        import subprocess

        ham = str(yol or "").strip()
        if not re.match(r"^[A-Za-z]:[\\/]", ham):
            return {"ok": False, "hata": ceviri.t("Yalnızca yerel sürücüdeki yollar açılabilir.")}
        try:
            hedef = Path(ham).resolve()
        except (OSError, ValueError) as e:
            return {"ok": False, "hata": f"Yol cozulemedi: {e}"}
        if not hedef.exists():
            return {"ok": False, "hata": f"Dosya bulunamadi: {hedef}"}
        try:
            if hedef.is_dir():
                subprocess.Popen(["explorer.exe", str(hedef)])
            else:
                subprocess.Popen(["explorer.exe", f"/select,{hedef}"])
        except OSError as e:
            return {"ok": False, "hata": f"Explorer acilamadi: {e}"}
        return {"ok": True}

    def ek_sil(self, yol: str) -> dict:
        self._ekler = [y for y in self._ekler if y != yol]
        return {"ok": True}

    def _dosya_birakildi(self, e: dict) -> None:
        """pencere.dom.document.events.drop olayi (bkz. main()).

        Gercek dosya yolu tarayici File API'sinde YOK (guvenlik nedeniyle
        taraycilar bunu vermez) — pywebview'in kendi enjeksiyonu her dosyaya
        'pywebviewFullPath' alanini ekliyor, yol oradan okunur.
        """
        dosyalar = (e.get("dataTransfer") or {}).get("files") or []
        yollar = [d.get("pywebviewFullPath") for d in dosyalar if d.get("pywebviewFullPath")]
        if yollar:
            self._son_birakma = self._ek_kaydet(yollar)

    def birakilan_ekleri_al(self) -> dict:
        """JS surukle-birak sonucunu buradan cekiyor (olay Python tarafinda geliyor)."""
        sonuc = getattr(self, "_son_birakma", None)
        self._son_birakma = None
        return sonuc or {"ok": True, "ekler": [], "uyarilar": []}

    def ek_yapistir(self) -> dict:
        """Panodaki dosyalari eke ekler (Ctrl+V). Tarayici clipboard API'si
        Explorer'da kopyalanmis dosyalari (CF_HDROP) vermiyor, o yuzden
        Windows'ta dogrudan clipboard'a bakiyoruz; olmayan platformda ya da
        panoda dosya yoksa sessizce bos doner, JS metne yapistirmaya devam eder.
        """
        yollar = _pano_dosyalari()
        if not yollar:
            return {"ok": True, "ekler": [], "uyarilar": []}
        return self._ek_kaydet(yollar)

    # ------------------------------------------------------------------
    # degisiklikler / geri alma
    # ------------------------------------------------------------------
    def gecmis(self) -> dict:
        """Ajanin yaptigi, henuz geri alinmamis dosya islemleri."""
        try:
            return {"ok": True, "kayitlar": journal.bekleyen_kayitlar(30)}
        except Exception as e:
            return {"ok": False, "hata": f"Gunluk okunamadi: {e}"}

    def geri_al(self, yol: str) -> dict:
        """Belirtilen dosyanin son islemini geri alir.

        Geri almanin kendisi de yedeklenir (journal.py), yani yanlis basilan bir
        dugme kalici kayba yol acmaz.
        """
        try:
            return {"ok": True, "mesaj": journal.geri_al(yol)}
        except Exception as e:
            return {"ok": False, "hata": f"Geri alinamadi: {e}"}


def _takilma_bekcisi(pencere: Any) -> None:
    """Arayuz thread'i donarsa (Windows: "Python yanit vermiyor") butun
    thread'lerin yigin izini ~/.vekil/takilma.log'a yazar.

    Neden: 2026-09-15'te pencere dort kez dondu, WER raporunda yalnizca imza
    var, Python yigini yok. Ilk donma py-spy ile yakalandi (_one_al ->
    on_top kilitlenmesi, oradaki nota bak); bir sonrakinin de kanitla
    gelmesi icin bu bekci duruyor.

    Nasil: evaluate_js arayuz thread'inde Invoke ile kosar; o thread donmussa
    cagri hic donmez. Bekci cagriyi yapmadan once faulthandler'in C duzeyi
    zamanlayicisini kurar, cagri donerse iptal eder. Python duzeyinde
    olcum YAPILMIYOR: gozlenen donmada GIL, .NET ozellik atamasinda bekleyen
    thread'de kaldi; o durumda ne yeni thread baslar ne time.sleep doner
    (ilk surum boyle sessiz kaldi). faulthandler'in zamanlayicisi GIL
    istemez, dogrudan dosya tanimlayicisina yazar. Daemon thread, kapanisi
    geciktirmez. Tek seferlik: ayni donma icin ust uste rapor gurultu olur.
    """
    import faulthandler
    import time

    ESIK_SN = 15.0

    def _dongu() -> None:
        time.sleep(5.0)
        try:
            yol = journal.KOK / "takilma.log"
            yol.parent.mkdir(parents=True, exist_ok=True)
            # Dosya acik kalmali: faulthandler yalnizca tanimlayiciyi tutar.
            f = open(yol, "a", encoding="utf-8")
            f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} oturum basladi; "
                    f"asagida 'Timeout' varsa arayuz thread'i {ESIK_SN:.0f} sn "
                    f"yanit vermedi =====\n")
            f.flush()
        except Exception:
            return
        # Olu adam kolu: zamanlayici HIC iptal edilmez, her turda yeniden
        # kurulur. Iptal edip uyuyan surumde donma uyku sirasinda gelirse
        # (GIL kilitliyken sleep de donmez) yeniden kurulamiyordu — testte
        # yakalandi. Tur suresi (ping + 3 sn) esigin cok altinda.
        while True:
            faulthandler.dump_traceback_later(ESIK_SN, repeat=False, file=f)
            try:
                pencere.evaluate_js("1")
            except Exception:
                pass
            time.sleep(3.0)

    threading.Thread(target=_dongu, daemon=True, name="limina-bekci").start()


def _bagimliliklari_denetle() -> str | None:
    """Ajan yolunun (vekil_v0 -> mcp_bridge) ihtiyac duydugu paketler bu
    yorumlayicida var mi? pencere.py'nin kendisi mcp/google.genai'yi ICE
    AKTARMAZ; ajan tembel yuklenir (gui_kopru._varsayilan_kosucu). Bu yuzden
    yanlis yorumlayiciyla (.venv yerine sistem Python'u) acilan pencere
    sorunsuz gorunur, ilk gorevde/yenilemede "No module named 'mcp'" ile
    duser — ve hata sohbet balonunda cikar, nedeni anlasilmaz. Denetim bu
    yuzden pencere ACILMADAN yapiliyor.
    """
    import importlib.util
    # google.genai artik zorunlu degil: saglayici secime bagli (limina.model).
    # Gemini seciliyken paket yoksa gorev basinda anlasilir bir hata doner.
    eksik = [ad for ad in ("mcp", "httpx")
             if importlib.util.find_spec(ad) is None]
    if not eksik:
        return None
    venv = PROJE_KOKU / ".venv" / "Scripts" / "python.exe"
    ipucu = (f"Proje sanal ortamiyla baslat (proje kokunden):\n  {venv} -m limina"
             if venv.exists() else
             f"Kur: {sys.executable} -m pip install -r requirements.txt")
    return (f"Eksik paket(ler): {', '.join(eksik)}\n"
            f"Calisan yorumlayici: {sys.executable}\n  {ipucu}")


def main() -> int:
    hata = _bagimliliklari_denetle()
    if hata:
        print(f"\n  ORTAM HATASI\n  {hata}\n")
        return 1

    from limina import kurulum
    kurulum.politikayi_hazirla()        # ilk acilis: policy.toml / persona.md sablondan

    politika = Politika(KOK / "policy.toml")

    # gate.py ayni kontrolu vekil_v0 ice aktarilirken de yapiyor; burada tekrar
    # ediliyor cunku hata mesaji pencere acilmadan, terminalde gorunsun.
    hata = politika.kod_koku_yazilabilir_mi(KOK)
    if hata:
        print(f"\n  YERLESIM HATASI\n  {hata}\n")
        return 1

    if not ARAYUZ.exists():
        print(f"Arayuz dosyasi yok: {ARAYUZ}\n"
              f"index.html '{KOK / 'arayuz'}' klasorunun icinde olmali.")
        return 1

    api = Api(politika)
    pencere = webview.create_window(
        "Limina",
        str(ARAYUZ),
        js_api=api,
        width=1000, height=780, min_size=(640, 480),
        background_color="#0F0F0F",
        # pywebview varsayilani False: metin secimini SESSIZCE kapatir (body'ye
        # user-select:none enjekte eder). Gorev metinleri/ajan ciktilari
        # secilemiyor/kopyalanamiyor sikayetinin kaynagi buydu.
        text_select=True,
    )
    api._pencere = pencere

    def _surukle_birak_bagla() -> None:
        """Surukle-birak DOM olaylarina baglanir. pywebview'in eski
        'events.file_drop' API'si bu surumde YOK (kaldirildi); guncel yol
        window.dom.document.events uzerinden DOMEventHandler ile dinlemek.
        Baglanma pencere YUKLENDIKTEN SONRA yapilmali (webview.start'a
        callback olarak verilir) — dom.document erisimi JS'e evaluate_js
        atar, pencere hazir olmadan cagrilirsa patlar.
        Yoksa sessizce dusuyoruz; dosya secici dugmesi her kosulda calisiyor.
        """
        _takilma_bekcisi(pencere)
        try:
            from webview.dom import DOMEventHandler

            def _engelle(*_args) -> None:
                pass    # sadece native tarafta preventDefault/stopPropagation icin

            pencere.dom.document.events.dragenter += DOMEventHandler(_engelle, True, True)
            pencere.dom.document.events.dragover += DOMEventHandler(_engelle, True, True, debounce=500)
            pencere.dom.document.events.drop += DOMEventHandler(api._dosya_birakildi, True, True)
            api._surukle_destegi = True
        except Exception:
            api._surukle_destegi = False

    # Pencere kapaniyorsa onay alinamaz -> RED (SECURITY.md).
    pencere.events.closing += lambda: api._kopru.kapat()

    # MCP sunuculari pencereyle birlikte ARKA PLANDA baglanir: acilisi
    # bloklamaz, kullanici ilk gorevi yazana kadar cogu zaman hazirdir; hazir
    # degilse gorev baglantiyi bekler (vekil_v0.mcp_baglan kilidi).
    def _mcp_arkada() -> None:
        try:
            from limina import vekil_v0
            vekil_v0.mcp_arka_planda_baglan()
        except Exception as e:      # ajan yuklenemedi: ilk gorevde ayni hata sohbet balonunda cikar
            print(f"  (MCP arka plan baglantisi baslatilamadi: {type(e).__name__}: {e})")
    threading.Thread(target=_mcp_arkada, daemon=True, name="mcp-on-yukle").start()

    webview.start(_surukle_birak_bagla, icon=str(IKON) if IKON.exists() else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
