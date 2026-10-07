# kisayol.py — masaustune "Pevrai" kisayolu (.lnk) kurar.
#
#   python -m pevrai.kisayol
#
# Neden .lnk, .bat degil: .bat once bir konsol penceresi acar (pythonw'a
# gecse bile bir an gorunur) ve ikon tasimaz. .lnk dogrudan pythonw'u
# hedefler: konsol yok, ikon var, "Baslangic konumu" proje koku — yani
# policy.toml'daki goreli MCP komutlari ve `-m pevrai` her zaman dogru
# yerden calisir.
#
# Neden mutlak pythonw: PATH'teki "pythonw" sistem Python'una cozulebilir
# (2026-09-15'te oldu: mcp yok -> pencere ilk gorevde dustu). Kisayol, BU
# komutu calistiran yorumlayicinin pythonw'unu (sys.executable'in kardesi)
# hedefler; o yoksa proje kokundeki .venv denenir. Yani `pip install` ile
# baska bir ortama kurulmus Pevrai da kisayol alabilir.
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pevrai import PAKET, PROJE_KOKU

IKON = PAKET / "arayuz" / "pevrai.ico"


def _pythonw() -> Path | None:
    adaylar = [Path(sys.executable).with_name("pythonw.exe"),
               PROJE_KOKU / ".venv" / "Scripts" / "pythonw.exe"]
    for a in adaylar:
        if a.exists():
            return a
    return None


PYTHONW = _pythonw()


def masaustu() -> Path:
    # Masaustu tasinmis olabilir (OneDrive vb.); kabuktan sor.
    cikti = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
        capture_output=True, text=True, check=True).stdout.strip()
    return Path(cikti)


def kur(hedef_klasor: Path | None = None) -> Path:
    """Kisayolu yazar, yolunu dondurur. Varsa uzerine yazar."""
    if PYTHONW is None:
        raise SystemExit(f"pythonw.exe bulunamadi ({Path(sys.executable).parent} ve {PROJE_KOKU / '.venv'}).\n"
                         f"Pevrai'yi kurdugun Python ile calistir: python -m pevrai.kisayol")
    if not IKON.exists():
        raise SystemExit(f"Ikon yok: {IKON}")
    klasor = hedef_klasor or masaustu()
    lnk = klasor / "Pevrai.lnk"
    # WScript.Shell COM: ek paket gerekmez. Yollar tek tirnakli PowerShell
    # dizesi; tek tirnak icermeyen Windows yollarinda kacis gerekmiyor.
    for y in (lnk, PYTHONW, PROJE_KOKU, IKON):
        if "'" in str(y):
            raise SystemExit(f"Yolda tek tirnak var, kisayol yazilamadi: {y}")
    betik = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}'); "
        f"$s.TargetPath = '{PYTHONW}'; "
        f"$s.Arguments = '-m pevrai'; "
        f"$s.WorkingDirectory = '{PROJE_KOKU}'; "
        f"$s.IconLocation = '{IKON},0'; "
        f"$s.Description = 'Pevrai'; "
        f"$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", betik], check=True)
    return lnk


if __name__ == "__main__":
    yol = kur()
    print(f"Kisayol yazildi: {yol}")
    print(f"  hedef : {PYTHONW} -m pevrai")
    print(f"  konum : {PROJE_KOKU}")
    sys.exit(0)
