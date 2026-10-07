# ag_arayuz_testi.py — Dusunce Agi alani (pevrai/arayuz/ag.js): headless Chrome, sahte kopru.
#
# Olculen: alan aciliyor ve 3B tuval gercekten CIZIYOR (bos degil); baloncuga
# tiklayinca denetci onu aciyor; tur/kapi/esik degisiklikleri ag_kaydet'e
# gidiyor; baloncuk ve baglanti eklenebiliyor; "Atesle" kosuyu alip SIRAYI
# gosteriyor ve engellenen dugum gerekcesiyle goruluyor; okuma goreve
# gonderilebiliyor; ikon adlari IKON tablosunda; dil degisince Ingilizce.
#
#   python tests/ag_arayuz_testi.py
from __future__ import annotations

import json
import re
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


def _dugum(kimlik, tur, baslik, konum, **ek):
    return {"kimlik": kimlik, "tur": tur, "baslik": baslik, "metin": ek.get("metin", ""),
            "yol": ek.get("yol", ""), "kapi": ek.get("kapi", "herhangi"), "esik": ek.get("esik"),
            "k": None, "yanlilik": 0, "sira": None, "kaynak": "kullanici", "renk": "",
            "konum": konum, "etiketler": []}


AG = {"ad": "kompost", "aciklama": "",
      "dugumler": [_dugum("n1", "fikir", "Hedef kitle", [-120, -60, 20], metin="Balkonda yetiştirenler."),
                   _dugum("n2", "dosya", "notlar.md", [-90, 70, -60], yol="kum/notlar.md"),
                   _dugum("n3", "kural", "Başlıklar ## ile", [40, 0, 40], kapi="hepsi"),
                   _dugum("n4", "cikti", "Rehberi yaz", [160, -40, -30], kapi="esik", esik=1.2)],
      "baglantilar": [{"kaynak": "n1", "hedef": "n3", "agirlik": 1.0, "gecikme": 2},
                      {"kaynak": "n2", "hedef": "n3", "agirlik": 1.0, "gecikme": 4},
                      {"kaynak": "n3", "hedef": "n4", "agirlik": -1.0, "gecikme": 3}]}

KOSU = {"ad": "kompost", "uyaran": ["n1"], "bilinmeyen_uyaran": [], "uyarilar": [],
        "sessiz": [{"kimlik": "n4", "baslik": "Rehberi yaz", "tur": "cikti", "neden": "toplam 1 < eşik 1.2"}],
        "engellenen": [{"kimlik": "n2", "baslik": "notlar.md", "gerekce": "DENY: okuma kökü dışı"}],
        "sira": [{"sira": 1, "tik": 0, "kimlik": "n1", "tur": "fikir", "baslik": "Hedef kitle", "yol": "",
                  "kapi": "herhangi",
                  "kaynak": "kullanici"},
                 {"sira": 2, "tik": 2, "kimlik": "n3", "tur": "kural", "baslik": "Başlıklar ## ile", "yol": "",
                  "kapi": "hepsi", "kaynak": "kullanici"}]}
METIN = "## Ağ okuması: kompost — 2 düğüm sırayla ateşledi\n\n1. [fikir] Hedef kitle (tik 0)\nBalkonda yetiştirenler."

SAHTE = """(veri) => {
  const [AG, KOSU, METIN] = veri;
  const bos = () => Promise.resolve({ok: true, olaylar: [], calisiyor: false, sohbetler: [], kota: [], toplu_onaylar: [], kapali_araclar: []});
  window.CAGRI = []; window.TUM_KAYIT = [];
  window.pywebview = { api: new Proxy({}, { get: (_, ad) => {
    if (ad === 'ag_listesi') return () => Promise.resolve({ok: true, aglar: [
      {ad: AG.ad, dosya: 'kompost.json', aciklama: '', dugum: AG.dugumler.length, baglanti: AG.baglantilar.length, guncelleme: ''}]});
    if (ad === 'ag_getir') return () => Promise.resolve({ok: true, ag: JSON.parse(JSON.stringify(AG))});
    if (ad === 'ag_atesle') return (...a) => { window.CAGRI.push(['ag_atesle', a]); return Promise.resolve({ok: true, kosu: KOSU, metin: METIN}); };
    if (ad === 'ag_kaydet') return (...a) => { window.CAGRI.push(['ag_kaydet', a[0]]);
      (window.TUM_KAYIT = window.TUM_KAYIT || []).push(JSON.parse(JSON.stringify(a[0])));
      if (window.REDDET) return Promise.resolve({ok: false, hata: 'motor reddetti (deneme)'});
      return Promise.resolve({ok: true, uyarilar: ["'n4' asla ateşleyemez: en fazla 1 toplanır, eşik 1.2"]}); };
    if (ad === 'ag_gorev_baslat') return (...a) => { window.CAGRI.push(['ag_gorev_baslat', a]); return Promise.resolve({ok: true}); };
    if (ad === 'arayuz_ayarlari') return () => Promise.resolve({ok: true, arayuz: {genel: {dil: 'tr'}, gorunum: {}, sohbet: {}, gelismis: {}}});
    return bos;
  }})};
}"""


def ikon_kontrolu() -> None:
    """ag.js'in istedigi her ikon adi IKON tablosunda olmali: bilinmeyen ad
    hata vermez, SESSIZCE bos bir SVG cizer."""
    print("\n0) Ag alani ikonlari IKON tablosunda")
    kod = (PAKET / "arayuz" / "index.html").read_text(encoding="utf-8")
    bas = kod.find("const IKON")
    tablo = set(re.findall(r"\b([a-z0-9]+):\[", kod[bas:kod.find("\n};", bas)]))
    js = (PAKET / "arayuz" / "ag.js").read_text(encoding="utf-8")
    istenen = set(re.findall(r'ikon\("([a-z0-9]+)"', js))
    # ikonlu(kap, "ad", metin): ilk arguman parantez iceriyor, bir duzey izin ver.
    istenen |= set(re.findall(r'ikonlu\((?:[^()]|\([^()]*\))*?,\s*"([a-z0-9]+)"\s*,', js))
    istenen |= set(re.findall(r'\["([a-z0-9]+)", "[A-ZÇĞİÖŞÜ][^"]*", \(\)', js))      # arac cubugu
    istenen |= set(re.findall(r'satir\(ic, "[^"]+", "([a-z0-9]+)"', js))               # denetci satirlari
    eksik = sorted(istenen - tablo)
    dogrula(len(istenen) >= 8, f"{len(istenen)} farkli ikon adi bulundu")
    dogrula(not eksik, f"tabloda olmayan ikon yok ({eksik})")


def main() -> int:
    from playwright.sync_api import sync_playwright
    html = PAKET / "arayuz" / "index.html"
    ikon_kontrolu()
    print("\n1) Ag alani (headless Chrome)")
    with sync_playwright() as p:
        tarayici = p.chromium.launch(channel="chrome", headless=True)
        sayfa = tarayici.new_page(viewport={"width": 1180, "height": 820})
        hatalar: list[str] = []
        sayfa.on("pageerror", lambda e: hatalar.append(str(e)))
        def kare_bekle():
            """Tuval koordinatlari (_nokta) animasyon karesinde hesaplaniyor;
            sabit ms beklemek yukluyken yetmiyor. Iki gercek kare bekle."""
            sayfa.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

        sayfa.goto(html.as_uri()); sayfa.wait_for_timeout(400)
        sayfa.evaluate(SAHTE, [AG, KOSU, METIN]); sayfa.wait_for_timeout(200)
        sayfa.evaluate("dilAyarla('tr')")
        sayfa.evaluate("gorunum('ag')"); sayfa.wait_for_timeout(700)
        dogrula(sayfa.evaluate("() => document.getElementById('ag-gorunum').classList.contains('acik')"), "Ağ alanı açıldı")
        dogrula(sayfa.evaluate("() => getComputedStyle(document.getElementById('akis')).display === 'none'"), "sohbet akışı gizlendi")

        # 3B tuval gercekten cizdi mi: saydam olmayan piksel say.
        dolu = sayfa.evaluate("""() => { const c = document.getElementById('ag-tuval');
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 8) n += 1; return n; }""")
        dogrula(dolu > 3000, f"tuval 3B sahneyi cizdi ({dolu} piksel)")
        dogrula(sayfa.evaluate("() => Object.keys(Ag.D._nokta || {}).length") == 4, "dort baloncuk izdusumu hesaplandi")
        # Dondurunce izdusum degisiyor (gercekten uc boyut)
        kare_bekle()
        once = sayfa.evaluate("() => Ag.D._nokta.n1.x")
        sayfa.evaluate("() => { Ag.D.donme.y += 1.0; }"); sayfa.wait_for_timeout(200)
        dogrula(abs(sayfa.evaluate("() => Ag.D._nokta.n1.x") - once) > 5, "dondurme izdusumu degistiriyor (3B)")

        # Baloncuk secimi ve denetci
        sayfa.evaluate("() => { Ag.D.secili = 'n3'; Ag.ciz(); }"); sayfa.wait_for_timeout(300)
        dogrula(sayfa.evaluate("() => document.querySelector('.ag-uye-bas strong').textContent") == "n3", "denetci secili baloncugu acti")
        dogrula(sayfa.evaluate("() => document.querySelectorAll('.ag-baglanti').length") == 3, "gelen + giden baglantilar listelendi")
        sayfa.select_option(".ag-satir select >> nth=1", "esik")   # Kapı: ağırlıklı eşik
        sayfa.wait_for_timeout(900)
        cagri = sayfa.evaluate("() => window.CAGRI")
        kaydedilen = [c for c in cagri if c[0] == "ag_kaydet"]
        dogrula(bool(kaydedilen) and next(d for d in kaydedilen[-1][1]["dugumler"] if d["kimlik"] == "n3")["kapi"] == "esik",
                "kapi degisikligi ag_kaydet'e gitti")

        # Baloncuk ekleme
        sayfa.click(".ag-araclar button >> nth=1"); sayfa.wait_for_timeout(900)   # Baloncuk ekle
        dogrula(sayfa.evaluate("() => Ag.D.ag.dugumler.length") == 5, "yeni baloncuk eklendi")
        kaydedilen = [c for c in sayfa.evaluate("() => window.CAGRI") if c[0] == "ag_kaydet"]
        dogrula(len(kaydedilen[-1][1]["dugumler"]) == 5, "ekleme de kaydedildi")

        # Baglama kipi: kaynak secili -> hedefe tiklamak baglanti kurar
        sayfa.evaluate("() => { Ag.D.secili = 'n1'; Ag.ciz(); }")
        sayfa.click(".ag-araclar button >> nth=2"); sayfa.wait_for_timeout(200)   # Bağla
        dogrula(sayfa.evaluate("() => Ag.D.baglaniyor") == "n1", "baglama kipi kaynakla acildi")
        sayfa.evaluate("() => { const n = Ag.D._nokta.n4; const c = document.getElementById('ag-tuval');"
                       " const k = c.getBoundingClientRect();"
                       " c.dispatchEvent(new PointerEvent('pointerdown', {clientX: k.left + n.x, clientY: k.top + n.y,"
                       " bubbles: true, pointerId: 1})); }")
        sayfa.wait_for_timeout(900)
        dogrula(sayfa.evaluate("() => Ag.D.ag.baglantilar.some(b => b.kaynak === 'n1' && b.hedef === 'n4')"),
                "tuvalde hedefe tiklayinca baglanti kuruldu")

        # SURUKLEME — bu bolum bir regresyon testi: ciz() her cagrildiginda
        # <canvas>'i yeniden yaratiyordu, dolayisiyla pointerdown'dan sonra
        # pointermove KOPMUS tuvale gidiyordu: ne baloncuk tasinabiliyordu ne
        # de ag dondurulebiliyordu. Tuval artik sabit; iskelet bir kez kurulur.
        def surukle(bas, bit, dugme_basi=None):
            sayfa.evaluate("""([bas, bit]) => {
              const c = document.getElementById('ag-tuval'); const k = c.getBoundingClientRect();
              const olay = (tip, p) => c.dispatchEvent(new PointerEvent(tip, {clientX: k.left + p[0],
                clientY: k.top + p[1], bubbles: true, pointerId: 7, isPrimary: true, buttons: 1}));
              olay('pointerdown', bas);
              const n = 6;
              for (let i = 1; i <= n; i += 1) olay('pointermove', [bas[0] + (bit[0] - bas[0]) * i / n,
                                                                   bas[1] + (bit[1] - bas[1]) * i / n]);
              olay('pointerup', bit);
            }""", [bas, bit])
            sayfa.wait_for_timeout(250)

        bos_nokta = sayfa.evaluate("""() => { const c = document.getElementById('ag-tuval');
            return [c.clientWidth - 40, c.clientHeight - 40]; }""")     # baloncuksuz kose
        aci_once = sayfa.evaluate("() => [Ag.D.donme.x, Ag.D.donme.y]")
        surukle(bos_nokta, [bos_nokta[0] - 120, bos_nokta[1] - 60])
        aci_sonra = sayfa.evaluate("() => [Ag.D.donme.x, Ag.D.donme.y]")
        dogrula(abs(aci_sonra[1] - aci_once[1]) > 0.2 and abs(aci_sonra[0] - aci_once[0]) > 0.1,
                f"bos alani suruklemek agi DONDURUYOR ({aci_once} -> {aci_sonra})")

        konum_once = sayfa.evaluate("() => Ag.D.ag.dugumler.find(d => d.kimlik === 'n1').konum.slice()")
        kare_bekle()
        n1 = sayfa.evaluate("() => [Ag.D._nokta.n1.x, Ag.D._nokta.n1.y]")
        surukle(n1, [n1[0] + 70, n1[1] + 45])
        konum_sonra = sayfa.evaluate("() => Ag.D.ag.dugumler.find(d => d.kimlik === 'n1').konum.slice()")
        dogrula(any(abs(a - b) > 4 for a, b in zip(konum_once, konum_sonra)),
                f"baloncugu suruklemek TASIYOR ({konum_once} -> {konum_sonra})")
        sayfa.wait_for_timeout(800)
        kaydedilen = [c for c in sayfa.evaluate("() => window.CAGRI") if c[0] == "ag_kaydet"]
        dogrula(any(abs(a - b) > 4 for a, b in
                    zip(next(d for d in kaydedilen[-1][1]["dugumler"] if d["kimlik"] == "n1")["konum"], konum_once)),
                "tasinan konum kaydedildi")
        dogrula(sayfa.evaluate("() => document.querySelectorAll('#ag-tuval').length") == 1,
                "tuval TEK: paneller tazelense de yeniden yaratilmiyor")

        # Nefes: sahne duruyormus gibi gorunmesin (kayitli konum degismeden)
        n1_ekran = sayfa.evaluate("() => Ag.D._nokta.n1.x"); sayfa.wait_for_timeout(420)
        konum_esit = sayfa.evaluate("() => Ag.D.ag.dugumler.find(d => d.kimlik === 'n1').konum.slice()")
        dogrula(abs(sayfa.evaluate("() => Ag.D._nokta.n1.x") - n1_ekran) > 0.05
                and konum_esit == konum_sonra, "hafif nefes hareketi var ama KAYITLI konum degismiyor")

        # --- Gorunum: donme ekseni KUMENIN merkezi ---
        # Donme dunya sifiri etrafinda olsaydi, agirlik merkezi oradan uzak bir
        # ag ekran disindaki bir nokta etrafinda savrulurdu ("islevsiz" donme).
        # Eksen dugumlerin agirlik merkezidir ve ag yuklenince/sifirlaninca
        # sabitlenir; her karede yeniden hesaplansaydi tek bir dugumu tasimak
        # butun sahneyi kaydirirdi.
        def ekran_ortasindan_sapma():
            return sayfa.evaluate("""() => { const c = document.getElementById('ag-tuval');
                const n = Object.values(Ag.D._nokta);
                const ox = n.reduce((t, p) => t + p.x, 0) / n.length, oy = n.reduce((t, p) => t + p.y, 0) / n.length;
                return [Math.abs(ox - c.clientWidth / 2), Math.abs(oy - c.clientHeight / 2)]; }""")

        sayfa.evaluate("() => { Ag.D.ag.dugumler.forEach(d => { d.konum[0] += 600; d.konum[1] += 400; }); }")
        sayfa.evaluate("""() => { const c = document.getElementById('ag-tuval');
            c.dispatchEvent(new MouseEvent('dblclick', {clientX: 5, clientY: 5, bubbles: true})); }""")
        sayfa.wait_for_timeout(250)
        sapma = ekran_ortasindan_sapma()
        dogrula(sapma[0] < 60 and sapma[1] < 60,
                f"konumlar kaydirilip gorunum sifirlaninca ag EKRAN ORTASINDA {sapma}")
        sayfa.evaluate("() => { Ag.D.donme = {x: 0.4, y: 1.57}; }"); sayfa.wait_for_timeout(250)
        sapma2 = ekran_ortasindan_sapma()
        dogrula(sapma2[0] < 60 and sapma2[1] < 60,
                f"dondurunce de merkezde: KUMENIN kendi merkezi etrafinda donuyor {sapma2}")
        kare_bekle()
        tasima_once = sayfa.evaluate("() => Ag.D._nokta.n3.x")
        sayfa.evaluate("() => { Ag.D.ag.dugumler.find(d => d.kimlik === 'n1').konum[0] += 300; }")
        sayfa.wait_for_timeout(200)
        dogrula(abs(sayfa.evaluate("() => Ag.D._nokta.n3.x") - tasima_once) < 1,
                "bir dugumu tasimak DIGERLERINI kaydirmiyor (eksen sabit)")
        sayfa.evaluate("""() => { Ag.D.ag.dugumler.forEach(d => { d.konum[0] -= 600; d.konum[1] -= 400; });
            Ag.D.ag.dugumler.find(d => d.kimlik === 'n1').konum[0] -= 300;
            Ag.D.donme = {x: -0.35, y: 0.6}; const c = document.getElementById('ag-tuval');
            c.dispatchEvent(new MouseEvent('dblclick', {clientX: 5, clientY: 5, bubbles: true})); }""")
        sayfa.wait_for_timeout(250)

        # Tekerlek: imlecin altindaki nokta yerinde kalmali (tek sabit merkez degil)
        sayfa.wait_for_timeout(200)
        kare_bekle()
        once = sayfa.evaluate("() => [Ag.D.olcek, Ag.D._nokta.n1.x, Ag.D._nokta.n1.y]")
        sayfa.evaluate("""() => { const c = document.getElementById('ag-tuval'); const k = c.getBoundingClientRect();
            const n = Ag.D._nokta.n1;
            c.dispatchEvent(new WheelEvent('wheel', {deltaY: -120, clientX: k.left + n.x, clientY: k.top + n.y,
                                                     bubbles: true, cancelable: true})); }""")
        sayfa.wait_for_timeout(250)
        sonra = sayfa.evaluate("() => [Ag.D.olcek, Ag.D._nokta.n1.x, Ag.D._nokta.n1.y]")
        dogrula(sonra[0] > once[0], f"tekerlek yakinlastirdi ({once[0]:.2f} -> {sonra[0]:.2f})")
        dogrula(abs(sonra[1] - once[1]) < 6 and abs(sonra[2] - once[2]) < 6,
                f"IMLECIN altindaki baloncuk yerinde kaldi ({once[1:]} -> {sonra[1:]})")

        # --- Sag tik ile baglama: ilk tik kaynak, ikinci tik hedef ---
        sayfa.evaluate("() => { Ag.D.ag.baglantilar = Ag.D.ag.baglantilar.filter(b => !(b.kaynak === 'n4' && b.hedef === 'n1')); }")
        def sag_tik(kimlik):
            kare_bekle()
            # GERCEK sira: tarayici sag tikta once pointerdown, sonra contextmenu,
            # sonra pointerup uretir. Yalnizca contextmenu gondermek, pointerdown'un
            # de baglamaya karistigi sonsuz zincir hatasini gizlemisti.
            sayfa.evaluate("""(k) => { const c = document.getElementById('ag-tuval');
                const r = c.getBoundingClientRect(); const n = Ag.D._nokta[k];
                const x = r.left + n.x, y = r.top + n.y;
                c.dispatchEvent(new PointerEvent('pointerdown', {clientX: x, clientY: y, button: 2,
                    buttons: 2, bubbles: true, pointerId: 9, isPrimary: true}));
                c.dispatchEvent(new MouseEvent('contextmenu', {clientX: x, clientY: y, button: 2,
                    bubbles: true, cancelable: true}));
                c.dispatchEvent(new PointerEvent('pointerup', {clientX: x, clientY: y, button: 2,
                    bubbles: true, pointerId: 9})); }""", kimlik)
            sayfa.wait_for_timeout(250)
        sag_tik("n4")
        dogrula(sayfa.evaluate("() => Ag.D.baglaniyor") == "n4", "ilk sag tik KAYNAGI secti")
        once_sayi = sayfa.evaluate("() => Ag.D.ag.baglantilar.length")
        sag_tik("n1")
        dogrula(sayfa.evaluate("() => Ag.D.ag.baglantilar.some(b => b.kaynak === 'n4' && b.hedef === 'n1')"),
                "ikinci sag tik BAGLANTIYI kurdu")
        dogrula(sayfa.evaluate("() => Ag.D.ag.baglantilar.length") == once_sayi + 1, "TEK baglanti eklendi")
        dogrula(sayfa.evaluate("() => Ag.D.baglaniyor") is None,
                "baglama kipi KAPANDI (hedef yeni kaynak olmuyor: sonsuz zincir yok)")
        # Zincir gercekten kirildi mi: ucuncu bir dugume sag tik yeni bir baglanti
        # DEGIL, yeni bir kaynak secimi olmali.
        sag_tik("n3")
        dogrula(sayfa.evaluate("() => Ag.D.ag.baglantilar.length") == once_sayi + 1,
                "ucuncu sag tik kendiliginden baglanti KURMADI")
        dogrula(sayfa.evaluate("() => Ag.D.baglaniyor") == "n3", "ucuncu sag tik yeni KAYNAK secti")
        sayfa.evaluate("""() => { const c = document.getElementById('ag-tuval');
            c.dispatchEvent(new MouseEvent('contextmenu', {clientX: 5, clientY: 5, bubbles: true, cancelable: true})); }""")
        sayfa.wait_for_timeout(200)
        # Ayni cifti ikinci kez baglamak: kopya olusmaz ve kip yine kapanir.
        sag_tik("n4"); sag_tik("n1")
        dogrula(sayfa.evaluate("() => Ag.D.ag.baglantilar.filter(b => b.kaynak === 'n4' && b.hedef === 'n1').length") == 1
                and sayfa.evaluate("() => Ag.D.baglaniyor") is None,
                "var olan baglanti tekrarlanmiyor ve kip yine kapaniyor")
        sag_tik("n1")
        sayfa.evaluate("""() => { const c = document.getElementById('ag-tuval');
            c.dispatchEvent(new MouseEvent('contextmenu', {clientX: 5, clientY: 5, bubbles: true, cancelable: true})); }""")
        sayfa.wait_for_timeout(200)
        dogrula(sayfa.evaluate("() => Ag.D.baglaniyor") is None, "bos alana sag tik baglamayi IPTAL etti")

        # --- Renk ---
        sayfa.evaluate("() => { Ag.D.secili = 'n1'; Ag.D.sekme = 'denetci'; Ag.ciz(); }"); sayfa.wait_for_timeout(250)
        dogrula(sayfa.evaluate("() => document.querySelectorAll('.ag-palet .ag-renk').length") >= 8,
                "renk paleti cizildi (turun rengi + hazir renkler)")
        sayfa.click(".ag-palet .ag-renk >> nth=2"); sayfa.wait_for_timeout(900)
        secilen = sayfa.evaluate("() => Ag.D.ag.dugumler.find(d => d.kimlik === 'n1').renk")
        dogrula(bool(secilen) and secilen.startswith("#"), f"baloncuga renk atandi ({secilen})")
        kaydedilen = [c for c in sayfa.evaluate("() => window.CAGRI") if c[0] == "ag_kaydet"]
        dogrula(next(d for d in kaydedilen[-1][1]["dugumler"] if d["kimlik"] == "n1")["renk"] == secilen,
                "renk kaydedildi")
        sayfa.click(".ag-palet .ag-renk >> nth=0"); sayfa.wait_for_timeout(900)
        dogrula(sayfa.evaluate("() => Ag.D.ag.dugumler.find(d => d.kimlik === 'n1').renk") == "",
                "ilk dugme rengi TURUN rengine dondurdu")

        # --- Alan secimi (kutu) ve toplu islemler ---
        sayfa.evaluate("""() => { const c = document.getElementById('ag-tuval');
            c.dispatchEvent(new MouseEvent('dblclick', {clientX: 5, clientY: 5, bubbles: true})); }""")
        sayfa.wait_for_timeout(300)
        # Ctrl+surukle kutu cizer; plain surukle DONDURMEYE dokunmaz.
        def kutu_sec(bas, bit, ctrl=True):
            sayfa.evaluate("""([bas, bit, ctrl]) => {
              const c = document.getElementById('ag-tuval'); const k = c.getBoundingClientRect();
              const olay = (tip, p, ek) => c.dispatchEvent(new PointerEvent(tip, Object.assign(
                {clientX: k.left + p[0], clientY: k.top + p[1], bubbles: true, pointerId: 11,
                 isPrimary: true, button: 0, buttons: 1}, ek || {})));
              olay('pointerdown', bas, {ctrlKey: ctrl});
              for (let i = 1; i <= 5; i += 1) olay('pointermove', [bas[0] + (bit[0] - bas[0]) * i / 5,
                                                                   bas[1] + (bit[1] - bas[1]) * i / 5], {ctrlKey: ctrl});
              olay('pointerup', bit, {ctrlKey: ctrl});
            }""", [bas, bit, ctrl])
            sayfa.wait_for_timeout(300)

        kutular = sayfa.evaluate("""() => { const c = document.getElementById('ag-tuval');
            return {w: c.clientWidth, h: c.clientHeight, n: Object.entries(Ag.D._nokta)
              .map(([k, p]) => [k, Math.round(p.x), Math.round(p.y)])}; }""")
        kutu_sec([2, 2], [kutular["w"] - 2, kutular["h"] - 2])
        hepsi = sayfa.evaluate("() => Ag.D.secililer.size")
        dogrula(hepsi == len(kutular["n"]), f"butun tuvali saran kutu HEPSINI secti ({hepsi}/{len(kutular['n'])})")
        dogrula(sayfa.evaluate("() => document.querySelector('.ag-sag-ic h4').textContent").find("seçili") >= 0,
                "toplu panel acildi")

        # Yalnizca bir baloncugu saran dar kutu: yaricap en yakin komsunun
        # yarisindan kucuk secilir ki sahnedeki diger baloncuklar girmesin.
        kare_bekle()
        n1 = sayfa.evaluate("""() => { const n = Ag.D._nokta.n1;
            let en = 1e9;
            Object.entries(Ag.D._nokta).forEach(([k, p]) => {
              if (k !== 'n1') en = Math.min(en, Math.hypot(p.x - n.x, p.y - n.y)); });
            return [n.x, n.y, Math.max(6, Math.min(40, en / 2 - 4))]; }""")
        kutu_sec([n1[0] - n1[2], n1[1] - n1[2]], [n1[0] + n1[2], n1[1] + n1[2]])
        dogrula(sayfa.evaluate("() => Array.from(Ag.D.secililer)") == ["n1"],
                f"dar kutu secimi DEGISTIRDI ({sayfa.evaluate('() => Array.from(Ag.D.secililer)')})")

        # Birakirken Shift: secimi degistirmek yerine EKLE
        kare_bekle()
        n2k = sayfa.evaluate("""() => { const n = Ag.D._nokta.n2;
            let en = 1e9;
            Object.entries(Ag.D._nokta).forEach(([k, p]) => {
              if (k !== 'n2') en = Math.min(en, Math.hypot(p.x - n.x, p.y - n.y)); });
            return [n.x, n.y, Math.max(6, Math.min(40, en / 2 - 4))]; }""")
        sayfa.evaluate("""([bas, bit]) => {
          const c = document.getElementById('ag-tuval'); const k = c.getBoundingClientRect();
          const o = (t, p, ek) => c.dispatchEvent(new PointerEvent(t, Object.assign(
            {clientX: k.left + p[0], clientY: k.top + p[1], bubbles: true, pointerId: 13,
             isPrimary: true, button: 0, buttons: 1}, ek)));
          o('pointerdown', bas, {ctrlKey: true}); o('pointermove', bit, {ctrlKey: true, shiftKey: true});
          o('pointerup', bit, {shiftKey: true}); }""",
          [[n2k[0] - n2k[2], n2k[1] - n2k[2]], [n2k[0] + n2k[2], n2k[1] + n2k[2]]])
        sayfa.wait_for_timeout(300)
        dogrula(sorted(sayfa.evaluate("() => Array.from(Ag.D.secililer)")) == ["n1", "n2"],
                f"Shift ile birakinca secime EKLENDI ({sayfa.evaluate('() => Array.from(Ag.D.secililer)')})")
        sayfa.keyboard.press("Escape"); sayfa.wait_for_timeout(200)
        kutu_sec([n1[0] - n1[2], n1[1] - n1[2]], [n1[0] + n1[2], n1[1] + n1[2]])

        # Ctrl+tik secime ekler/cikarir
        kare_bekle()
        n3 = sayfa.evaluate("() => [Ag.D._nokta.n3.x, Ag.D._nokta.n3.y]")
        sayfa.evaluate("""(p) => { const c = document.getElementById('ag-tuval'); const k = c.getBoundingClientRect();
            c.dispatchEvent(new PointerEvent('pointerdown', {clientX: k.left + p[0], clientY: k.top + p[1],
              ctrlKey: true, bubbles: true, pointerId: 12, isPrimary: true, button: 0, buttons: 1})); }""", n3)
        sayfa.wait_for_timeout(250)
        dogrula(sorted(sayfa.evaluate("() => Array.from(Ag.D.secililer)")) == ["n1", "n3"], "Ctrl+tik secime EKLEDI")

        # Toplu renk
        sayfa.click(".ag-palet .ag-renk >> nth=3"); sayfa.wait_for_timeout(900)
        renkler = sayfa.evaluate("() => Ag.D.ag.dugumler.filter(d => ['n1','n3'].includes(d.kimlik)).map(d => d.renk)")
        dogrula(len(set(renkler)) == 1 and renkler[0].startswith("#"), f"secilenlerin HEPSI ayni rengi aldi ({renkler})")

        # Toplu silme iki adimli
        once = sayfa.evaluate("() => Ag.D.ag.dugumler.length")
        sayfa.click("text=Seçilenleri sil"); sayfa.wait_for_timeout(250)
        dogrula(sayfa.evaluate("() => Ag.D.ag.dugumler.length") == once, "ilk tik SILMEDI (onay bekliyor)")
        dogrula(sayfa.evaluate("() => !!document.body.textContent.match(/Emin misin/)"), "onay soruldu")
        sayfa.click("text=Emin misin"); sayfa.wait_for_timeout(900)
        dogrula(sayfa.evaluate("() => Ag.D.ag.dugumler.length") == once - 2, "ikinci tik iki baloncugu sildi")
        dogrula(sayfa.evaluate("() => Ag.D.ag.baglantilar.every(b => !['n1','n3'].includes(b.kaynak) && !['n1','n3'].includes(b.hedef))"),
                "silinen baloncuklarin BAGLANTILARI da kalkti")
        kaydedilen = [c for c in sayfa.evaluate("() => window.CAGRI") if c[0] == "ag_kaydet"]
        dogrula(len(kaydedilen[-1][1]["dugumler"]) == once - 2, "silme kaydedildi")
        dogrula(sayfa.evaluate("() => Ag.D.secililer.size") == 0, "silmeden sonra secim bosaldi")

        # Escape secimi birakir
        kutu_sec([2, 2], [kutular["w"] - 2, kutular["h"] - 2])
        dogrula(sayfa.evaluate("() => Ag.D.secililer.size") > 0, "yeni secim yapildi")
        sayfa.keyboard.press("Escape"); sayfa.wait_for_timeout(250)
        dogrula(sayfa.evaluate("() => Ag.D.secililer.size") == 0 and sayfa.evaluate("() => Ag.D.kutu") is None,
                "Escape secimi birakti")

        # Ctrl'siz surukle hala DONDURUYOR (kutu secimi dondurmeyi calmadi)
        aci = sayfa.evaluate("() => Ag.D.donme.y")
        surukle([kutular["w"] - 30, kutular["h"] - 30], [kutular["w"] - 150, kutular["h"] - 90])
        dogrula(abs(sayfa.evaluate("() => Ag.D.donme.y") - aci) > 0.2 and sayfa.evaluate("() => Ag.D.secililer.size") == 0,
                "ctrl'siz surukle hala DONDURUYOR, secim yapmiyor")

        # Atesleme
        sayfa.click(".ag-araclar button >> nth=0"); sayfa.wait_for_timeout(600)   # Ateşle
        cagri = [c for c in sayfa.evaluate("() => window.CAGRI") if c[0] == "ag_atesle"]
        dogrula(bool(cagri) and cagri[-1][1][0] == "kompost", f"ag_atesle cagrildi ({cagri and cagri[-1][1]})")
        dogrula(sayfa.evaluate("() => document.querySelectorAll('.ag-sira-oge:not(.sessiz)').length") == 2,
                "okuma sirasi listelendi")
        dogrula(sayfa.evaluate("() => document.querySelector('.ag-sira-oge.sessiz').textContent")
                .find("toplam 1 < eşik 1.2") >= 0, "ATESLEMEYEN dugum SEBEBIYLE listelendi")
        dogrula(sayfa.evaluate("() => document.querySelector('.ag-sira-oge').textContent").startswith("1"), "sira numarali")
        dogrula(sayfa.evaluate("() => document.querySelector('.ag-metin').textContent").startswith("## Ağ okuması"),
                "okuma metni panelde")
        dogrula(sayfa.evaluate("() => document.body.textContent.includes('okuma kökü dışı')"),
                "ENGELLENEN dugum gerekcesiyle gorunuyor")
        dogrula(sayfa.evaluate("() => document.body.textContent.includes('1 sessiz')"), "sessiz sayisi gorunuyor")
        dogrula(sayfa.evaluate("() => Ag.D.uyarilar.length") >= 1, "statik analiz uyarisi arayuze geldi")
        sayfa.wait_for_timeout(2600)
        dogrula(sayfa.evaluate("() => Ag.D.animasyon && Ag.D.animasyon.bitti"), "animasyon bitti")
        dogrula(sayfa.evaluate("() => document.querySelector('.ag-durum').textContent.includes('ateşledi')"),
                "arac cubugundaki durum bitince tazelendi")

        # Goreve gonderme
        sayfa.fill(".ag-gonder input", "Rehberi yaz")
        sayfa.click(".ag-gonder button"); sayfa.wait_for_timeout(300)
        cagri = [c for c in sayfa.evaluate("() => window.CAGRI") if c[0] == "ag_gorev_baslat"]
        dogrula(bool(cagri) and cagri[-1][1][0] == "kompost" and cagri[-1][1][2] == "Rehberi yaz",
                f"ag_gorev_baslat: ag + uyaran + gorev ({cagri and cagri[-1][1]})")

        # Dar pencere: 1251px'lik bir pencerede arac cubugu sag panelin ustune biniyordu.
        for genislik in (1250, 1040, 860):
            sayfa.set_viewport_size({"width": genislik, "height": 800}); sayfa.wait_for_timeout(300)
            binme = sayfa.evaluate("""() => { const a = document.querySelector('.ag-araclar').getBoundingClientRect();
                const s = document.querySelector('.ag-sag').getBoundingClientRect();
                const o = document.querySelector('.ag-orta').getBoundingClientRect();
                return {tasan: Math.round(a.right - o.right), binen: Math.round(a.right - s.left)}; }""")
            dogrula(binme["tasan"] <= 1 and binme["binen"] <= 1,
                    f"{genislik}px: arac cubugu sag panele binmiyor ({binme})")
        sayfa.set_viewport_size({"width": 1180, "height": 820}); sayfa.wait_for_timeout(250)

        sayfa.evaluate("dilAyarla('en')"); sayfa.evaluate("() => Ag.ciz()"); sayfa.wait_for_timeout(300)
        dogrula(sayfa.evaluate("() => document.querySelector('.ag-yan h3').textContent") == "Networks", "dil degisince Ingilizce")
        # Tek dugumlu ag: donme ekseni sabit oldugu icin surukleme GORUNUR ve
        # birakinca dugum yerinde kalir (eksen her karede hesaplansaydi merkeze
        # geri ziplardi). Kalan ilk dugumle calisir: onceki adimlar dugum silmis
        # olabilir.
        kalan = sayfa.evaluate("""() => { const k = Ag.D.ag.dugumler[0].kimlik;
            Ag.D.ag.dugumler = Ag.D.ag.dugumler.filter(d => d.kimlik === k);
            Ag.D.ag.baglantilar = []; Ag.D.secililer.clear(); Ag.ciz(); return k; }""")
        sayfa.wait_for_timeout(250)
        kare_bekle()
        tek = sayfa.evaluate("(k) => [Ag.D._nokta[k].x, Ag.D._nokta[k].y]", kalan)
        surukle(tek, [tek[0] + 90, tek[1] + 55])
        sonra_tek = sayfa.evaluate("(k) => [Ag.D._nokta[k].x, Ag.D._nokta[k].y]", kalan)
        dogrula(abs(sonra_tek[0] - tek[0]) > 25 and abs(sonra_tek[1] - tek[1]) > 15,
                f"TEK dugumlu agda surukleme goruluyor ve yerinde kaliyor ({tek} -> {sonra_tek})")

        # --- Secim yapiskanligi: Ctrl ile girilen secimden DUZ tikla cikilir ---
        sayfa.evaluate("dilAyarla('tr')")   # bu blok metne bakiyor; EN kontrolu yukarida bitti
        # Onceki adimlar agi tek dugume indirdi; alani yeniden acmak agi
        # diskten TAZELER (ajan araclarla yazmis olabilir).
        sayfa.evaluate("() => Ag.ac()"); sayfa.wait_for_timeout(700)
        dogrula(len(sayfa.evaluate("() => Ag.D.ag.dugumler")) > 1,
                "alani yeniden acmak agi kopruden TAZELEDI (bellekteki eski hal kalmadi)")
        sayfa.evaluate("() => { Ag.D.secililer.clear(); Ag.D.secili = null; Ag.ciz(); }")
        sayfa.wait_for_timeout(200)
        kalan_kimlikler = sayfa.evaluate("() => Ag.D.ag.dugumler.map(d => d.kimlik)")
        a_k, b_k = kalan_kimlikler[0], kalan_kimlikler[1]

        def tikla(kimlik, ctrl=False):
            kare_bekle()
            sayfa.evaluate("""([k, ctrl]) => { const c = document.getElementById('ag-tuval');
                const r = c.getBoundingClientRect(); const n = Ag.D._nokta[k];
                c.dispatchEvent(new PointerEvent('pointerdown', {clientX: r.left + n.x, clientY: r.top + n.y,
                  ctrlKey: ctrl, bubbles: true, pointerId: 21, isPrimary: true, button: 0, buttons: 1}));
                c.dispatchEvent(new PointerEvent('pointerup', {clientX: r.left + n.x, clientY: r.top + n.y,
                  bubbles: true, pointerId: 21, button: 0})); }""", [kimlik, ctrl])
            sayfa.wait_for_timeout(250)

        tikla(a_k, ctrl=True); tikla(b_k, ctrl=True)
        dogrula(sayfa.evaluate("() => Ag.D.secililer.size") == 2, "Ctrl+tik iki baloncugu secti")
        tikla(a_k)
        dogrula(sayfa.evaluate("() => Array.from(Ag.D.secililer)") == [a_k],
                f"DUZ tik = YALNIZCA BUNU SEC (cikmak icin yine Ctrl gerekmiyor) "
                f"({sayfa.evaluate('() => Array.from(Ag.D.secililer)')})")
        tikla(a_k, ctrl=True)
        sayfa.evaluate("""() => { const c = document.getElementById('ag-tuval');
            c.dispatchEvent(new PointerEvent('pointerdown', {clientX: 8, clientY: 8, bubbles: true,
              pointerId: 22, isPrimary: true, button: 0, buttons: 1}));
            c.dispatchEvent(new PointerEvent('pointerup', {clientX: 8, clientY: 8, bubbles: true,
              pointerId: 22, button: 0})); }""")
        sayfa.wait_for_timeout(250)
        dogrula(sayfa.evaluate("() => Ag.D.secililer.size") == 0, "bos alana duz tik da secimi birakti")
        dogrula(sayfa.evaluate("() => Ag.D.secKipi") is False, "'Seç' kipi tek seferlik (acik kalmiyor)")

        # --- Yolsuz dosya dugumu butun agi kaydedilemez yapiyordu ---
        # Motor fail-closed: tek eksik alan AGIN TAMAMINI reddeder ve o andan
        # sonra her kayit hata verirdi (ust uste kirmizi bildirim).
        sayfa.evaluate("(k) => { Ag.D.secili = k; Ag.D.sekme = 'denetci'; Ag.ciz(); }", a_k)
        sayfa.wait_for_timeout(200)
        sayfa.evaluate("() => { window.CAGRI = []; }")
        sayfa.select_option(".ag-sag-ic .ag-satir select >> nth=0", "dosya"); sayfa.wait_for_timeout(1000)
        dogrula(sayfa.evaluate("() => window.CAGRI.filter(c => c[0] === 'ag_kaydet').length") == 0,
                "yolsuz dosya dugumu KAYDEDILMIYOR (motorun reddedecegi ag gonderilmiyor)")
        dogrula(sayfa.evaluate("() => !!document.querySelector('.ag-durum.eksik')")
                and sayfa.evaluate("() => document.querySelector('.ag-durum.eksik').textContent").find("yol") >= 0,
                "sebep ARAC CUBUGUNDA yaziyor (baska baloncuk secili olsa da gorunur): "
                + str(sayfa.evaluate("() => document.querySelector('.ag-araclar').textContent"))[:70])
        sayfa.fill(".ag-sag-ic .ag-satir input >> nth=1", "kum/notlar.md"); sayfa.wait_for_timeout(1200)
        kayit = [c for c in sayfa.evaluate("() => window.CAGRI") if c[0] == "ag_kaydet"]
        dogrula(bool(kayit), "yol girilince kayit kendiliginden surdu")
        dogrula(sayfa.evaluate("() => !document.querySelector('.ag-durum.eksik')"), "uyari kalkti")

        # --- Motor reddederse SON IYI hale don ---
        # Arayuz motorun butun kurallarini bilmiyor (ornegin "engelleyici
        # baglanti dongunun icinde olamaz"). Boyle bir degisiklikten sonra
        # AGIN TAMAMI kaydedilemez hale gelip her kayit hata veriyordu.
        iyi_hal = sayfa.evaluate("() => JSON.parse(Ag.D.sonIyi).dugumler.length")
        sayfa.evaluate("() => { window.REDDET = true; }")
        sayfa.evaluate("""() => { Ag.D.ag.dugumler.push({kimlik: 'gecersiz', tur: 'fikir', baslik: 'x',
            metin: '', yol: '', kapi: 'herhangi', esik: null, k: null, yanlilik: 0, sira: null,
            kaynak: 'kullanici', renk: '', konum: [0, 0, 0], etiketler: []}); Ag.ciz(); }""")
        sayfa.evaluate("() => Ag.D.ag.dugumler.length")
        sayfa.evaluate("() => { Ag.D.ag.aciklama = 'degisiklik'; }")
        sayfa.evaluate("() => Ag.ciz()")
        sayfa.evaluate("""() => { const d = Ag.D.ag.dugumler[0]; d.baslik = d.baslik + '!'; }""")
        # kaydet() debounce'unu tetiklemek icin denetciden bir degisiklik yap
        sayfa.evaluate("(k) => { Ag.D.secili = k; Ag.D.sekme = 'denetci'; Ag.ciz(); }", a_k)
        sayfa.wait_for_timeout(200)
        sayfa.fill(".ag-sag-ic .ag-satir input >> nth=0", "Reddedilecek")
        sayfa.wait_for_timeout(1200)
        dogrula(sayfa.evaluate("() => Ag.D.ag.dugumler.length") == iyi_hal,
                f"kayit reddedilince SON IYI hale donuldu ({sayfa.evaluate('() => Ag.D.ag.dugumler.length')} == {iyi_hal})")
        dogrula(sayfa.evaluate("() => !Ag.D.ag.dugumler.some(d => d.kimlik === 'gecersiz')"),
                "reddedilen degisiklik geri alindi")
        sayfa.evaluate("() => { window.REDDET = false; }")
        # Geri alma secimi temizler (hangi dugumun degistigi belirsiz kalmasin);
        # denetciyi yeniden ac.
        sayfa.evaluate("(k) => { Ag.D.secili = k; Ag.D.sekme = 'denetci'; Ag.ciz(); }", a_k)
        sayfa.wait_for_timeout(250)
        sayfa.fill(".ag-sag-ic .ag-satir input >> nth=0", "Yeniden kaydedilebilir")
        sayfa.wait_for_timeout(1200)
        dogrula(sayfa.evaluate("(k) => Ag.D.ag.dugumler.find(d => d.kimlik === k).baslik", a_k) == "Yeniden kaydedilebilir",
                "geri alindiktan sonra ag YINE KAYDEDILEBILIR durumda")

        dogrula(not hatalar, f"JS hatasi yok ({hatalar})")
        tarayici.close()
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
