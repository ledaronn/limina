"""Brand migration regression tests; all user data and credentials are synthetic."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pevrai import anahtar, ceviri, PAKET
from pevrai.uyumluluk import ortam, veri_koku


class SahteAnahtarDeposu:
    def __init__(self):
        self.veri = {}

    def get_password(self, servis, kimlik):
        return self.veri.get((servis, kimlik))

    def set_password(self, servis, kimlik, deger):
        self.veri[servis, kimlik] = deger

    def delete_password(self, servis, kimlik):
        self.veri.pop((servis, kimlik), None)


class KimlikGecisi(unittest.TestCase):
    def test_eski_ortam_ve_yeni_onceligi(self):
        with patch.dict(os.environ, {"LIMINA_POLICY": "old-policy.toml"}, clear=True):
            self.assertEqual(ortam("POLICY"), "old-policy.toml")
            os.environ["PEVRAI_POLICY"] = "worker-policy.toml"
            self.assertEqual(ortam("POLICY"), "worker-policy.toml")
            os.environ["PEVRAI_POLICY"] = ""
            self.assertEqual(ortam("POLICY"), "")

    def test_mevcut_veri_tasinmadan_okunur(self):
        with tempfile.TemporaryDirectory() as tmp:
            yerel = Path(tmp)
            self.assertEqual(veri_koku(yerel), yerel / "Pevrai")
            eski = yerel / "Limina"
            eski.mkdir()
            policy = eski / "policy.toml"
            policy.write_text("# synthetic policy", encoding="utf-8")
            self.assertEqual(veri_koku(yerel), eski)
            yeni = yerel / "Pevrai"
            yeni.mkdir()
            self.assertEqual(veri_koku(yerel), eski)
            (yeni / "policy.toml").write_text("# new synthetic policy", encoding="utf-8")
            self.assertEqual(veri_koku(yerel), yeni)
            self.assertEqual(policy.read_text(encoding="utf-8"), "# synthetic policy")

    def test_donmus_uygulama_eski_veriyi_bulur(self):
        with tempfile.TemporaryDirectory() as tmp:
            yerel = Path(tmp)
            (yerel / "Limina").mkdir()
            env = dict(os.environ, LOCALAPPDATA=tmp)
            for name in ("PEVRAI_POLICY", "LIMINA_POLICY"):
                env.pop(name, None)
            code = ("import sys; sys.frozen=True; sys._MEIPASS=sys.argv[1]; "
                    "import pevrai; print(pevrai.PROJE_KOKU.name)")
            result = subprocess.run([sys.executable, "-c", code, tmp],
                                    cwd=PAKET.parent, env=env, capture_output=True,
                                    text=True, check=True)
            self.assertEqual(result.stdout.strip(), "Limina")
            self.assertFalse((yerel / "Pevrai").exists())

    def test_journal_eski_ortam_yolunu_kullanir(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, LIMINA_VEKIL_KOK=tmp)
            env.pop("PEVRAI_VEKIL_KOK", None)
            code = ("import sys; from pathlib import Path; from pevrai import journal; "
                    "assert journal.KOK == Path(sys.argv[1])")
            subprocess.run([sys.executable, "-c", code, tmp], cwd=PAKET.parent,
                           env=env, capture_output=True, check=True)

    def test_eski_dil_ve_yeni_dil_onceligi(self):
        eski = ceviri._dil
        try:
            with patch.dict(os.environ, {"LIMINA_DIL": "tr"}, clear=True):
                ceviri.dil_sifirla()
                self.assertEqual(ceviri.dil(), "tr")
                os.environ["PEVRAI_DIL"] = "en"
                ceviri.dil_sifirla()
                self.assertEqual(ceviri.dil(), "en")
        finally:
            ceviri._dil = eski

    def test_eski_anahtar_yuvalari_guncellenir_ve_silinir(self):
        kr = SahteAnahtarDeposu()
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(anahtar, "_keyring", return_value=kr), \
                patch.object(anahtar, "DOSYA", Path(tmp) / "credentials.json"), \
                patch.object(anahtar, "YUVA_DIZINI", Path(tmp) / "slots.json"), \
                patch.dict(os.environ, {}, clear=True):
            for yuva in ("", "work"):
                with self.subTest(yuva=yuva):
                    key = anahtar.kimlik("openai", yuva)
                    kr.veri["limina", key] = "old-synthetic-key"
                    self.assertEqual(anahtar.oku("openai", yuva), "old-synthetic-key")
                    self.assertEqual(anahtar.kaynak("openai", yuva), "keyring")
                    self.assertIsNone(anahtar.yaz("openai", "new-synthetic-key", yuva))
                    self.assertEqual(anahtar.oku("openai", yuva), "new-synthetic-key")
                    self.assertNotIn(("limina", key), kr.veri)
                    self.assertIsNone(anahtar.yaz("openai", "", yuva))
                    self.assertIsNone(anahtar.oku("openai", yuva))
                    kr.veri["limina", key] = "old-synthetic-key"
                    self.assertIsNone(anahtar.yaz("openai", "", yuva))
                    self.assertIsNone(anahtar.oku("openai", yuva))

    def test_yeni_anahtar_eski_anahtardan_once_gelir(self):
        kr = SahteAnahtarDeposu()
        kr.veri["limina", "openai"] = "old-synthetic-key"
        kr.veri["pevrai", "openai"] = "new-synthetic-key"
        with patch.object(anahtar, "_keyring", return_value=kr):
            self.assertEqual(anahtar.oku("openai"), "new-synthetic-key")

    def test_arayuz_eski_tercihleri_korur(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True)
            try:
                page = browser.new_page()
                errors = []
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.add_init_script("""localStorage.clear();
                  localStorage.setItem('limina.dil','tr');
                  localStorage.setItem('limina.model','old-model');
                  localStorage.setItem('pevrai.model','current-model');
                  localStorage.setItem('limina.arayuz','{"gorunum":{"tema":"acik"}}');
                  localStorage.setItem('limina.not-taslaklari','[["demo",{"title":"Synthetic draft"}]]');
                """)
                page.goto((PAKET / "arayuz" / "index.html").as_uri())
                self.assertEqual(page.title(), "Pevrai")
                state = page.evaluate("""() => ({
                  language: DIL, model: seciliModel,
                  draft: localStorage.getItem('pevrai.not-taslaklari'),
                  original: localStorage.getItem('limina.not-taslaklari'),
                  theme: localStorage.getItem('pevrai.arayuz')
                })""")
                self.assertEqual(state["language"], "tr")
                self.assertEqual(state["model"], "current-model")
                self.assertEqual(state["draft"], state["original"])
                self.assertEqual(json.loads(state["draft"])[0][0], "demo")
                self.assertEqual(json.loads(state["theme"])["gorunum"]["tema"], "acik")
                self.assertEqual(page.evaluate("document.documentElement.dataset.tema"), "acik")
                self.assertEqual(errors, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
