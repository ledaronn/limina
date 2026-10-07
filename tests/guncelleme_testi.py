"""Surum denetimi: sahte HTTP, saat ve gecici ayar dosyalari."""
from pathlib import Path
import json
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pevrai.guncelleme import Denetleyici, surum_parcala, _http


class GuncellemeTesti(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"
        self.now = 200000.0
        self.calls = []
        self.reply = {"tag_name": "v1.10.0"}

    def http(self, repo):
        self.calls.append(repo)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply

    def kontrolcu(self):
        return Denetleyici("pevrai", "1.9.9", self.path, istek=self.http, saat=lambda: self.now)

    def test_kapali_iken_hic_istek_ve_dosya_yok(self):
        denet = self.kontrolcu()
        self.assertIsNone(denet.kontrol(False))
        self.assertFalse(denet.baslat(False))
        self.assertFalse(self.path.exists())
        self.assertEqual(self.calls, [])

    def test_yeni_surumu_sayisal_karsilastirir(self):
        denet = self.kontrolcu()
        self.assertEqual(denet.kontrol(True), {"surum": "v1.10.0", "url": "https://github.com/ledaronn/pevrai/releases"})
        self.assertIsNone(denet.bildirim(False))
        self.assertEqual(self.calls, ["pevrai"])

    def test_eski_ayni_ve_gecersiz_surumu_gostermez(self):
        for etiket in ("v1.9.9", "v1.8.0", "v1.10.0-rc.1", "<script>", "x", None):
            with self.subTest(etiket=etiket):
                self.path.unlink(missing_ok=True)
                self.reply = {"tag_name": etiket}
                self.assertIsNone(self.kontrolcu().kontrol(True))

    def test_gunluk_sinir_yeniden_baslatmada_da_korunur(self):
        denet = self.kontrolcu()
        denet.kontrol(True)
        self.assertIsNotNone(self.kontrolcu().kontrol(True))
        self.assertEqual(len(self.calls), 1)
        self.now += 86400
        self.kontrolcu().kontrol(True)
        self.assertEqual(len(self.calls), 2)

    def test_ag_hatasi_sessiz_ve_gunluk_sinir_icinde(self):
        self.reply = TimeoutError("synthetic offline")
        denet = self.kontrolcu()
        self.assertIsNone(denet.kontrol(True))
        self.assertIsNone(denet.kontrol(True))
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(denet.bildirim(True))

    def test_kapatilan_surumu_tekrar_gostermez_yenisini_gosterir(self):
        denet = self.kontrolcu()
        denet.kontrol(True)
        denet.kapat("v1.10.0")
        self.assertIsNone(denet.bildirim(True))
        self.assertIsNone(self.kontrolcu().kontrol(True))
        self.now += 86400
        self.reply = {"tag_name": "v1.11.0"}
        self.assertEqual(self.kontrolcu().kontrol(True)["surum"], "v1.11.0")
        self.assertEqual(set(json.loads(self.path.read_text())), {"son_kontrol", "surum", "kapatilan"})

    def test_onbellek_yazilamazsa_istek_yok(self):
        denet = self.kontrolcu()
        with patch.object(denet, "_yaz", return_value=False):
            self.assertIsNone(denet.kontrol(True))
        self.assertEqual(self.calls, [])

    def test_arka_plan_cakisan_istek_acmaz(self):
        entered, release = threading.Event(), threading.Event()
        def bekleyen(repo):
            self.calls.append(repo)
            entered.set()
            release.wait(3)
            return self.reply
        denet = Denetleyici("pevrai", "1.9.9", self.path, istek=bekleyen, saat=lambda:self.now)
        self.assertTrue(denet.baslat(True))
        self.assertTrue(entered.wait(3))
        self.assertFalse(denet.baslat(True))
        release.set()
        for _ in range(200):
            if denet.bildirim(True):
                break
            threading.Event().wait(.01)
        self.assertEqual(len(self.calls), 1)
        self.assertIsNotNone(denet.bildirim(True))

    def test_http_kisisel_veri_tasimaz(self):
        with patch("pevrai.guncelleme.urlopen") as open_url:
            open_url.return_value.__enter__.return_value.read.return_value = b'{"tag_name":"v2.0.0"}'
            self.assertEqual(_http("pevrai")["tag_name"], "v2.0.0")
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertEqual(request.full_url, "https://api.github.com/repos/ledaronn/pevrai/releases/latest")
        self.assertNotIn("Authorization", dict(request.header_items()))

    def test_bilinmeyen_depo_ve_on_surumu_kabul_etmez(self):
        with self.assertRaises(ValueError):
            Denetleyici("outside", "1.0.0", self.path)
        self.assertEqual(surum_parcala("v1.2.3+build.4"), (1, 2, 3))
        self.assertIsNone(surum_parcala("1.2.3-beta"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
