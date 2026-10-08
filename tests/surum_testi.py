"""Version identity works with stale editable metadata and frozen resources."""
from importlib.metadata import PackageNotFoundError
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pevrai.baslat import surum


class VersionIdentity(unittest.TestCase):
    def test_source_version_wins_over_stale_editable_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'pyproject.toml').write_text('[project]\nversion="2.3.4"\n', encoding='utf-8')
            with patch('pevrai.DONMUS', False), patch('pevrai.KAYNAK_KOK', Path(tmp)), \
                 patch('importlib.metadata.version', return_value='1.0.0'):
                self.assertEqual(surum(), '2.3.4')

    def test_frozen_version_uses_bundled_metadata_without_pyproject(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('pevrai.DONMUS', True), patch('pevrai.KAYNAK_KOK', Path(tmp)), \
                 patch('importlib.metadata.version', return_value='2.3.4'):
                self.assertEqual(surum(), '2.3.4')

    def test_installed_package_without_source_pyproject(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('pevrai.DONMUS', False), patch('pevrai.KAYNAK_KOK', Path(tmp)), \
                 patch('importlib.metadata.version', return_value='2.3.4'):
                self.assertEqual(surum(), '2.3.4')

    def test_missing_metadata_is_detectable_by_build_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('pevrai.DONMUS', True), patch('pevrai.KAYNAK_KOK', Path(tmp)), \
                 patch('importlib.metadata.version', side_effect=PackageNotFoundError('pevrai')):
                self.assertEqual(surum(), '(surum bilgisi yok)')


if __name__ == '__main__':
    unittest.main(verbosity=2)
