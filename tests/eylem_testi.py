"""Tarayici eylem izinlerini modelsiz sinar.

Bu motor izin kapisinin en yeni katmani: hangi eylemin hangi sitede serbest,
sorulan ya da yasak oldugu. Yanlis calisirsa ya ajan felc olur ya da onaysiz
odeme yapabilir — ikisi de kotu, o yuzden her hucre ayri sinaniyor.

Calistirma:  python tests/eylem_testi.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # proje koku -> 'limina' paketi
from limina.gate import ALLOW, ASK, DENY, Politika, eylem_kategorisi

# Mesaj metinleri KAYNAK DILDE (Turkce) dogrulanir: ceviri.dil() normalde
# kullanicinin config/arayuz.toml ayarini okur, testin sonucu kisisel bir
# ayara bagli olamaz (Ingilizce secili bir makinede bu dosya kirilirdi).
from limina import ceviri as _ceviri
_ceviri.dil_ayarla("tr")

HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


POLITIKA_METNI = """
[filesystem]
okuma_koklari = ["{kok}"]
yazma_koklari = ["{kok}"]
yasak_kaliplar = [".env"]

[model]
varsayilan = "test"

[araclar]
browser_open = "NETWORK"
browser_read = "READ"
browser_snapshot = "READ"
browser_click = "WRITE_HAFIF"
browser_fill = "WRITE_HAFIF"
browser_download = "DESTRUCTIVE"

[browser]
izinli_alanlar = ["wikipedia.org", "ornekokul.edu.tr", "bilinmeyen-site.com"]

[browser.eylemler]
gezinme = "izin"
okuma = "izin"
tiklama = "izin"
form = "izin"
indirme = "sor"
gonderim = "sor"
odeme = "yasak"

[browser.profiller."ornekokul.edu.tr"]
indirme = "izin"

[browser.profiller."bilinmeyen-site.com"]
tiklama = "sor"
form = "yasak"
"""


def politika_kur() -> Politika:
    kok = Path(tempfile.mkdtemp()).as_posix()
    yol = Path(tempfile.mkdtemp()) / "policy.toml"
    yol.write_text(POLITIKA_METNI.format(kok=kok), encoding="utf-8")
    return Politika(yol)


def main() -> int:
    pol = politika_kur()

    print("\n1) Kategori tespiti — ayni arac, farkli kategori")
    durumlar = [
        ("browser_open", {"url": "https://x.com"}, "gezinme"),
        ("browser_read", {}, "okuma"),
        ("browser_snapshot", {}, "okuma"),
        ("browser_fill", {"name": "Ara"}, "form"),
        ("browser_download", {"name": "rapor.pdf"}, "indirme"),
        ("browser_click", {"name": "Ileri"}, "tiklama"),
        ("browser_click", {"name": "Sonraki sayfa"}, "tiklama"),
        ("browser_click", {"name": "Model sec"}, "tiklama"),
        ("browser_click", {"name": "Gonder"}, "gonderim"),
        ("browser_click", {"name": "Paylas"}, "gonderim"),
        ("browser_click", {"name": "Sil"}, "gonderim"),
        ("browser_click", {"name": "Satin Al"}, "odeme"),
        ("browser_click", {"name": "Odemeyi tamamla"}, "odeme"),
        ("browser_click", {"name": "Ödeme Yap"}, "odeme"),
        ("browser_click", {"name": "Sepete ekle"}, "odeme"),
        ("browser_click", {"name": "Para transferi"}, "odeme"),
        ("read_file", {"path": "x"}, None),
    ]
    for arac, args, beklenen in durumlar:
        bulunan = eylem_kategorisi(arac, args)
        etiket = f"{arac}({args.get('name') or args.get('url') or ''})"
        dogrula(bulunan == beklenen, f"{etiket:38} -> {bulunan}")

    print("\n2) Yanlis pozitif olmamali")
    for ad in ["Model sec", "Modern gorunum", "Kodu kopyala", "Devam et", "Giris yap",
               "Daha fazla yukle", "Kaydet", "Iptal", "Ara"]:
        dogrula(eylem_kategorisi("browser_click", {"name": ad}) == "tiklama",
                f"'{ad}' sıradan tiklama sayildi")

    print("\n3) Varsayilan profil")
    wiki = "https://tr.wikipedia.org/wiki/Trigonometri"
    dogrula(pol.karar("browser_open", {"url": wiki}).sonuc == ALLOW, "gezinme serbest")
    dogrula(pol.karar("browser_read", {}, wiki).sonuc == ALLOW, "okuma serbest")
    dogrula(pol.karar("browser_click", {"name": "Ileri"}, wiki).sonuc == ALLOW, "tiklama serbest")
    dogrula(pol.karar("browser_download", {"name": "a.pdf"}, wiki).sonuc == ASK,
            "indirme varsayilan olarak SORULUR")
    dogrula(pol.karar("browser_click", {"name": "Gonder"}, wiki).sonuc == ASK,
            "gonderim SORULUR")
    dogrula(pol.karar("browser_click", {"name": "Satin Al"}, wiki).sonuc == DENY,
            "odeme YASAK — guvenli sitede bile")

    print("\n4) Site istisnasi gevsetebiliyor")
    okul = "https://www.ornekokul.edu.tr/duyurular"
    dogrula(pol.karar("browser_download", {"name": "duyuru.pdf"}, okul).sonuc == ALLOW,
            "ornekokul.edu.tr'de indirme serbest (profil)")
    dogrula(pol.karar("browser_click", {"name": "Satin Al"}, okul).sonuc == DENY,
            "profil odemeyi ACMIYOR — istisna yazilmadi")
    dogrula(pol.karar("browser_download", {"name": "a.pdf"}, wiki).sonuc == ASK,
            "istisna diger siteye sizmadi")

    print("\n5) Site istisnasi sikilastirabiliyor")
    bilinmeyen = "https://bilinmeyen-site.com/form"
    dogrula(pol.karar("browser_click", {"name": "Ileri"}, bilinmeyen).sonuc == ASK,
            "bu sitede sıradan tiklama bile soruluyor")
    dogrula(pol.karar("browser_fill", {"name": "Ad"}, bilinmeyen).sonuc == DENY,
            "bu sitede form doldurma yasak")
    dogrula(pol.karar("browser_read", {}, bilinmeyen).sonuc == ALLOW,
            "yazilmayan kategori varsayilanda kaliyor")

    print("\n6) Alt alan adlari")
    dogrula(pol.karar("browser_download", {"name": "a.pdf"},
                      "https://ogr.ornekokul.edu.tr/x").sonuc == ALLOW, "alt alan profili miras aliyor")
    dogrula(pol.karar("browser_download", {"name": "a.pdf"},
                      "https://sahte-ornekokul.edu.tr.kotu.com/x").sonuc == ASK,
            "benzer ama farkli alan adi profili ALMIYOR")

    print("\n7) Adres bilinmiyorsa varsayilan uygulanir")
    dogrula(pol.karar("browser_download", {"name": "a.pdf"}, "").sonuc == ASK,
            "adressiz indirme soruluyor")
    dogrula(pol.karar("browser_click", {"name": "Satin Al"}, "").sonuc == DENY,
            "adressiz odeme yasak")
    dogrula(pol.karar("browser_download", {"name": "a.pdf"}, "cop veri").sonuc == ASK,
            "bozuk adres cokmuyor, varsayilana dusuyor")

    print("\n8) Alan adi beyaz listesi hala ustte")
    dogrula(pol.karar("browser_open", {"url": "https://kotusite.com"}).sonuc == DENY,
            "liste disi site profilden bagimsiz reddediliyor")
    dogrula(pol.karar("browser_open", {"url": "about:blank"}).sonuc == DENY,
            "desteklenmeyen protokol reddediliyor")

    print("\n9) Tarayici disi araclar etkilenmedi")
    dogrula(pol.karar("browser_read", {}, wiki).sonuc == ALLOW, "okuma hala serbest")
    d = pol.karar("read_file", {"path": "/olmayan/yol/x.txt"})
    dogrula(d.sonuc in (ALLOW, DENY), "dosya araci eski yoldan geciyor")

    print("\n10) Ayarsiz politika taban degerleri kullanir")
    yol = Path(tempfile.mkdtemp()) / "policy.toml"
    kok = Path(tempfile.mkdtemp()).as_posix()
    yol.write_text(f'[filesystem]\nokuma_koklari = ["{kok}"]\nyazma_koklari = ["{kok}"]\n'
                   f'yasak_kaliplar = []\n[model]\nvarsayilan = "t"\n'
                   f'[araclar]\nbrowser_click = "WRITE_HAFIF"\nbrowser_download = "DESTRUCTIVE"\n'
                   f'[browser]\nizinli_alanlar = ["x.com"]\n', encoding="utf-8")
    bos = Politika(yol)
    dogrula(bos.karar("browser_click", {"name": "Satin Al"}, "https://x.com").sonuc == DENY,
            "ayar yoksa odeme yine YASAK")
    dogrula(bos.karar("browser_download", {"name": "a"}, "https://x.com").sonuc == ASK,
            "ayar yoksa indirme yine SORULUR")

    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
