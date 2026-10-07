# ekip_testi.py — coklu ajan temeli: adli anahtar yuvalari, [ajanlar.*], model.kur(ajan=)
#
#   python tests/ekip_testi.py
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pevrai import kurulum
kurulum.politikayi_hazirla(sessiz=True)
from pevrai import anahtar, ayarlar, ceviri, model
from pevrai.gate import Politika

ceviri.dil_ayarla("tr")
HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


def main() -> int:
    d = Path(tempfile.mkdtemp(prefix="pevrai_ekip_"))
    eski_dosya, eski_dizin, eski_kr = anahtar.DOSYA, anahtar.YUVA_DIZINI, anahtar._keyring
    eski_ortam = {k: os.environ.pop(k, None) for k in anahtar.ORTAM_DEGISKENI.values()}
    anahtar.DOSYA, anahtar.YUVA_DIZINI, anahtar._keyring = d / "credentials.json", d / "yuvalar.json", (lambda: None)
    try:
        print("\n1) Adli anahtar yuvalari")
        dogrula(anahtar.yuvalar("gemini") == [], "baslangicta yuva yok")
        dogrula(anahtar.yaz("gemini", "AIzaVarsayilan12345") is None, "varsayilan yuva yazildi")
        dogrula(anahtar.yaz("gemini", "AIzaIkinciHesap12345", yuva="is") is None, "adli yuva 'is' yazildi")
        dogrula(anahtar.yaz("gemini", "AIzaX", yuva="bosluk lu") is not None, "gecersiz yuva adi reddedildi")
        dogrula(anahtar.yuvalar("gemini") == ["is"], f"yuva dizini: {anahtar.yuvalar('gemini')}")
        dogrula(anahtar.oku("gemini") == "AIzaVarsayilan12345" and anahtar.oku("gemini", "is") == "AIzaIkinciHesap12345",
                "yuvalar birbirine karismiyor")
        dogrula(anahtar.kimlik("gemini", "is") == "gemini#is" and anahtar.kimlik("gemini", "") == "gemini",
                "depo kimligi: saglayici#yuva; varsayilan yuva eski ad (mevcut kurulum degismez)")
        os.environ["GOOGLE_API_KEY"] = "AIzaOrtam1234567"
        dogrula(anahtar.oku("gemini", "is") == "AIzaIkinciHesap12345" and anahtar.oku("gemini", "yok") is None,
                "adli yuvada ortam degiskeni yedegi YOK (ortam varsayilan yuvaya ait)")
        os.environ.pop("GOOGLE_API_KEY")
        dogrula(anahtar.yaz("gemini", "", yuva="is") is None and anahtar.yuvalar("gemini") == []
                and anahtar.oku("gemini", "is") is None, "yuva silinince dizinden de dustu")
        dogrula(anahtar.maskele(anahtar.oku("gemini")) == "••••••••2345", "maske")

        print("\n2) [ajanlar.<ad>] policy.toml")
        anahtar.yaz("openai", "sk-ikinci-hesap-1234", yuva="ikinci")
        pol_yol = d / "policy.toml"
        pol_yol.write_text(f"""
[filesystem]
okuma_koklari = ["{d.as_posix()}"]
yazma_koklari = ["{(d / 'kum').as_posix()}"]
[model]
saglayici = "gemini"
varsayilan = "gemini-3.5-flash-lite"
[araclar]
write_file = "WRITE"
[ajanlar.yazar]
saglayici = "gemini"
model = "gemini-3.5-flash-lite"
rol = "Metinleri yazar."
[ajanlar.elestirmen]
saglayici = "openai"
model = "gpt-5-mini"
anahtar_yuvasi = "ikinci"
""", encoding="utf-8")
        pol = Politika(pol_yol)
        dogrula(set(pol.ajanlar) == {"yazar", "elestirmen"}, f"iki ajan yuklendi: {sorted(pol.ajanlar)}")
        dogrula(pol.ajanlar["elestirmen"]["anahtar_yuvasi"] == "ikinci" and pol.ajanlar["yazar"]["anahtar_yuvasi"] == "",
                "yuva alani okundu; bos = varsayilan")
        for kotu, beklenen in [('[ajanlar.x]\nsaglayici = "uydurma"\n', "taninmiyor"),
                               ('[ajanlar.x]\nsaglayici = "gemini"\nsifre = "abc"\n', "bilinmeyen alan"),
                               ('[ajanlar."kotu ad"]\nsaglayici = "gemini"\n', "ad"),
                               ('[ajanlar.x]\nmodel = "a b"\n', "gecersiz")]:
            (d / "kotu.toml").write_text(pol_yol.read_text(encoding="utf-8") + "\n" + kotu, encoding="utf-8")
            try:
                Politika(d / "kotu.toml"); dogrula(False, f"bozuk tanim kabul edildi: {kotu[:30]!r}")
            except ValueError as e:
                dogrula(beklenen in str(e), f"fail-closed: {str(e)[:70]}")

        print("\n3) model.kur(ajan=...)")
        with patch.dict(os.environ, {}, clear=False):
            s1 = model.kur(pol, ajan=pol.ajanlar["yazar"])
            s2 = model.kur(pol, ajan=pol.ajanlar["elestirmen"])
            dogrula(type(s1).__name__ == "Gemini" and type(s2).__name__ == "OpenAIUyumlu", "iki farkli saglayici ayni anda kuruldu")
            dogrula(model.kur(pol, ajan=pol.ajanlar["yazar"]) is s1, "ayni tanim -> onbellekten ayni istemci")
            dogrula(model.kur(pol) is s1, "ajan=None -> [model] ayarlari (varsayilan yuva, gemini) = yazar ile ayni istemci")
            try:
                model.kur(pol, ajan={"saglayici": "openai", "anahtar_yuvasi": "yok"})
                dogrula(False, "anahtarsiz yuva kabul edildi")
            except model.ModelHatasi as e:
                dogrula(e.code == 401 and "'yok' yuvasinda" in e.mesaj, f"anahtarsiz yuva -> 401, yuva adi mesajda: {e.mesaj[:60]}")

        print("\n4) ayarlar.ajan_yaz / ajan_sil / ajanlar_oku")
        # POLICY_YEDEK de gecici: yoksa _guvenli_yaz kullanicinin gercek yedegini ezer.
        with patch.object(ayarlar, "POLICY", pol_yol), patch.object(ayarlar, "POLICY_YEDEK", d / "policy.toml.yedek"), \
                patch.object(ayarlar, "KOK", d):
            dogrula(ayarlar.ajan_yaz("arastirmaci", "openai", "gpt-5-mini", "", "Kaynak bulur.", "https://openrouter.ai/api/v1") is None,
                    "yeni ajan yazildi")
            p2 = Politika(pol_yol)
            dogrula(p2.ajanlar["arastirmaci"]["taban_url"] == "https://openrouter.ai/api/v1" and p2.ajanlar["arastirmaci"]["rol"] == "Kaynak bulur.",
                    "geri okundu")
            dogrula(ayarlar.ajan_yaz("arastirmaci", "openai", "gpt-5-mini", "", "", "") is None
                    and Politika(pol_yol).ajanlar["arastirmaci"]["rol"] == "", "guncelleme: bos rol satiri siler")
            dogrula(ayarlar.ajan_yaz("x", "gemini", "", "olmayan_yuva") is not None, "tanimsiz yuva reddedildi")
            dogrula(ayarlar.ajan_yaz("kötü ad", "gemini") is not None, "gecersiz ad reddedildi")
            liste = ayarlar.ajanlar_oku()
            dogrula({a["ad"] for a in liste} == {"yazar", "elestirmen", "arastirmaci"} and
                    all("anahtar" not in k or k in ("anahtar_var", "anahtar_kaynak", "anahtar_yuvasi") for a in liste for k in a),
                    "panel listesi anahtar tasimiyor")
            dogrula(next(a for a in liste if a["ad"] == "elestirmen")["anahtar_var"], "elestirmen yuvasinda anahtar var")
            dogrula(ayarlar.ajan_sil("arastirmaci") is None and "arastirmaci" not in Politika(pol_yol).ajanlar, "ajan silindi")
            dogrula(ayarlar.ajan_sil("arastirmaci") is not None, "olmayan ajan silinemez")
            dogrula(Politika(pol_yol).ajanlar["yazar"]["rol"] == "Metinleri yazar.", "diger tanimlar dokunulmadi")

        print("\n5) Ajan -> API baglantisi (yeni bicim) ve eski tanimlarin okunmasi")
        from pevrai import model_zinciri
        metin = pol_yol.read_text(encoding="utf-8").replace(
            'varsayilan = "gemini-3.5-flash-lite"\n', 'varsayilan = "gemini-3.5-flash-lite"\nzincir = ["is", "ev"]\n', 1)
        metin += ('\n[baglantilar.is]\nad = "Is hesabi"\nsaglayici = "openai"\ntaban_url = "https://api.ornek.com/v1"\n'
                  'anahtar_yuvasi = "ikinci"\nmodeller = ["m-a", "m-b", "m-c"]\n'
                  '[baglantilar.ev]\nad = "Ev"\nsaglayici = "gemini"\nmodeller = ["g-1"]\n')
        pol_yol.write_text(metin, encoding="utf-8")
        with patch.object(ayarlar, "POLICY", pol_yol), patch.object(ayarlar, "POLICY_YEDEK", d / "policy.toml.yedek"), \
                patch.object(ayarlar, "KOK", d):
            dogrula(ayarlar.ajan_yaz("arastirmaci", baglanti="is", model="m-b", rol="Kaynak bulur.", renk="#AABBCC") is None,
                    "baglantili ajan yazildi")
            p3 = Politika(pol_yol)
            a = p3.ajanlar["arastirmaci"]
            dogrula(a["baglanti"] == "is" and a["saglayici"] == "openai" and a["taban_url"] == "https://api.ornek.com/v1"
                    and a["anahtar_yuvasi"] == "ikinci" and a["model"] == "m-b" and a["renk"] == "#aabbcc",
                    "saglayici/adres/yuva baglantidan geldi")
            dogrula(p3.ajanlar["elestirmen"]["baglanti"] == "" and p3.ajanlar["elestirmen"]["anahtar_yuvasi"] == "ikinci",
                    "eski bicim ajan aynen okunuyor")
            ham = pol_yol.read_text(encoding="utf-8")
            bolum = ham[ham.index("[ajanlar.arastirmaci]"):].split("\n[", 1)[0]
            dogrula("saglayici" not in bolum and "anahtar_yuvasi" not in bolum and 'baglanti = "is"' in bolum,
                    "yeni bicimde eski alanlar yazilmadi")
            # Limit sirasi: ajanin modeli, ayni baglantinin digerleri, sonra genel zincir
            z = [h.anahtar for h in model_zinciri.zincir(p3, ajan=a, ajan_adi="arastirmaci")]
            dogrula(z == ["is|m-b", "is|m-a", "is|m-c", "ev|g-1"], f"kendi modeli > kendi baglantisi > genel ({z})")
            z = [h.anahtar for h in model_zinciri.zincir(p3, ajan=p3.ajanlar["yazar"], ajan_adi="yazar")]
            dogrula(z == ["|gemini-3.5-flash-lite"], f"eski bicim ajan: tek halka, davranis degismedi ({z})")
            dogrula(ayarlar.ajan_yaz("x", baglanti="yok") is not None, "tanimsiz baglanti reddedildi")
            dogrula(ayarlar.ajan_yaz("x", baglanti="is", renk="kirmizi") is not None, "bozuk renk reddedildi")
            hata, _ = ayarlar.baglanti_sil("is")
            dogrula(hata is not None and "arastirmaci" in hata and "is" in Politika(pol_yol).baglantilar,
                    f"ajanin kullandigi baglanti silinemez: {str(hata)[:60]}")
            dogrula(ayarlar.ajan_yaz("arastirmaci", "gemini", "", "", "", "") is None
                    and Politika(pol_yol).ajanlar["arastirmaci"]["baglanti"] == "", "eski bicime donus: baglanti silindi")
            dogrula(ayarlar.ajan_yaz("arastirmaci", baglanti="ev") is None
                    and Politika(pol_yol).ajanlar["arastirmaci"]["model"] == "g-1", "model bos -> baglantinin ilk modeli")
            liste = {x["ad"]: x for x in ayarlar.ajanlar_oku()}
            dogrula(liste["arastirmaci"]["baglanti_ad"] == "Ev" and liste["arastirmaci"]["renk"].startswith("#")
                    and isinstance(liste["arastirmaci"]["gorunum"], int), "panel listesi: baglanti adi, renk, gorunum")
        for kotu, beklenen in [('[ajanlar.y]\nbaglanti = "yok"\n', "tanimli degil"),
                               ('[ajanlar.y]\nbaglanti = "is"\nsaglayici = "gemini"\n', "baglantidan gelir"),
                               ('[ajanlar.y]\nbaglanti = "is"\nrenk = "red"\n', "renk"),
                               ('[ajanlar.y]\nbaglanti = "is"\ngorunum = 12\n', "gorunum")]:
            (d / "kotu.toml").write_text(pol_yol.read_text(encoding="utf-8") + "\n" + kotu, encoding="utf-8")
            try:
                Politika(d / "kotu.toml"); dogrula(False, f"bozuk tanim kabul edildi: {kotu[:30]!r}")
            except ValueError as e:
                dogrula(beklenen in str(e), f"fail-closed: {str(e)[:70]}")
        # [baglantilar] yokken 'ana' = eski [model] ayari
        (d / "ana.toml").write_text('[filesystem]\nokuma_koklari = []\nyazma_koklari = []\n[model]\nsaglayici = "gemini"\n'
                                    'varsayilan = "g-hizli"\nguclu = "g-guclu"\n[ajanlar.z]\nbaglanti = "ana"\n', encoding="utf-8")
        pa = Politika(d / "ana.toml")
        dogrula(pa.ajanlar["z"]["model"] == "g-hizli"
                and [h.model for h in model_zinciri.zincir(pa, ajan=pa.ajanlar["z"])] == ["g-hizli", "g-guclu"],
                "baglantisiz kurulumda 'ana' baglantisi = eski [model]")
    finally:
        anahtar.DOSYA, anahtar.YUVA_DIZINI, anahtar._keyring = eski_dosya, eski_dizin, eski_kr
        for k, v in eski_ortam.items():
            if v is not None:
                os.environ[k] = v
        shutil.rmtree(d, ignore_errors=True)
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
