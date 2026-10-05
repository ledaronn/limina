"""kurulum_arayuz_testi.py — ilk kurulum ekrani, headless Chrome; sahte API.

Dogrulananlar: ekran yalnizca kurulum gerekliyse acilir; varsayilan dil
Ingilizce; adimlar secimi toplar ve TEK cagriyla (kurulum_uygula) yazar;
"Varsayilanlarla bitir" ekrandaki varsayilanlari gonderir; hatalar gosterilir;
dar ekranda yatay kaydirma yok; innerHTML yok (arayuz_testi genel denetler).

    python tests/kurulum_arayuz_testi.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import expect, sync_playwright  # noqa: E402

DURUM = {
    "ok": True, "gerekli": True, "dil": "en", "tema": "koyu", "ekip_gorunumu": "ofis",
    "calisma": "C:\\Users\\ornek\\Limina", "calisma_varsayilan": "C:\\Users\\ornek\\Limina",
    "ek_klasorler": [
        {"ad": "Downloads", "baslik": "İndirilenler", "yol": "C:\\Users\\ornek\\Downloads", "var": True, "secili": True},
        {"ad": "Desktop", "baslik": "Masaüstü", "yol": "C:\\Users\\ornek\\Desktop", "var": True, "secili": True},
        {"ad": "Documents", "baslik": "Belgeler", "yol": "C:\\Users\\ornek\\Documents", "var": False, "secili": False},
    ],
    "paketler": [
        {"ad": "tarayici", "baslik": "Tarayıcı", "aciklama": "Chrome'u ayrı bir profille açar.", "ikon": "web", "acik": True},
        {"ad": "notes", "baslik": "Smart Notes", "aciklama": "Yerel notlar.", "ikon": "dosya", "acik": False},
    ],
}

FAKE = """window.calls=[]; window.DURUM=%s; window.UYGULA_YANITI={ok:true,hatalar:[]};
window.pywebview={api:new Proxy({}, {get:(_,name)=>(...args)=>{
  window.calls.push({name,args:JSON.parse(JSON.stringify(args))});
  if(name==='kurulum_durumu')return Promise.resolve(window.DURUM);
  if(name==='kurulum_uygula')return Promise.resolve(window.UYGULA_YANITI);
  if(name==='klasor_sec')return Promise.resolve({ok:true,yol:'D:\\\\Isler'});
  if(name==='arayuz_ayarlari')return Promise.resolve({ok:true,arayuz:{genel:{dil:'en',kurulum_tamam:!window.DURUM.gerekli}}});
  if(name==='saglayici_bilgisi')return Promise.resolve({ok:true,anahtar_var:true});
  if(name==='ayarlar_oku')return Promise.resolve({ok:true,durum:{},arayuz:{genel:{}}});
  return Promise.resolve({ok:true,olaylar:[],sohbetler:[],komutlar:[],modeller:[],calisiyor:false,plugins:[],taslaklar:{}});
}})};"""

HATA = 0


def dogrula(kosul, mesaj):
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


def sayfa_ac(browser, durum, genislik=1280):
    sayfa = browser.new_page(viewport={"width": genislik, "height": 800})
    hatalar = []
    sayfa.on("pageerror", lambda e: hatalar.append(str(e)))
    sayfa.add_init_script("try{localStorage.clear()}catch(e){}")
    sayfa.add_init_script(FAKE % json.dumps(durum))
    sayfa.goto((Path(__file__).resolve().parents[1] / "limina/arayuz/index.html").as_uri())
    return sayfa, hatalar


def uygulanan(sayfa):
    return sayfa.evaluate("calls.filter(c=>c.name==='kurulum_uygula').map(c=>c.args[0])")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)

        print("\n1) Kurulum gerekli degilse ekran acilmaz")
        sayfa, hatalar = sayfa_ac(browser, {**DURUM, "gerekli": False})
        sayfa.wait_for_timeout(900)
        dogrula(not sayfa.locator("#kurulum-perde").is_visible(), "ekran kapali")
        dogrula(not hatalar, f"sayfa hatasi yok {hatalar}")
        sayfa.close()

        print("\n2) Adim adim: varsayilan Ingilizce, secimler tek cagriyla yazilir")
        sayfa, hatalar = sayfa_ac(browser, DURUM)
        perde = sayfa.locator("#kurulum-perde")
        expect(perde).to_be_visible(timeout=5000)
        dogrula(True, "ilk acilista ekran acildi")
        expect(sayfa.locator("#kurulum-baslik")).to_have_text("Welcome to Limina")
        dogrula(sayfa.locator("#mod-ad").inner_text() == "Balanced" and sayfa.locator("#model-ad").inner_text() == "Automatic",
                "Ingilizce acilista mod/model dugmeleri de Ingilizce (HTML'deki Turkce ilk metin kalmadi)")
        dogrula(sayfa.locator("input[name=k-dil]:checked").evaluate("e=>e.closest('label').textContent") == "English",
                "varsayilan dil English")
        sayfa.get_by_text("Türkçe", exact=True).click()
        expect(sayfa.locator("#kurulum-baslik")).to_have_text("Limina'ya hoş geldin")
        dogrula(sayfa.evaluate("DIL") == "tr", "dil secimi hemen uygulandi")
        sayfa.get_by_role("button", name="Devam").click()
        expect(sayfa.locator("#kurulum-baslik")).to_have_text("Klasörler")
        dogrula(sayfa.locator("input[name=k-calisma]:checked").evaluate("e=>e.closest('label').textContent").startswith("Varsayılan klasör"),
                "calisma klasoru: varsayilan secili")
        dogrula(sayfa.locator("input[name=k-ek-Documents]").is_disabled(), "olmayan klasor secilemez")
        sayfa.get_by_text("Kendi klasörümü seçeceğim").click()
        expect(sayfa.locator("label:has(input[name=k-calisma]:checked) .k-yol")).to_have_text("D:\\Isler")
        dogrula(True, "klasor secici sonucu gosterildi")
        sayfa.locator("label:has(input[name=k-ek-Downloads])").click()
        sayfa.get_by_role("button", name="Devam").click()
        expect(sayfa.locator("#kurulum-baslik")).to_have_text("Araçlar ve eklentiler")
        sayfa.locator("label:has(input[name=k-paket-tarayici])").click()
        sayfa.locator("label:has(input[name=k-paket-notes])").click()
        sayfa.get_by_role("button", name="Devam").click()
        expect(sayfa.locator("#kurulum-baslik")).to_have_text("Görünüm")
        sayfa.get_by_text("Açık tema", exact=True).click()
        dogrula(sayfa.evaluate("document.documentElement.dataset.tema") == "acik", "tema hemen onizlendi")
        sayfa.get_by_text("Sade kartlar", exact=True).click()
        dogrula(uygulanan(sayfa) == [], "son adima kadar hicbir sey yazilmadi")
        sayfa.get_by_role("button", name="Devam").click()
        expect(sayfa.locator("#kurulum-baslik")).to_have_text("Hazır")
        dogrula("D:\\Isler" in sayfa.locator("#kurulum-govde").inner_text(), "ozet secilen klasoru gosteriyor")
        sayfa.get_by_role("button", name="Şimdilik geç").click()
        expect(perde).to_be_hidden()
        u = uygulanan(sayfa)
        dogrula(len(u) == 1, "tek kurulum_uygula cagrisi")
        dogrula(u and u[0] == {"dil": "tr", "tema": "acik", "ekip_gorunumu": "kart",
                               "calisma": {"tur": "ozel", "yol": "D:\\Isler"},
                               "ek_klasorler": {"Downloads": False, "Desktop": True, "Documents": False},
                               "paketler": {"tarayici": False, "notes": True}}, f"gonderilen secimler: {u}")
        dogrula(not hatalar, f"sayfa hatasi yok {hatalar}")
        sayfa.close()

        print("\n3) Varsayilanlarla bitir + model ayarina gec; hata gosterimi")
        sayfa, hatalar = sayfa_ac(browser, DURUM)
        expect(sayfa.locator("#kurulum-perde")).to_be_visible(timeout=5000)
        sayfa.evaluate("window.UYGULA_YANITI={ok:false,hatalar:['Tarayıcı kapatılamadı']}")
        sayfa.get_by_role("button", name="Finish with defaults").click()
        expect(sayfa.locator(".k-hatalar")).to_contain_text("Tarayıcı kapatılamadı")
        dogrula(True, "hata metni gosterildi, ekran acik kaldi")
        u = uygulanan(sayfa)
        dogrula(u and u[0]["dil"] == "en" and u[0]["calisma"] == {"tur": "varsayilan"}
                and u[0]["paketler"] == {"tarayici": True, "notes": False}, f"varsayilanlar gonderildi: {u}")
        sayfa.get_by_role("button", name="Add a model connection").click()
        expect(sayfa.locator("#kurulum-perde")).to_be_hidden()
        expect(sayfa.locator("#ayar-perde")).to_be_visible()
        dogrula(True, "hata sonrasi ikinci tik ekrandan cikardi ve Ayarlar > Model acildi")
        dogrula(sayfa.evaluate("ayarSekme") == "model", "model sekmesi")
        dogrula(not hatalar, f"sayfa hatasi yok {hatalar}")
        sayfa.close()

        print("\n4) Dar ekran (telefon genisligi): yatay kaydirma yok")
        sayfa, hatalar = sayfa_ac(browser, DURUM, genislik=360)
        expect(sayfa.locator("#kurulum-perde")).to_be_visible(timeout=5000)
        sayfa.get_by_role("button", name="Continue").click()
        tasma = sayfa.evaluate("document.getElementById('kurulum').scrollWidth - document.getElementById('kurulum').clientWidth")
        dogrula(tasma <= 0, f"kurulum penceresi tasmiyor ({tasma}px)")
        kutu = sayfa.locator("#kurulum").bounding_box()
        dogrula(kutu["x"] >= 0 and kutu["x"] + kutu["width"] <= 360, f"pencere ekranda: {kutu}")
        sayfa.close()
        browser.close()

    print(f"\nSonuc: {'HEPSI GECTI' if HATA == 0 else f'{HATA} KALDI'}")
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
