# gezinme_testi.py — paneller ile sohbet arasinda gezinme + arka plan gorevi.
#
# Kullanici bildirimi: "sohbet disinda bir paneli acarsak yeni sohbete ya da
# herhangi bir sohbete gidemiyoruz, tekrar o panelin ikonuna tiklayip
# kapatmamiz gerekiyor." Iki kok neden vardi:
#   1. Kenar cubugunda AKTIF sohbete tiklamak hicbir sey yapmiyordu.
#   2. Gorev calisirken sohbet_ac/yeni_sohbet reddediyor, arayuz PANELDE
#      kaliyordu.
# Ayrica: gorev arka planda calisiyordu ama baska paneldeyken ONAY isterse
# gorunmuyordu; gorev sessizce asili kaliyordu.
#
#   python tests/gezinme_testi.py
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


# Sahte kopru: iki sohbet; GOREV_VAR iken sohbet_ac/yeni_sohbet reddeder
# (gercek kopru boyle davranir: tek isci var).
SAHTE = """() => {
  window.CAGRI = []; window.GOREV_VAR = false; window.OLAYLAR = [];
  const sohbetler = () => [
    {id: 's1', baslik: 'Birinci sohbet', guncelleme: '2026-09-24T10:00:00', aktif: true},
    {id: 's2', baslik: 'Ikinci sohbet', guncelleme: '2026-09-23T10:00:00', aktif: false}];
  window.pywebview = { api: new Proxy({}, { get: (_, ad) => {
    if (ad === 'olaylari_cek') return () => { const o = window.OLAYLAR; window.OLAYLAR = [];
      return Promise.resolve({ok: true, olaylar: o, calisiyor: window.GOREV_VAR, sohbetler: sohbetler(),
        kota: [], toplu_onaylar: [], kapali_araclar: [], uyarilar: []}); };
    if (ad === 'sohbet_ac') return (k) => { window.CAGRI.push(['sohbet_ac', k]);
      return Promise.resolve(window.GOREV_VAR
        ? {ok: false, hata: 'Önce çalışan görevi durdur: bir görev çalışırken başka sohbete geçilemez.'}
        : {ok: true, olaylar: []}); };
    if (ad === 'yeni_sohbet') return () => { window.CAGRI.push(['yeni_sohbet']);
      return Promise.resolve(window.GOREV_VAR ? {ok: false, hata: 'Önce çalışan görevi durdur.'} : {ok: true, id: 's3'}); };
    if (ad === 'saglayici_bilgisi') return () => Promise.resolve({ok: true, anahtar_var: true});
    if (ad === 'arayuz_ayarlari') return () => Promise.resolve({ok: true, arayuz: {genel: {dil: 'tr'}, gorunum: {}, sohbet: {}, gelismis: {}}});
    if (ad === 'ag_listesi') return () => Promise.resolve({ok: true, aglar: []});
    if (ad === 'ekip_projeler' || ad === 'ekip_kosular') return () => Promise.resolve({ok: true, projeler: [], kosular: []});
    if (ad === 'ajanlar') return () => Promise.resolve({ok: true, ajanlar: []});
    if (ad === 'anahtar_yuvalari') return () => Promise.resolve({ok: true, yuvalar: {}});
    if (ad === 'araclar_durumu' || ad === 'paketler') return () => Promise.resolve({ok: true, paketler: [], araclar: []});
    return () => Promise.resolve({ok: true});
  }})};
}"""

PANELLER = [("ag", "ray-ag", "ag-gorunum"), ("ekip", "ray-ekip", "ekip-gorunum"),
            ("araclar", "ray-araclar", "araclar-gorunum")]


def main() -> int:
    from playwright.sync_api import sync_playwright
    html = PAKET / "arayuz" / "index.html"
    with sync_playwright() as p:
        tarayici = p.chromium.launch(channel="chrome", headless=True)
        sayfa = tarayici.new_page(viewport={"width": 1280, "height": 860})
        hatalar: list[str] = []
        sayfa.on("pageerror", lambda e: hatalar.append(str(e)))
        sayfa.goto(html.as_uri()); sayfa.wait_for_timeout(400)
        sayfa.evaluate(SAHTE); sayfa.wait_for_timeout(300)
        sayfa.evaluate("dilAyarla('tr')")
        def yan_acik():
            return sayfa.evaluate("() => document.getElementById('yan').classList.contains('acik')"
                                  " || document.body.classList.contains('sabit-yan')")

        def yan_ac():
            # Kullanici gibi: panel acikken kenar cubugunu dugmesiyle acar
            if not yan_acik():
                sayfa.click("#ray-yan"); sayfa.wait_for_timeout(350)

        def sohbet_gorunuyor():
            return sayfa.evaluate("() => getComputedStyle(document.getElementById('akis')).display !== 'none'")

        def panel_acik(kap):
            return sayfa.evaluate(f"() => document.getElementById('{kap}').classList.contains('acik')")

        print("\n1) Panel acikken sohbete donmek (panel ikonuna basmadan)")
        for ad, ray, kap in PANELLER:
            sayfa.evaluate(f"gorunum('{ad}')"); sayfa.wait_for_timeout(250)
            dogrula(panel_acik(kap) and not sohbet_gorunuyor(), f"{ad} paneli acildi")
            yan_ac()
            # AKTIF sohbet satirina GERCEKTEN tikla (eskiden hicbir sey olmuyordu).
            # Hile yok: tiklama sohbete goturmezse test KALIR.
            dogrula(sayfa.evaluate("() => !!document.querySelector('#sohbet-listesi .sohbet.aktif')"),
                    f"{ad}: aktif sohbet satiri listede")
            sayfa.click("#sohbet-listesi .sohbet.aktif"); sayfa.wait_for_timeout(300)
            dogrula(sohbet_gorunuyor() and not panel_acik(kap), f"{ad}: AKTIF sohbete tik sohbete GOTURDU")

        sayfa.evaluate("gorunum('ekip')"); sayfa.wait_for_timeout(250)
        yan_ac()
        sayfa.click("#sohbet-listesi .sohbet:not(.aktif)"); sayfa.wait_for_timeout(350)
        dogrula(sohbet_gorunuyor() and not panel_acik("ekip-gorunum"), "BASKA bir sohbete tik da sohbete goturdu")
        dogrula(["sohbet_ac", "s2"] in sayfa.evaluate("() => window.CAGRI"), "o sohbet acildi (sohbet_ac cagrildi)")

        print("\n2) Panel acikken Yeni sohbet")
        for ad, ray, kap in PANELLER:
            sayfa.evaluate(f"gorunum('{ad}')"); sayfa.wait_for_timeout(200)
            yan_ac()
            sayfa.click("#yan-yeni"); sayfa.wait_for_timeout(300)
            dogrula(sohbet_gorunuyor() and not panel_acik(kap), f"{ad}: 'Yeni sohbet' sohbete goturdu")

        print("\n3) Gorev CALISIRKEN panelden sohbete gecis")
        sayfa.evaluate("() => { window.GOREV_VAR = true; }"); sayfa.wait_for_timeout(300)
        sayfa.evaluate("gorunum('ag')"); sayfa.wait_for_timeout(250)
        yan_ac()
        sayfa.click("#yan-yeni"); sayfa.wait_for_timeout(350)
        dogrula(sohbet_gorunuyor() and not panel_acik("ag-gorunum"),
                "reddedilse de PANELDE kalinmadi, calisan gorevin sohbetine gidildi")
        dogrula(sayfa.evaluate("() => document.body.textContent.includes('Önce çalışan görevi durdur')"),
                "sebep soylendi (cevrilmis mesaj)")

        print("\n4) Arka plan: gorev calisirken baska panelde hap gorunur")
        sayfa.evaluate("gorunum('ag')"); sayfa.wait_for_timeout(400)
        dogrula(sayfa.evaluate("() => !!document.getElementById('arka-plan')"), "baska panelde 'gorev calisiyor' hapi var")
        dogrula(sayfa.evaluate("() => document.getElementById('arka-plan').textContent.includes('çalışıyor')"),
                "hap gorevin calistigini soyluyor")
        # Onay gelirse hap degisir ve bir kez uyarir
        sayfa.evaluate("""() => { window.OLAYLAR.push({tip: 'onay_gerekli', veri: {istek: {arac: 'write_file',
            args: {path: 'kum/x.txt'}, risk: 'WRITE', etki: 'kum/x.txt yazilacak', yikici: false,
            toplu_sunulabilir: false}}}); }""")
        sayfa.wait_for_timeout(500)
        dogrula(sayfa.evaluate("() => document.getElementById('arka-plan').classList.contains('onay')"),
                "ONAY beklerken hap onay durumuna geciyor")
        dogrula(sayfa.evaluate("() => document.getElementById('arka-plan').textContent.includes('onay')"),
                "hap onay beklendigini soyluyor (gorev sessizce asili kalmiyor)")
        sayfa.click("#arka-plan"); sayfa.wait_for_timeout(300)
        dogrula(sohbet_gorunuyor() and not panel_acik("ag-gorunum"), "hapa tiklamak sohbete dondurdu")
        dogrula(sayfa.evaluate("() => !!document.querySelector('#kolon .onay')"),
                "onay karti sohbette BEKLIYOR (arka planda gelen olay kaybolmadi)")
        dogrula(sayfa.evaluate("() => !document.getElementById('arka-plan')"), "sohbetteyken hap yok")

        print("\n5) Gorev bitince hap kalkar")
        sayfa.evaluate("gorunum('ag')"); sayfa.wait_for_timeout(200)
        sayfa.evaluate("""() => { window.GOREV_VAR = false; bekleyenOnay = null;
            window.OLAYLAR.push({tip: 'gorev_bitti', veri: {metin: 'bitti', durduruldu: false}}); }""")
        sayfa.wait_for_timeout(500)
        dogrula(sayfa.evaluate("() => !document.getElementById('arka-plan')"), "gorev bitince hap kalkti")

        print("\n6) Kenar cubugu baska bir islemde kendiliginden kapanir")
        sayfa.mouse.move(900, 400)                # fare ray/panel uzerinde kalmasin (hover acmasin)

        def sabitle():
            if not sayfa.evaluate("() => document.body.classList.contains('sabit-yan')"):
                sayfa.click("#ray-yan")
            sayfa.wait_for_timeout(300)

        def kapandi(neden):
            sayfa.mouse.move(900, 400); sayfa.wait_for_timeout(500)
            dugme = sayfa.evaluate("() => document.getElementById('ray-yan').classList.contains('aktif')")
            dogrula(not yan_acik() and not dugme, f"{neden}: kenar cubugu kapandi, dugme sondu")

        sabitle()
        dogrula(yan_acik() and sayfa.evaluate("() => document.getElementById('ray-yan').classList.contains('aktif')"),
                "dugmeye basinca acilir ve dugme yanar")
        for ray, ad in (("#ray-eklentiler", "Bilesenler"), ("#ray-ag", "Dusunce Agi"),
                        ("#ray-ekip", "Ekip"), ("#ray-araclar", "Araclar")):
            sabitle(); sayfa.click(ray); kapandi(f"{ad} paneline gecince")
        sayfa.evaluate("gorunum('sohbet')")
        sabitle(); sayfa.click("#sohbet-listesi .sohbet:not(.aktif)"); kapandi("sohbet secince")
        sabitle(); sayfa.click("#yan-yeni"); kapandi("Yeni sohbet")
        sabitle(); sayfa.keyboard.press("Escape"); kapandi("Esc")
        sabitle(); sayfa.mouse.click(900, 300); kapandi("ana alana tiklayinca")
        sabitle(); sayfa.click("#yan-ayarlar"); kapandi("Ayarlar")
        sayfa.keyboard.press("Escape"); sayfa.wait_for_timeout(300)
        sabitle(); sayfa.click("#ray-yan"); kapandi("dugmeye yeniden basinca")
        sayfa.click("#ray-ara"); sayfa.wait_for_timeout(300)
        dogrula(yan_acik() and sayfa.evaluate("() => document.getElementById('ray-yan').classList.contains('aktif')"),
                "arama da acar ve dugmeyi yakar (eskiden dugme sonuk kaliyordu)")
        sayfa.fill("#arama", "Iki"); sayfa.wait_for_timeout(300)
        dogrula(yan_acik(), "aramaya yazarken acik kalir")
        sayfa.fill("#arama", "")

        print("\n7) Ayarlar her acilista Genel'den baslar")
        def acik_sekme():
            return sayfa.evaluate("() => (document.querySelector('#ayar-menu button.aktif') || {}).textContent || ''")
        sayfa.click("#ray-ayarlar"); sayfa.wait_for_timeout(400)
        dogrula("Genel" in acik_sekme(), f"ilk acilis: Genel ({acik_sekme()!r})")
        sayfa.evaluate("() => { ayarSekme = 'tarayici'; ayarMenusuCiz(); ayarSekmeCiz(); }"); sayfa.wait_for_timeout(300)
        sayfa.keyboard.press("Escape"); sayfa.wait_for_timeout(300)
        for yol, ad in (("#ray-ayarlar", "ray dugmesi"), ("#yan-ayarlar", "kenar cubugu 'Ayarlar'")):
            if yol == "#yan-ayarlar":
                sabitle()
            sayfa.click(yol); sayfa.wait_for_timeout(400)
            dogrula("Genel" in acik_sekme(), f"Tarayici'da kapatildiktan sonra {ad}: yine Genel ({acik_sekme()!r})")
            sayfa.keyboard.press("Escape"); sayfa.wait_for_timeout(300)
        sayfa.keyboard.press("Control+Comma"); sayfa.wait_for_timeout(400)
        dogrula("Genel" in acik_sekme(), "Ctrl+, : Genel")
        sayfa.keyboard.press("Escape"); sayfa.wait_for_timeout(300)
        sayfa.evaluate("() => ayarlariAc('model')"); sayfa.wait_for_timeout(400)
        dogrula("Model" in acik_sekme(), "sekme adi verilince o sekme acilir (ilk kurulum: Model)")

        print("\n8) Ayarlar acikken arkadaki logo animasyonu durur (kasma)")
        sayfa.evaluate("() => { const k = document.getElementById('karsilama'); if (k) k.remove(); karsilamaKur(); }")
        sayfa.wait_for_timeout(300)
        durum = sayfa.evaluate("""() => [...new Set(document.getAnimations()
            .filter(a => a.effect && a.effect.target && a.effect.target.closest && a.effect.target.closest('#ana svg'))
            .map(a => a.playState))]""")
        dogrula(durum == ["paused"], f"ayarlar acik: logo animasyonlari duraklatildi ({durum})")
        sayfa.keyboard.press("Escape"); sayfa.wait_for_timeout(300)
        durum = sayfa.evaluate("""() => [...new Set(document.getAnimations()
            .filter(a => a.effect && a.effect.target && a.effect.target.closest && a.effect.target.closest('#ana svg'))
            .map(a => a.playState))]""")
        dogrula(durum == ["running"], f"ayarlar kapaninca logo yeniden oynuyor ({durum})")
        katman = sayfa.evaluate("() => { const l = document.querySelector('.logo-buyuk'); return l ? getComputedStyle(l).willChange : 'YOK'; }")
        dogrula(katman == "transform", f"logo kendi katmaninda: boyama butun pencereyi kaplamaz ({katman})")

        dogrula(not hatalar, f"JS hatasi yok ({hatalar[:2]})")
        tarayici.close()
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
