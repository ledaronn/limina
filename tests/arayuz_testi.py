"""Arayuz sozlesmesini modelsiz, pencere acmadan denetler.

Asil isi ARAYUZ.md 9/4'u otomatik kurala cevirmek: arac ciktisi hicbir kod
yolunda HTML olarak ayristirilmamali. Kural bir yorum satiri olarak kalirsa
ilk aceleci degisiklikte kirilir; burada test ediliyor.

Calistirma:  python tests/arayuz_testi.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # proje koku -> 'pevrai' paketi
from pevrai import PAKET, PROJE_KOKU
from pevrai import kurulum
kurulum.politikayi_hazirla(sessiz=True)   # temiz klonda policy.toml sablondan

KOK = PROJE_KOKU                       # policy.toml burada
HTML = PAKET / "arayuz" / "index.html"

HATA_SAYISI = 0

# HTML metnini DOM'a ayristirarak sokan her sey. Biri bile gecerse
# okunan bir web sayfasi arayuze script enjekte edebilir.
YASAK_KALIPLAR = [
    r"\.innerHTML\b",
    r"\.outerHTML\b",
    r"\binsertAdjacentHTML\b",
    r"\bdocument\.write\b",
    r"\bcreateContextualFragment\b",
    r"\beval\s*\(",
    r"\bnew\s+Function\s*\(",
]

# Uzak kaynak: pencere calistigi anda ag baglantisi olmamali (offline calisir,
# ve tedarik zinciri yuzeyi acmaz). Butun varliklar diskten gelir.
UZAK_KALIPLAR = [r"src\s*=\s*[\"']https?://", r"href\s*=\s*[\"']https?://",
                 r"\bfetch\s*\(\s*[\"']https?://"]


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA_SAYISI
    if kosul:
        print(f"  GECTI  {mesaj}")
    else:
        HATA_SAYISI += 1
        print(f"  KALDI  {mesaj}")


def satir_no(metin: str, indeks: int) -> int:
    return metin.count("\n", 0, indeks) + 1


def kod_govdesi(metin: str) -> str:
    """Yorumlari bosluga cevirir, satir numaralari korunur.

    Yorumun icinde 'innerHTML' gecmesi bir ihlal degil (tarayici yorumu
    calistirmaz) — kuralin kendisini anlatan satir testi kirmasin diye.
    '//' ancak ':' ile onunde degilse yorum sayilir, yoksa https:// kesilirdi.
    """
    def bosalt(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    metin = re.sub(r"/\*.*?\*/", bosalt, metin, flags=re.S)      # /* ... */
    metin = re.sub(r"<!--.*?-->", bosalt, metin, flags=re.S)     # <!-- ... -->
    metin = re.sub(r"(?<!:)//[^\n]*", bosalt, metin)             # // ...
    return metin


def _kare_uret() -> str:
    """640x360 (16:9) gecerli bir JPEG, base64. En-boy orani testinin girdisi."""
    import base64
    import io
    from PIL import Image
    tampon = io.BytesIO()
    Image.new("RGB", (640, 360), (40, 40, 40)).save(tampon, "JPEG")
    return base64.b64encode(tampon.getvalue()).decode("ascii")


# pywebview yerine: her api cagrisi "ok" ve bos liste doner. Yoklama dongusu
# (yokla) bununla sessizce doner; olaylar dogrudan olayIsle'ye verilir.
SAHTE_API = ("() => { window.pywebview = { api: new Proxy({}, { get: () => () => "
             "Promise.resolve({ok:true, olaylar:[], sohbetler:[], komutlar:[], tavan:0, "
             "calisiyor:false}) }) }; }")


def tarayici_karti_testi() -> None:
    """Tarayici kartinin davranisi: headless Chrome'da, modelsiz, pencere acmadan.

    Playwright zaten proje bagimliligi (tarayici.py). Statik metin analizi
    "bir kart var, icinde uc adim" gibi bir iddiayi sinayamaz; bunun icin
    JS'in gercekten kosmasi gerekiyor. Kurulu Chrome headless acilir.
    """
    print("\n6) Etkinlik karti (headless Chrome, modelsiz)")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:      # test ATLANMAZ, kirmizi yanar: sessiz atlama degersiz
        dogrula(False, f"playwright ice aktarilamadi, davranis testi kosamadi: {e}")
        return
    kare = _kare_uret()

    with sync_playwright() as p:
        try:
            tarayici = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            tarayici = p.chromium.launch(headless=True)
        sayfa = tarayici.new_page(viewport={"width": 1000, "height": 780})
        sayfa.goto(HTML.resolve().as_uri())
        sayfa.evaluate(SAHTE_API)
        # Varsayilan arayuz dili Ingilizce; bu test KAYNAK dildeki (Turkce)
        # metinleri karsilastiriyor. Ceviriyi degil davranisi sinadigi icin
        # dil burada Turkce'ye sabitlenir — ceviri sozlugu degisince test kirilmasin.
        sayfa.evaluate("dilAyarla('tr')")

        def olay(tip: str, veri: dict) -> None:
            sayfa.evaluate("(o) => olayIsle(o)", {"tip": tip, "veri": veri})

        def say(secici: str) -> int:
            return sayfa.evaluate("(s) => document.querySelectorAll(s).length", secici)

        def bosluk() -> dict:
            return sayfa.evaluate(
                "() => { const k = document.querySelector('.etkinlik .kare-ac').getBoundingClientRect();"
                " const i = document.querySelector('.etkinlik .kare img').getBoundingClientRect();"
                " return {kutu: k.height, img: i.height, genislik: k.width,"
                "         imgGenislik: i.width, oran: i.width / i.height}; }")

        # --- uc tarayici adimi, uc ayri model turu (adim 1, 2, 3) ---
        olay("gorev_basladi", {"gorev": "wikipedia'da trigonometri ara", "mod": "dengeli"})
        for adim, (arac, sure) in enumerate(
                [("browser_open", 1.2), ("browser_read", 0.03), ("browser_click", 0.5)], 1):
            olay("arac_cagrildi", {"arac": arac, "args": {"url": "https://tr.wikipedia.org"},
                                   "risk": "READ", "karar": "ALLOW", "adim": adim, "sira": adim})
            olay("arac_sonucu", {"arac": arac, "sonuc": "ok", "karar": "ALLOW", "sure_sn": sure})
            olay("tarayici", {"kare": kare, "url": "https://tr.wikipedia.org", "baslik": "Vikipedi"})

        dogrula(say(".etkinlik") == 1, f"uc tarayici adimi -> BIR kart ({say('.etkinlik')})")
        dogrula(say(".etkinlik .adim") == 3, f"kartin icinde uc adim ({say('.etkinlik .adim')})")
        dogrula(say("#sabit.dolu .etkinlik") == 1 and say("#kolon .etkinlik") == 0,
                "gorev surerken kart #sabit'te (yazi alaninin ustunde), akista degil")
        sureler = sayfa.evaluate(
            "() => Array.from(document.querySelectorAll('.etkinlik .adim .sure')).map(s => s.textContent)")
        dogrula(sureler == ["1.2 sn", "<0.1 sn", "0.5 sn"],
                f"0.03 sn '<0.1 sn' diye gosteriliyor, '0.0' degil ({sureler})")
        ozet = sayfa.evaluate("() => document.querySelector('.etkinlik .ozet .alt').textContent")
        dogrula(ozet.startswith("3 işlem") and "1.7 sn" in ozet, f"ozet satiri: {ozet!r}")
        bilgi = sayfa.evaluate("() => document.querySelector('.etkinlik .kare-gizlilik').title")
        dogrula(bilgi == "Pevrai bu sayfayı kullanıyor. Görüntü kaydedilmez ve modele gönderilmez.",
                "gizlilik aciklamasi kisa bilgi etiketinin uzerinde korunuyor")
        dogrula(sayfa.locator(".kare-alan").inner_text() == "tr.wikipedia.org"
                and sayfa.locator(".kare-sayfa").inner_text() == "Vikipedi",
                "site adresi ve sayfa adi onizlemenin ustunde")
        dogrula(sayfa.locator(".adim:visible").count() == 1,
                "varsayilan gorunumde yalnizca son islem gorunur")
        sayfa.locator(".adim-gecmisi").click()
        dogrula(sayfa.locator(".adim:visible").count() == 3
                and sayfa.locator(".adim-gecmisi").get_attribute("aria-expanded") == "true",
                "islem gecmisi tum adimlari acar")
        sayfa.locator(".adim-gecmisi").click()

        sayfa.wait_for_function("() => document.querySelector('.etkinlik .kare img').naturalWidth > 0")
        for g, y in [(1000, 780), (640, 480), (1400, 900), (390, 640)]:
            sayfa.set_viewport_size({"width": g, "height": y})
            b = bosluk()
            dogrula(b["kutu"] >= 48 and b["img"] >= b["kutu"]
                    and abs(b["genislik"] - b["imgGenislik"]) < 1.5
                    and abs(b["oran"] - 640 / 360) < 0.02,
                    f"{g}x{y}: onizleme tam genislikte, {b['kutu']:.0f}px yukseklik, oran 16:9 korundu")
            # Sabit kart akisi yutmasin: 640x480'de kart butun ekrani kapliyor,
            # onay karti gorunmez kaliyordu (gozlemlendi). Butce: kart <= yarim
            # pencere, bilgi satiri kartin GORUNUR alaninda.
            olcu = sayfa.evaluate(
                "() => { const k = document.querySelector('#sabit .etkinlik');"
                " const b = k.querySelector('.bilgi').getBoundingClientRect();"
                " const r = k.getBoundingClientRect();"
                " return {kart: r.height, akis: akis.getBoundingClientRect().height,"
                "         bilgiIcerde: b.bottom <= r.bottom + 1 && b.top >= r.top}; }")
            dogrula(olcu["kart"] <= y * 0.5 and olcu["akis"] >= 100 and olcu["bilgiIcerde"],
                    f"{g}x{y} sabitken kart {olcu['kart']:.0f}px <= yarim pencere, akisa "
                    f"{olcu['akis']:.0f}px kaldi, bilgi satiri gorunur")
            dogrula(sayfa.evaluate("document.documentElement.scrollWidth <= innerWidth"),
                    f"{g}x{y}: yatay tasma yok")

        # Acik buyuk goruntu ayni gorevin yeni karesi ve sayfa bilgisiyle yenilenir.
        sayfa.locator(".kare-genislet").click()
        baslik = '<img src=x onerror=alert(1)> ' + 'Uzun sayfa başlığı ' * 30
        olay("tarayici", {"kare": kare, "url": "https://example.org/" + "a" * 300, "baslik": baslik})
        dogrula(sayfa.locator("#kare-baslik").inner_text() == baslik.strip()
                and sayfa.locator("#kare-baslik img").count() == 0,
                "buyuk goruntude yeni sayfa adi yenilenir; dis kaynak metni HTML olamaz")
        dogrula(sayfa.evaluate("karePerde.scrollWidth <= karePerde.clientWidth"),
                "uzun sayfa adi ve adres modal pencereyi tasirmaz")
        sayfa.keyboard.press("Escape")

        # Uzun gecmis ve kisa pencere: resim listeyi ortemez; liste kendi icinde kayar.
        for i in range(12):
            olay("arac_cagrildi", {"arac": "browser_read", "args": {},
                                   "risk": "READ", "karar": "ALLOW", "adim": i + 4, "sira": i + 4})
            olay("arac_sonucu", {"arac": "browser_read", "sonuc": "ok", "karar": "ALLOW", "sure_sn": .03})
        for g, y in [(1400, 900), (640, 480), (390, 640)]:
            sayfa.set_viewport_size({"width": g, "height": y})
            sayfa.locator(".adim-gecmisi").click()
            olcu = sayfa.evaluate("""() => {
                const kart = document.querySelector('#sabit .etkinlik');
                const govde = kart.querySelector('.govde');
                const onizleme = kart.querySelector('.kare').getBoundingClientRect();
                return {tasmaz: kart.querySelector('.bilgi').getBoundingClientRect().bottom
                                  <= kart.getBoundingClientRect().bottom + 1,
                        ortmez: onizleme.bottom <= govde.getBoundingClientRect().top + 1,
                        kayar: govde.scrollHeight > govde.clientHeight,
                        akis: akis.getBoundingClientRect().height};
            }""")
            dogrula(olcu["tasmaz"] and olcu["ortmez"] and olcu["kayar"] and olcu["akis"] >= 100,
                    f"{g}x{y}: uzun islem gecmisi kaydirilir; onizleme, liste ve alt bilgi cakismiyor")
            sayfa.locator(".adim-gecmisi").click()

        # --- gorev bitince kart akista, kendi yerinde ---
        olay("yanit_parcasi", {"metin": "Sayfayı okudum."})
        olay("gorev_bitti", {"metin": "Sayfayı okudum.", "durduruldu": False})
        dogrula(say("#kolon .etkinlik") == 1 and say("#sabit .etkinlik") == 0
                and not sayfa.evaluate("() => sabit.classList.contains('dolu')"),
                "bitince kart akista, #sabit bos")
        sira = sayfa.evaluate(
            "() => Array.from(kolon.children).map(c => c.className.split(' ')[0])")
        dogrula(sira.index("kullanici-sar") < sira.index("etkinlik") < sira.index("yanit-sar"),
                f"kart akista kullanici mesaji ile yanit arasinda ({sira})")
        dogrula(sayfa.evaluate("() => document.querySelector('.etkinlik').classList.contains('bitti')"),
                "kart 'bitti' durumuna gecti")
        dogrula(sayfa.evaluate("() => document.querySelector('.etkinlik').open === false"),
                "bitince kart kapali durur (diger etkinlik kartlari gibi)")
        sayfa.evaluate("() => { document.querySelector('.etkinlik').open = true; }")
        for g, y in [(1000, 780), (640, 480)]:
            sayfa.set_viewport_size({"width": g, "height": y})
            b = bosluk()
            dogrula(b["img"] >= b["kutu"] and abs(b["genislik"] - b["imgGenislik"]) < 1.5,
                    f"{g}x{y} akista (acik): onizleme tam genislikte, yanlarda bosluk yok")

        # --- Genislet kartin uzerinde ---
        sayfa.locator(".etkinlik summary .kucuk").click()
        dogrula(sayfa.evaluate("() => karePerde.classList.contains('acik') && kareBuyuk.src.length > 100"),
                "Genişlet: buyutulmus kare acildi")
        dogrula(sayfa.evaluate("() => document.querySelector('.etkinlik').open === true"),
                "Genişlet summary'nin acik/kapali durumunu degistirmedi")
        dogrula(sayfa.evaluate("karePerde.open && document.activeElement.id === 'kare-kapat'"),
                "buyuk onizleme modal acilir, klavye odagi kapatma dugmesinde")
        sayfa.keyboard.press("Tab")
        dogrula(sayfa.evaluate("karePerde.contains(document.activeElement) || document.activeElement === document.body"),
                "modal acikken Tab sohbet kontrollerine gecmez")
        sayfa.keyboard.press("Escape")
        dogrula(sayfa.evaluate("!karePerde.open && !karePerde.classList.contains('acik')"
                               " && document.activeElement.classList.contains('kare-genislet')"),
                "Esc kapatti, odak buyutme dugmesine dondu")
        sayfa.locator(".kare-ac").click()
        dogrula(sayfa.evaluate("karePerde.open"), "onizlemeye tiklamak da buyutur")
        sayfa.locator("#kare-kapat").click()
        dogrula(sayfa.evaluate("!karePerde.open && !kareBuyuk.hasAttribute('src')"),
                "kapatma dugmesi diyalogu ve buyuk kareyi temizledi")

        # --- ikinci gorev: karisik (tarayici + dosya) -> yine TEK kart ---
        olay("gorev_basladi", {"gorev": "ikinci", "mod": "dengeli"})
        olay("arac_cagrildi", {"arac": "browser_open", "args": {"url": "https://example.com"},
                               "risk": "NETWORK", "karar": "ALLOW", "adim": 1, "sira": 1})
        olay("arac_sonucu", {"arac": "browser_open", "sonuc": "ok", "karar": "ALLOW", "sure_sn": 0.8})
        olay("arac_cagrildi", {"arac": "read_file", "args": {"path": "kum/a.txt"},
                               "risk": "READ", "karar": "ALLOW", "adim": 2, "sira": 2})
        olay("arac_sonucu", {"arac": "read_file", "sonuc": "icerik", "karar": "ALLOW", "sure_sn": 0.02})
        dogrula(say(".etkinlik") == 2 and say("#sabit .etkinlik") == 1,
                "yeni gorev yeni kart acti (eski akista, yeni sabit)")
        dogrula(say("#sabit .etkinlik .adim") == 2,
                "tarayici ve dosya adimi AYNI kartta (karisik gorevde iki sabit kart olmaz)")
        dogrula(sayfa.evaluate("() => document.querySelector('#sabit .etkinlik .ozet .bas').textContent") == "Çalışıyor",
                "karisik gorevin basligi 'Çalışıyor'")
        dogrula(sayfa.evaluate("() => document.querySelector('#sabit .etkinlik .kare.bos') !== null"
                               " && document.querySelector('#sabit .etkinlik .bilgi').hidden"),
                "kare gelmeden goruntu kutusu ve bilgi satiri gorunmez")
        olay("yanit_parcasi", {"metin": "bitti"})
        olay("gorev_bitti", {"metin": "bitti", "durduruldu": False})

        # --- bes dosya yazan gorev: BES kart degil BIR kart, bes adim; onay AYRI ---
        olay("gorev_basladi", {"gorev": "bes dosya", "mod": "dengeli"})
        for i in range(1, 6):
            olay("arac_cagrildi", {"arac": "write_file", "args": {"path": f"kum/d{i}.txt"},
                                   "risk": "WRITE", "karar": "ASK", "adim": i, "sira": i})
            if i == 3:
                olay("onay_gerekli", {"istek": {"arac": "write_file", "args": {"path": "kum/d3.txt"},
                                                "risk": "WRITE", "etki": "yeni dosya", "yikici": False,
                                                "toplu_sunulabilir": True}})
                dogrula(say("#kolon .onay") == 1 and say("#sabit .onay") == 0
                        and say("#sabit .etkinlik") == 1,
                        "onay karti akista AYRI, sabit kartin icine gomulmedi")
                olay("onay_sonucu", {"arac": "write_file", "cevap": "evet"})
            olay("arac_sonucu", {"arac": "write_file", "sonuc": "yazildi", "karar": "ASK", "sure_sn": 0.2})
        dogrula(say("#sabit .etkinlik") == 1 and say("#sabit .etkinlik .adim") == 5,
                f"bes dosya adimi -> BIR sabit kart, bes adim ({say('#sabit .etkinlik .adim')})")
        dogrula(sayfa.evaluate("() => document.querySelector('#sabit .etkinlik .ozet .bas').textContent")
                == "Dosyalar üzerinde çalışıyor", "baslik 'Dosyalar üzerinde çalışıyor'")
        dogrula(sayfa.evaluate("() => document.querySelector('#sabit .etkinlik .ozet .alt').textContent")
                == "5 işlem · 1.0 sn", "ozet: 5 islem, toplam sure")
        dogrula(sayfa.evaluate("() => !document.querySelector('#sabit .etkinlik').classList.contains('tarayici')"
                               " && document.querySelector('#sabit .etkinlik .bilgi').hidden"),
                "dosya kartinda canli goruntu ve tarayici bilgi satiri yok")
        olay("yanit_parcasi", {"metin": "bes dosya yazildi"})
        olay("gorev_bitti", {"metin": "x", "durduruldu": False})
        dogrula(say("#sabit .etkinlik") == 0 and say("#kolon .etkinlik") == 3,
                "bitince dosya karti da akista (uc gorev, uc kart)")
        sira =sayfa.evaluate("() => Array.from(kolon.children).map(c => c.className.split(' ')[0])")
        son_kart = max(i for i, c in enumerate(sira) if c == "etkinlik")
        dogrula(sira.index("onay") > son_kart and sira[-1] == "yanit-sar" and sira[son_kart - 1] == "kullanici-sar",
                f"akis sirasi: mesaj, kart, onay, yanit ({sira[son_kart - 1:]})")

        # --- arsiv oynatmasi: kart dogrudan akista, kare yok (kaydedilmiyor) ---
        sayfa.evaluate("() => akisiKur(["
                       "{tip:'gorev_basladi', veri:{gorev:'eski'}},"
                       "{tip:'arac_cagrildi', veri:{arac:'browser_read', args:{}, risk:'READ', karar:'ALLOW', adim:1, sira:1}},"
                       "{tip:'arac_sonucu', veri:{arac:'browser_read', sonuc:'x', karar:'ALLOW', sure_sn:0.03}},"
                       "{tip:'yanit_parcasi', veri:{metin:'ok'}},"
                       "{tip:'gorev_bitti', veri:{metin:'ok', durduruldu:false}}])")
        dogrula(say("#kolon .etkinlik") == 1 and say("#sabit .etkinlik") == 0
                and say(".etkinlik .kare.bos") == 1,
                "arsivden acilan sohbette kart akista, kare yok (kaydedilmedi)")
        tarayici.close()


# Durum tutan sahte api: araclar/arac_ayarla/araclar_hepsi/olaylari_cek
# birbirini gorur. Panel ve anahtar ayni durumu gostermeli.
SAHTE_ARAC_API = """() => {
  const D = { hepsi: false, kapali: new Set(), cagrilar: [] };
  const LISTE = [
    {ad:"browser_open", risk:"NETWORK", aciklama:"Sayfa acar", kaynak:"yerel"},
    {ad:"read_file", risk:"READ", aciklama:"Dosya okur", kaynak:"yerel"},
    {ad:"trash", risk:"DESTRUCTIVE", aciklama:"Cope tasir", kaynak:"yerel"},
    {ad:"okuma.add_note", risk:"?", aciklama:"Not ekler", kaynak:"MCP", gizli:true},
  ];
  function liste() {
    return LISTE.map((a) => {
      let durum = "acik", sebep = "";
      if (a.gizli) { durum = "gizli"; sebep = "policy.toml [araclar] içinde sınıflandırılmadı"; }
      else if (D.hepsi) { durum = "kapali"; sebep = "sohbet modu: bütün araçlar kapalı"; }
      else if (D.kapali.has(a.ad)) { durum = "kapali"; sebep = "bu sohbette kullanıcı kapattı"; }
      return Object.assign({}, a, {durum, sebep});
    });
  }
  window.SAHTE = D;
  window.pywebview = { api: {
    olaylari_cek: () => Promise.resolve({olaylar:[], sohbetler:[], calisiyor:false,
                                         hepsi_kapali: D.hepsi, kapali_araclar: Array.from(D.kapali)}),
    araclar: () => Promise.resolve({ok:true, araclar: liste(), hepsi_kapali: D.hepsi, calisiyor:false}),
    paketler: () => {
      /* pencere.Api.paketler'in sekli: yerlesik paketler + MCP sunuculari */
      const L = liste();
      const bul = (ad) => L.find((a) => a.ad === ad);
      const satir = (ad, baslik) => Object.assign({baslik, aciklama: bul(ad).aciklama}, bul(ad));
      return Promise.resolve({ok:true, hepsi_kapali: D.hepsi, calisiyor:false, risk_seviyeleri:["READ","WRITE"],
        paketler: [
          {paket:"cekirdek", tur:"yerlesik", ad:"Temel okuma", ikon:"kalkan", aciklama:"x", cekirdek:true, kurulu:true,
           araclar:[satir("read_file", "Dosya okuma")]},
          {paket:"dosya_duzenleme", tur:"yerlesik", ad:"Dosya düzenleme", ikon:"klasor", aciklama:"y", cekirdek:false, kurulu:true,
           araclar:[satir("trash", "Çöpe taşıma")]},
          {paket:"tarayici", tur:"yerlesik", ad:"Tarayıcı", ikon:"web", aciklama:"z", cekirdek:false, kurulu:true,
           araclar:[satir("browser_open", "Sayfa açma")]},
          {paket:"mcp:okuma", tur:"mcp", ad:"okuma", ikon:"araclar", aciklama:"", cekirdek:false, kurulu:true, tanimli:true,
           araclar:[satir("okuma.add_note", "Add note")]},
        ]});
    },
    araclar_hepsi: (acik) => { D.cagrilar.push(["araclar_hepsi", acik]); D.hepsi = !acik; D.kapali.clear();
                               return Promise.resolve({ok:true, hepsi_kapali: D.hepsi, kapali_araclar: []}); },
    arac_ayarla: (ad, acik) => { D.cagrilar.push(["arac_ayarla", ad, acik]);
                                 if (D.hepsi) { D.hepsi = false; LISTE.filter(a => !a.gizli).forEach(a => D.kapali.add(a.ad)); }
                                 if (acik) D.kapali.delete(ad); else D.kapali.add(ad);
                                 return Promise.resolve({ok:true}); },
    komutlar: () => Promise.resolve({ok:true, komutlar:[]}),
    mod_kotasi: () => Promise.resolve({ok:true, tavan:0}),
    sohbetler: () => Promise.resolve({ok:true, sohbetler:[]}),
  } };
}"""


def araclar_paneli_testi() -> None:
    print("\n7) Araclar paneli ve sohbet anahtari (headless Chrome, modelsiz)")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        dogrula(False, f"playwright ice aktarilamadi: {e}")
        return
    with sync_playwright() as p:
        try:
            tarayici = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            tarayici = p.chromium.launch(headless=True)
        sayfa = tarayici.new_page(viewport={"width": 1000, "height": 780})
        sayfa.goto(HTML.resolve().as_uri())
        sayfa.evaluate(SAHTE_ARAC_API)
        sayfa.evaluate("dilAyarla('tr')")    # kaynak dil metinleri karsilastiriliyor (bkz. bolum 6)
        sayfa.wait_for_timeout(700)          # yoklama bir tur donsun

        def kartlar() -> list[dict]:
            return sayfa.evaluate(
                "() => Array.from(document.querySelectorAll('.arac-kart')).map(k => ({"
                " ad: k.querySelector('.ad').textContent,"
                " risk: k.querySelector('.ust .rozet').title,"   # risk KODU ipucunda; gorunen metin cevrili
                " durum: k.querySelector('.durum .rozet').textContent,"
                " sebep: k.querySelector('.durum').textContent,"
                " dugme: (k.querySelector('.eylem button') || {}).textContent || null }))")

        sayfa.evaluate("() => gorunum('araclar')")
        sayfa.wait_for_function("() => document.querySelectorAll('.arac-kart').length === 4")
        k = {x["ad"]: x for x in kartlar()}
        dogrula(k["browser_open"]["risk"] == "NETWORK" and k["trash"]["risk"] == "DESTRUCTIVE",
                "risk seviyesi her kartta")
        dogrula(k["read_file"]["durum"] == "açık" and k["read_file"]["dugme"] == "Kapat",
                "acik arac: 'açık' + Kapat dugmesi")
        # Gizli (siniflandirilmamis) MCP araci: Ac/Kapat dugmesi YOK — onun yerine
        # risk secici + "Ekle" (policy.toml [araclar]'a yazar, kapi o zaman tanir).
        # Panel "acamaz": ancak KALICI bir siniflandirma yazarak gorunur kilar.
        dogrula(k["okuma.add_note"]["durum"] == "gizli" and k["okuma.add_note"]["dugme"] == "Ekle"
                and "sınıflandırılmadı" in k["okuma.add_note"]["sebep"]
                and sayfa.evaluate("() => !!Array.from(document.querySelectorAll('.arac-kart')).find(k => k.querySelector('.ad').textContent === 'okuma.add_note').querySelector('.eylem select')"),
                "gizli arac: sebebi gorunur, Ac/Kapat yok; risk secici + Ekle (siniflandirma) var")

        # tek arac kapat
        sayfa.evaluate("() => Array.from(document.querySelectorAll('.arac-kart')).find(k => k.querySelector('.ad').textContent === 'browser_open').querySelector('.eylem button').click()")
        sayfa.wait_for_function("() => Array.from(document.querySelectorAll('.arac-kart .durum .rozet')).some(r => r.textContent === 'kapalı')")
        k = {x["ad"]: x for x in kartlar()}
        cagri = sayfa.evaluate("() => SAHTE.cagrilar[SAHTE.cagrilar.length - 1]")
        dogrula(cagri == ["arac_ayarla", "browser_open", False], f"Kapat -> arac_ayarla(browser_open, false) ({cagri})")
        dogrula(k["browser_open"]["durum"] == "kapalı" and "kullanıcı kapattı" in k["browser_open"]["sebep"]
                and k["browser_open"]["dugme"] == "Aç",
                "kapali arac: 'kapalı' + sebep + Aç dugmesi")
        dogrula(sayfa.evaluate("() => document.querySelector('.arac-ozet span').textContent") == "Bu sohbette 1 araç kapalı.",
                "ozet satiri kapali sayisini soyluyor")
        dogrula(sayfa.evaluate("() => sohbetModu") is False, "tek arac kapali = sohbet modu DEGIL")

        # sohbet anahtari -> hepsi kapali; panel bunu gosterir
        sayfa.evaluate("() => gorunum('sohbet')")
        sayfa.evaluate("() => sohbetAnahtar.click()")
        sayfa.wait_for_function("() => sohbetModu === true")
        dogrula(sayfa.evaluate("() => SAHTE.cagrilar[SAHTE.cagrilar.length - 1]") == ["araclar_hepsi", False],
                "anahtar araclar_hepsi(false) dedi — panelle AYNI yol")
        dogrula(sayfa.evaluate("() => sohbetAd.textContent") == "Sohbet", "anahtar 'Sohbet' gosteriyor")
        sayfa.evaluate("() => gorunum('araclar')")
        sayfa.wait_for_function("() => (document.querySelector('.arac-ozet span') || {}).textContent === 'Sohbet modu: bu sohbette bütün araçlar kapalı.'")
        k = {x["ad"]: x for x in kartlar()}
        dogrula(all(k[a]["durum"] == "kapalı" and "sohbet modu" in k[a]["sebep"]
                    for a in ("browser_open", "read_file", "trash")),
                "panel: butun acilabilir araclar 'kapalı', sebep sohbet modu")
        dogrula(k["okuma.add_note"]["durum"] == "gizli", "gizli arac sohbet modunda da 'gizli' (kapali degil)")

        # panelden tek arac ac -> sohbet modundan cikar, anahtar 'Görev'e doner
        sayfa.evaluate("() => Array.from(document.querySelectorAll('.arac-kart')).find(k => k.querySelector('.ad').textContent === 'read_file').querySelector('.eylem button').click()")
        sayfa.wait_for_function("() => sohbetModu === false", timeout=3000)
        k = {x["ad"]: x for x in kartlar()}
        dogrula(k["read_file"]["durum"] == "açık" and k["trash"]["durum"] == "kapalı",
                "panelden read_file acildi, digerleri kapali kaldi")
        dogrula(sayfa.evaluate("() => sohbetAd.textContent") == "Görev",
                "anahtar yoklamadan 'Görev'e dondu (durum tek yerde)")

        # Hepsini ac
        sayfa.evaluate("() => Array.from(document.querySelectorAll('.arac-ozet button')).find(b => b.textContent === 'Hepsini aç').click()")
        sayfa.wait_for_function("() => (document.querySelector('.arac-ozet span') || {}).textContent === 'Bu sohbette bütün araçlar açık.'")
        dogrula(True, "Hepsini aç -> hepsi acik")

        # sohbet degisince anahtar yeni sohbetin durumuna doner (yoklama)
        sayfa.evaluate("() => { SAHTE.hepsi = true; }")
        sayfa.wait_for_function("() => sohbetModu === true")
        dogrula(sayfa.evaluate("() => sohbetAd.textContent") == "Sohbet",
                "yoklamadan gelen hepsi_kapali anahtari gunceller (sohbet gecisi)")
        tarayici.close()


def yol_tiklama_testi() -> None:
    """Sohbetteki yerel yol tiklanabilir; tik Explorer'a gider, calistirmaz.
    UNC yolu ne arayuzde tiklanabilir olur ne Python tarafinda acilir."""
    print("\n8) Yol tiklama: sohbetteki yol Explorer'da gosterilir (kural iki yerde)")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        dogrula(False, f"playwright ice aktarilamadi: {e}")
        return
    with sync_playwright() as p:
        try:
            tarayici = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            tarayici = p.chromium.launch(headless=True)
        sayfa = tarayici.new_page(viewport={"width": 1000, "height": 780})
        sayfa.goto(HTML.resolve().as_uri())
        sayfa.evaluate(
            "() => { window.CAGRI = []; window.pywebview = { api: { dosya_goster: (y) => {"
            " CAGRI.push(y); return Promise.resolve({ok: true}); } } };"
            " const k = document.createElement('div'); k.id = 'deneme';"
            " k.appendChild(markdown('yaz `D:\\\\kum\\\\a.txt` ve `\\\\\\\\sunucu\\\\pay\\\\b.txt` ve `read_file`'));"
            " document.body.appendChild(k); }")
        kodlar = sayfa.evaluate(
            "() => Array.from(document.querySelectorAll('#deneme code')).map(c => ({"
            " metin: c.textContent, yol: c.classList.contains('yol'), rol: c.getAttribute('role') }))")
        dogrula(kodlar[0]["yol"] and kodlar[0]["rol"] == "button", "yerel yol tiklanabilir (role=button)")
        dogrula(not kodlar[1]["yol"], "UNC yolu tiklanabilir DEGIL")
        dogrula(not kodlar[2]["yol"], "duz kod tiklanabilir DEGIL")
        sayfa.click("#deneme code.yol")
        dogrula(sayfa.evaluate("() => CAGRI") == ["D:\\kum\\a.txt"],
                "tik dosya_goster'e yolu aynen iletir")
        tarayici.close()

    # Python tarafi: ayni kural, Explorer cagrilmadan
    import subprocess
    from unittest.mock import patch
    from pevrai.pencere import Api
    from pevrai.gate import Politika
    api = Api(Politika(KOK / "policy.toml"))
    with patch.object(subprocess, "Popen") as popen:
        r = api.dosya_goster("\\\\sunucu\\pay\\b.txt")
        dogrula(not r["ok"] and not popen.called, "UNC yolu reddedilir, Explorer cagrilmaz")
        r = api.dosya_goster(str(KOK / "OLMAYAN_dosya_xyz.txt"))
        dogrula(not r["ok"] and not popen.called, "olmayan yol reddedilir")
        r = api.dosya_goster(str(KOK / "policy.toml"))
        args = popen.call_args[0][0] if popen.called else None
        dogrula(r["ok"] and args and args[0] == "explorer.exe" and args[1].startswith("/select,"),
                f"var olan dosya: explorer.exe /select ile (liste arguman) ({args})")
        popen.reset_mock()
        r = api.dosya_goster(str(KOK))
        args = popen.call_args[0][0] if popen.called else None
        dogrula(r["ok"] and args and args[0] == "explorer.exe" and not args[1].startswith("/select"),
                "klasor: dogrudan acilir")


def secim_testi() -> None:
    """Arayuz metinleri secilmez; yalnizca icerik (istem, yanit, cikti, kod)
    secilir. Ctrl+A ile secince dugmeler/ipuclari mavi yanmasin."""
    print("\n8b) Metin secimi: yalnizca istem ve cikti secilebilir")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        dogrula(False, f"playwright ice aktarilamadi: {e}")
        return
    with sync_playwright() as p:
        try:
            tarayici = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            tarayici = p.chromium.launch(headless=True)
        sayfa = tarayici.new_page(viewport={"width": 1000, "height": 780})
        sayfa.goto(HTML.resolve().as_uri())
        sayfa.evaluate("() => { kullaniciMesaji('istem metni'); yanitMesaji('yanit metni\\n\\n```py\\nx = 1\\n```'); }")
        secim = sayfa.evaluate("""() => {
          const s = (q) => { const e = document.querySelector(q); return e ? getComputedStyle(e).userSelect : 'YOK'; };
          return {ipucu: s('#dip .ipucu'), mod: s('#dip button'), ray: s('#ray button, nav button'),
                  istem: s('.kullanici'), yanit: s('.yanit p, .yanit'), kod: s('.yanit pre, .kod-blok pre'),
                  girdi: s('#girdi')};
        }""")
        for ad in ("ipucu", "mod", "ray"):
            dogrula(secim[ad] == "none", f"arayuz metni secilmez: {ad} ({secim[ad]})")
        for ad in ("istem", "yanit", "kod", "girdi"):
            dogrula(secim[ad] in ("text", "auto"), f"icerik secilebilir: {ad} ({secim[ad]})")
        # Ctrl+A: secilen metinde arayuz yazisi olmamali, icerik olmali
        sayfa.mouse.click(500, 300)
        sayfa.keyboard.press("Control+A")
        secilen = sayfa.evaluate("() => String(getSelection())")
        dogrula("Shift + Enter" not in secilen and "istem metni" in secilen,
                f"Ctrl+A yalnizca icerigi secer ({secilen[:60]!r})")
        tarayici.close()


def main() -> int:
    if not HTML.exists():
        print(f"  KALDI  {HTML} yok")
        return 1
    metin = HTML.read_text(encoding="utf-8")
    kod = kod_govdesi(metin)

    print("\n1) HTML enjeksiyon yolu kapali mi (ARAYUZ.md 9/4)")
    for kalip in YASAK_KALIPLAR:
        bulgular = [satir_no(kod, m.start()) for m in re.finditer(kalip, kod)]
        dogrula(not bulgular,
                f"{kalip} kullanilmiyor" if not bulgular
                else f"{kalip} -> satir {bulgular}")

    print("\n2) Uzak kaynak yok (offline calisir)")
    for kalip in UZAK_KALIPLAR:
        dogrula(not re.search(kalip, kod), f"{kalip} yok")

    # Arayuzun diger betikleri de ayni denetimden gecer (ekip, ag, ofis ve
    # depoya konmus three.js). Eklentiler (Codex) kendi testinde.
    print("\n2b) Diger arayuz betikleri: HTML enjeksiyonu ve uzak kaynak yok")
    betikler = sorted(list((PAKET / "arayuz").glob("*.js")) + list((PAKET / "arayuz" / "ofis").glob("*.js"))
                      + list((PAKET / "arayuz" / "vendor").glob("*.js")))
    betikler = [b for b in betikler if b.name != "eklentiler.js"]
    dogrula(len(betikler) >= 5, f"{len(betikler)} betik tarandi ({', '.join(b.name for b in betikler)})")
    for yol in betikler:
        govde = kod_govdesi(yol.read_text(encoding="utf-8"))
        ihlal = [kalip for kalip in YASAK_KALIPLAR + UZAK_KALIPLAR if re.search(kalip, govde)]
        dogrula(not ihlal, f"{yol.relative_to(PAKET / 'arayuz').as_posix()}: temiz ({ihlal})")
    kaynaklar = re.findall(r"<script[^>]*\bsrc\s*=\s*[\"']([^\"']+)", kod)
    dogrula(kaynaklar and all(not re.match(r"[a-z]+:", k) for k in kaynaklar),
            f"index.html yalnizca yerel betikleri yukluyor ({len(kaynaklar)})")

    print("\n3) Onay karti sozlesmesi")
    dogrula("toplu_sunulabilir" in kod,
            "'Tumu' dugmesi toplu_sunulabilir bayragina bagli")
    # Bayrak kontrolu ile dugme ayni satirda olmali; ayrisirlarsa kural sessizce kirilir.
    dogrula(re.search(r"if\s*\(\s*istek\.toplu_sunulabilir\s*\)\s*dugme\(", kod) is not None,
            "dugme yalnizca bayrak dogruyken uretiliyor")
    dogrula("untrusted_content" in kod,
            "dis kaynak ciktisi gorsel olarak isaretleniyor")

    print("\n3b) Ayarlar bolum ikonlari")
    # Her sekme ikon(ad) ile ciziliyor; IKON tablosunda olmayan bir ad SESSIZCE
    # bos bir SVG uretir (ikon(ad) bilinmeyen adda hata vermiyor). Sohbet
    # sekmesi boyle ikonsuz kalmisti. Ikonlar satir ici; tablo disina cikan
    # bir ad = ya yazim hatasi ya da uzak kaynak denemesi.
    ikon_bas = kod.find("const IKON")
    ikon_blok = kod[ikon_bas:kod.find("\n};", ikon_bas)]
    ikon_adlari = set(re.findall(r"\b([a-z0-9]+):\[", ikon_blok))
    sekmeler = re.findall(r'\["([a-z]+)",\s*"([a-z0-9]+)",\s*"[^"]+"\]',
                          kod[kod.find("const AYAR_SEKMELERI"):kod.find("function ayarlariAc")])
    dogrula(len(sekmeler) == 7, f"Ayarlar sekme listesi okundu ({len(sekmeler)} sekme; sadelestirme: 10 -> 7)")
    for kod_adi, ikon_adi in sekmeler:
        dogrula(ikon_adi in ikon_adlari, f"'{kod_adi}' sekmesinin ikonu IKON tablosunda ({ikon_adi})")

    print("\n4) Python tarafi")
    for dosya in ("pencere.py", "gui_kopru.py", "olaylar.py"):
        yol = PAKET / dosya
        dogrula(yol.exists(), f"{dosya} var")
    pencere = (PAKET / "pencere.py")
    if pencere.exists():
        p = pencere.read_text(encoding="utf-8")
        dogrula("kapat()" in p, "pencere kapanisi kopruye baglanmis (onay -> RED)")
        # Kaba: pencere.py metninde gecen her "calistir" bunu kirar, docstring
        # dahil. Bir kez oyle oldu ve alti tur "ilgisiz" diye tasindi. Kaba
        # olmasi kusur degil — kirmizi bir test ya duzeltilir ya silinir, tasinmaz.
        dogrula("calistir" not in p,
                "pencere.py ajan dongusunu dogrudan cagirmiyor (kopru uzerinden)")

    print("\n5) Yerlesim: ajan kendi kodunu degistiremiyor")
    politika_yolu = KOK / "policy.toml"
    if not politika_yolu.exists():
        dogrula(False, f"policy.toml bulunamadi ({politika_yolu}) - kod kokunde calistir")
    else:
        from pevrai.gate import Politika
        politika = Politika(politika_yolu)
        hata = politika.kod_koku_yazilabilir_mi(KOK)
        dogrula(hata is None, hata or f"kaynak kod ({KOK}) yazma koklerinin disinda")
        # Kontrolun gercekten calistigini da dogrula: kendi kokunu yazilabilir
        # ilan et, ihlali yakalamasi gerekir. Yakalamiyorsa test degersizdir.
        politika.yazma = [KOK]
        dogrula(politika.kod_koku_yazilabilir_mi(KOK) is not None,
                "kontrol ihlali gercekten yakaliyor")

    print("\n5b) Sag panel yok — tarayici gorunumu tek yerde (kart)")
    # Iki yerde iki tarayici gorunumu tutmak ikisinin zamanla ayrismasi demek.
    # Panel silindi; olu kodu ve CSS'i de silinmis olmali.
    for iz in ('id="calisma"', "#calisma", "calismaGoster", "calismaGizle", "calismaKilitli"):
        dogrula(iz not in metin, f"'{iz}' izi kalmamis")
    dogrula("Pevrai bu sayfayı kullanıyor" in metin and "modele gönderilmez" in metin,
            "bilgi satiri korunmus")

    tarayici_karti_testi()
    araclar_paneli_testi()
    yol_tiklama_testi()
    secim_testi()

    print("\n9) Masaustu kisayolu (pevrai.kisayol) gecici klasore yazilabiliyor")
    import tempfile
    from pevrai import kisayol
    dogrula(kisayol.IKON.exists(), f"ikon var ({kisayol.IKON.name})")
    with tempfile.TemporaryDirectory(prefix="pevrai_lnk_") as d:
        try:
            lnk = kisayol.kur(Path(d))
            dogrula(lnk.exists() and lnk.stat().st_size > 0, "Pevrai.lnk yazildi")
        except SystemExit as e:
            dogrula(False, f"kisayol kurulamadi: {e}")

    print(f"\nSonuc: {'TUM TESTLER GECTI' if HATA_SAYISI == 0 else f'{HATA_SAYISI} test kaldi'}")
    return 1 if HATA_SAYISI else 0


if __name__ == "__main__":
    sys.exit(main())
