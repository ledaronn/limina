"""Gercek DOM ile surum bildirimi, kapatma ve sabit indirme koprusu."""
from pathlib import Path
import sys
import unittest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


class GuncellemeArayuzu(unittest.TestCase):
    def test_bildirim_kapanir_indirme_sabit_kopruden_gecer(self):
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True)
            try:
                page = browser.new_page(viewport={"width":360,"height":780})
                errors = []
                page.on("pageerror",lambda err:errors.append(str(err)))
                page.add_init_script("""localStorage.clear(); window.calls=[];
                  window.update={surum:'v0.2.0',url:'https://example.com/untrusted'};
                  window.pywebview={api:new Proxy({}, {get:(_,name)=>(...args)=>{
                    calls.push([name,args]);
                    if(name==='guncelleme_kapat')window.update=null;
                    if(name==='arayuz_ayarlari')return Promise.resolve({ok:true,arayuz:{genel:{dil:'en',kurulum_tamam:true}}});
                    return Promise.resolve({ok:true,olaylar:[],calisiyor:false,guncelleme:window.update,sohbetler:[],komutlar:[]});
                  }})};""")
                page.goto((ROOT/"pevrai/arayuz/index.html").as_uri())
                notice = page.locator("#guncelleme-bildirim")
                expect(notice).to_contain_text("Version v0.2.0 is available")
                bounds=notice.bounding_box()
                self.assertGreaterEqual(bounds["x"],0)
                self.assertLessEqual(bounds["x"]+bounds["width"],360)
                notice.get_by_role("button",name="Download",exact=True).click()
                self.assertEqual(page.evaluate("calls.filter(c=>c[0]==='guncelleme_indir')"),[["guncelleme_indir",[]]])
                self.assertEqual(page.locator("a[href='https://example.com/untrusted']").count(),0)
                notice.get_by_role("button",name="Dismiss notification",exact=True).click()
                expect(notice).to_have_count(0)
                page.wait_for_timeout(350)
                expect(notice).to_have_count(0)
                self.assertEqual(page.evaluate("calls.filter(c=>c[0]==='guncelleme_kapat')"),[["guncelleme_kapat",["v0.2.0"]]])
                page.evaluate("guncellemeBildirimi({surum:'v0.3.0'})")
                expect(notice).to_be_visible()
                page.evaluate("guncellemeBildirimi(null)")
                expect(notice).to_have_count(0)
                self.assertEqual(errors,[])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
