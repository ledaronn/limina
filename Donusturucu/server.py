# server.py — Donusturucu'yu MCP sunucusu olarak disari acar (stdio).
# Kendi izin kontrolunu yapmaz: yol denetimi Vekil'in kapisinda (gate.py) olur.
from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from core_engine import DocumentConverter

mcp = MCPServer("donusturucu")
_converter = DocumentConverter()


@mcp.tool()
def convert(src: str, target_format: str, dst_dir: str) -> str:
    """Bir belgeyi baska bir formata donusturur. Sadece su donusumler desteklenir:
    PPTX/PPT/DOCX/MD/TXT -> PDF, PDF -> PPTX veya PNG, PNG/JPG -> PDF. Baska hicbir kaynak/hedef
    kombinasyonu calismaz — once list_formats ile desteklenen matrisi kontrol et.
    Metin duzenleme, OCR, tarama veya toplu/klasor donusumu YAPMAZ — tek dosya alir.
    MD/TXT UTF-8 olmalidir; duz metin aktarilir, Markdown isaretleri korunur.

    Args:
        src: Donusturulecek dosyanin tam yolu.
        target_format: Hedef uzanti, orn. 'pdf', 'pptx', 'png' (nokta olmadan da olur).
        dst_dir: Ciktinin yazilacagi klasorun tam yolu.
    """
    sonuc = _converter.convert_file(src, target_ext=target_format, output_dir=dst_dir)
    if sonuc["success"]:
        return f"Donusturuldu: '{sonuc['source']}' -> '{sonuc['target']}'"
    raise ValueError(f"Donusturulemedi: {sonuc['error']}")


@mcp.tool()
def list_formats() -> str:
    """Desteklenen kaynak->hedef donusum matrisini metin olarak listeler. Bir donusum
    denemeden once hangi formatlarin calistigini kontrol etmek icin kullan."""
    satirlar = [
        f"{kaynak} -> {', '.join(hedefler)}"
        for kaynak, hedefler in DocumentConverter.CONVERSION_MAP.items()
    ]
    return "Desteklenen donusumler:\n" + "\n".join(satirlar)


if __name__ == "__main__":
    mcp.run()
