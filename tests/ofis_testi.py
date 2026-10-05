# ofis_testi.py — ekip ofisinin Python tarafi (limina/ofis.py): masa eslemesi,
# kod uzantilari, bilinmeyen arac, gorunusun belirlenimli olmasi, olaylara masa
# alaninin eklenmesi ve isci olay aktarimi (ADIM_BASLADI/OLCUM dahil).
#
#   python tests/ofis_testi.py
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from limina import kurulum
kurulum.politikayi_hazirla(sessiz=True)
from limina import ceviri, ekip, ofis
from limina.olaylar import Olay, OlayTipi

ceviri.dil_ayarla("tr")
HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


def main() -> int:
    print("\n1) Masa eslemesi")
    tablo = [
        (("write_file", {"path": "D:/x/app.py"}), "kod"),
        (("edit_file", {"path": "src/stil.CSS"}), "kod"),
        (("read_file", {"path": "ayar.toml"}), "kod"),
        (("write_file", {"path": "rapor.md"}), "dosya"),
        (("edit_file", {"path": "notlar.txt"}), "dosya"),
        (("read_file", {"path": "belge.pdf"}), "arsiv"),
        (("mkdir", {"path": "yeni/"}), "yerinde"),           # hazirlik: ajan yerinden oynamaz
        (("list_dir", {"path": "."}), "arsiv"),
        (("search", {"sorgu": "x"}), "arsiv"),
        (("read_document", {"path": "a.docx"}), "arsiv"),
        (("degisiklik_gecmisi", {}), "arsiv"),
        (("ekip_mesaj", {"metin": "x"}), "istisare"),
        (("ekip_gelen", {}), "istisare"),
        (("ag_atesle", {}), "ag"),
        (("browser_open", {"url": "https://x"}), "web"),
        (("ekip_isci", {"ad": "a"}), "bekleme"),
        (("write_file", "{'path': 'a.py'}"), "dosya"),       # isciden duz metin args: yol bilinmez
        (("write_file", {"path": "Makefile"}), "dosya"),      # uzantisiz
    ]
    for (arac, args), beklenen in tablo:
        dogrula(ofis.masa_bul(arac, args) == beklenen, f"{arac} {args!s:30.30} -> {beklenen}")
    dogrula(ofis.masa_bul("uydurma_arac", {}, "READ") == "arsiv", "eslenmeyen okuma araci -> arsiv (risk)")
    dogrula(ofis.masa_bul("trash", {}, "DESTRUCTIVE") == "dosya", "eslenmeyen yazma araci -> dosya (risk)")
    dogrula(ofis.masa_bul("uydurma_arac", {}) == "diger", "bilinmeyen arac, risk yok -> diger (kaybolmaz)")
    dogrula(ofis.kod_mu("a/b/c.JS") and not ofis.kod_mu("a.py/notlar") and not ofis.kod_mu(""), "kod_mu: son parca, buyuk/kucuk harf")
    dogrula([m["kod"] for m in ofis.masalar()] == ["kod", "dosya", "arsiv", "istisare", "ag", "web", "kapi", "bekleme"],
            "sekiz masa (3.1)")
    dogrula({m["kod"] for m in ofis.masalar()} | {"diger", "yerinde"} == ofis.MASA_KODLARI, "MASA_KODLARI masalarla uyumlu")
    dogrula(all(ofis.masa_bul(a, {}) in ofis.MASA_KODLARI for a in ekip.ISCI_ARACLARI), "her isci aracinin masasi tanimli")

    print("\n2) masa_ekle: tek yardimci")
    v = ofis.masa_ekle({"arac": "write_file", "args": {"path": "x.md"}, "risk": "WRITE"})
    dogrula(v["masa"] == "dosya", "masa alani eklendi")
    dogrula(ofis.masa_ekle({"arac": "write_file", "masa": "kod"})["masa"] == "kod", "var olan masa ezilmez")
    dogrula("masa" not in ofis.masa_ekle({"mesaj": "x"}), "arac yoksa masa eklenmez")

    print("\n3) Gorunus belirlenimli")
    a1, a2 = ofis.ajan_gorunumu("yazar"), ofis.ajan_gorunumu("yazar")
    dogrula(a1 == a2 and a1["renk"] in ofis.RENKLER and 0 <= a1["gorunum"] < ofis.GORUNUM_SAYISI,
            f"ayni ad -> ayni gorunus {a1}")
    # ekip.js renk(): h = h*31 + kod (32 bit) % 6 — kart gorunumuyle ayni renk
    h = 0
    for c in "tablocu":
        h = (h * 31 + ord(c)) % 2 ** 32
    dogrula(ofis.ajan_gorunumu("tablocu")["renk"] == ofis.RENKLER[h % 6], "ekip.js renk() ile ayni formul")
    dogrula(ofis.ajan_gorunumu("x", {"renk": "#AABBCC", "gorunum": 3}) == {"renk": "#aabbcc", "gorunum": 3},
            "tanimdaki renk/gorunum kullanilir")
    dogrula(ofis.ajan_gorunumu("x", {"renk": "kirmizi", "gorunum": 99}) == ofis.ajan_gorunumu("x"),
            "bozuk renk/gorunum -> addan")
    farkli = {ofis.ajan_gorunumu(a)["renk"] for a in ("yazar", "tablocu", "giris", "sonuc", "arastirmaci", "elestirmen")}
    dogrula(len(farkli) >= 3, f"farkli adlar farkli renkler ({len(farkli)})")

    print("\n4) duzen(): kopru verisi, cevrili adlar, anahtar yok")

    class P:
        ajanlar = {"yazar": {"saglayici": "openai", "model": "m1", "anahtar_yuvasi": "", "rol": "Yazar.",
                             "taban_url": "", "baglanti": "is", "renk": "", "gorunum": None}}
        baglantilar = {"is": {"ad": "İş hesabı", "saglayici": "openai", "taban_url": "", "anahtar_yuvasi": "api-is",
                              "modeller": ["m1"]}}
    d = ofis.duzen(P())
    dogrula(len(d["masalar"]) == 8 and d["masalar"][0]["ad"] == "Kod masası", "masalar Turkce")
    dogrula(d["ajanlar"][0]["baglanti_ad"] == "İş hesabı" and d["ajanlar"][0]["model"] == "m1", "ajan: baglanti ve model")
    dogrula("anahtar" not in json.dumps(d), "duzen anahtar/yuva tasimiyor")
    ceviri.dil_ayarla("en")
    dogrula(ofis.duzen(P())["masalar"][0]["ad"] == "Code desk", "Ingilizce: Code desk")
    tr = {m["kod"]: m for m in (ceviri.dil_ayarla("tr") or ofis.masalar())}
    ceviri.dil_ayarla("en")
    ayni = [m["kod"] for m in ofis.masalar() if m["ad"] == tr[m["kod"]]["ad"] or m["aciklama"] == tr[m["kod"]]["aciklama"]]
    dogrula(not ayni, f"butun masa metinleri cevrili ({ayni})")
    ceviri.dil_ayarla("tr")

    print("\n5) Isci olay aktarimi: yeni olay turleri ve masa")
    d = Path(tempfile.mkdtemp(prefix="limina_ofis_"))
    try:
        dosya = d / "olaylar.jsonl"
        satirlar = [
            {"tip": "ADIM_BASLADI", "veri": {"adim": 1, "azami": 8}},
            {"tip": "OLCUM", "veri": {"adim": 1, "girdi_token": 10, "cikti_token": 5}},
            {"tip": "ARAC_CAGRILDI", "veri": {"arac": "write_file", "args": {"path": "D:/x/app.js"}, "risk": "WRITE"}},
            {"tip": "ARAC_CAGRILDI", "veri": {"arac": "ekip_mesaj", "args": {"kime": "b"}, "risk": "WRITE_HAFIF",
                                              "masa": "istisare"}},
            {"tip": "MODEL_GECIS", "veri": {"eski": "a", "yeni": "b", "sebep": "limit"}},
            {"tip": "ONAY_GEREKLI", "veri": {"istek": "x"}},
            {"tip": "YANIT_PARCASI", "veri": {"metin": "x"}},
        ]
        dosya.write_text("\n".join(json.dumps(s) for s in satirlar) + "\nbozuk satir\n", encoding="utf-8")

        class Oturum:
            olaylar: list = []

            def yayinla(self, o):
                self.olaylar.append(o)
        o = Oturum()
        isci = {"tarif": {"olaylar": str(dosya), "ad": "giris"}, "okunan": 0}
        ekip._olaylari_aktar(isci, o)
        tipler = [x.tip for x in o.olaylar]
        dogrula(tipler == [OlayTipi.ADIM_BASLADI, OlayTipi.OLCUM, OlayTipi.ARAC_CAGRILDI, OlayTipi.ARAC_CAGRILDI,
                           OlayTipi.MODEL_GECIS],
                f"ADIM_BASLADI, OLCUM, MODEL_GECIS aktarildi; onay/yanit aktarilmadi ({[t.name for t in tipler]})")
        dogrula(all(x.veri.get("ajan") == "giris" for x in o.olaylar), "hepsi ajan etiketli")
        dogrula(o.olaylar[2].veri["masa"] == "kod" and o.olaylar[3].veri["masa"] == "istisare",
                "masa: yoksa eklendi, varsa korundu")
        ekip._olaylari_aktar(isci, o)
        dogrula(len(o.olaylar) == 5, "ikinci okumada tekrar yok")

        print("\n6) Isci olay dosyasinda args sozluk kalir, uzun metin kisalir")
        v = ekip._duz_deger({"path": "a.md", "content": "x" * 5000, "n": 3, "l": [1, 2]})
        dogrula(v["path"] == "a.md" and len(v["content"]) == 300 and v["n"] == 3 and v["l"] == "[1, 2]", "args sozlugu duz ve kisa")
        dogrula(json.loads(json.dumps(v)) == v, "JSON'a yazilabilir")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("\n7) Ana surecte arac_cagrildi masa tasir (vekil_v0 tek yardimcidan)")
    kaynak = (Path(ekip.__file__).parent / "vekil_v0.py").read_text(encoding="utf-8")
    dogrula("OlayTipi.ARAC_CAGRILDI, ofis.masa_ekle(" in kaynak, "vekil_v0 ARAC_CAGRILDI -> ofis.masa_ekle")
    dogrula(isinstance(Olay(OlayTipi.EKIP_MESAJ, {"rol": "planlayici"}), Olay), "rol olayi kurulabilir")

    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
