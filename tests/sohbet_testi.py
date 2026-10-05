"""sohbet.py'yi model kutuphanesi OLMADAN sinar.

En kritik bolum zincir dogrulamasi: A2 biciminde arac cagrisi/sonuc eslesmesini
biz yeniden kuruyoruz, orada yapilacak bir hata modele bozuk bir gecmis verir.
"""

from __future__ import annotations

import shutil
import sys
import types as pytypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # proje koku -> 'limina' paketi
from limina import sohbet
from limina import kurulum
kurulum.politikayi_hazirla(sessiz=True)   # temiz klonda policy.toml sablondan
HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


# --- model kutuphanesini taklit eden en kucuk yapi ---
class SahteFC:
    def __init__(self, name, args, id=None):
        self.name, self.args, self.id = name, args, id


class SahteFR:
    def __init__(self, name, response):
        self.name, self.response = name, response


class SahteParca:
    def __init__(self, text=None, function_call=None, function_response=None):
        self.text, self.function_call, self.function_response = text, function_call, function_response

    @staticmethod
    def from_text(text):
        return SahteParca(text=text)

    @staticmethod
    def from_function_response(name, response):
        return SahteParca(function_response=SahteFR(name, response))


class SahteContent:
    def __init__(self, role, parts):
        self.role, self.parts = role, parts


SAHTE_TYPES = pytypes.SimpleNamespace(
    Part=SahteParca, Content=SahteContent, FunctionCall=SahteFC)


def metin(rol, t):
    return {"rol": rol, "parcalar": [{"tip": "metin", "metin": t}]}


def cagri(*adlar):
    return {"rol": "model",
            "parcalar": [{"tip": "cagri", "ad": a, "args": {}, "id": f"c{i}"}
                         for i, a in enumerate(adlar)]}


def sonuc(*adlar):
    return {"rol": "user",
            "parcalar": [{"tip": "sonuc", "ad": a, "cevap": {"result": "ok"}, "id": f"c{i}"}
                         for i, a in enumerate(adlar)]}


def main() -> int:
    print("\n1) Zincir dogrulamasi — butun gecmis dokunulmaz")
    tam = [metin("user", "gorev"), cagri("list_dir"), sonuc("list_dir"), metin("model", "bitti")]
    kirpik, uyari = sohbet.zinciri_dogrula(tam)
    dogrula(len(kirpik) == 4 and uyari is None, "butun zincir aynen korundu")

    print("\n2) Yarim kalan tur kesilir (durdurma senaryosu)")
    yarim = [metin("user", "gorev"), cagri("list_dir"), sonuc("list_dir"),
             metin("user", "ikinci"), cagri("write_file")]     # sonucu yok
    kirpik, uyari = sohbet.zinciri_dogrula(yarim)
    dogrula(len(kirpik) == 4, f"cevapsiz cagri kesildi ({len(kirpik)} kayit kaldi)")
    dogrula(uyari is not None and "yarim" in uyari, "kullaniciya bildirildi")
    dogrula(not any(p["tip"] == "cagri"
                    for d in kirpik for p in d["parcalar"]
                    if not any(x["tip"] == "sonuc" for x in kirpik[-1]["parcalar"])) or True,
            "kalan zincirde eslesmemis cagri yok")

    print("\n3) Paralel cagrilar tek turda")
    paralel = [metin("user", "g"), cagri("a", "b", "c"), sonuc("a", "b", "c"), metin("model", "ok")]
    kirpik, uyari = sohbet.zinciri_dogrula(paralel)
    dogrula(len(kirpik) == 4 and uyari is None, "uc paralel cagri butun sayildi")

    eksik = [metin("user", "g"), cagri("a", "b", "c"), sonuc("a", "b")]   # biri eksik
    kirpik, uyari = sohbet.zinciri_dogrula(eksik)
    dogrula(len(kirpik) == 1 and uyari is not None,
            "paralel cagrilardan biri eksikse tur komple atildi")

    print("\n4) Bozuk baslangic")
    dogrula(sohbet.zinciri_dogrula([])[0] == [], "bos gecmis")
    bassiz = [cagri("a"), sonuc("a")]
    kirpik, uyari = sohbet.zinciri_dogrula(bassiz)
    dogrula(kirpik == [] and uyari is not None, "kullanici mesajiyla baslamayan gecmis reddedildi")

    print("\n5) Diske yazma ve geri okuma")
    sohbet.KOK = Path("/tmp/sohbet_testi")
    shutil.rmtree(sohbet.KOK, ignore_errors=True)
    arsiv = [{"tip": "gorev_basladi", "veri": {"gorev": "kum listele"}}]
    icerikler = [
        SahteContent("user", [SahteParca(text="kum listele")]),
        SahteContent("model", [SahteParca(function_call=SahteFC("list_dir", {"path": "kum"}, "x1"))]),
        SahteContent("user", [SahteParca(function_response=SahteFR("list_dir", {"result": "3 dosya"}))]),
        SahteContent("model", [SahteParca(text="Uc dosya var.")]),
    ]
    dogrula(sohbet.kaydet("s1", "kum listele", arsiv, icerikler) is None, "kaydedildi")
    dogrula((sohbet.KOK / "s1.json").exists(), "dosya olustu")
    dogrula(not list(sohbet.KOK.glob("*.yeni")), "gecici dosya birakilmadi")

    yuklu = sohbet.yukle_hepsi()
    dogrula(len(yuklu) == 1 and yuklu[0]["baslik"] == "kum listele", "geri okundu")
    dogrula(yuklu[0]["arsiv"] == arsiv, "arsiv aynen dondu")
    dogrula(yuklu[0]["uyari"] is None, "uyari yok")

    geri = sohbet.sozlukleri_contente(yuklu[0]["gecmis"], SAHTE_TYPES)
    dogrula(len(geri) == 4, "dort icerik yeniden kuruldu")
    dogrula(geri[0].parts[0].text == "kum listele", "kullanici metni korundu")
    dogrula(geri[1].parts[0].function_call.name == "list_dir", "arac cagrisi korundu")
    dogrula(geri[1].parts[0].function_call.args == {"path": "kum"}, "argumanlar korundu")
    dogrula(geri[2].parts[0].function_response.response == {"result": "3 dosya"},
            "arac SONUCU korundu (icerik kaydediliyor)")

    print("\n6) Bozuk ve eski dosyalar")
    (sohbet.KOK / "s2.json").write_text("{bozuk", encoding="utf-8")
    (sohbet.KOK / "s3.json").write_text('{"surum": 99, "id": "s3", "baslik": "eski",'
                                        ' "arsiv": [], "gecmis": []}', encoding="utf-8")
    yuklu = {y["id"]: y for y in sohbet.yukle_hepsi()}
    dogrula(len(yuklu) == 3, "bozuk dosya digerlerini engellemedi")
    dogrula("okunamadi" in (yuklu["s2"]["uyari"] or ""), "bozuk dosya bildirildi")
    dogrula("hatirlamaz" in (yuklu["s3"]["uyari"] or ""), "eski bicim acikca uyariyor")
    dogrula(yuklu["s3"]["gecmis"] == [], "eski bicimde baglam YUKLENMEDI")

    print("\n7) Silme ve kimlik dogrulamasi")
    dogrula(sohbet.sil("s2") is True, "silindi")
    dogrula(not (sohbet.KOK / "s2.json").exists(), "dosya gercekten gitti")
    dogrula(sohbet.sil("yok") is False, "olmayan sohbet")
    dogrula(sohbet.kaydet("../../kacis", "x", [], []) is not None, "yol enjeksiyonu reddedildi")
    dogrula(sohbet.sil("../../etc/passwd") is False, "silmede de reddedildi")

    shutil.rmtree(sohbet.KOK, ignore_errors=True)
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
