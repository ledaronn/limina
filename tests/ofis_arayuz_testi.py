# ofis_arayuz_testi.py — Ekip ofisi (pevrai/arayuz/ofis/*.js): headless Chrome, sahte kopru.
#
# WebGL: Chrome --use-angle=swiftshader ile acilir (yazilim GL). WebGL yine de
# yoksa test 3B yolunu SINAYAMADIGINI yuksek sesle soyler ve kart gorunumu
# yolunu dogrular; "WebGL yok -> kart gorunumu" yolu her kosuda ayrica
# --disable-3d-apis ile sinanir (sessiz atlama yok).
#
# Olculen (docs/OFIS_TASARIM.md 5 Faz 2, 7):
#   - iskelet bir kez kurulur: tuval yeniden cizimde ayni oge
#   - masa ve ajan etiketleri DOM'da, secilemez; sistem karakterleri var
#   - kamera: sol surukle doner, sag surukle kaydirir, tekerlek IMLECIN
#     altindaki noktayi yerinde tutar, cift tik odaklanir, "Ofise don"
#   - kare talep uzerine: hareketsiz sahnede kare cizilmez; ofisten cikinca
#     1 sn boyunca kare sayisi 0; Ayarlar acikken 0
#   - plan onay karti ofisin ustundeki panelde (sohbet akisinda degil)
#   - dar pencere (390x640): yatay tasma yok
#   - performans: cizim cagrisi sayisi; kare suresi rakami yazilir, 33 ms hedefi
#     yalnizca --olcum ile sinanir (makineye bagli: ayni kod 21-34 ms)
#
#   python tests/ofis_arayuz_testi.py
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pevrai import PAKET

HATA = 0
WEBGL_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


SAHTE = """() => {
  const bos = () => Promise.resolve({ok: true, olaylar: [], calisiyor: false, sohbetler: [], kota: [], toplu_onaylar: [], kapali_araclar: []});
  window.CAGRI = [];
  const AJANLAR = [
    {ad: 'yazar', saglayici: 'gemini', etkin_model: 'gemini-3.5-flash', rol: 'Metin yazar.', anahtar_var: true, renk: '#dcaa65', gorunum: 1, baglanti: 'b1', baglanti_ad: 'Gemini', model: 'gemini-3.5-flash'},
    {ad: 'tablocu', saglayici: 'openai', etkin_model: 'gpt-5-mini', rol: '', anahtar_var: true, renk: '#79b9a0', gorunum: 4, baglanti: '', model: 'gpt-5-mini'},
    {ad: 'arastirmaci', saglayici: 'openai', etkin_model: 'deepseek-chat', rol: '', anahtar_var: true, renk: '#91a9e8', gorunum: 6, baglanti: '', model: ''}];
  window.pywebview = { api: new Proxy({}, { get: (_, ad) => {
    if (ad === 'ekip_projeler') return () => Promise.resolve({ok: true, projeler: [{kimlik: 'p1', ad: 'Kompost', klasor: 'D:/ornek/kum/kompost', aciklama: ''}]});
    if (ad === 'ajanlar') return () => Promise.resolve({ok: true, ajanlar: AJANLAR});
    if (ad === 'ofis_duzeni') return () => Promise.resolve({ok: true, masalar: [
      {kod: 'kod', ad: 'Kod masası', aciklama: 'k'}, {kod: 'dosya', ad: 'Dosya masası', aciklama: 'd'}, {kod: 'arsiv', ad: 'Arşiv', aciklama: 'a'},
      {kod: 'istisare', ad: 'İstişare masası', aciklama: 'i'}, {kod: 'ag', ad: 'Düşünce Ağı köşesi', aciklama: 'g'},
      {kod: 'web', ad: 'Web masası', aciklama: 'w'}, {kod: 'kapi', ad: 'Onay kapısı', aciklama: 'o'}, {kod: 'bekleme', ad: 'Dinlenme alanı', aciklama: 'b'}],
      ajanlar: AJANLAR.map((a) => ({ad: a.ad, renk: a.renk, gorunum: a.gorunum, baglanti: a.baglanti, baglanti_ad: a.baglanti_ad || '', model: a.model, rol: a.rol}))});
    if (ad === 'anahtar_yuvalari') return () => Promise.resolve({ok: true, yuvalar: {}});
    if (ad === 'ekip_kosular') return () => Promise.resolve({ok: true, kosular: [
      {kimlik: '20260924-101010', proje: 'p1', gorev: 'Kompost rehberi', durum: 'bitti', baslangic: '2026-09-24T10:10:10'},
      {kimlik: '20260924-090000', proje: 'p1', gorev: 'Eski kosu', durum: 'bitti', baslangic: '2026-09-24T09:00:00'}]});
    if (ad === 'ekip_kosu') return (k) => Promise.resolve({ok: true, kosu: {kimlik: k, proje: 'p1', gorev: 'x', durum: 'bitti', plan: [], sonuclar: [], pano: [], birlestirici: 'ok'}});
    if (ad === 'ekip_kosu_olaylari') return (k) => Promise.resolve({ok: true, olaylar: k === '20260924-101010' ? window.KAYIT || [] : []});
    if (ad === 'arayuz_ayarlari') return () => Promise.resolve({ok: true, arayuz: {genel: {dil: 'tr'}, gorunum: {}, sohbet: {}, gelismis: {}}});
    if (ad === 'baglantilar') return () => Promise.resolve({ok: true, baglantilar: [
      {kimlik: 'b1', ad: 'Gemini', saglayici: 'gemini', modeller: ['gemini-3.5-flash', 'gemini-3.5-pro'], anahtar_var: true},
      {kimlik: 'ds', ad: 'DeepSeek', saglayici: 'openai', modeller: ['deepseek-chat'], anahtar_var: false}]});
    if (ad === 'ofis_ajan_karti') return (a) => Promise.resolve({ok: true, ad: a, zincir: [
      {etiket: 'Gemini · gemini-3.5-flash', dolu_bitis: '2026-09-25T23:59'}, {etiket: 'Gemini · gemini-3.5-pro', dolu_bitis: ''}],
      yazdiklari: ['D:/x/giris.md']});
    if (ad === 'ajan_yaz') return (...a) => { const old=AJANLAR.find(x=>x.ad===a[0]); const value={ad: a[0], rol: a[4], renk: a[7], gorunum: a[8] == null ? 2 : a[8], baglanti: a[6], baglanti_ad: a[6]==='ds'?'DeepSeek':'Gemini',
      model: a[2], etkin_model: a[2], anahtar_var: true, saglayici: a[1] || (a[6]==='ds'?'openai':'gemini')};
      if(old)Object.assign(old,value);else AJANLAR.push(value); return Promise.resolve({ok: true}); };
    if (ad === 'ajan_sil') return (a) => { const i = AJANLAR.findIndex((x) => x.ad === a); if (i >= 0) AJANLAR.splice(i, 1); return Promise.resolve({ok: true}); };
    return bos;
  }})};
  /* her kopru cagrisi kaydedilir: oynatma sirasinda YAZMA cagrisi olmadigi denetlenir */
  const asil = window.pywebview.api;
  window.pywebview.api = new Proxy({}, { get: (_, ad) => (...a) => { window.CAGRI.push([ad, a]); return asil[ad](...a); } });
}"""


def sayfa_ac(p, genislik=1280, yukseklik=860, args=None):
    tarayici = p.chromium.launch(channel="chrome", headless=True, args=args if args is not None else WEBGL_ARGS)
    sayfa = tarayici.new_page(viewport={"width": genislik, "height": yukseklik})
    hatalar: list[str] = []
    sayfa.on("pageerror", lambda e: hatalar.append(str(e)))
    sayfa.goto((PAKET / "arayuz" / "index.html").as_uri()); sayfa.wait_for_timeout(400)
    sayfa.evaluate(SAHTE); sayfa.wait_for_timeout(150)
    sayfa.evaluate("dilAyarla('tr')")
    sayfa.evaluate("gorunum('ekip')"); sayfa.wait_for_timeout(1200)
    return tarayici, sayfa, hatalar


def kareler(sayfa) -> int:
    return sayfa.evaluate("OfisSahne.D.kareSayisi")


def statik_kontroller() -> None:
    print("\n0) Ofis dosyalari: ikonlar tabloda, three.js depoda ve surumu sabit")
    kod = (PAKET / "arayuz" / "index.html").read_text(encoding="utf-8")
    bas = kod.find("const IKON")
    tablo = set(re.findall(r"\b([a-z0-9]+):\[", kod[bas:kod.find("\n};", bas)]))
    istenen: set[str] = set()
    for js in (PAKET / "arayuz" / "ofis").glob("*.js"):
        metin = js.read_text(encoding="utf-8")
        istenen |= set(re.findall(r'ikon\("([a-z0-9]+)"', metin))
        istenen |= set(re.findall(r'ikonlu\([^,]+, "([a-z0-9]+)"', metin))
        istenen |= set(re.findall(r'\["[a-z]+", "([a-z0-9]+)", "[A-ZÇĞİÖŞÜ][^"]+"\]', metin))
    dogrula(len(istenen) >= 6 and not (istenen - tablo), f"ofis ikonlari tabloda ({sorted(istenen - tablo)})")
    three = PAKET / "arayuz" / "vendor" / "three.min.js"
    bas_metin = three.read_text(encoding="utf-8")[:600] if three.exists() else ""
    dogrula("three.js r159" in bas_metin and "SHA-256" in bas_metin, "vendor/three.min.js: surum ve kaynak basta yazili")
    dogrula((PAKET / "arayuz" / "vendor" / "THREE_LICENSE").exists(), "three.js lisansi depoda")
    dogrula('src="vendor/three.min.js"' not in kod, "three.js acilista yuklenmiyor (tembel)")


def webgl_yolu(p) -> None:
    print("\n1) 3B ofis (headless Chrome + SwiftShader)")
    tarayici, sayfa, hatalar = sayfa_ac(p)
    kip = sayfa.evaluate("Ofis.D.kip")
    if kip != "3b":
        print("  UYARI  WebGL bu ortamda acilamadi: 3B yolu SINANAMADI, kart gorunumu dogrulaniyor")
        dogrula(sayfa.evaluate("() => !!document.querySelector('#ekip-gorunum .ek-bilgi') && !!document.querySelector('.ek-dis')"),
                "WebGL yok -> kart gorunumu + bilgi satiri")
        tarayici.close()
        return
    dogrula(True, "WebGL var: ofis 3B kipinde")
    dogrula(sayfa.evaluate("() => document.querySelectorAll('#ekip-gorunum canvas.of-tuval').length") == 1, "tek tuval")
    masalar = sayfa.evaluate("() => [...document.querySelectorAll('.of-etiket.masa .of-etiket-ad')].map(e => e.textContent)")
    dogrula(len(masalar) == 8 and "İstişare masası" in masalar and "Onay kapısı" in masalar, f"sekiz masa etiketi ({masalar})")
    ajanlar = sayfa.evaluate("() => [...document.querySelectorAll('.of-etiket.ajan .of-etiket-ad')].map(e => e.textContent)")
    dogrula(set(ajanlar) == {"yazar", "tablocu", "arastirmaci", "Planlayıcı", "Birleştirici"}, f"ajanlar + iki sistem karakteri ({ajanlar})")
    dogrula(sayfa.evaluate("() => [...document.querySelectorAll('.of-etiket')].every(e => getComputedStyle(e).userSelect === 'none')"),
            "etiketler secilemez")
    dogrula(sayfa.evaluate("() => getComputedStyle(document.querySelector('.of-etiketler')).pointerEvents === 'none'"),
            "etiket katmani tiklamayi tuvale birakir")
    dogrula(sayfa.evaluate("() => [...document.querySelectorAll('#ekip-gorunum svg')].every(s => s.querySelector('path'))"),
            "bos (bilinmeyen adli) svg yok")
    dogrula(sayfa.evaluate("() => !document.querySelector('.of-cekmece.acik') && !!document.querySelector('.of-gorev.acik .of-gorev-metin')"),
            "cekmece kapali; gorev cubugu altta")
    sayfa.evaluate("() => { Ekip.D.sekme = 'ajanlar'; Ofis.D.cekmece = true; Ofis.ciz(); }"); sayfa.wait_for_timeout(150)
    dogrula(sayfa.evaluate("() => !!document.querySelector('.of-cekmece.acik .ek-ic h2')"), "cekmece: Ajanlar formu ekip.js'ten")

    print("\n2) Iskelet bir kez kurulur")
    sayfa.evaluate("() => { window._tuval = document.querySelector('canvas.of-tuval'); }")
    for adim in ("() => { Ekip.D.sekme = 'ajanlar'; Ekip.ciz(); }", "() => { Ekip.D.sekme = 'gecmis'; Ekip.ciz(); }",
                 "() => { Ofis.D.cekmece = false; Ofis.ciz(); }", "() => Ofis.olay({tip: 'ekip_mesaj', veri: {durum: 'calisiyor'}})"):
        sayfa.evaluate(adim); sayfa.wait_for_timeout(120)
    dogrula(sayfa.evaluate("() => document.querySelector('canvas.of-tuval') === window._tuval"), "tuval yeniden cizimlerde ayni oge")
    sayfa.evaluate("gorunum('sohbet')"); sayfa.wait_for_timeout(100); sayfa.evaluate("gorunum('ekip')"); sayfa.wait_for_timeout(700)
    dogrula(sayfa.evaluate("() => document.querySelector('canvas.of-tuval') === window._tuval"), "alandan cikip donunce de ayni tuval")
    dogrula(not sayfa.evaluate("() => document.querySelector('.of-cekmece.acik')"), "cekmece kapali kaldi (durum korunur)")

    print("\n3) Kamera")
    kutu = sayfa.evaluate("() => { const r = document.querySelector('canvas.of-tuval').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
    cx, cy = kutu[0] + kutu[2] * 0.5, kutu[1] + kutu[3] * 0.55
    yon0 = sayfa.evaluate("OfisSahne.D.kuresel.yon")
    sayfa.mouse.move(cx, cy); sayfa.mouse.down(); sayfa.mouse.move(cx + 120, cy + 10, steps=6); sayfa.mouse.up()
    dogrula(abs(sayfa.evaluate("OfisSahne.D.kuresel.yon") - yon0) > 0.3, "sol surukle: yorunge doner")
    h0 = sayfa.evaluate("[OfisSahne.D.hedef.x, OfisSahne.D.hedef.z]")
    sayfa.mouse.move(cx, cy); sayfa.mouse.down(button="right"); sayfa.mouse.move(cx - 150, cy - 60, steps=6); sayfa.mouse.up(button="right")
    h1 = sayfa.evaluate("[OfisSahne.D.hedef.x, OfisSahne.D.hedef.z]")
    dogrula(abs(h1[0] - h0[0]) + abs(h1[1] - h0[1]) > 1, f"sag surukle: kaydirir ({h0} -> {h1})")
    dogrula(not sayfa.evaluate("() => document.querySelector('.menu.acik, #baglam-menu.acik')"), "sag tik baglam menusu acmadi")
    # Tekerlek: imlecin altindaki zemin noktasi ekranda yerinde kalmali
    mx, my = kutu[0] + kutu[2] * 0.3, kutu[1] + kutu[3] * 0.4
    zemin = sayfa.evaluate(f"OfisSahne.zemineIndir({mx}, {my})")
    r0 = sayfa.evaluate("OfisSahne.D.kuresel.r")
    sayfa.mouse.move(mx, my)
    for _ in range(3):
        sayfa.mouse.wheel(0, -120); sayfa.wait_for_timeout(40)
    r1 = sayfa.evaluate("OfisSahne.D.kuresel.r")
    sonra = sayfa.evaluate(f"OfisSahne.izdusum({zemin['x']}, 0, {zemin['z']})") if zemin else {"x": 1e9, "y": 1e9}
    kayma = ((sonra["x"] - mx) ** 2 + (sonra["y"] - my) ** 2) ** 0.5
    dogrula(r1 < r0 * 0.8, f"tekerlek yakinlastirir (r {r0:.1f} -> {r1:.1f})")
    dogrula(kayma < 6, f"yakinlasma IMLECIN oldugu yere: imlecin altindaki nokta {kayma:.1f} px kaydi")
    # Cift tik: istisare masasina odaklan
    sayfa.evaluate("OfisSahne.ofiseDon()"); sayfa.wait_for_timeout(800)
    nokta = sayfa.evaluate("(() => { const g = OfisSahne.D.masalar.istisare.grup.position; return OfisSahne.izdusum(g.x, 0.8, g.z); })()")
    sayfa.mouse.dblclick(nokta["x"], nokta["y"])
    sayfa.wait_for_function("() => OfisSahne.D.gecis === null", timeout=8000)   # gecis bitti (yavas makinede de)
    hedef = sayfa.evaluate("[OfisSahne.D.hedef.x, OfisSahne.D.hedef.z, OfisSahne.D.kuresel.r]")
    dogrula(abs(hedef[0] - (-1)) < 0.3 and abs(hedef[1] - 1.5) < 0.3 and hedef[2] < 12, f"cift tik: masaya odaklandi ({hedef})")
    sayfa.click("text=Ofise dön"); sayfa.wait_for_timeout(100)
    sayfa.wait_for_function("() => OfisSahne.D.gecis === null", timeout=8000)
    dogrula(abs(sayfa.evaluate("OfisSahne.D.kuresel.r") - 30) < 0.5, "Ofise don: baslangic gorunumu")
    sayfa.evaluate("document.body.classList.add('animasyon-az')")
    sayfa.evaluate("OfisSahne.odaklan({tur: 'masa', kod: 'kod'})")
    dogrula(sayfa.evaluate("OfisSahne.D.gecis === null && Math.abs(OfisSahne.D.kuresel.r - 9) < 0.01"), "animasyon-az: odaklanma aninda (gecis yok)")
    sayfa.evaluate("document.body.classList.remove('animasyon-az'); OfisSahne.ofiseDon()"); sayfa.wait_for_timeout(800)

    print("\n4) Kare talep uzerine; ofis gorunmezken kare yok")
    sayfa.wait_for_timeout(300)
    k0 = kareler(sayfa); sayfa.wait_for_timeout(1000); k1 = kareler(sayfa)
    dogrula(k1 - k0 == 0, f"hareketsiz sahne: 1 sn'de {k1 - k0} kare")
    sayfa.mouse.move(cx, cy); sayfa.mouse.down(); sayfa.mouse.move(cx + 60, cy, steps=5); sayfa.mouse.up(); sayfa.wait_for_timeout(100)
    dogrula(kareler(sayfa) > k1, "surukleyince kare cizildi")
    # surekli bir animasyon varken ofisten cik: kare durmali
    sayfa.evaluate("OfisSahne.animasyonEkle(() => true)")
    sayfa.wait_for_timeout(300)
    sayfa.evaluate("gorunum('sohbet')"); sayfa.wait_for_timeout(100)
    k0 = kareler(sayfa); sayfa.wait_for_timeout(1000); k1 = kareler(sayfa)
    dogrula(k1 - k0 == 0 and sayfa.evaluate("OfisSahne.D.kare === null"), f"ofisten cikinca 1 sn: {k1 - k0} kare, rAF bekleyen yok")
    sayfa.evaluate("gorunum('ekip')"); sayfa.wait_for_timeout(600)
    dogrula(kareler(sayfa) > k1, "donunce cizim surer")
    sayfa.evaluate("ayarlariAc()"); sayfa.wait_for_timeout(200)
    k0 = kareler(sayfa); sayfa.wait_for_timeout(800); k1 = kareler(sayfa)
    dogrula(k1 - k0 == 0, f"Ayarlar acikken kare yok ({k1 - k0})")
    sayfa.evaluate("document.getElementById('ayar-perde').classList.remove('acik')"); sayfa.wait_for_timeout(300)
    dogrula(kareler(sayfa) > k1, "Ayarlar kapaninca cizim surer")
    sayfa.evaluate("OfisSahne.D.animasyonlar.clear()")

    print("\n5) Plan onayi ofisin ustunde, sohbet akisinda degil")
    sayfa.evaluate("() => olayIsle({tip: 'ekip_mesaj', veri: {durum: 'planlaniyor', kimlik: 'k1'}})")
    sayfa.evaluate("""() => olayIsle({tip: 'onay_gerekli', veri: {istek: {arac: 'ekip_plan', args: {alt_gorev: 2, alan: 'D:/x'},
        risk: 'WRITE', etki: 'Çalışma alanı: D:/x\\n• giris [yazar] → giris.md: yaz', yikici: false, toplu_sunulabilir: false}}})""")
    sayfa.wait_for_timeout(200)
    dogrula(sayfa.evaluate("() => !!document.querySelector('.of-onay .onay')"), "onay karti .of-onay panelinde")
    dogrula(sayfa.evaluate("() => !document.querySelector('#kolon .onay')"), "sohbet akisinda ayni kart yok")
    dogrula(sayfa.evaluate("() => document.querySelector('.of-onay').getBoundingClientRect().height > 40"), "cekmece kapaliyken de gorunur")
    sayfa.evaluate("() => { Ekip.D.sekme = 'projeler'; Ofis.D.cekmece = true; Ofis.ciz(); }"); sayfa.wait_for_timeout(100)
    dogrula(sayfa.evaluate("() => !!document.querySelector('.of-onay .onay')"), "cekmece yeniden cizilince kart kaybolmadi")
    sayfa.click(".of-onay >> text=İzin ver"); sayfa.wait_for_timeout(100)
    dogrula(sayfa.evaluate("() => window.CAGRI.some(c => c[0] === 'onay_cevapla' && c[1][0] === 'evet')"), "karar mevcut akistan gitti (onay_cevapla)")
    sayfa.evaluate("() => olayIsle({tip: 'onay_sonucu', veri: {arac: 'ekip_plan', cevap: 'evet'}})"); sayfa.wait_for_timeout(1500)
    dogrula(sayfa.evaluate("() => !document.querySelector('.of-onay .onay')"), "cevaplanan kart panelden kalkti")
    # Birlestiricinin yazma onayi da ofiste verilir (kullanici: "sohbete donmeden onay verilemiyor")
    sayfa.evaluate("() => olayIsle({tip: 'ekip_mesaj', veri: {durum: 'birlestiriliyor', kimlik: 'k1'}})")
    sayfa.evaluate("() => olayIsle({tip: 'ekip_mesaj', veri: {rol: 'birlestirici', durum: 'calisiyor', kimlik: 'k1'}})")
    sayfa.evaluate("""() => olayIsle({tip: 'onay_gerekli', veri: {istek: {arac: 'write_file', args: {path: 'D:/x/rapor.md', content: 'x'},
        risk: 'WRITE', etki: 'rapor.md yazilacak', yikici: false, toplu_sunulabilir: true}}})""")
    sayfa.wait_for_timeout(200)
    dogrula(sayfa.evaluate("() => !!document.querySelector('.of-onay .onay') && !document.querySelector('#kolon .onay')"),
            "kosu surerken birlestiricinin yazma onayi ofiste, sohbette degil")
    dogrula(sayfa.evaluate("() => Ofis.D.durum.karakterler['@birlestirici'].masa") == "kapi", "birlestirici kapida bekliyor")
    dogrula(not sayfa.evaluate("() => document.getElementById('arka-plan') && document.getElementById('arka-plan').classList.contains('onay')"),
            "'Sohbette onay bekleniyor' durtmesi yok")
    sayfa.click(".of-onay >> text=İzin ver"); sayfa.wait_for_timeout(100)
    dogrula(sayfa.evaluate("() => window.CAGRI.filter(c => c[0] === 'onay_cevapla').length") == 2, "ofisten verilen onay mevcut akistan gitti")
    sayfa.evaluate("() => olayIsle({tip: 'onay_sonucu', veri: {arac: 'write_file', cevap: 'evet'}})"); sayfa.wait_for_timeout(1500)
    dogrula(sayfa.evaluate("() => !document.querySelector('.of-onay .onay')"), "yazma onayi da cevaplaninca kalkti")
    sayfa.evaluate("gorunum('sohbet')"); sayfa.wait_for_timeout(100)
    sayfa.evaluate("""() => olayIsle({tip: 'onay_gerekli', veri: {istek: {arac: 'write_file', args: {path: 'D:/x/b.md', content: 'y'},
        risk: 'WRITE', etki: 'b.md', yikici: false, toplu_sunulabilir: true}}})""")
    sayfa.wait_for_timeout(200)
    dogrula(sayfa.evaluate("() => !!document.querySelector('#kolon .onay')"), "Ekip alani kapaliyken onay sohbet akisinda (eski davranis)")
    sayfa.evaluate("() => { const k = document.querySelector('#kolon .onay'); cevapla(k, 'red'); }")
    sayfa.evaluate("gorunum('ekip')"); sayfa.wait_for_timeout(600)
    dogrula(not hatalar, f"JS hatasi yok ({hatalar})")

    print("\n6) Performans: CPU 4x yavas, hareketli sahne")
    cdp = sayfa.context.new_cdp_session(sayfa)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    sayfa.evaluate("() => { Ofis.D.cekmece = false; Ofis.ciz(); }"); sayfa.wait_for_timeout(300)
    # Kamera surekli doner: her kare gercekten cizilir. Kare suresi = ardisik
    # rAF zaman damgalari arasi. IZ KAYDI KAPALIYKEN olculur (iz kaydinin kendi
    # yuku sureyi olculdugu kadar sisiriyordu); boyama ve kare sayilari ayri
    # bir izden okunur.
    OLC = """(n) => new Promise((coz) => {
      const araliklar = []; let onceki = 0;
      OfisSahne.animasyonEkle((dt, zaman) => {
        OfisSahne.D.kuresel.yon += 0.01; OfisSahne.kameraGit(OfisSahne.D.hedef, OfisSahne.D.kuresel.r);
        if (onceki) araliklar.push(zaman - onceki); onceki = zaman;
        if (araliklar.length >= n) { coz(araliklar); return false; }
        return true;
      });
    })"""
    sayfa.evaluate(OLC, 30)                                   # isinma (golgelendirici derleme vb.)
    # Uc parti x 120 kare; ORTANCA partinin ortalamasi sinanir. Bu makinede
    # (acik editor, tarayici) ayni sahne 22-38 ms arasinda oynadi: tek bir
    # gurultulu parti testi dusurmesin, gercek bir yavaslama yine yakalansin.
    partiler = [sayfa.evaluate(OLC, 120) for _ in range(3)]
    sure = sorted(partiler, key=lambda x: sum(x) / len(x))[1]
    tarayici.start_tracing(page=sayfa, categories=["devtools.timeline", "disabled-by-default-devtools.timeline.frame"])
    iz_sure = sayfa.evaluate(OLC, 60)
    iz = json.loads(tarayici.stop_tracing())
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    olaylar = iz.get("traceEvents", iz if isinstance(iz, list) else [])
    boyama = sum(1 for o in olaylar if o.get("name") == "Paint")
    kare_iz = sum(1 for o in olaylar if o.get("name") == "DrawFrame")
    ort = sum(sure) / len(sure)
    p95 = sorted(sure)[int(len(sure) * 0.95) - 1]
    gl = sayfa.evaluate("OfisSahne.D.glAdi") or "?"
    print(f"      GL: {gl[:70]} (yazilim: {sayfa.evaluate('OfisSahne.D.yazilimGL')}), "
          f"cizim cagrisi: {sayfa.evaluate('OfisSahne.D.renderer.info.render.calls')}")
    print(f"      1280x860, CPU 4x: 3 x 120 kare, parti ortalamalari "
          + " / ".join(f"{sum(x) / len(x):.1f}" for x in partiler) + f" ms; ortanca parti {ort:.1f} ms, p95 {p95:.1f} ms")
    print(f"      iz (60 kare, iz yuku dahil ort. {sum(iz_sure) / len(iz_sure):.1f} ms): {boyama} Paint, {kare_iz} DrawFrame")
    # Kare SURESI makineye bagli: ayni kod bu dizustunde zamanla 21 -> 34 ms
    # gidiyor (A/B ile olculdu, kod ayni). hepsi.py'de makineden bagimsiz olan
    # sinanir (cizim cagrisi); 33 ms hedefi --olcum ile ayrica sinanir.
    cagri = sayfa.evaluate("OfisSahne.D.renderer.info.render.calls")
    dogrula(cagri <= 40, f"cizim cagrisi <= 40 ({cagri}; birlestirme ve ornekleme bozulmamis)")
    if "--olcum" in sys.argv:
        dogrula(ort < 33, f"hareketli sahnede ortalama kare suresi < 33 ms (ortanca parti {ort:.1f} ms)")
    else:
        print(f"      (bilgi) kare suresi hedefi 33 ms; sinamak icin: python tests/ofis_arayuz_testi.py --olcum")
    tarayici.close()


def dar_pencere(p) -> None:
    print("\n7) Dar pencere (390x640): yatay tasma yok")
    tarayici, sayfa, hatalar = sayfa_ac(p, 390, 640)
    if sayfa.evaluate("Ofis.D.kip") == "3b":
        tasma = sayfa.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        dogrula(tasma <= 0, f"yatay tasma yok ({tasma} px)")
        sayfa.evaluate("() => { Ekip.D.sekme = 'projeler'; Ofis.D.cekmece = true; Ofis.ciz(); }"); sayfa.wait_for_timeout(200)
        dogrula(sayfa.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0, "cekmece acikken de tasma yok")
        g = sayfa.evaluate("() => { const r = document.querySelector('.of-gorev').getBoundingClientRect(); return [r.left, r.right]; }")
        dogrula(g[0] >= 0 and g[1] <= 390, f"gorev cubugu ekrana sigiyor ({g})")
        sahne = sayfa.evaluate("() => document.querySelector('.of-sahne').getBoundingClientRect().height")
        cek = sayfa.evaluate("() => { const r = document.querySelector('.of-cekmece').getBoundingClientRect(); return [r.top, r.width]; }")
        dogrula(sahne >= 200, f"sahne gorunur ({sahne:.0f} px)")
        dogrula(cek[1] <= 390 and cek[0] >= sahne - 1, f"cekmece alta indi ({cek})")
    dogrula(not hatalar, f"JS hatasi yok ({hatalar})")
    tarayici.close()


def webgl_yok(p) -> None:
    print("\n8) WebGL yok -> kart gorunumu (bos ekran yok)")
    tarayici, sayfa, hatalar = sayfa_ac(p, args=["--disable-3d-apis"])
    dogrula(sayfa.evaluate("Ofis.D.kip") == "kart", "kip: kart")
    dogrula(sayfa.evaluate("() => !document.querySelector('canvas.of-tuval') && !!document.querySelector('.ek-dis .ek-ic h2')"),
            "Ekip alani bugunku kart gorunumunu cizdi")
    dogrula(sayfa.evaluate("() => document.querySelector('#ekip-gorunum .ek-bilgi').textContent.includes('WebGL')"), "ustte tek satir bilgi")
    dogrula(sayfa.evaluate("() => typeof THREE === 'undefined'"), "three.js hic yuklenmedi")
    dogrula(not hatalar, f"JS hatasi yok ({hatalar})")
    tarayici.close()


# Belgedeki (7) dizi: plan -> onay -> iki isci farkli masalarda -> pano mesaji
# (istisare) -> biri hata -> birlestirici -> bitti. 'ek' varsayilan ajanla:
# kapidan gecici kopya girer.
DIZI = [
    ("ekip_mesaj", {"durum": "planlaniyor", "kimlik": "k1"}),
    ("ekip_mesaj", {"rol": "planlayici", "durum": "calisiyor", "kimlik": "k1"}),
    ("#A", None),
    ("ekip_mesaj", {"rol": "planlayici", "durum": "bitti", "kimlik": "k1"}),
    ("onay_gerekli", {"istek": {"arac": "ekip_plan", "args": {}, "risk": "WRITE", "etki": "plan", "yikici": False, "toplu_sunulabilir": False}}),
    ("#B", None),
    ("onay_sonucu", {"arac": "ekip_plan", "cevap": "evet"}),
    ("ekip_mesaj", {"durum": "calisiyor", "kimlik": "k1", "uyeler": ["giris", "tablo", "ek"]}),
    ("arac_cagrildi", {"arac": "ekip_isci", "args": {"ad": "giris", "ajan": "yazar"}, "ajan": "giris", "masa": "bekleme"}),
    ("arac_cagrildi", {"arac": "ekip_isci", "args": {"ad": "tablo", "ajan": "tablocu"}, "ajan": "tablo", "masa": "bekleme"}),
    ("arac_cagrildi", {"arac": "ekip_isci", "args": {"ad": "ek", "ajan": "varsayilan"}, "ajan": "ek", "masa": "bekleme"}),
    ("#C0", None),
    ("adim_basladi", {"adim": 1, "ajan": "giris"}),
    ("arac_cagrildi", {"arac": "write_file", "args": {"path": "D:/x/app.py"}, "ajan": "giris", "masa": "kod", "karar": "ALLOW"}),
    ("arac_cagrildi", {"arac": "read_file", "args": {"path": "D:/x/veri.pdf"}, "ajan": "tablo", "masa": "arsiv", "karar": "ALLOW"}),
    ("adim_basladi", {"adim": 2, "ajan": "tablo"}),
    ("#C", None),
    ("arac_cagrildi", {"arac": "ekip_mesaj", "args": {"kime": "giris"}, "ajan": "tablo", "masa": "istisare"}),
    ("ekip_mesaj", {"kimden": "tablo", "kime": "giris", "metin": "Başlıkları '## ' ile yaz. " + "x" * 80, "sira": 1}),
    ("#D", None),
    ("arac_sonucu", {"arac": "ekip_isci", "ajan": "tablo", "hata": True, "sonuc": "HATA", "karar": "ALLOW"}),
    ("arac_sonucu", {"arac": "ekip_isci", "ajan": "giris", "hata": False, "sonuc": "tamam", "karar": "ALLOW"}),
    ("arac_sonucu", {"arac": "ekip_isci", "ajan": "ek", "hata": False, "sonuc": "tamam", "karar": "ALLOW"}),
    ("#E", None),
    ("ekip_mesaj", {"durum": "birlestiriliyor", "kimlik": "k1"}),
    ("ekip_mesaj", {"rol": "birlestirici", "durum": "calisiyor", "kimlik": "k1"}),
    ("arac_cagrildi", {"arac": "read_file", "args": {"path": "D:/x/app.py"}, "masa": "kod", "karar": "ALLOW"}),
    ("#F", None),
    ("ekip_mesaj", {"rol": "birlestirici", "durum": "bitti", "kimlik": "k1"}),
    ("ekip_mesaj", {"durum": "bitti", "kimlik": "k1"}),
    ("#G", None),
]
BEKLENEN = {
    "A": {"@planlayici": ("istisare", "calisiyor"), "yazar": ("bekleme", "bosta")},
    "B": {"@planlayici": ("kapi", "onay_bekliyor")},
    "C0": {"yazar": ("bekleme", "planda_bekliyor"), "tablocu": ("bekleme", "planda_bekliyor"), "~ek": ("kapi", "planda_bekliyor"),
           "@planlayici": ("bekleme", "bosta")},
    "C": {"yazar": ("kod", "calisiyor"), "tablocu": ("arsiv", "dusunuyor"), "arastirmaci": ("bekleme", "bosta")},
    "D": {"tablocu": ("istisare", "calisiyor")},
    "E": {"tablocu": ("istisare", "hata"), "yazar": ("bekleme", "bitti"), "~ek": ("bekleme", "bitti")},
    "F": {"@birlestirici": ("istisare", "calisiyor")},
    "G": {"@birlestirici": ("bekleme", "bitti"), "~ek": ("kapi", "bitti"), "tablocu": ("istisare", "hata")},
}


def durum_makinesi(sayfa) -> None:
    print("\n9) Durum makinesi (ofis/durum.js): olay dizisi -> {masa, durum}")
    sonuc = sayfa.evaluate("""(dizi) => {
      const noktalar = OfisSahne.noktaSayilari();
      let d = OfisDurum.bos(['yazar', 'tablocu', 'arastirmaci'], noktalar);
      const anlar = {}, degismedi = [];
      for (const [tip, veri] of dizi) {
        if (tip.startsWith('#')) { anlar[tip.slice(1)] = JSON.parse(JSON.stringify(d)); continue; }
        const once = JSON.stringify(d);
        d = OfisDurum.durumUygula(d, {tip, veri, zaman: 1000});
        if (JSON.stringify(d) === once && tip !== 'onay_sonucu') degismedi.push(tip);
      }
      return anlar;
    }""", [list(x) for x in DIZI])
    for an, beklenen in BEKLENEN.items():
        k = sonuc[an]["karakterler"]
        gercek = {a: (k[a]["masa"], k[a]["durum"]) if a in k else None for a in beklenen}
        dogrula(gercek == beklenen, f"{an}: {gercek}")
    c = sonuc["C"]["karakterler"]
    dogrula(c["yazar"]["isci"] == "giris" and c["~ek"]["gecici"] and c["~ek"]["ajan"] is None,
            "isci -> karakter: giris=yazar; varsayilan ajanli 'ek' gecici kopya")
    d = sonuc["D"]["karakterler"]
    dogrula(len(d["tablocu"]["balon"]["metin"]) <= 61 and d["tablocu"]["balon"]["tam"].startswith("Başlıkları")
            and d["yazar"]["zarf"] == 1, "pano: gonderende kisa balon (tam metin ayri), alicida zarf")
    dogrula(sonuc["F"]["karakterler"]["@birlestirici"]["sonAraclar"][-1]["arac"] == "read_file",
            "birlestirici calisirken ajansiz arac cagrisi birlestiriciye yazildi")
    dogrula("app.py" in " ".join(sonuc["E"]["karakterler"]["yazar"]["yazdiklari"]), "yazdigi dosyalar (write_file, ALLOW)")
    dogrula(sonuc["G"]["karakterler"]["~ek"]["ayrildi"], "kosu bitince gecici kopya kapidan cikar")
    ayni = sayfa.evaluate("""(dizi) => {
      const olaylar = dizi.filter(([t]) => !t.startsWith('#')).map(([tip, veri]) => ({tip, veri, zaman: 5}));
      const bas = OfisDurum.bos(['yazar', 'tablocu'], OfisSahne.noktaSayilari());
      const kopya = JSON.stringify(bas);
      const a = JSON.stringify(OfisDurum.oynat(bas, olaylar)), b = JSON.stringify(OfisDurum.oynat(bas, olaylar));
      return [a === b, JSON.stringify(bas) === kopya];
    }""", [list(x) for x in DIZI])
    dogrula(ayni[0], "saf: ayni olay dizisi ayni durumu verir")
    dogrula(ayni[1], "girdi durumu degistirilmez")
    ek = sayfa.evaluate("""() => {
      const n = OfisSahne.noktaSayilari();
      let d = OfisDurum.bos(['yazar'], n);
      const u = (tip, veri, zaman) => { d = OfisDurum.durumUygula(d, {tip, veri, zaman}); };
      u('ekip_mesaj', {durum: 'planlaniyor', kimlik: 'k'}, 0);
      u('arac_cagrildi', {arac: 'ekip_isci', args: {ad: 'a1', ajan: 'yazar'}, ajan: 'a1'}, 0);
      u('arac_cagrildi', {arac: 'ekip_isci', args: {ad: 'a2', ajan: 'yazar'}, ajan: 'a2'}, 0);
      u('arac_cagrildi', {arac: 'write_file', args: {path: 'x.md'}, ajan: 'a1', masa: 'dosya'}, 1000);
      u('arac_cagrildi', {arac: 'write_file', args: {path: 'y.md'}, ajan: 'a2', masa: 'dosya'}, 1000);
      const ikiIsci = [d.karakterler.yazar.isci, !!d.karakterler['~a2'], d.karakterler.yazar.nokta !== d.karakterler['~a2'].nokta];
      u('_zaman', {simdi: 1000 + 6 * 60 * 1000});
      const sessiz = d.karakterler.yazar.durum;
      u('arac_cagrildi', {arac: 'uydurma_arac', ajan: 'a1'}, 2000);
      const bilinmeyenMasa = d.karakterler.yazar.masa;
      u('gorev_bitti', {durduruldu: true});
      return {ikiIsci, sessiz, bilinmeyenMasa, durdu: d.karakterler.yazar.durum, kosu: d.kosu.durum};
    }""")
    deniz = sayfa.evaluate("""() => {
      let d = OfisDurum.bos(['Deniz'], OfisSahne.noktaSayilari());
      const u = (tip, veri) => { d = OfisDurum.durumUygula(d, {tip, veri, zaman: 1}); };
      u('ekip_mesaj', {durum: 'planlaniyor', kimlik: 'k'});
      u('arac_cagrildi', {arac: 'ekip_isci', args: {ad: 'Deniz', ajan: 'Deniz'}, ajan: 'Deniz', masa: 'bekleme'});
      u('arac_cagrildi', {arac: 'mkdir', args: {path: 'D:/kum/Deniz'}, ajan: 'Deniz', masa: 'yerinde', karar: 'ALLOW'});
      const mkdirSonra = d.karakterler.Deniz.masa;
      u('arac_cagrildi', {arac: 'write_file', args: {path: 'D:/kum/Deniz/test_matematik.py'}, ajan: 'Deniz', masa: 'kod', karar: 'ALLOW'});
      return [mkdirSonra, d.karakterler.Deniz.masa, !d.masaGecmisi.yerinde];
    }""")
    dogrula(deniz == ["bekleme", "kod", True], f"mkdir ajani yerinden oynatmaz, .py yazmasi kod masasina ({deniz})")
    dogrula(ek["ikiIsci"] == ["a1", True, True], f"ayni ajana iki alt gorev: ikincisi kopya, ayni masada farkli nokta ({ek['ikiIsci']})")
    dogrula(ek["sessiz"] == "bilinmiyor", "calisan karakterden 5 dk olay yok -> durum bilinmiyor")
    dogrula(ek["bilinmeyenMasa"] == "diger", "masasi olmayan olay -> 'diger' (kaybolmaz)")
    dogrula(ek["durdu"] == "bilinmiyor" and ek["kosu"] == "hata", "gorev durduruldu, bitis olayi yok -> bilinmiyor")


def canli_sahne(p) -> None:
    print("\n10) Sahne olaylari izler (canli)")
    tarayici, sayfa, hatalar = sayfa_ac(p)
    if sayfa.evaluate("Ofis.D.kip") != "3b":
        print("  UYARI  WebGL yok: canli sahne SINANAMADI"); tarayici.close(); return
    durum_makinesi(sayfa)
    sayfa.evaluate("() => { Ofis.D.cekmece = false; Ofis.ciz(); }")

    def olay(tip, veri):
        sayfa.evaluate("(o) => olayIsle(o)", {"tip": tip, "veri": veri})
    for tip, veri in DIZI:
        if tip == "#C":
            break
        if not tip.startswith("#"):
            olay(tip, veri)
    sayfa.wait_for_function("() => Object.values(OfisSahne.D.ajanlar).every(k => !k.yol)", timeout=8000)   # yurume bitti (sabit sure degil)
    konum = sayfa.evaluate("""() => { const k = OfisSahne.D.ajanlar.yazar, h = OfisSahne.masaNoktasi('kod', Ofis.D.durum.karakterler.yazar.nokta);
      return Math.hypot(k.grup.position.x - h[0], k.grup.position.z - h[1]); }""")
    dogrula(konum < 0.05, f"yazar kod masasina yurudu ({konum:.2f})")
    dogrula(sayfa.evaluate("() => OfisSahne.D.ajanlar.yazar.rozet.textContent") == "giris · çalışıyor", "rozet: isci · durum")
    poz = sayfa.evaluate("""() => { const k = OfisSahne.D.ajanlar.yazar, b = OfisSahne.D.ajanlar.arastirmaci;
      return [k.oturuyor, k.grup.position.y < 0, Math.abs(k.bacaklar[0].rotation.x + Math.PI / 2) < 0.01, b.oturuyor, b.grup.position.y < 0]; }""")
    dogrula(poz[:3] == [True, True, True], f"masada calisan oturur: kalca iner, bacaklar one ({poz[:3]})")
    dogrula(poz[3:] == [True, True], "bostaki ajan kanepede oturur")
    son_kare = sayfa.evaluate("""() => {
      const k = OfisSahne.D.ajanlar.yazar;
      k.yol = {noktalar: [[k.grup.position.x, k.grup.position.z]], i: 0, hiz: 3.2};
      k.oturuyor = false; k.grup.position.y = 0;
      k.bacaklar.forEach(b => { b.rotation.x = 0; });
      Array.from(OfisSahne.D.animasyonlar).forEach(f => f(0.016, performance.now()));
      return [!k.yol, k.oturuyor, k.grup.position.y < 0,
        k.bacaklar.every(b => Math.abs(b.rotation.x + Math.PI / 2) < 0.01)];
    }""")
    dogrula(son_kare == [True, True, True, True], f"son yuruyus karesinde oturma pozu korunur ({son_kare})")
    dogrula(sayfa.evaluate("() => OfisSahne.D.ajanlar.tablocu.halka.visible"), "dusunen karakterin basinda halka")
    k0 = kareler(sayfa); sayfa.wait_for_timeout(500)
    dogrula(kareler(sayfa) > k0, "calisan varken kareler akar (gercek is suruyor)")
    olay("ekip_mesaj", {"kimden": "tablo", "kime": "giris", "metin": "<img src=x onerror=\"window.XSS=1\"> Başlıkları ## ile yaz, uzun bir not " + "y" * 60, "sira": 1})
    sayfa.wait_for_timeout(300)
    balon = sayfa.evaluate("() => { const b = document.querySelector('.of-balon'); return b && [b.textContent, b.querySelectorAll('*').length]; }")
    dogrula(bool(balon) and balon[0].startswith("<img") and balon[1] == 0 and len(balon[0]) <= 61, f"balon duz metin, kisa ({balon})")
    dogrula(not sayfa.evaluate("() => window.XSS"), "balondaki HTML calismadi")
    sayfa.click(".of-balon"); sayfa.wait_for_timeout(100)
    dogrula(len(sayfa.evaluate("() => document.querySelector('.of-balon').textContent")) > 100, "tiklayinca tam metin")
    dogrula(sayfa.evaluate("() => !!document.querySelector('.of-zarf')"), "alicinin ustunde zarf")
    # animasyon azaltilmis: yeni hedefe isinlanir
    sayfa.evaluate("document.body.classList.add('animasyon-az')")
    olay("arac_cagrildi", {"arac": "list_dir", "args": {"path": "D:/x"}, "ajan": "giris", "masa": "arsiv"})
    konum = sayfa.evaluate("""() => { const k = OfisSahne.D.ajanlar.yazar, h = OfisSahne.masaNoktasi('arsiv', Ofis.D.durum.karakterler.yazar.nokta);
      return Math.hypot(k.grup.position.x - h[0], k.grup.position.z - h[1]); }""")
    dogrula(konum < 0.01, "animasyon-az: yurume yerine isinlanir")
    sayfa.evaluate("document.body.classList.remove('animasyon-az')")
    olay("gorev_bitti", {"metin": "x", "durduruldu": True}); sayfa.wait_for_timeout(300)
    dogrula(sayfa.evaluate("() => OfisSahne.D.ajanlar.yazar.gri && OfisSahne.D.ajanlar.yazar.rozet.textContent === 'durum bilinmiyor'"),
            "durduruldu: bitis olayi gelmeyen karakter gri, 'durum bilinmiyor'")
    sayfa.wait_for_function("() => Object.values(OfisSahne.D.ajanlar).every(k => !k.yol) && OfisSahne.D.animasyonlar.size === 0",
                            timeout=10000)
    k0 = kareler(sayfa); sayfa.wait_for_timeout(1500)
    dogrula(kareler(sayfa) - k0 == 0, f"kimse calismiyor/yurumuyorken kare yok ({kareler(sayfa) - k0})")

    print("\n11) Gecmis oynatma: canli degil, kopruye yazmaz")
    kayit = [{"t": i * 0.3, "tip": t, "veri": v} for i, (t, v) in enumerate(x for x in DIZI if not x[0].startswith("#"))]
    sayfa.evaluate("(k) => { window.KAYIT = k; }", kayit)
    sayfa.evaluate("() => { Ekip.D.sekme = 'gecmis'; Ekip.D.detay = null; Ofis.D.cekmece = true; Ekip.ciz(); }"); sayfa.wait_for_timeout(300)
    sayfa.evaluate("() => { window.CAGRI = []; }")
    sayfa.click(".of-cekmece .ek-kart.tikla >> nth=0"); sayfa.wait_for_timeout(300)
    sayfa.click("text=Ofiste oynat"); sayfa.wait_for_timeout(400)
    dogrula(sayfa.evaluate("() => document.querySelector('.of-oynatma') && document.querySelector('.of-oynatma').textContent.includes('canlı değil')"),
            "oynatma cubugu: 'canli degil'")
    sayfa.select_option(".of-hiz", "16"); sayfa.wait_for_timeout(4000)
    dogrula(sayfa.evaluate("() => Ofis.D.oynatma && Ofis.D.oynatma.i === Ofis.D.oynatma.olaylar.length"), "kayit sonuna kadar oynadi")
    dogrula(sayfa.evaluate("() => Ofis.D.oynatma.durum.karakterler['@birlestirici'].durum") == "bitti",
            "oynatma ayni durum makinesinden gecti")
    dogrula(sayfa.evaluate("() => OfisSahne.D.ajanlar.tablocu.rozet.textContent.includes('hata')"), "sahne oynatma durumunu gosteriyor")
    yazma = sayfa.evaluate("""() => window.CAGRI.map(c => c[0]).filter(a => !['ekip_kosu', 'ekip_kosu_olaylari', 'ekip_kosular',
      'ekip_projeler', 'ajanlar', 'anahtar_yuvalari', 'ofis_duzeni', 'olaylari_cek', 'durum', 'yokla',
      'eklenti_katalog'].includes(a))""")
    dogrula(not yazma, f"oynatma sirasinda yazma cagrisi yok ({sorted(set(yazma))})")
    sayfa.click(".of-oynatma button[title='Oynatmayı kapat']"); sayfa.wait_for_timeout(300)
    dogrula(sayfa.evaluate("() => !document.querySelector('.of-oynatma') && Ofis.D.oynatma === null"), "oynatma kapandi, canli duruma donuldu")
    sayfa.evaluate("() => { Ekip.D.detay = null; Ofis.D.cekmece = true; Ekip.ciz(); }"); sayfa.wait_for_timeout(200)
    sayfa.click(".of-cekmece .ek-kart.tikla >> nth=1"); sayfa.wait_for_timeout(300)
    sayfa.click("text=Ofiste oynat"); sayfa.wait_for_timeout(400)
    dogrula(sayfa.evaluate("() => !document.querySelector('.of-oynatma') && !!document.querySelector('.of-cekmece .ek-ic h2')"),
            "kaydi olmayan kosu: oynatma yok, kart gorunumu kalir")
    dogrula(not hatalar, f"JS hatasi yok ({hatalar})")
    tarayici.close()


def etkilesim(p) -> None:
    print("\n13) Etkilesim: ajan/masa kartlari, pano, ise alma, gorev cubugu")
    tarayici, sayfa, hatalar = sayfa_ac(p)
    if sayfa.evaluate("Ofis.D.kip") != "3b":
        print("  UYARI  WebGL yok: etkilesim SINANAMADI"); tarayici.close(); return

    def olay(tip, veri):
        sayfa.evaluate("(o) => olayIsle(o)", {"tip": tip, "veri": veri})

    def ekranda(anahtar, y=1.0):
        return sayfa.evaluate(f"(() => {{ const g = OfisSahne.D.ajanlar['{anahtar}'].grup.position; return OfisSahne.izdusum(g.x, {y}, g.z); }})()")

    def cagrilar(ad):
        return sayfa.evaluate(f"() => window.CAGRI.filter(c => c[0] === '{ad}').map(c => c[1])")
    for tip, veri in DIZI:
        if tip == "#D":
            break
        if not tip.startswith("#"):
            olay(tip, veri)
    sayfa.evaluate("() => { olayIsle({tip: 'ekip_mesaj', veri: {kimden: 'tablo', kime: 'giris', metin: 'Başlıkları ## ile yaz', sira: 1}}); }")
    sayfa.wait_for_function("() => Object.values(OfisSahne.D.ajanlar).every(k => !k.yol)", timeout=8000)   # yurume bitti (sabit sure degil)
    dogrula(sayfa.evaluate("() => !!document.querySelector('.of-gorev.acik textarea, .of-gorev.acik input.of-gorev-metin')"), "gorev cubugu gorunur")
    dogrula(sayfa.evaluate("() => !document.querySelector('.of-cekmece.acik')"), "cekmece varsayilan kapali (gorev cubukta)")
    # ajana tikla
    n = ekranda("yazar"); sayfa.mouse.click(n["x"], n["y"]); sayfa.wait_for_timeout(500)
    dogrula(sayfa.evaluate("() => Ofis.D.panel && Ofis.D.panel.tur === 'ajan' && Ofis.D.panel.kod === 'yazar'"), "ajana tik -> ajan karti")
    kart = sayfa.evaluate("() => document.querySelector('.of-panel').textContent")
    dogrula("Metin yazar." in kart and "Kod masası" in kart and "app.py" in kart, "kart: rol, su anki masa, son isler")
    dogrula("limit doldu" in kart and "gemini-3.5-pro" in kart, "kart: baglanti · model ve limit durumu (zincir)")
    dogrula("giris.md" in kart and "günlük" in kart, "kart: bu kosuda gunluge yazdigi dosyalar")
    dogrula(cagrilar("ofis_ajan_karti")[-1] == ["yazar", "giris", "k1"], "kart verisi: ajan + isci + kosu kimligiyle istendi")
    sayfa.fill(".of-panel .of-kart-gir input", "Tablo sütunlarını değiştirme"); sayfa.click(".of-panel .of-kart-gir button"); sayfa.wait_for_timeout(200)
    dogrula(cagrilar("ekip_pano_yaz")[-1] == ["Tablo sütunlarını değiştirme", "giris"], "karttan ona ozel pano mesaji (isci adiyla)")
    # Ctrl+tik: ekip secimi
    n = ekranda("arastirmaci")
    sayfa.keyboard.down("Control"); sayfa.mouse.click(n["x"], n["y"]); sayfa.keyboard.up("Control"); sayfa.wait_for_timeout(200)
    dogrula(sayfa.evaluate("() => !Ekip.D.secili.has('arastirmaci') && !OfisSahne.D.ajanlar.arastirmaci.ekip.visible"),
            "Ctrl+tik: ekipten cikti, parlama kalkti")
    sayfa.keyboard.down("Control"); sayfa.mouse.click(n["x"], n["y"]); sayfa.keyboard.up("Control"); sayfa.wait_for_timeout(200)
    dogrula(sayfa.evaluate("() => Ekip.D.secili.has('arastirmaci') && OfisSahne.D.ajanlar.arastirmaci.ekip.visible"),
            "Ctrl+tik: ekibe girdi, secili karakter parlar")
    dogrula(sayfa.evaluate("() => Ofis.D.panel.kod === 'yazar'"), "Ctrl+tik karti degistirmedi")
    # esyalar: kagit yigini -> dosya masasinda yazilan dosyalar; ag dugumleri -> Dusunce Agi
    olay("arac_cagrildi", {"arac": "write_file", "args": {"path": "D:/x/rapor.md"}, "ajan": "giris", "masa": "dosya", "karar": "ALLOW"})
    sayfa.evaluate("() => OfisSahne.ofiseDon()")
    sayfa.wait_for_function("() => OfisSahne.D.gecis === null && Object.values(OfisSahne.D.ajanlar).every(k => !k.yol)", timeout=8000)
    yigin = sayfa.evaluate("(() => { const g = OfisSahne.D.masalar.dosya.grup.position; return OfisSahne.izdusum(g.x - 0.6, 0.95, g.z); })()")
    sayfa.mouse.click(yigin["x"], yigin["y"]); sayfa.wait_for_timeout(300)
    kart = sayfa.evaluate("() => Ofis.D.panel && Ofis.D.panel.tur === 'dosyalar' && document.querySelector('.of-panel').textContent")
    dogrula(bool(kart) and "rapor.md" in kart, f"kagit yigini -> yazilan dosyalar ({str(kart)[:60]})")
    sayfa.click(".of-panel >> text=rapor.md"); sayfa.wait_for_timeout(150)
    dogrula(cagrilar("dosya_goster")[-1:] == [["D:/x/rapor.md"]], "dosyaya tik -> Explorer'da gosterir (dosya_goster; yurutmez)")
    ag = sayfa.evaluate("(() => { const g = OfisSahne.D.masalar.ag.grup.position; return OfisSahne.izdusum(g.x, 1.6, g.z); })()")
    sayfa.mouse.click(ag["x"], ag["y"]); sayfa.wait_for_timeout(400)
    dogrula(sayfa.evaluate("() => document.getElementById('ag-gorunum').classList.contains('acik')"), "ag dugumleri -> Dusunce Agi ekrani")
    sayfa.evaluate("gorunum('ekip')"); sayfa.wait_for_timeout(700)
    raf = sayfa.evaluate("(() => { const g = OfisSahne.D.masalar.arsiv.grup.position; return OfisSahne.izdusum(g.x + 1.4, 1.8, g.z - 2.6); })()")
    sayfa.mouse.click(raf["x"], raf["y"]); sayfa.wait_for_timeout(300)
    dogrula(sayfa.evaluate("() => Ofis.D.cekmece && Ekip.D.sekme === 'gecmis'"), "arsiv raflari -> Gecmis")
    sayfa.evaluate("() => { Ofis.D.cekmece = false; Ofis.ciz(); }")
    n = ekranda("yazar"); sayfa.mouse.click(n["x"], n["y"]); sayfa.wait_for_timeout(300)
    # istisare masasi: pano
    nokta = sayfa.evaluate("(() => { const g = OfisSahne.D.masalar.istisare.grup.position; return OfisSahne.izdusum(g.x, 0.8, g.z + 0.3); })()")
    sayfa.mouse.click(nokta["x"], nokta["y"]); sayfa.wait_for_timeout(400)
    kart = sayfa.evaluate("() => Ofis.D.panel && Ofis.D.panel.tur === 'masa' && Ofis.D.panel.kod === 'istisare' && document.querySelector('.of-panel').textContent")
    dogrula(bool(kart) and "Başlıkları ## ile yaz" in kart and "tablocu" in kart, "istisare masasi: pano ve orada calisan")
    sayfa.select_option(".of-panel select.of-hiz", "tablo")
    sayfa.fill(".of-panel .of-kart-gir input", "Bitince haber ver"); sayfa.keyboard.press("Enter"); sayfa.wait_for_timeout(200)
    dogrula(cagrilar("ekip_pano_yaz")[-1] == ["Bitince haber ver", "tablo"], "panodan tek isciye yazildi (mevcut ekip_pano_yaz)")
    # gorev cubugu: kosu surerken baslatma kapali, Durdur var
    dogrula(sayfa.evaluate("() => document.querySelector('.of-gorev .birincil').disabled"), "kosu surerken 'Ekibi baslat' kapali")
    sayfa.click(".of-gorev >> text=Durdur"); sayfa.wait_for_timeout(100)
    dogrula(len(cagrilar("durdur")) == 1, "Durdur mevcut akisi cagirdi")
    olay("ekip_mesaj", {"durum": "bitti", "kimlik": "k1"}); sayfa.wait_for_timeout(200)
    sayfa.fill(".of-gorev-metin", "Kompost rehberini güncelle"); sayfa.keyboard.press("Enter"); sayfa.wait_for_timeout(300)
    baslat = cagrilar("ekip_gorev_baslat")
    dogrula(bool(baslat) and baslat[-1][0] == "Kompost rehberini güncelle" and baslat[-1][1] == "p1"
            and sorted(baslat[-1][2]) == ["arastirmaci", "tablocu", "yazar"], f"gorev cubugu: proje + secili ekip ile baslatti ({baslat[-1:]})")
    # ise al
    sayfa.click(".of-ust >> text=İşe al"); sayfa.wait_for_timeout(400)
    dogrula(sayfa.evaluate("() => [...document.querySelectorAll('.of-panel select')][0].options.length") == 2, "ise alma: baglantilar listelendi")
    sayfa.fill(".of-panel .of-form input >> nth=0", "cevirmen"); sayfa.fill(".of-panel .of-form input >> nth=1", "Metni çevirir.")
    sayfa.click(".of-panel .of-renk >> nth=3")
    sayfa.click(".of-panel .of-form >> text=İşe al"); sayfa.wait_for_timeout(250)
    yaz = cagrilar("ajan_yaz")
    dogrula(bool(yaz) and yaz[-1] == ["cevirmen", "", "gemini-3.5-flash", "", "Metni çevirir.", "", "b1", "#c4a0d9", None],
            f"ajan_yaz: ad, rol, baglanti + model, renk ({yaz[-1:]})")
    sayfa.wait_for_timeout(150)
    sayfa.wait_for_function("() => !!OfisSahne.D.ajanlar.cevirmen", timeout=5000)
    giris = sayfa.evaluate("() => { const k = OfisSahne.D.ajanlar.cevirmen; return [!!k.kapidanGirdi, !!k.yol || !!k.hedef, k.hedef && k.hedef.masa]; }")
    dogrula(giris == [True, True, "bekleme"], f"yeni ajan kapidan girdi, dinlenme alanina yuruyor ({giris})")
    sayfa.wait_for_function("() => Object.values(OfisSahne.D.ajanlar).every(k => !k.yol)", timeout=8000)   # yurume bitti (sabit sure degil)
    dogrula(sayfa.evaluate("() => Ofis.D.durum.karakterler.cevirmen.masa") == "bekleme"
            and sayfa.evaluate("() => !OfisSahne.D.ajanlar.cevirmen.yol"), "dinlenme alanina vardi")
    # sil: iki adim
    sayfa.evaluate("() => { Ofis.D.panel = {tur: 'ajan', kod: 'cevirmen'}; Ofis.ciz(); }"); sayfa.wait_for_timeout(200)
    sayfa.click(".of-panel >> text=Ajanı sil"); sayfa.wait_for_timeout(150)
    dogrula(not cagrilar("ajan_sil") and "Emin misin?" in sayfa.evaluate("() => document.querySelector('.of-panel').textContent"),
            "sil: once onay istenir")
    sayfa.click(".of-panel >> text=Emin misin?"); sayfa.wait_for_function("() => !OfisSahne.D.ajanlar.cevirmen", timeout=8000)
    dogrula(cagrilar("ajan_sil") == [["cevirmen"]], "ikinci tikla ajan_sil")
    dogrula(sayfa.evaluate("() => !OfisSahne.D.ajanlar.cevirmen && !Ofis.D.durum.karakterler.cevirmen"), "karakter kapidan cikti, ofisten kalkti")
    dogrula(not hatalar, f"JS hatasi yok ({hatalar})")
    tarayici.close()


def tek_ajan(p) -> None:
    print("\n14) Tek ajana dogrudan gorev (Faz 5)")
    tarayici, sayfa, hatalar = sayfa_ac(p)
    if sayfa.evaluate("Ofis.D.kip") != "3b":
        print("  UYARI  WebGL yok: tek ajan arayuzu SINANAMADI"); tarayici.close(); return
    d = sayfa.evaluate("""() => {
      let d = OfisDurum.bos(['yazar', 'tablocu'], OfisSahne.noktaSayilari());
      const u = (tip, veri) => { d = OfisDurum.durumUygula(d, {tip, veri, zaman: 1}); };
      u('ekip_mesaj', {durum: 'planlaniyor', kimlik: 'k9', tek: 'yazar'});
      u('onay_gerekli', {istek: {arac: 'ekip_plan', args: {alt_gorev: 1, alan: 'D:/x', tek: 'yazar'}}});
      const kapida = [d.karakterler.yazar.masa, d.karakterler.yazar.durum, d.karakterler['@planlayici'].masa];
      u('onay_sonucu', {arac: 'ekip_plan', cevap: 'evet'});
      const sonra = [d.karakterler.yazar.masa, d.karakterler.yazar.durum];
      u('ekip_mesaj', {durum: 'calisiyor', kimlik: 'k9', uyeler: ['yazar']});
      u('arac_cagrildi', {arac: 'ekip_isci', args: {ad: 'yazar', ajan: 'yazar'}, ajan: 'yazar'});
      u('arac_cagrildi', {arac: 'write_file', args: {path: 'yazar/not.md'}, ajan: 'yazar', masa: 'dosya', karar: 'ALLOW'});
      const calisma = [d.karakterler.yazar.masa, d.karakterler.yazar.durum, !!d.karakterler['~yazar']];
      return {kapida, sonra, calisma};
    }""")
    dogrula(d["kapida"] == ["kapi", "onay_bekliyor", "bekleme"], f"onay beklenirken kapida AJANIN KENDISI, planlayici degil ({d['kapida']})")
    dogrula(d["sonra"] == ["bekleme", "bosta"], "onaydan sonra kapidan doner")
    dogrula(d["calisma"] == ["dosya", "calisiyor", False], "isci ajanin kendi karakteri (kopya yok), dosya masasinda")
    sayfa.evaluate("() => { Ofis.D.panel = {tur: 'ajan', kod: 'yazar'}; Ofis.ciz(); }"); sayfa.wait_for_timeout(300)
    dogrula(sayfa.evaluate("() => document.querySelector('.of-panel').textContent.includes('Bu ajana görev ver')"), "ajan kartinda 'Bu ajana gorev ver'")
    sayfa.fill(".of-panel textarea.of-tek-gorev", "Kompost hakkında kısa bir not yaz")
    sayfa.fill(".of-panel input.of-tek-yol", "notlar/")
    sayfa.click(".of-panel >> text=Görevi ver"); sayfa.wait_for_timeout(300)
    cagri = sayfa.evaluate("() => window.CAGRI.filter(c => c[0] === 'ekip_tek_gorev_baslat').map(c => c[1])")
    dogrula(cagri == [["Kompost hakkında kısa bir not yaz", "p1", "yazar", "notlar/", None]], f"kopru: gorev, proje, ajan, yol ({cagri})")
    dogrula(sayfa.evaluate("() => !Ofis.D.panel && Ekip.D.kosu && Ekip.D.kosu.durum === 'planlaniyor'"), "kart kapandi, kosu basladi")
    sayfa.evaluate("() => { Ofis.D.panel = {tur: 'ajan', kod: 'yazar'}; Ofis.ciz(); }"); sayfa.wait_for_timeout(200)
    dogrula(not sayfa.evaluate("() => document.querySelector('.of-panel').textContent.includes('Bu ajana görev ver')"),
            "kosu surerken ikinci gorev verilemez")
    dogrula(not hatalar, f"JS hatasi yok ({hatalar})")
    tarayici.close()


def uctan_uca(p) -> None:
    """Gercek isci surecleri + sahte model (ekip_orkestra_testi); olay dizisi
    ofis durum makinesine verilir: masa alani gelsin, karakterler dogru yerde."""
    import os
    import subprocess
    import tempfile
    print("\n12) Uctan uca: gercek ekip kosusunun olaylari -> ofis durumu")
    dokum = Path(tempfile.mkdtemp(prefix="pevrai_ofis_")) / "olaylar.json"
    ortam = dict(os.environ, PEVRAI_OFIS_DOKUM=str(dokum), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(Path(__file__).parent / "ekip_orkestra_testi.py")], env=ortam,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    dogrula(r.returncode == 0 and dokum.exists(), "ekip_orkestra_testi kostu ve olaylari doktu")
    if not dokum.exists():
        print(r.stdout[-1500:]); return
    olaylar = [{"tip": o["tip"].lower(), "veri": o["veri"]} for o in json.loads(dokum.read_text(encoding="utf-8"))]
    dogrula(all(o["veri"].get("masa") for o in olaylar if o["tip"] == "arac_cagrildi"), f"{len(olaylar)} olay; her arac cagrisinda masa var")
    tarayici = p.chromium.launch(channel="chrome", headless=True, args=["--disable-3d-apis"])
    sayfa = tarayici.new_page()
    sayfa.goto((PAKET / "arayuz" / "index.html").as_uri()); sayfa.wait_for_timeout(300)
    sonuc = sayfa.evaluate("""(olaylar) => {
      let d = OfisDurum.bos(['yazar'], OfisSahne.noktaSayilari());
      const gecti = {};
      for (const o of olaylar) {
        d = OfisDurum.durumUygula(d, Object.assign({zaman: 1}, o));
        Object.values(d.karakterler).forEach((k) => { (gecti[k.anahtar] = gecti[k.anahtar] || new Set()).add(k.masa); });
      }
      const k = d.karakterler;
      return {yazar: [k.yazar.masa, k.yazar.durum, k.yazar.isci], sonuc: k['~sonuc'] && [k['~sonuc'].masa, k['~sonuc'].durum, k['~sonuc'].ayrildi],
              bir: [k['@birlestirici'].masa, k['@birlestirici'].durum], plan: k['@planlayici'].durum,
              gecti: Object.fromEntries(Object.entries(gecti).map(([a, s]) => [a, [...s].sort()])), kosu: d.kosu.durum,
              yazdi: k.yazar.yazdiklari};
    }""", olaylar)
    tarayici.close()
    print(f"      gecilen masalar: {sonuc['gecti']}")
    dogrula(sonuc["kosu"] == "bitti", "kosu bitti")
    dogrula(sonuc["yazar"][:2] == ["bekleme", "bitti"], f"giris iscisi (yazar ajani) bitti, dinlenmede ({sonuc['yazar']})")
    dogrula({"dosya", "istisare"} <= set(sonuc["gecti"].get("yazar", [])), "yazar dosya masasinda yazdi, istisarede panoya yazdi")
    dogrula(any("giris.md" in y for y in sonuc["yazdi"]), f"yazdigi dosya: giris.md ({sonuc['yazdi']})")
    dogrula(sonuc["sonuc"] and sonuc["sonuc"][1] == "bitti" and sonuc["sonuc"][2], f"varsayilan isci 'sonuc': gecici kopya, bitti, cikti ({sonuc['sonuc']})")
    dogrula("istisare" in sonuc["gecti"].get("@planlayici", []) and "kapi" in sonuc["gecti"].get("@planlayici", []),
            "planlayici istisarede calisti, onay icin kapida bekledi")
    dogrula(sonuc["bir"] == ["bekleme", "bitti"] and "istisare" in sonuc["gecti"].get("@birlestirici", []), "birlestirici istisarede calisti, bitti")


def ajan_duzenleme(p) -> None:
    print("\nAjan karti -> ortak duzenleme formu -> kaydet")
    tarayici, sayfa, hatalar = sayfa_ac(p)
    try:
        if sayfa.evaluate("Ofis.D.kip") != "3b":
            dogrula(False, "ajan karti duzenleme icin yazilim WebGL gerekli")
            return
        sayfa.evaluate("OfisSahne.D.onSec({tur:'ajan',kod:'yazar'})")
        sayfa.locator(".of-panel").get_by_role("button",name="Düzenle",exact=True).click()
        form = sayfa.locator(".of-panel .of-form")
        sayfa.wait_for_function("document.querySelector('.of-panel .of-form select').options.length===2")
        dogrula(form.get_by_label("Ad",exact=True).input_value()=="yazar" and form.get_by_label("Ad",exact=True).is_editable() is False,
                "ajan adi korunur; yeniden adlandirma ikinci ajan olusturmaz")
        dogrula(form.get_by_label("Model",exact=True).input_value()=="gemini-3.5-flash" and form.get_by_label("Görünüm",exact=True).input_value()=="1",
                "mevcut model ve gorunum dolduruldu")
        form.get_by_label("Bağlantı",exact=True).select_option("ds")
        form.get_by_label("Görünüm",exact=True).select_option(label="4")
        form.get_by_label("Rol (isteğe bağlı)",exact=True).fill("Taslağı inceler.")
        form.locator(".of-renk[title='#91a9e8']").click()
        form.get_by_role("button",name="Kaydet",exact=True).click()
        sayfa.wait_for_function("Ofis.D.panel.tur==='ajan' && Ekip.D.ajanlar.find(a=>a.ad==='yazar').baglanti==='ds'")
        args=sayfa.evaluate("CAGRI.filter(c=>c[0]==='ajan_yaz').at(-1)[1]")
        dogrula(args==["yazar","","deepseek-chat","","Taslağı inceler.","","ds","#91a9e8",3],
                f"baglanti/model/renk/gorunum tek ajan_yaz ile kaydedildi ({args})")
        sayfa.locator(".of-panel").get_by_role("button",name="Düzenle",exact=True).click()
        sayfa.wait_for_timeout(120)
        form=sayfa.locator(".of-panel .of-form")
        dogrula(form.get_by_label("Bağlantı",exact=True).input_value()=="ds" and form.get_by_label("Görünüm",exact=True).input_value()=="3",
                "yeniden acilan form kaydedilen secimleri gosterir")
        dogrula(sayfa.evaluate("Ekip.D.ajanlar.filter(a=>a.ad==='yazar').length") == 1, "mevcut ajan guncellendi, kopya olusmadi")
        # Eski dogrudan saglayici kaydi, renk/rol duzenlerken baska baglantiya gecmez.
        sayfa.evaluate("OfisSahne.D.onSec({tur:'ajan',kod:'tablocu'})")
        sayfa.locator(".of-panel").get_by_role("button",name="Düzenle",exact=True).click()
        sayfa.wait_for_timeout(120)
        form=sayfa.locator(".of-panel .of-form")
        dogrula(form.get_by_label("Bağlantı",exact=True).input_value()=="", "eski saglayiciyi koru secili")
        form.get_by_role("button",name="Kaydet",exact=True).click()
        sayfa.wait_for_timeout(180)
        args=sayfa.evaluate("CAGRI.filter(c=>c[0]==='ajan_yaz').at(-1)[1]")
        dogrula(args[:4]==["tablocu","openai","gpt-5-mini",""] and args[6]=="", "eski saglayici/model baglantisiz haliyle korunur")
        dogrula(not hatalar, f"duzenleme sirasinda sayfa hatasi yok {hatalar}")
    finally:
        tarayici.close()


def main() -> int:
    from playwright.sync_api import sync_playwright
    statik_kontroller()
    with sync_playwright() as p:
        ajan_duzenleme(p)
        webgl_yolu(p)
        dar_pencere(p)
        webgl_yok(p)
        canli_sahne(p)
        etkilesim(p)
        tek_ajan(p)
        uctan_uca(p)
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
