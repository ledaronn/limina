"""packaging/build.py — Windows dagitimi: PyInstaller (onedir) + istege bagli Inno Setup.

    python packaging/build.py            # dist/Limina/  (Limina.exe, limina-cli.exe)
    python packaging/build.py --kurulum  # + dist/Limina-Kurulum-<surum>.exe (Inno Setup gerekir)

Her adimin sonunda dogrulama var: exe uretildi mi, --tani calisiyor mu,
Donusturucu MCP sunucusu exe uzerinden ayaga kalkiyor mu. Dogrulanmayan
paket "uretildi" sayilmaz.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
DIST = KOK / "dist" / "Limina"
ISCC_ADAYLARI = [Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
                 Path(r"C:\Program Files\Inno Setup 6\ISCC.exe")]


def surum() -> str:
    import tomllib
    return tomllib.loads((KOK / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def calistir(komut: list[str], **kw) -> subprocess.CompletedProcess:
    print("  $", " ".join(str(k) for k in komut))
    return subprocess.run(komut, check=True, cwd=str(KOK), **kw)


def boyut_mb(klasor: Path) -> float:
    return sum(p.stat().st_size for p in klasor.rglob("*") if p.is_file()) / 1_000_000


def pyinstaller() -> None:
    print("\n[1/3] PyInstaller")
    for eski in (KOK / "build" / "limina", DIST):
        shutil.rmtree(eski, ignore_errors=True)
    calistir([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
              "--distpath", str(KOK / "dist"), "--workpath", str(KOK / "build"),
              str(KOK / "packaging" / "limina.spec")])
    for ad in ("Limina.exe", "limina-cli.exe"):
        if not (DIST / ad).is_file():
            raise SystemExit(f"URETILEMEDI: {DIST / ad}")
    print(f"  dist/Limina: {boyut_mb(DIST):.0f} MB")


def dogrula() -> None:
    print("\n[2/3] Dogrulama (dondurulmus exe ile)")
    ortam = dict(os.environ)
    # Kisisel veri koku: gercek %LOCALAPPDATA%/Limina'ya dokunmadan gecici bir kok
    gecici = KOK / "build" / "dogrulama_localappdata"
    shutil.rmtree(gecici, ignore_errors=True)
    gecici.mkdir(parents=True)
    ortam["LOCALAPPDATA"] = str(gecici)
    r = subprocess.run([str(DIST / "limina-cli.exe"), "--tani"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=ortam, timeout=120)
    print("\n".join("    " + s for s in r.stdout.splitlines()))
    if r.returncode != 0 or "dondurulmus .exe" not in r.stdout:
        raise SystemExit(f"--tani basarisiz (cikis {r.returncode}):\n{r.stderr[-2000:]}")
    for zorunlu in ("MCP (zorunlu)      var", "HTTP (zorunlu)     var", "pencere (zorunlu)  var"):
        if zorunlu not in r.stdout:
            raise SystemExit(f"Zorunlu bilesen pakette yok: {zorunlu!r}")
    if f"Veri    : {gecici}" not in r.stdout:
        raise SystemExit("Dondurulmus surum kisisel dosyalari LOCALAPPDATA altina koymuyor!")

    # Converter MCP: Limina.exe --mcp-sunucu <betik> gercekten stdio sunucusu mu?
    print("  MCP sunucusu (Limina.exe --mcp-sunucu Donusturucu/server.py) ...")
    betik = DIST / "_internal" / "Donusturucu" / "server.py"
    p = subprocess.Popen([str(DIST / "Limina.exe"), "--mcp-sunucu", str(betik)],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ortam)
    istek = (b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05",'
             b'"capabilities":{},"clientInfo":{"name":"build","version":"0"}}}\n')
    try:
        p.stdin.write(istek); p.stdin.flush()
        bas = time.monotonic(); satir = b""
        while time.monotonic() - bas < 60:
            satir = p.stdout.readline()
            if satir.strip():
                break
        if b'"result"' not in satir or b"serverInfo" not in satir:
            raise SystemExit(f"MCP sunucusu initialize'a cevap vermedi: {satir[:300]!r}\n{p.stderr.read()[-1500:]!r}")
        print("    initialize -> " + satir.decode("utf-8", "replace")[:120].strip() + " ...")
    finally:
        p.kill()
    print("  DOGRULANDI")


def inno() -> None:
    print("\n[3/3] Inno Setup")
    iscc = next((a for a in ISCC_ADAYLARI if a.is_file()), None)
    if iscc is None:
        raise SystemExit("Inno Setup 6 bulunamadi. Kur: winget install JRSoftware.InnoSetup  "
                         "(ya da https://jrsoftware.org/isdl.php), sonra tekrar calistir.")
    calistir([str(iscc), f"/DSurum={surum()}", f"/DKok={KOK}", str(KOK / "packaging" / "limina.iss")])
    cikti = KOK / "dist" / f"Limina-Kurulum-{surum()}.exe"
    if not cikti.is_file():
        raise SystemExit(f"Kurulum paketi uretilemedi: {cikti}")
    print(f"  {cikti} ({cikti.stat().st_size / 1_000_000:.0f} MB)")


if __name__ == "__main__":
    pyinstaller()
    dogrula()
    if "--kurulum" in sys.argv:
        inno()
    print("\nTamam.")
