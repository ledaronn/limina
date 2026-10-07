"""kayit_testi.py — arac kayit defteri (@arac) ve bildirimsel yol dogrulamasi.

Modelsiz. Sinanan seyler:
  1) Kayit defteri: her yerel arac tek bildirimden tablo/sema/yol modu/paket/
     panel bilgisi uretiyor; vekil_v0.ARAC_TABLOSU ve ARAC ayni kaynaktan.
  2) Kapi: yol dogrulamasi ada bagli degil, bildirime bagli — cok argumanli
     bir MCP araci policy.toml tablo bicimiyle bildirilince her argumani ayri
     denetleniyor; bildirimsiz MCP araci denetlenmiyor (bilinen bosluk, acik).
  3) ayarlar.arac_siniflandir(yollar=...) tablo bicimi yazar, geri okunur.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pevrai import kurulum
kurulum.politikayi_hazirla(sessiz=True)
from pevrai import ayarlar, gate

# Mesaj metinleri KAYNAK DILDE (Turkce) dogrulanir: ceviri.dil() normalde
# kullanicinin config/arayuz.toml ayarini okur, testin sonucu kisisel bir
# ayara bagli olamaz (Ingilizce secili bir makinede bu dosya kirilirdi).
from pevrai import ceviri as _ceviri
_ceviri.dil_ayarla("tr")
from pevrai.araclar import kayit
from pevrai.gate import ALLOW, ASK, DENY, Politika

HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


def bolum1_kayit() -> None:
    print("\n1) Kayit defteri")
    k = kayit.kayitlar()
    dogrula(set(k) >= {"list_dir", "read_file", "search", "degisiklik_gecmisi", "read_document",
                       "write_file", "move", "rename", "trash", "browser_open", "browser_read",
                       "browser_snapshot", "browser_click", "browser_fill", "browser_download"},
            f"15 yerlesik arac kayitli ({len(k)})")
    dogrula(kayit.paketler()["cekirdek"] == {"list_dir": "READ", "read_file": "READ", "search": "READ", "degisiklik_gecmisi": "READ"},
            "cekirdek paket kayit defterinden dogru")
    dogrula(kayit.yol_modlari()["move"] == {"path": "yaz", "dst": "yaz"} and "browser_open" not in kayit.yol_modlari(),
            "yol modlari: move iki yol, browser_open yolsuz")
    s = {x["name"]: x for x in kayit.semalar()}
    dogrula(s["write_file"]["parameters"]["required"] == ["path", "content"] and "ÜZERİNE" in s["write_file"]["description"],
            "sema ve model aciklamasi bildirimden")
    dogrula(kayit.bilgiler()["trash"][0] == "Çöpe taşıma", "panel bilgisi bildirimden")
    dogrula(kayit.okuyanlar() == ("list_dir", "search", "read_file", "read_document"), "okuyanlar sirasi sabit")

    from pevrai import vekil_v0, paketler
    dogrula(vekil_v0.ARAC_TABLOSU["write_file"] is k["write_file"].fn, "vekil_v0.ARAC_TABLOSU kayit defterinden")
    dogrula(any(x["name"] == "trash" for x in vekil_v0.ARAC), "vekil_v0.ARAC kayit defterinden")
    dogrula(paketler.YERLESIK["tarayici"]["araclar"]["browser_download"] == "DESTRUCTIVE", "paketler.YERLESIK kayit defterinden")
    dogrula(paketler.ARAC_BILGI["move"][0] == "Taşıma", "paketler.ARAC_BILGI kayit defterinden")
    dogrula(gate.YOL_BILDIRIMLERI["write_file"] == {"path": "yaz"} and gate.ARAC_YOL_MODU["converter.convert"] == "oku",
            "gate bildirimleri kayit defterinden + MCP varsayilani")

    # Ayni ad iki kez kaydedilemez, gecersiz risk/yol modu reddedilir
    try:
        kayit.arac(ad="list_dir", paket="x", risk="READ", baslik="", aciklama="", modele="")(lambda y, a: "")
        dogrula(False, "cift kayit reddedilmeli")
    except ValueError:
        dogrula(True, "ayni ad ikinci kez kaydedilemez")
    try:
        kayit.arac(ad="_deneme_x", paket="x", risk="SUPER", baslik="", aciklama="", modele="")(lambda y, a: "")
        dogrula(False, "gecersiz risk reddedilmeli")
    except ValueError:
        dogrula(True, "gecersiz risk reddedildi")
    try:
        kayit.arac(ad="_deneme_y", paket="x", risk="READ", baslik="", aciklama="", modele="", yollar={"p": "sil"})(lambda y, a: "")
        dogrula(False, "gecersiz yol modu reddedilmeli")
    except ValueError:
        dogrula(True, "gecersiz yol modu reddedildi")


POLITIKA_SABLON = '''
[filesystem]
okuma_koklari = ["{oku}"]
yazma_koklari = ["{yaz}"]
yasak_kaliplar = [".env"]
[model]
varsayilan = "m"
[mcp.sunucu]
komut = ["python", "x.py"]
[araclar]
read_file = "READ"
write_file = "WRITE"
move = "WRITE_HAFIF"
"converter.convert" = "WRITE"
"sunucu.kopyala" = {{ risk = "WRITE", yollar = {{ kaynak = "oku", hedef = "yaz" }} }}
"sunucu.bildirimsiz" = "WRITE"
'''


def bolum2_kapi() -> None:
    print("\n2) Kapi: bildirimsel yol dogrulamasi")
    d = Path(tempfile.mkdtemp(prefix="pevrai_kayit_"))
    oku, yaz = d / "oku", d / "yaz"
    oku.mkdir(); yaz.mkdir()
    (oku / "a.txt").write_text("x", encoding="utf-8")
    pol_dosya = d / "policy.toml"
    pol_dosya.write_text(POLITIKA_SABLON.format(oku=oku.as_posix(), yaz=yaz.as_posix()), encoding="utf-8")
    try:
        pol = Politika(pol_dosya)
        dogrula(pol.yol_bildirimleri.get("sunucu.kopyala") == {"kaynak": "oku", "hedef": "yaz"}
                and pol.araclar["sunucu.kopyala"] == "WRITE",
                "tablo bicimi okundu: risk + yollar")
        # MCP: her arguman kendi moduyla
        k = pol.karar("sunucu.kopyala", {"kaynak": str(oku / "a.txt"), "hedef": str(yaz / "b.txt")})
        dogrula(k.sonuc == ASK and k.yol == (oku / "a.txt").resolve(), f"MCP araci: iki yol da kok icinde -> ASK, birincil yol kaynak ({k.sonuc})")
        k = pol.karar("sunucu.kopyala", {"kaynak": str(oku / "a.txt"), "hedef": str(d / "disari.txt")})
        dogrula(k.sonuc == DENY and "hedef" in k.gerekce, f"MCP araci: ikinci arguman kok DISI -> DENY ({k.gerekce[:60]})")
        k = pol.karar("sunucu.kopyala", {"kaynak": str(yaz / "b.txt"), "hedef": str(yaz / "c.txt")})
        dogrula(k.sonuc == DENY, "MCP araci: 'oku' argumani yalnizca yazma kokunde -> DENY (okuma koku degil)")
        k = pol.karar("sunucu.kopyala", {"kaynak": str(oku / ".env"), "hedef": str(yaz / "c.txt")})
        dogrula(k.sonuc == DENY, "MCP araci: kara liste yol argumanina da uygulanir")
        # bildirimsiz MCP araci: yol denetlenmez (bilinen bosluk — panel uyarir)
        k = pol.karar("sunucu.bildirimsiz", {"path": str(d / "disari.txt")})
        dogrula(k.sonuc == ASK, "bildirimsiz MCP araci: yol denetlenmez (ASK) — panel bunu uyariyor")
        # yerlesik: move iki yol
        (yaz / "m.txt").write_text("x", encoding="utf-8")
        dogrula(pol.karar("move", {"path": str(yaz / "m.txt"), "dst": str(d / "disari.txt")}).sonuc == DENY, "move: dst kok disi -> DENY")
        dogrula(pol.karar("move", {"path": str(yaz / "m.txt"), "dst": str(yaz / "n.txt")}).sonuc == ALLOW, "move: iki yol kok icinde -> ALLOW (WRITE_HAFIF)")
        # converter: gate varsayilan bildirimi (eski policy.toml'lar duz satir tasir)
        dogrula(pol.karar("converter.convert", {"src": str(oku / "a.txt"), "dst_dir": str(d)}).sonuc == DENY, "converter: dst_dir kok disi -> DENY")
        dogrula(pol.karar("converter.convert", {"src": str(oku / "a.txt"), "dst_dir": str(yaz)}).sonuc == ASK, "converter: iki yol gecerli -> ASK")
        # bozuk tablo bicimi acilista reddedilir
        pol_dosya.write_text(POLITIKA_SABLON.format(oku=oku.as_posix(), yaz=yaz.as_posix()).replace('kaynak = "oku"', 'kaynak = "sil"'), encoding="utf-8")
        try:
            Politika(pol_dosya); dogrula(False, "gecersiz yol modu acilista reddedilmeli")
        except ValueError:
            dogrula(True, "gecersiz yol modu acilista reddedildi (fail-closed)")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def bolum3_ayarlar() -> None:
    print("\n3) ayarlar.arac_siniflandir(yollar=...)")
    d = Path(tempfile.mkdtemp(prefix="pevrai_kayit_ayar_"))
    eski = (ayarlar.KOK, ayarlar.POLICY, ayarlar.POLICY_YEDEK)
    ayarlar.KOK, ayarlar.POLICY, ayarlar.POLICY_YEDEK = d, d / "policy.toml", d / "policy.toml.yedek"
    try:
        (d / "kum").mkdir()
        ayarlar.POLICY.write_text(POLITIKA_SABLON.format(oku=(d / "kum").as_posix(), yaz=(d / "kum").as_posix()), encoding="utf-8")
        dogrula(ayarlar.arac_siniflandir("sunucu.oku_dosya", "READ", {"path": "oku"}) is None, "yollar ile siniflandirildi")
        pol = Politika(ayarlar.POLICY)
        dogrula(pol.araclar["sunucu.oku_dosya"] == "READ" and pol.yol_bildirimleri["sunucu.oku_dosya"] == {"path": "oku"},
                "tablo bicimi yazildi ve geri okundu")
        dogrula(ayarlar.arac_siniflandir("sunucu.oku_dosya", "READ", {"path": "sil"}) is not None, "gecersiz yol modu reddedildi")
        dogrula(ayarlar.arac_siniflandir("sunucu.oku_dosya", "READ", {"kötü ad": "oku"}) is not None, "gecersiz arguman adi reddedildi")
        dogrula(ayarlar.arac_siniflandir("sunucu.oku_dosya", "WRITE") is None, "yollarsiz yeniden siniflandirma duz satira doner")
        pol = Politika(ayarlar.POLICY)
        dogrula(pol.araclar["sunucu.oku_dosya"] == "WRITE" and "sunucu.oku_dosya" not in pol.yol_bildirimleri, "duz satir: bildirim yok")
        dogrula(ayarlar.arac_sinif_sil("sunucu.kopyala") is None and "sunucu.kopyala" not in Politika(ayarlar.POLICY).araclar,
                "tablo bicimli satir da silinebiliyor")
    finally:
        ayarlar.KOK, ayarlar.POLICY, ayarlar.POLICY_YEDEK = eski
        shutil.rmtree(d, ignore_errors=True)


def main() -> int:
    bolum1_kayit()
    bolum2_kapi()
    bolum3_ayarlar()
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
