# ceviri_arayuz_testi.py — Ingilizce modda arayuzun HER gorunumu cevrilmis mi?
#
# Neden calisma aninda: statik tarama "A " + "B" birlestirmelerini yanlis
# okuyor (son denetimde 27 bulgunun 25'i yanlis alarmdi). Burada t() sarilir,
# EN modunda her gorunum/sekme acilir ve sozlukte OLMAYAN her Turkce anahtar
# yakalanir. Bu oturumda iki kez olan hatayi yakalar: kaynak metin degisir,
# EN karsiligi eski metinde kalir, arayuz Ingilizce kullaniciya Turkce konusur.
#
#   python tests/ceviri_arayuz_testi.py
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from playwright.sync_api import sync_playwright
from pevrai import PAKET

SAHTE = """() => {
  const bos = () => Promise.resolve({ok: true, olaylar: [], calisiyor: false, sohbetler: [], kota: [],
    toplu_onaylar: [], kapali_araclar: [], uyarilar: [], aglar: [], projeler: [], kosular: [], ajanlar: [],
    yuvalar: {}, paketler: [], araclar: []});
  const ag = {ad: 'demo', aciklama: '', tetik: '', dugumler: [
    {kimlik: 'a', tur: 'dosya', baslik: 'A', metin: '{gorev}', yol: '', kapi: 'esik', esik: 1, k: null,
     yanlilik: 0, sira: null, kaynak: 'ajan', renk: '', konum: [0, 0, 0], etiketler: []},
    {kimlik: 'b', tur: 'fikir', baslik: 'B', metin: 'x {gorev}', yol: '', kapi: 'en_az', esik: null, k: 2,
     yanlilik: 0, sira: null, kaynak: 'kullanici', renk: '', konum: [40, 0, 0], etiketler: []}],
    baglantilar: [{kaynak: 'a', hedef: 'b', agirlik: -1, gecikme: 1}]};
  window.pywebview = { api: new Proxy({}, { get: (_, ad) => {
    if (ad === 'ag_listesi') return () => Promise.resolve({ok: true, aglar: [{ad: 'demo', dosya: 'd.json', aciklama: '',
      tetik: '', dugum: 2, baglanti: 1, ajan: true, guncelleme: ''}]});
    if (ad === 'ag_getir') return () => Promise.resolve({ok: true, ag: JSON.parse(JSON.stringify(ag))});
    if (ad === 'ag_kaydet') return () => Promise.resolve({ok: true, uyarilar: []});
    if (ad === 'saglayici_bilgisi') return () => Promise.resolve({ok: true, saglayici: 'openai',
      saglayicilar: ['gemini', 'openai', 'anthropic'], adlar: {}, taban_url: '', anahtar_var: false,
      anahtar_maske: '', anahtar_kaynak: 'yok', ortam_degiskeni: 'OPENAI_API_KEY', keyring: false});
    if (ad === 'ayarlar_oku') return () => Promise.resolve({ok: true, model_varsayilan: 'm', model_guclu: 'g',
      okuma_koklari: ['C:/x'], yazma_koklari: ['C:/y'], profiller: {}, araclar: {}, mcp: {}, izinli_alanlar: ['a.com'],
      acma_klasoru: '', persona_acik: true, arayuz: {genel: {dil: 'en'}}, yasak_kaliplar: ['*.pem']});
    if (ad === 'baglantilar') return () => {
      const g = new Date(); g.setDate(g.getDate() + 1);
      const gece = g.getFullYear() + '-' + String(g.getMonth() + 1).padStart(2, '0') + '-'
        + String(g.getDate()).padStart(2, '0') + 'T00:00';
      return Promise.resolve({ok: true, derin: 'b1/m2', keyring: false,
        saglayici_adlari: {gemini: 'Google Gemini', openai: 'OpenAI-compatible', anthropic: 'Anthropic Claude'},
        hazirlar: [{kod: 'gemini', ad: 'Google Gemini', saglayici: 'gemini', taban_url: '', ornek: ['g1']},
                   {kod: 'ollama', ad: 'Ollama', saglayici: 'openai', taban_url: 'http://localhost:11434/v1',
                    ornek: [], anahtarsiz: true},
                   {kod: 'ozel', ad: 'Özel (OpenAI-uyumlu)', saglayici: 'openai', taban_url: '', ornek: []}],
        baglantilar: [
          {kimlik: 'b1', ad: 'First', saglayici: 'openai', taban_url: 'https://api.deepseek.com/v1',
           modeller: ['m1', 'm2'], sanal: false, anahtar_var: true, anahtar_maske: '****abcd',
           anahtar_kaynak: 'dosya', anahtarsiz_olabilir: true, dolu: {m1: gece}},
          {kimlik: 'b2', ad: 'Second', saglayici: 'gemini', taban_url: '', modeller: ['g1'], sanal: false,
           anahtar_var: false, anahtar_maske: '', anahtar_kaynak: 'yok', anahtarsiz_olabilir: false,
           dolu: {g1: '2026-01-01T10:15'}}]});
    };
    if (ad === 'arayuz_ayarlari') return () => Promise.resolve({ok: true, arayuz: {genel: {dil: 'en'}, gorunum: {}, sohbet: {}, gelismis: {}}});
    return bos;
  }})};
}"""

with sync_playwright() as p:
    # SwiftShader: Ekip alani 3B ofisle acilsin (ofis metinleri de taransin)
    tarayici = p.chromium.launch(channel="chrome", headless=True,
                                 args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    sayfa = tarayici.new_page(viewport={"width": 1280, "height": 900})
    hatalar = []
    sayfa.on("pageerror", lambda e: hatalar.append(str(e)))
    sayfa.goto((PAKET / "arayuz" / "index.html").as_uri()); sayfa.wait_for_timeout(400)
    sayfa.evaluate(SAHTE); sayfa.wait_for_timeout(200)
    # t()'yi sar: EN'de sozlukte olmayan anahtari kaydet
    sayfa.evaluate("""() => {
      window.EKSIK = new Set();
      const asil = window.t;
      window.t = function (m, p) {
        if (typeof m === 'string' && DIL === 'en' && !(m in CEVIRI.en) && /[çğıöşüÇĞİÖŞÜ]/.test(m)) window.EKSIK.add(m);
        return asil(m, p);
      };
    }""")
    sayfa.evaluate("dilAyarla('en')"); sayfa.wait_for_timeout(300)
    sayfa.evaluate("() => { const k = document.getElementById('karsilama'); if (k) k.remove(); karsilamaKur(); }")
    sayfa.wait_for_timeout(400)
    for gorunum in ("ag", "ekip", "araclar", "eklentiler", "sohbet"):
        sayfa.evaluate(f"gorunum('{gorunum}')"); sayfa.wait_for_timeout(500)
    # Ag: denetci + toplu panel + okuma
    sayfa.evaluate("gorunum('ag')"); sayfa.wait_for_timeout(500)
    sayfa.evaluate("() => { Ag.D.secili = 'a'; Ag.D.sekme = 'denetci'; Ag.ciz(); }"); sayfa.wait_for_timeout(300)
    sayfa.evaluate("() => { Ag.D.secili = 'b'; Ag.ciz(); }"); sayfa.wait_for_timeout(300)
    sayfa.evaluate("() => { Ag.D.secililer = new Set(['a','b']); Ag.D.secili = null; Ag.ciz(); }"); sayfa.wait_for_timeout(300)
    sayfa.evaluate("() => { Ag.D.sekme = 'okuma'; Ag.ciz(); }"); sayfa.wait_for_timeout(300)
    # Ekip sekmeleri
    sayfa.evaluate("gorunum('ekip')"); sayfa.wait_for_timeout(400)
    for s in ("ajanlar", "projeler", "gecmis", "gorev"):
        sayfa.evaluate(f"() => {{ Ekip.D.sekme = '{s}'; Ekip.ciz(); }}"); sayfa.wait_for_timeout(250)
    # Ekip ofisi: 3B kip (ust cubuk, cekmece, etiketler) ve WebGL yok bilgi satiri
    print("  ofis kipi:", sayfa.evaluate("() => window.Ofis && Ofis.D.kip"))
    sayfa.evaluate("() => { Ofis.D.cekmece = false; Ofis.ciz(); Ofis.D.cekmece = true; Ofis.ciz(); }"); sayfa.wait_for_timeout(300)
    sayfa.evaluate("() => { const k = Ofis.D.kip; Ofis.D.kip = 'kart'; Ekip.ciz(); Ofis.D.kip = k; Ofis.D.iskelet = null; Ekip.ciz(); }")
    sayfa.wait_for_timeout(300)
    # Canli ofis: rozetler, balon, zarf, kartlar (ajan / sistem / masa+pano / ise alma / sonuc), oynatma cubugu
    for tip, veri in [("ekip_mesaj", {"durum": "planlaniyor", "kimlik": "k1"}),
                      ("ekip_mesaj", {"rol": "planlayici", "durum": "calisiyor", "kimlik": "k1"}),
                      ("onay_gerekli", {"istek": {"arac": "ekip_plan", "args": {}, "risk": "WRITE", "etki": "x", "yikici": False, "toplu_sunulabilir": False}}),
                      ("onay_sonucu", {"arac": "ekip_plan", "cevap": "evet"}),
                      ("ekip_mesaj", {"durum": "calisiyor", "kimlik": "k1", "uyeler": ["a", "b"]}),
                      ("arac_cagrildi", {"arac": "ekip_isci", "args": {"ad": "a", "ajan": "varsayilan"}, "ajan": "a", "masa": "bekleme"}),
                      ("arac_cagrildi", {"arac": "ekip_isci", "args": {"ad": "b", "ajan": "varsayilan"}, "ajan": "b", "masa": "bekleme"}),
                      ("adim_basladi", {"adim": 1, "ajan": "a"}),
                      ("arac_cagrildi", {"arac": "write_file", "args": {"path": "x.md"}, "ajan": "b", "masa": "dosya", "karar": "ALLOW"}),
                      ("ekip_mesaj", {"kimden": "a", "kime": "b", "metin": "hello", "sira": 1}),
                      ("hata", {"mesaj": "x", "ajan": "b"})]:
        sayfa.evaluate("(o) => olayIsle(o)", {"tip": tip, "veri": veri})
    sayfa.wait_for_timeout(300)
    for panel in ("{tur: 'ajan', kod: '~a'}", "{tur: 'ajan', kod: '@planlayici'}", "{tur: 'ajan', kod: '@birlestirici'}",
                  "{tur: 'masa', kod: 'istisare'}", "{tur: 'masa', kod: 'kod'}", "{tur: 'ise_al'}"):
        sayfa.evaluate(f"() => {{ Ofis.D.panel = {panel}; Ofis.ciz(); }}"); sayfa.wait_for_timeout(250)
    sayfa.evaluate("() => { olayIsle({tip: 'gorev_bitti', veri: {metin: 'ok', durduruldu: true}}); Ofis.D.panel = {tur: 'sonuc'}; Ofis.ciz(); }")
    sayfa.wait_for_timeout(300)
    sayfa.evaluate("() => { Ofis.D.oynatma = {kimlik: 'k', olaylar: [{t: 0, tip: 'ekip_mesaj', veri: {durum: 'planlaniyor'}}], i: 0, hiz: 4, duraklat: true, "
                   "durum: Ofis.D.durum, zamanlayici: null}; Ofis.ciz(); }")
    sayfa.wait_for_timeout(200)
    sayfa.evaluate("() => { Ofis.oynatmaBitir(); }")
    # Ayarlar: her sekme, gelismis acik
    sayfa.evaluate("gorunum('sohbet')")
    sayfa.evaluate("() => ayarlariAc('genel')"); sayfa.wait_for_timeout(600)
    sekmeler = sayfa.evaluate("() => (typeof AYAR_SEKMELERI !== 'undefined' ? AYAR_SEKMELERI : []).map(s => s[0])")
    for s in sekmeler:
        sayfa.evaluate(f"() => {{ ayarSekme = '{s}'; ayarMenusuCiz(); ayarSekmeCiz(); }}"); sayfa.wait_for_timeout(350)
        sayfa.evaluate("() => { const b = [...document.querySelectorAll('#ayar-ic button')].find(x => /Advanced|Gelişmiş/i.test(x.textContent)); if (b) b.click(); }")
        sayfa.wait_for_timeout(350)
    # Ayarlar > Model: API baglanti kartlari, duzenleme formu, yeni baglanti formu
    sayfa.evaluate("() => { ayarSekme = 'model'; ayarMenusuCiz(); ayarSekmeCiz(); }"); sayfa.wait_for_timeout(500)
    sayfa.evaluate("() => { const b = document.querySelectorAll('.api-kart .api-dugme')[2]; if (b) b.click(); }")
    sayfa.wait_for_timeout(300)
    duzenleme_formu = sayfa.evaluate("() => document.querySelectorAll('.api-form').length")
    sayfa.evaluate("() => { const b = [...document.querySelectorAll('.api-form button')]"
                   ".find(x => /İptal|Cancel/.test(x.textContent)); if (b) b.click(); }")
    sayfa.wait_for_timeout(200)
    sayfa.evaluate("() => { const b = document.querySelector('.api-ekle'); if (b) b.click(); }"); sayfa.wait_for_timeout(300)
    sayfa.evaluate("() => { const s = document.querySelector('.api-form select');"
                   " if (s) { s.value = '1'; s.dispatchEvent(new Event('change')); } }")
    sayfa.wait_for_timeout(200)
    api_kart = sayfa.evaluate("() => document.querySelectorAll('.api-kart').length")
    api_form = sayfa.evaluate("() => document.querySelectorAll('.api-form').length")
    # Sohbet ekranindaki model secici menusu
    sayfa.evaluate("() => { ayarlariKapat(); gorunum('sohbet'); document.getElementById('model-sec').click(); }")
    sayfa.wait_for_timeout(400)
    secici_oge = sayfa.evaluate("() => document.querySelectorAll('#menu-model.acik .oge').length")
    sayfa.evaluate("() => menuKapat()")
    sayfa.evaluate("""() => { olayIsle({tip: 'model_gecis', veri: {eski: 'A · m1', yeni: 'B · m2', sebep: 'limit'}});
        olayIsle({tip: 'model_gecis', veri: {eski: 'C · m3', yeni: '', sebep: 'anahtar'}});
        olayIsle({tip: 'hata', veri: {mesaj: 'x', kota: true, zincir: true}}); }""")
    sayfa.wait_for_timeout(200)
    # Yalnizca belli DURUMLARDA cizilen metinler: calisma ani taramasi ancak
    # gosterilen seyi gorebilir, bu durumlari da olustur.
    ayarlariKapat = "() => { if (typeof ayarlariKapat === 'function') ayarlariKapat(); }"
    sayfa.evaluate(ayarlariKapat)
    sayfa.evaluate("gorunum('ag')"); sayfa.wait_for_timeout(300)
    sayfa.evaluate("() => { calisiyor = true; arkaPlanDurumu(); }"); sayfa.wait_for_timeout(200)   # arka plan hapi
    sayfa.evaluate("""() => olayIsle({tip: 'onay_gerekli', veri: {istek: {arac: 'write_file',
        args: {path: 'kum/x.txt'}, risk: 'WRITE', etki: 'kum/x.txt', yikici: false,
        toplu_sunulabilir: false}}})"""); sayfa.wait_for_timeout(300)               # onay bekleyen hap
    sayfa.evaluate("() => arkaPlanDurumu()"); sayfa.wait_for_timeout(200)
    sayfa.evaluate("gorunum('sohbet')"); sayfa.wait_for_timeout(300)                 # onay karti sohbette
    sayfa.evaluate("() => { calisiyor = false; bekleyenOnay = null; arkaPlanDurumu(); }")
    eksik = sayfa.evaluate("() => Array.from(window.EKSIK)")
    tarayici.close()
print(f"\n1) Ingilizce modda {len(sekmeler)} ayar sekmesi ve butun gorunumler tarandi")
for m in sorted(eksik):
    print("  CEVRILMEMIS  " + m.replace(chr(10), " ")[:140])
print(("  GECTI  " if not eksik else "  KALDI  ") + f"cevrilmemis metin yok ({len(eksik)})")
print(("  GECTI  " if not hatalar else "  KALDI  ") + f"JS hatasi yok ({hatalar[:2]})")
api_tamam = duzenleme_formu == 1 and api_kart == 2 and api_form == 1 and secici_oge == 5
print(("  GECTI  " if secici_oge == 5 else "  KALDI  ")
      + f"model secici: otomatik + 3 model + yonet ({secici_oge} oge)")
print(("  GECTI  " if api_tamam else "  KALDI  ")
      + f"API ekrani tarandi (duzenleme formu {duzenleme_formu}, {api_kart} kart, yeni form {api_form})")
tamam = not eksik and not hatalar and api_tamam
print("\nSonuc: " + ("TUM TESTLER GECTI" if tamam else "test kaldi"))
sys.exit(0 if tamam else 1)
