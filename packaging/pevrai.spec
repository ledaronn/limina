# -*- mode: python ; coding: utf-8 -*-
# pevrai.spec — PyInstaller tarifi. Calistir: python packaging/build.py
#
# Tek dist klasoru (onedir), iki exe:
#   Pevrai.exe       pencere (konsolsuz). Ayrica --mcp-sunucu <betik> ile
#                    ayni exe stdio MCP sunucusu olur (bkz. pevrai/baslat.py).
#   pevrai-cli.exe   konsol: gorev, --gecmis, --geri-al, --tani.
#
# NEDEN onedir, onefile DEGIL: onefile her acilista kendini gecici klasore
# acar (150+ MB, 5-10 sn), MCP alt sureci icin sys.executable yine ayni
# arsivi acar, antivirusler sever sanmaz. onedir + kurulum programi (Inno)
# tek tikla kurulum verir, acilis aninda.
#
# VERI DOSYALARI BEYAZ LISTE: proje klasoru toptan alinmaz. policy.toml,
# config/persona.md, chrome-profil, .venv — hicbiri pakete girmez.
# Kisisel dosyalar dondurulmus surumde %LOCALAPPDATA%/Pevrai'da uretilir.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

KOK = Path(SPECPATH).resolve().parent          # proje koku (packaging/ ustu)

# --- veri: (kaynak, hedef klasor) --------------------------------------------
datas = [
    (str(KOK / "pevrai" / "arayuz"), "pevrai/arayuz"),        # index.html, ikon, eklenti js/css
    (str(KOK / "policy.example.toml"), "."),                   # ilk acilis sablonu
    (str(KOK / "config" / "persona.example.md"), "config"),
    (str(KOK / "Donusturucu" / "server.py"), "Donusturucu"),   # converter MCP (runpy ile)
    (str(KOK / "Donusturucu" / "core_engine.py"), "Donusturucu"),
    (str(KOK / "LICENSE"), "."),
    (str(KOK / "NOTICE"), "."),
]
# Playwright surucusu (node + paket) paket verisi olarak gelir; hook yok.
datas += collect_data_files("playwright", includes=["driver/**/*"])
# Sertifika demeti (httpx/certifi), pymupdf verileri
datas += collect_data_files("certifi")
datas += collect_data_files("pymupdf")
datas += copy_metadata("pevrai")  # Runtime version/update checks need distribution metadata.

# --- gizli iceri aktarimlar --------------------------------------------------
hiddenimports = [
    # kayit defteri modulleri import aninda kayit olur; hepsi acikca
    *collect_submodules("pevrai"),
    # winrt ad-uzayi paketi: statik analiz yakalamiyor
    "winrt", "winrt._winrt", "winrt.system", "winrt.runtime",
    "winrt.windows.foundation", "winrt.windows.foundation.collections",
    "winrt.windows.globalization", "winrt.windows.graphics.imaging",
    "winrt.windows.media.ocr", "winrt.windows.storage.streams",
    # saglayicilar ve mcp
    *collect_submodules("google.genai"), *collect_submodules("mcp"),
    "anthropic", "keyring", "keyring.backends", "keyring.backends.Windows",
    "keyring.backends.null",  # Package probes must not read the user's system vault.
    # belge okuyucular (Donusturucu runpy ile kosunca da bulunmali)
    "pymupdf", "docx", "pptx", "openpyxl", "PIL", "yaml",
]
binaries = []
try:
    from PyInstaller.utils.hooks import collect_dynamic_libs
    binaries += collect_dynamic_libs("winrt")
except Exception:
    pass

# --- analiz: iki giris, ortak PYZ --------------------------------------------
a_gui = Analysis([str(KOK / "packaging" / "giris_pencere.py")],
                 pathex=[str(KOK)], binaries=binaries, datas=datas,
                 hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
                 excludes=["tkinter", "customtkinter", "tkinterdnd2", "pytest", "IPython"],
                 noarchive=False)
a_cli = Analysis([str(KOK / "packaging" / "giris_cli.py")],
                 pathex=[str(KOK)], binaries=binaries, datas=[],
                 hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
                 excludes=["tkinter", "customtkinter", "tkinterdnd2", "pytest", "IPython"],
                 noarchive=False)
MERGE((a_gui, "Pevrai", "Pevrai"), (a_cli, "pevrai-cli", "pevrai-cli"))

pyz_gui = PYZ(a_gui.pure)
exe_gui = EXE(pyz_gui, a_gui.scripts, [],
              exclude_binaries=True, name="Pevrai",
              icon=str(KOK / "pevrai" / "arayuz" / "pevrai.ico"),
              console=False, disable_windowed_traceback=False,
              upx=False, bootloader_ignore_signals=False, strip=False)

pyz_cli = PYZ(a_cli.pure)
exe_cli = EXE(pyz_cli, a_cli.scripts, [],
              exclude_binaries=True, name="pevrai-cli",
              icon=str(KOK / "pevrai" / "arayuz" / "pevrai.ico"),
              console=True, upx=False, strip=False)

coll = COLLECT(exe_gui, a_gui.binaries, a_gui.datas,
               exe_cli, a_cli.binaries, a_cli.datas,
               name="Pevrai", upx=False, strip=False)
