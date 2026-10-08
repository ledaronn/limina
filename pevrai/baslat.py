# baslat.py — tek giris noktasi: pencere, MCP alt sureci ya da tanilama.
#
#   python -m pevrai                     -> pencere (pencere.main)
#   Pevrai.exe                           -> pencere
#   Pevrai.exe --mcp-sunucu <betik.py>   -> betigi stdio MCP sunucusu olarak kosar
#   Pevrai.exe --tani                    -> ortam tanilamasi (metin), pencere acmaz
#   Pevrai.exe --isci <tarif.json>       -> ekip iscisi (dar politika, ayri surec; bkz. ekip.py)
#
# NEDEN AYRI DOSYA: pencere.py modul duzeyinde webview'i (WinForms/CLR) ice
# aktarir. MCP alt sureci icin o yuku odemek istemiyoruz — ve bir stdio
# sunucusunun stdout'una pencere kodunun tek satir bile yazmasi protokolu
# bozar. Bu yuzden argv burada, hicbir agir modul yuklenmeden okunur.
#
# DONDURULMUS SURUMDE python.exe yok: policy.toml'daki
# komut = ["python", "Donusturucu/server.py"] satiri mcp_bridge.komut_cozumle
# ile [Pevrai.exe, --mcp-sunucu, <tam yol>] olur ve buraya duser. Betik ayni
# surecte, kendi klasoru sys.path'e eklenerek (core_engine gibi yan
# modulleri bulsun) __main__ olarak calisir.
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def _mcp_sunucu(betik: str) -> int:
    yol = Path(betik).resolve()
    if not yol.is_file():
        sys.stderr.write(f"MCP betigi yok: {yol}\n")
        return 2
    sys.path.insert(0, str(yol.parent))
    sys.argv = [str(yol)]
    runpy.run_path(str(yol), run_name="__main__")
    return 0


def tanila() -> str:
    """Kurulumun durumu, tek bakista. Kullanici 'acilmiyor' dediginde ilk
    istenen sey; --tani ciktisini yapistirmasi yeterli. Anahtar YAZILMAZ,
    yalnizca kaynagi (ortam/keyring/dosya/yok)."""
    import platform
    from pevrai import DONMUS, KAYNAK_KOK, PAKET, PROJE_KOKU
    satirlar = [
        f"Pevrai {surum()}",
        f"Python  : {platform.python_version()} ({'dondurulmus .exe' if DONMUS else 'kaynaktan'})",
        f"Sistem  : {platform.platform()}",
        f"Kod     : {PAKET}",
        f"Kaynak  : {KAYNAK_KOK}",
        f"Veri    : {PROJE_KOKU}",
    ]
    for ad in ("policy.toml", "config/persona.md", "config/arayuz.toml"):
        satirlar.append(f"  {ad:20} {'var' if (PROJE_KOKU / ad).exists() else 'yok (ilk acilista sablondan)'}")
    try:
        from pevrai import anahtar
        for s in ("gemini", "openai", "anthropic"):
            satirlar.append(f"Anahtar {s:10}: {anahtar.kaynak(s)}")
    except Exception as e:
        satirlar.append(f"Anahtar: okunamadi ({type(e).__name__}: {e})")
    import importlib.util
    for paket, ne in (("mcp", "MCP (zorunlu)"), ("httpx", "HTTP (zorunlu)"), ("webview", "pencere (zorunlu)"),
                      ("google.genai", "Gemini"), ("anthropic", "Anthropic"), ("keyring", "anahtar deposu"),
                      ("playwright", "tarayici"), ("pymupdf", "PDF"), ("docx", "DOCX"), ("pptx", "PPTX"),
                      ("openpyxl", "XLSX")):
        satirlar.append(f"  {ne:18} {'var' if importlib.util.find_spec(paket) else 'yok'}")
    try:
        from pevrai import ocr
        neden = ocr.kullanilamaz_nedeni()
        satirlar.append(f"  {'OCR':18} {'var, diller: ' + ', '.join(ocr.diller()) if neden is None else 'yok — ' + neden}")
    except Exception as e:
        satirlar.append(f"  {'OCR':18} hata: {type(e).__name__}: {e}")
    return "\n".join(satirlar)


def surum() -> str:
    from pevrai import DONMUS, KAYNAK_KOK
    # Editable metadata can be stale after changing the source version.
    if not DONMUS:
        try:
            import tomllib
            with (KAYNAK_KOK / "pyproject.toml").open("rb") as f:
                return str(tomllib.load(f)["project"]["version"])
        except (OSError, KeyError, ValueError):
            pass
    try:
        from importlib.metadata import version
        return version("pevrai")
    except Exception:
        return "(surum bilgisi yok)"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--mcp-sunucu"]:
        if len(argv) < 2:
            sys.stderr.write("Kullanim: --mcp-sunucu <betik.py>\n")
            return 2
        return _mcp_sunucu(argv[1])
    if argv[:1] == ["--isci"]:
        # Ekip iscisi: dar politikayla tek alt gorev (ekip.isci_calistir).
        if len(argv) < 2:
            sys.stderr.write("Kullanim: --isci <tarif.json>\n")
            return 2
        from pevrai.ekip import isci_calistir
        return isci_calistir(argv[1])
    if argv[:1] in (["--tani"], ["--surum"], ["--version"]):
        print(surum() if argv[0] != "--tani" else tanila())
        return 0
    from pevrai.pencere import main as pencere_main
    return pencere_main()


if __name__ == "__main__":
    sys.exit(main())
