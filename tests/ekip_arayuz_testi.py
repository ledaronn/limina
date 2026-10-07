# ekip_arayuz_testi.py — Ekip alani (pevrai/arayuz/ekip.js): headless Chrome, sahte API.
#
# Olculen: alan aciliyor, gorev baslatma dogru API cagrisiyla (proje + secili ajanlar),
# ekip_plan onay karti EKIP ALANINDA (sohbet akisinda degil), canli olaylar uye
# kartlarini/panoyu guncelliyor, kullanici panoya yazabiliyor, sekmeler JS
# hatasiz ciziliyor, dil degisince metinler Ingilizce.
#
#   python tests/ekip_arayuz_testi.py
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pevrai import PAKET

HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


SAHTE = """() => {
  const bos = () => Promise.resolve({ok: true, olaylar: [], calisiyor: false, sohbetler: [], kota: [], toplu_onaylar: [], kapali_araclar: []});
  window.CAGRI = [];
  window.pywebview = { api: new Proxy({}, { get: (_, ad) => {
    if (ad === 'ekip_projeler') return () => Promise.resolve({ok: true, projeler: [{kimlik: 'p1', ad: 'Kompost', klasor: 'D:/ornek/kum/kompost', aciklama: ''}]});
    if (ad === 'ajanlar') return () => Promise.resolve({ok: true, ajanlar: [
      {ad: 'yazar', saglayici: 'gemini', model: '', etkin_model: 'gemini-3.5-flash-lite', anahtar_yuvasi: '', rol: '', anahtar_var: true, taban_url: ''},
      {ad: 'tablocu', saglayici: 'openai', model: 'gpt-5-mini', etkin_model: 'gpt-5-mini', anahtar_yuvasi: 'ikinci', rol: '', anahtar_var: false, taban_url: ''}]});
    if (ad === 'anahtar_yuvalari') return () => Promise.resolve({ok: true, yuvalar: {gemini: [], openai: [{yuva: 'ikinci', kaynak: 'yok', maske: ''}], anthropic: []}});
    if (ad === 'ekip_kosular') return () => Promise.resolve({ok: true, kosular: [{kimlik: 'k1', proje: 'p1', gorev: 'eski', durum: 'bitti', baslangic: '2026-09-21T10:00:00'}]});
    if (ad === 'ekip_kosu') return (k) => Promise.resolve({ok: true, kosu: {kimlik: k, proje: 'p1', gorev: 'eski', durum: 'bitti', plan: [], sonuclar: [], pano: [], birlestirici: 'ok'}});
    if (ad === 'ekip_gorev_baslat') return (...a) => { window.CAGRI.push(['ekip_gorev_baslat', a]); return Promise.resolve({ok: true}); };
    if (ad === 'ekip_pano_yaz') return (...a) => { window.CAGRI.push(['ekip_pano_yaz', a]); return Promise.resolve({ok: true, sira: 1}); };
    if (ad === 'arayuz_ayarlari') return () => Promise.resolve({ok: true, arayuz: {genel: {dil: 'tr'}, gorunum: {}, sohbet: {}, gelismis: {}}});
    return bos;
  }})};
}"""


def ikon_kontrolu() -> None:
    """ekip.js'de ikon("ad") ile istenen her ad IKON tablosunda olmali: ikon()
    bilinmeyen adda hata vermez, BOS bir SVG cizer — ikon sessizce kaybolur."""
    import re
    print("\n0) Ekip alani ikonlari IKON tablosunda")
    kod = (PAKET / "arayuz" / "index.html").read_text(encoding="utf-8")
    bas = kod.find("const IKON")
    tablo = set(re.findall(r"\b([a-z0-9]+):\[", kod[bas:kod.find("\n};", bas)]))
    js = (PAKET / "arayuz" / "ekip.js").read_text(encoding="utf-8")
    istenen = set(re.findall(r'ikon\("([a-z0-9]+)"', js))
    istenen |= set(re.findall(r'\["[a-z]+", "([a-z0-9]+)", "[A-ZÇĞİÖŞÜ][^"]+"\]', js))  # alt gezinme (etiket buyuk harfle baslar)
    istenen |= set(re.findall(r'(?:etiket|dugme|meta)\([^)]*?"([a-z0-9]+)"\)', js))  # yardimcilar
    istenen |= set(re.findall(r'[a-z_]+: "([a-z0-9]+)"', js[js.find("DURUM_IKONU"):js.find("function durumIkonu")]))
    eksik = sorted(istenen - tablo)
    dogrula(len(istenen) >= 20, f"{len(istenen)} farkli ikon adi bulundu")
    dogrula(not eksik, f"tabloda olmayan ikon yok ({eksik})")


def main() -> int:
    from playwright.sync_api import sync_playwright
    html = PAKET / "arayuz" / "index.html"
    ikon_kontrolu()
    print("\n1) Ekip alani (headless Chrome)")
    with sync_playwright() as p:
        # Bu test Ekip alaninin KART gorunumunu sinar (WebGL yokken dusulen yol);
        # 3B ofis tests/ofis_arayuz_testi.py'de.
        tarayici = p.chromium.launch(channel="chrome", headless=True, args=["--disable-3d-apis"])
        sayfa = tarayici.new_page(viewport={"width": 1100, "height": 820})
        hatalar: list[str] = []
        sayfa.on("pageerror", lambda e: hatalar.append(str(e)))
        sayfa.goto(html.as_uri()); sayfa.wait_for_timeout(400)
        sayfa.evaluate(SAHTE); sayfa.wait_for_timeout(200)
        sayfa.evaluate("dilAyarla('tr')")
        sayfa.evaluate("gorunum('ekip')"); sayfa.wait_for_timeout(500)
        dogrula(sayfa.evaluate("() => document.getElementById('ekip-gorunum').classList.contains('acik')"), "Ekip alani acildi")
        dogrula(sayfa.evaluate("Ofis.D.kip") == "kart" and sayfa.evaluate("() => document.querySelector('#ekip-gorunum .ek-bilgi') !== null"),
                "WebGL yok: kart gorunumu + bilgi satiri")
        dogrula(sayfa.evaluate("() => getComputedStyle(document.getElementById('akis')).display === 'none'"), "sohbet akisi gizlendi")
        dogrula(sayfa.evaluate("() => document.querySelectorAll('.ek-cip.secili').length") == 2, "iki ajan varsayilan secili")
        dogrula(sayfa.evaluate("() => document.querySelectorAll('#ekip-gorunum svg').length") >= 12, "gorev sekmesi ikonlu")
        dogrula(sayfa.evaluate("() => [...document.querySelectorAll('#ekip-gorunum svg')].every(s => s.querySelector('path'))"), "bos (bilinmeyen adli) svg yok")
        sayfa.click("text=tablocu"); sayfa.wait_for_timeout(150)
        dogrula(sayfa.evaluate("() => document.querySelectorAll('.ek-cip.secili').length") == 1, "cip tiklayinca secim degisiyor")
        sayfa.click("text=Ekibi başlat"); sayfa.wait_for_timeout(150)
        dogrula(sayfa.evaluate("() => window.CAGRI.length") == 0, "bos gorevle baslatilmiyor")
        sayfa.fill("textarea.ek-gorev", "Kompost rehberi hazırla")
        sayfa.click("text=Ekibi başlat"); sayfa.wait_for_timeout(200)
        cagri = sayfa.evaluate("() => window.CAGRI")
        dogrula(bool(cagri) and cagri[0][0] == "ekip_gorev_baslat" and cagri[0][1][1] == "p1" and cagri[0][1][2] == ["yazar"],
                f"baslatma: proje + SECILI ajanlar gitti ({cagri})")

        def olay(tip, veri):
            sayfa.evaluate("(o) => olayIsle(o)", {"tip": tip, "veri": veri})
        olay("gorev_basladi", {"gorev": "x", "mod": "dengeli", "ekip": True})
        olay("ekip_mesaj", {"durum": "planlaniyor", "kimlik": "k2", "metin": "…"})
        olay("onay_gerekli", {"istek": {"arac": "ekip_plan", "args": {"alt_gorev": 2, "alan": "D:/x"}, "risk": "WRITE",
                                        "etki": "Çalışma alanı: D:/x\n• giris [yazar] → giris.md: yaz", "yikici": False, "toplu_sunulabilir": False}})
        sayfa.wait_for_timeout(200)
        dogrula(sayfa.evaluate("() => !!document.querySelector('#ekip-canli .onay')"), "ekip_plan onay karti EKIP ALANINDA")
        dogrula(sayfa.evaluate("() => !document.querySelector('#kolon .onay')"), "sohbet akisinda ayni kart YOK")
        dogrula(sayfa.evaluate("() => document.querySelector('#ekip-canli .onay').textContent.includes('giris.md')"), "kart plan metnini gosteriyor")
        olay("onay_sonucu", {"arac": "ekip_plan", "cevap": "evet"})
        olay("ekip_mesaj", {"durum": "calisiyor", "kimlik": "k2", "uyeler": ["giris", "tablo"]})
        olay("arac_cagrildi", {"arac": "write_file", "args": {"path": "D:/x/giris.md"}, "risk": "WRITE", "karar": "ALLOW", "ajan": "giris"})
        olay("ekip_mesaj", {"kimden": "giris", "kime": "tablo", "metin": "Başlık ## ile", "sira": 1})
        olay("arac_sonucu", {"arac": "ekip_isci", "ajan": "giris", "sonuc": "Giriş yazıldı.", "karar": "ALLOW"})
        sayfa.wait_for_timeout(200)
        dogrula(sayfa.evaluate("() => document.querySelectorAll('.ek-uye').length") == 2, "iki uye karti")
        dogrula(sayfa.evaluate("() => document.querySelector('.ek-uye.bitti strong').textContent") == "giris", "biten uye isaretli")
        dogrula(sayfa.evaluate("() => document.querySelector('.ek-mesaj').textContent.includes('Başlık ## ile')"), "pano mesaji listede")
        dogrula(sayfa.evaluate("() => document.querySelector('.ek-durum').textContent.includes('Üyeler çalışıyor')"), "durum satiri")
        sayfa.fill(".ek-pano-gir input", "Türkçe yazın"); sayfa.click("text=Gönder"); sayfa.wait_for_timeout(150)
        cagri = sayfa.evaluate("() => window.CAGRI")
        dogrula(cagri[-1][0] == "ekip_pano_yaz" and cagri[-1][1][0] == "Türkçe yazın", "kullanici panoya yazdi")
        olay("gorev_bitti", {"metin": "Birleştirme tamam.", "durduruldu": False}); sayfa.wait_for_timeout(200)
        dogrula(sayfa.evaluate("() => document.querySelector('.ek-sonuc') && document.querySelector('.ek-sonuc').textContent.includes('Birleştirme tamam')"),
                "birlestirici sonucu alanda")
        for sekme in ("ajanlar", "projeler", "gecmis"):
            sayfa.evaluate(f"() => {{ Ekip.D.sekme = '{sekme}'; Ekip.ciz(); }}"); sayfa.wait_for_timeout(150)
        dogrula(sayfa.evaluate("() => document.querySelectorAll('.ek-kart').length") >= 1, "gecmis listesi cizildi")
        sayfa.click(".ek-kart.tikla"); sayfa.wait_for_timeout(200)
        dogrula(sayfa.evaluate("() => document.querySelector('.ek-ic').textContent.includes('Listeye dön')"), "kosu detayi acildi")
        dogrula(sayfa.evaluate("() => [...document.querySelectorAll('#ekip-gorunum svg')].every(s => s.querySelector('path'))"), "gecmis detayinda da bos svg yok")
        sayfa.evaluate("dilAyarla('en')"); sayfa.evaluate("() => { Ekip.D.sekme = 'gorev'; Ekip.ciz(); }"); sayfa.wait_for_timeout(150)
        dogrula(sayfa.evaluate("() => document.querySelector('.ek-ic h2').textContent") == "Team task", "dil degisince Ingilizce")
        dogrula(not hatalar, f"JS hatasi yok ({hatalar})")
        tarayici.close()
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
