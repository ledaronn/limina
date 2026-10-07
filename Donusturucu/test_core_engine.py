"""Calistirma: python -B -m unittest discover -s Donusturucu -v"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from core_engine import DocumentConverter, LIBREOFFICE_TIMEOUT


def format_ciktisi() -> str:
    """Gercek list_formats govdesini MCP bagimliligi olmadan calistirir."""
    tree = ast.parse(Path(__file__).with_name("server.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "list_formats")
    fn.decorator_list = []
    module = ast.Module(body=[fn], type_ignores=[])
    namespace = {"DocumentConverter": DocumentConverter}
    exec(compile(ast.fix_missing_locations(module), "server.py", "exec"), namespace)
    return namespace["list_formats"]()


def arac_cagri_zaman_asimi() -> float:
    """mcp_bridge.ARAC_CAGRI_ZAMAN_ASIMI degerini MCP bagimliligi olmadan okur.

    mcp_bridge.py'yi DOGRUDAN import etmiyoruz: o dosya 'mcp' paketini import
    eder ve bu test ortaminda o paket olmayabilir (bkz. KURULUM.md). Kaynagi
    ayristirip sabiti okumak, ayni yontemi kullanan format_ciktisi() ile tutarli.
    """
    yol = Path(__file__).resolve().parent.parent / "pevrai" / "mcp_bridge.py"
    tree = ast.parse(yol.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "ARAC_CAGRI_ZAMAN_ASIMI" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("mcp_bridge.py icinde ARAC_CAGRI_ZAMAN_ASIMI bulunamadi.")


class ConverterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(os.path.realpath(self.temp.name))
        self.src = self.root / "notlar.md"
        self.src.write_text("# Deneme\nTürkçe: ığüşöç İĞÜŞÖÇ\n", encoding="utf-8")
        self.out = self.root / "cikti"
        self.out.mkdir()
        self.converter = DocumentConverter()
        self.soffice = patch("core_engine._soffice_yolu", return_value=os.path.realpath("soffice"))
        self.soffice.start()
        self.addCleanup(self.soffice.stop)

    def test_formats(self) -> None:
        output = format_ciktisi()
        for ext in (".md", ".txt"):
            self.assertIn(f"{ext} -> .pdf", output)
            self.assertEqual(self.converter.get_supported_targets("A" + ext.upper()), [".pdf"])

    def test_libreoffice_timeout_smaller_than_mcp_call_timeout(self) -> None:
        # LIBREOFFICE_TIMEOUT, mcp_bridge'in bir arac cagrisina verdigi sureden
        # KUCUK olmali. Aksi halde LibreOffice kendi zaman asimini bildirmeden
        # once koprü "sunucu yanit vermedi" der ve gercek sebep kaybolur.
        self.assertLess(LIBREOFFICE_TIMEOUT, arac_cagri_zaman_asimi())

    def test_text_success_and_arguments(self) -> None:
        def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
            self.assertIsInstance(args, list)
            self.assertIs(kwargs["shell"], False)
            self.assertIn("--infilter=Text (encoded):UTF8", args)
            self.assertEqual(args[-1], os.path.realpath(args[-1]))
            work = Path(args[args.index("--outdir") + 1])
            self.assertEqual(str(work), os.path.realpath(work))
            (work / "profil").mkdir()
            (work / "profil" / "test").write_text("profil", encoding="utf-8")
            (work / (Path(args[-1]).stem + ".pdf")).write_bytes(b"%PDF-test")
            return subprocess.CompletedProcess(args, 0, "", "")

        for ext in (".md", ".TXT"):
            with self.subTest(ext=ext):
                source = self.root / ("Türkçe boşluk & $dosya" + ext)
                source.write_text("Merhaba", encoding="utf-8-sig")
                with patch("core_engine.subprocess.run", side_effect=run):
                    result = self.converter.convert_file(str(source), "PDF", str(self.out))
                self.assertTrue(result["success"], result)
                self.assertEqual(Path(result["target"]).read_bytes(), b"%PDF-test")
                self.assertFalse(list(self.out.glob("donusturucu_*")))

    def test_failure_preserves_existing_pdf_and_cleans(self) -> None:
        old = self.out / "notlar.pdf"
        old.write_bytes(b"onceki PDF")
        for returncode, content in ((0, None), (0, b""), (1, b"%PDF-partial")):
            def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
                work = Path(args[args.index("--outdir") + 1])
                if content is not None:
                    (work / "notlar.pdf").write_bytes(content)
                return subprocess.CompletedProcess(args, returncode, "", "deneme hatasi")

            with self.subTest(code=returncode, content=content), patch("core_engine.subprocess.run", side_effect=run):
                result = self.converter.convert_file(str(self.src), output_dir=str(self.out))
                self.assertFalse(result["success"])
                self.assertEqual(old.read_bytes(), b"onceki PDF")
                self.assertEqual(list(self.out.iterdir()), [old])

    def test_timeout_cleans(self) -> None:
        with patch("core_engine.subprocess.run", side_effect=subprocess.TimeoutExpired(["soffice"], 120)):
            result = self.converter.convert_file(str(self.src), output_dir=str(self.out))
        self.assertFalse(result["success"])
        self.assertIn("zaman asimi", result["error"])
        self.assertEqual(list(self.out.iterdir()), [])

    def test_invalid_encoding(self) -> None:
        self.src.write_bytes(b"\xffinvalid")
        with patch("core_engine.subprocess.run") as run:
            result = self.converter.convert_file(str(self.src), output_dir=str(self.out))
        run.assert_not_called()
        self.assertFalse(result["success"])
        self.assertIn("UTF-8", result["error"])

    def test_missing_libreoffice(self) -> None:
        with patch("core_engine._soffice_yolu", return_value=None):
            result = self.converter.convert_file(str(self.src), output_dir=str(self.out))
        self.assertFalse(result["success"])
        self.assertIn("LibreOffice bulunamadi", result["error"])

    def test_resolves_symlinks(self) -> None:
        source_link = self.root / "kaynak.md"
        output_link = self.root / "hedef"
        try:
            source_link.symlink_to(self.src)
            output_link.symlink_to(self.out, target_is_directory=True)
        except OSError:
            self.skipTest("Bu ortamda sembolik baglanti olusturma yetkisi yok.")
        with patch.object(self.converter, "_convert_via_libreoffice", return_value=str(self.out / "notlar.pdf")) as convert:
            result = self.converter.convert_file(str(source_link), output_dir=str(output_link))
        convert.assert_called_once_with(str(self.src), str(self.out))
        self.assertTrue(result["success"])
        self.assertEqual(result["source"], str(self.src))


if __name__ == "__main__":
    unittest.main()
