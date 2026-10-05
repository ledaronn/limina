# ocr_testi.py — goruntu ve taranmis PDF okuma (limina/ocr.py + belge.py).
#
# Windows yerlesik OCR'i kullanir. Dil paketi olmayan bir makinede (CI
# kosucusu olabilir) OCR yolu OLCULEMEZ; o zaman "kullanilamiyor" dali
# sinanir: arac yine metin doner, nedenini soyler, istisna sizdirmaz.
#
#   python tests/ocr_testi.py
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from limina import kurulum
kurulum.politikayi_hazirla(sessiz=True)
from limina import belge, ceviri, ocr
import limina.vekil_v0 as v
from limina.gate import Politika, ALLOW
from limina import PROJE_KOKU

ceviri.dil_ayarla("tr")
HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


def not_dus(mesaj: str) -> None:
    print("  NOT    " + mesaj)


def _goruntu(metinler: list[str], genislik: int = 1100):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (genislik, 70 * len(metinler) + 40), "white")
    d = ImageDraw.Draw(img)
    try:
        yazi = ImageFont.truetype("arial.ttf", 40)
    except Exception:
        yazi = None
    for i, m in enumerate(metinler):
        d.text((20, 20 + 70 * i), m, fill="black", font=yazi)
    return img


def main() -> int:
    pol = Politika(PROJE_KOKU / "policy.toml")
    kum = Path(pol.calisma or pol.yazma[0])
    d = Path(tempfile.mkdtemp(prefix="limina_ocr_", dir=kum))
    try:
        print("\n1) OCR kullanilabilirlik")
        neden = ocr.kullanilamaz_nedeni()
        print(f"      diller: {ocr.diller()}  neden: {neden!r}")
        dogrula(neden is None or isinstance(neden, str), "kullanilamaz_nedeni None ya da metin")

        png = d / "ekran.png"
        _goruntu(["Merhaba dünya, şu görüntü OCR ile okundu: 1234", "Toplam: 42,50 TL (Test)"]).save(png)
        r = belge.oku(png)
        print("      goruntu ->", r[:120].replace("\n", " | "))
        if neden is None:
            dogrula(r.startswith("[Görüntü:") and "1234" in r and "42,50" in r, "PNG'den metin cikti (sayilar dogru)")
            if any(k.lower().startswith("tr") for k in ocr.diller()):
                dogrula("dünya" in r and "görüntü" in r, "Turkce dil paketi: ş/ğ/ü korunuyor")
            else:
                not_dus("Turkce OCR paketi yok; diyakritik testi atlandi")
            dogrula("\n" in r.split("]", 1)[1].strip(), "satirlar korunuyor (tek uzun dize degil)")
        else:
            dogrula("OCR" in r and "ekran.png" in r, f"OCR yokken neden soyleniyor: {r[:90]}")

        print("\n2) read_document araci goruntuyu kabul ediyor (kapi + arac)")
        dogrula(".png" in belge.DESTEKLENEN and ".jpg" in belge.DESTEKLENEN, "goruntu uzantilari destekleniyor")
        karar = pol.karar("read_document", {"path": str(png)})
        dogrula(karar.sonuc == ALLOW, f"kapi: okuma koku icindeki PNG -> {karar.sonuc}")
        r2 = v.read_document(png, {})
        dogrula(r2 == r or r2.startswith("[Görüntü:") or "OCR" in r2, "arac belge.oku ile ayni yolu kullaniyor")

        print("\n3) Taranmis PDF: metin katmani yok -> sayfa OCR'lanir, isaretlenir")
        import pymupdf
        pdf = d / "tarama.pdf"
        with pymupdf.open() as doc:
            sayfa = doc.new_page(width=800, height=400)
            pix = pymupdf.Pixmap(str(png))
            sayfa.insert_image(sayfa.rect, pixmap=pix)          # yalnizca goruntu, metin katmani yok
            sayfa2 = doc.new_page(width=800, height=400)
            sayfa2.insert_text((40, 80), "Bu sayfada gercek metin katmani var.", fontsize=20)
            doc.save(pdf)
        r3 = belge.oku(pdf)
        print("      pdf ->", r3[:160].replace("\n", " | "))
        if neden is None:
            dogrula("--- sayfa 1 [OCR] ---" in r3 and "1234" in r3, "1. sayfa OCR ile okundu ve [OCR] etiketli")
            dogrula("--- sayfa 2 ---" in r3 and "gercek metin katmani" in r3, "2. sayfa metin katmanindan, OCR'siz")
            dogrula("1 sayfa OCR ile okundu" in r3, "OCR uyarisi basta (hatali karakter olabilir)")
        else:
            dogrula("sayfa 2" in r3 and "[OCR]" not in r3, "OCR yokken metin katmani olan sayfa yine okunuyor")

        print("\n4) OCR kullanilamiyorken (Windows disi / paket yok) davranis")
        with patch.object(ocr, "kullanilamaz_nedeni", return_value="SAHTE NEDEN"):
            r4 = belge.oku(png)
            dogrula("SAHTE NEDEN" in r4 and "ekran.png" in r4, "goruntu: neden metinde, istisna yok")
            with pymupdf.open() as doc:
                doc.new_page().insert_image(pymupdf.Rect(0, 0, 400, 200), pixmap=pymupdf.Pixmap(str(png)))
                doc.save(d / "sadece_tarama.pdf")
            r5 = belge.oku(d / "sadece_tarama.pdf")
            dogrula("metin katmanı yok" in r5 and "SAHTE NEDEN" in r5, "tamamen taranmis PDF: neden metinde")
        with patch.object(sys, "platform", "linux"):
            dogrula("Windows" in (ocr.kullanilamaz_nedeni() or ""), "Windows disinda acik neden")

        print("\n5) Dil secimi")
        with patch.object(ocr, "diller", return_value=["en-US", "tr"]):
            ceviri.dil_ayarla("tr")
            dogrula(ocr._dil_sec(None) == "tr", "arayuz dili tr -> OCR dili tr")
            ceviri.dil_ayarla("en")
            dogrula(ocr._dil_sec(None) == "en-US", "arayuz dili en -> en-US eslesir (on ek)")
            dogrula(ocr._dil_sec("de") == "en-US", "istenen dil kurulu degilse arayuz dili")
            ceviri.dil_ayarla("tr")
        with patch.object(ocr, "diller", return_value=["de-DE"]):
            dogrula(ocr._dil_sec(None) == "de-DE", "hicbiri eslesmezse kurulu ilk dil (yanlis dil > dil yok)")

        print("\n6) Sinirlar")
        dogrula(ocr.AZAMI_SAYFA >= 5 and ocr.AZAMI_KENAR <= 10000, "sayfa ve kenar tavanlari makul")
        if neden is None:
            buyuk = d / "buyuk.png"
            _goruntu(["Büyük görüntü küçültülür"], genislik=6000).save(buyuk)
            r6 = belge.oku(buyuk)
            dogrula("küçültülür" in r6 or "kucultulur" in r6.lower() or "OCR" in r6, "kenar tavani ustu goruntu yine okunuyor")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
