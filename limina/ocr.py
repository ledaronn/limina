# ocr.py — goruntuden metin: ekran goruntusu, fotograf, taranmis PDF sayfasi.
#
# MOTOR: Windows'un yerlesik OCR'i (Windows.Media.Ocr, WinRT). Neden bu:
#   - Model indirmesi yok, ek ikili yok; dil paketleri Windows'un kendi
#     "Ayarlar > Zaman ve dil" ekranindan gelir (Turkce dahil).
#   - Limina zaten Windows'a bagli (pywebview/WinForms, Chrome profili).
#   - Tesseract ayri kurulum ister; RapidOCR ~15 MB ONNX + Turkce icin ayri
#     model demek. Ikisi de "pip install" ile bitmez.
# Bedeli: Linux/macOS'ta bu modul calismaz — belge.py o zaman OCR'siz davranir
# ve acik bir metinle soyler (bkz. kullanilamaz_nedeni).
#
# Bagimlilik: pyproject [ocr] ekstrasi (winrt-Windows.Media.Ocr ve kardesleri,
# Pillow). Kurulu degilse ImportError metne cevrilir, istisna sizmaz.
from __future__ import annotations

import sys
from pathlib import Path

from limina import ceviri
from limina.ceviri import t

GORUNTU_UZANTILARI = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
# Windows OCR'in ust siniri (OcrEngine.max_image_dimension) 10000 px; daha
# buyuk goruntu kucultulur. Kucultmek dogrulugu dusurmez, ekran goruntuleri
# zaten bunun cok altinda.
AZAMI_KENAR = 4000
# PDF sayfasi bu cozunurlukte rasterlestirilir: 150 dpi metin icin yeterli,
# 300 dpi sayfa basina 4x piksel = 4x sure demek.
PDF_DPI = 170
# Tek cagrida OCR'lanacak azami PDF sayfasi: model bir dosyayi sayfa
# araligiyla okur (start_page/end_page); tamamini tek seferde istemek
# taranmis 200 sayfalik kitapta dakikalar surerdi.
AZAMI_SAYFA = 20


def kullanilamaz_nedeni() -> str | None:
    """OCR bu makinede kullanilabilir mi? Kullanilamiyorsa NEDEN (metin).

    Uc ayri neden, uc ayri cozum — hepsini tek "OCR yok" demek kullaniciyi
    yanlis yere yollardi.
    """
    if sys.platform != "win32":
        return t("OCR yalnızca Windows'ta kullanılabilir (Windows.Media.Ocr).")
    try:
        from winrt.windows.media.ocr import OcrEngine  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return t("OCR bileşeni kurulu değil: pip install -e .[ocr]")
    if not diller():
        return t("Windows'ta OCR dil paketi yok. Ayarlar > Zaman ve dil > Dil ekranından "
                 "bir dil ekleyip 'Optik karakter tanıma' özelliğini kur.")
    return None


def diller() -> list[str]:
    """Windows'ta kurulu OCR dilleri (BCP-47 etiketleri, orn. 'tr', 'en-US')."""
    try:
        from winrt.windows.media.ocr import OcrEngine
        return [d.language_tag for d in OcrEngine.available_recognizer_languages]
    except Exception:
        return []


def _dil_sec(istenen: str | None) -> str | None:
    """Kullanilacak OCR dili. Sira: istenen -> arayuz dili -> kurulu ilk dil.

    Dil OCR'de onemli: Turkce paketi 'ş/ğ/ı'yi tanir, Ingilizce paketi bunlari
    yutar (olculdu: 'şu' -> '' ). Ama yanlis dil hic dil olmamasindan iyidir;
    o yuzden son care kurulu herhangi bir dil.
    """
    kurulu = diller()
    if not kurulu:
        return None
    adaylar = [istenen, ceviri.dil()]
    for aday in adaylar:
        if not aday:
            continue
        for k in kurulu:
            if k.lower() == aday.lower() or k.lower().startswith(aday.lower() + "-"):
                return k
    return kurulu[0]


def _tani(img, dil: str) -> str:
    """PIL goruntusunu Windows OCR'a verir, satirlari korunmus metin doner."""
    import asyncio
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter

    if img.mode != "RGBA":
        img = img.convert("RGBA")
    if max(img.size) > AZAMI_KENAR:
        oran = AZAMI_KENAR / max(img.size)
        img = img.resize((max(1, int(img.width * oran)), max(1, int(img.height * oran))))
    yazici = DataWriter()
    yazici.write_bytes(img.tobytes())
    bitmap = SoftwareBitmap.create_copy_from_buffer(yazici.detach_buffer(), BitmapPixelFormat.RGBA8,
                                                    img.width, img.height)
    motor = OcrEngine.try_create_from_language(Language(dil))
    if motor is None:
        raise RuntimeError(f"OcrEngine({dil})")

    async def calistir():
        return await motor.recognize_async(bitmap)

    # Arac cagrisi ajan is parcaciginda kosar, orada olay dongusu yok;
    # asyncio.run yeni bir dongu acar ve kapatir.
    sonuc = asyncio.run(calistir())
    # Satirlar: OCR'in kendi satir bolmesi korunur — tablo/liste yapisi
    # modelin isine yarar, tek uzun dize yaramaz.
    return "\n".join(satir.text for satir in sonuc.lines).strip()


def goruntu_oku(yol: Path, dil: str | None = None) -> str:
    """Bir goruntu dosyasindaki metni doner. Hata da METIN (istisna sizmaz)."""
    neden = kullanilamaz_nedeni()
    if neden:
        return t("'{ad}' bir görüntü; metni çıkarmak için OCR gerekir. {neden}", ad=yol.name, neden=neden)
    from PIL import Image
    secilen = _dil_sec(dil)
    try:
        with Image.open(yol) as img:
            img.load()
            metin = _tani(img, secilen)
            boyut = f"{img.width}x{img.height}"
    except Exception as e:
        return t("'{ad}' OCR ile okunamadı ({tur}): {hata}", ad=yol.name, tur=type(e).__name__, hata=e)
    baslik = t("[Görüntü: {ad}, {boyut}, OCR dili: {dil}]", ad=yol.name, boyut=boyut, dil=secilen)
    if not metin:
        return baslik + "\n" + t("(görüntüde okunabilir metin bulunamadı)")
    return baslik + "\n" + metin


def pdf_sayfasi_oku(sayfa, dil: str | None = None) -> str:
    """pymupdf sayfasini rasterlestirip OCR'lar. belge._pdf metin katmani
    olmayan sayfalarda cagirir. Kullanilamiyorsa bos dize; cagiran nedeni
    kullanilamaz_nedeni() ile kendisi soyler (sayfa basina tekrarlamaz)."""
    if kullanilamaz_nedeni():
        return ""
    from PIL import Image
    secilen = _dil_sec(dil)
    piksel = sayfa.get_pixmap(dpi=PDF_DPI, alpha=False)
    img = Image.frombytes("RGB", (piksel.width, piksel.height), piksel.samples)
    try:
        return _tani(img, secilen)
    except Exception:
        return ""
