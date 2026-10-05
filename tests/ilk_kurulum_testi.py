"""ilk_kurulum_testi.py — klasor yapisi kullanicinin: calisma klasoru zorunlu
degil; ilk kurulum ekraninin arka ucu (ayarlar.kurulum_*).

Gercek policy.toml'a, gercek ev klasorune ve config/arayuz.toml'a DOKUNULMAZ:
hepsi gecici klasore yonlendirilir.

    python tests/ilk_kurulum_testi.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_GECICI = Path(tempfile.mkdtemp(prefix="limina_kurulum_"))
os.environ["LIMINA_VEKIL_KOK"] = str(_GECICI / ".vekil")   # journal.INEN de buraya

from limina import KAYNAK_KOK, ayarlar, ceviri, kurulum  # noqa: E402
from limina.gate import ALLOW, Politika  # noqa: E402

ceviri.dil_ayarla("tr")
HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


def ortam() -> Path:
    """Sablondan (policy.example.toml) gecici bir kurulum: ilk acilisin aynisi."""
    kok = Path(tempfile.mkdtemp(prefix="proje_", dir=_GECICI))
    ev = Path(tempfile.mkdtemp(prefix="ev_", dir=_GECICI))
    for ad in ("Downloads", "Desktop", "Documents"):
        (ev / ad).mkdir()
    calisma = ev / "Limina"
    metin = (KAYNAK_KOK / "policy.example.toml").read_text(encoding="utf-8")
    metin = (metin.replace("{PROJE}", kok.as_posix()).replace("{EV}", ev.as_posix())
                  .replace("{CALISMA}", calisma.as_posix()))
    # MCP sunucusu testte baslatilmaz; kurulumla ilgisi yok.
    metin = metin.replace('[mcp.converter]\nkomut = ["python", "Donusturucu/server.py"]', "")
    (kok / "policy.toml").write_text(metin, encoding="utf-8")
    calisma.mkdir()
    (ev / ".vekil" / "indirilen").mkdir(parents=True)
    from limina import journal
    journal.INEN = ev / ".vekil" / "indirilen"   # sablondaki {EV}/.vekil/indirilen ile ayni
    ayarlar.KOK = kok
    ayarlar.POLICY = kok / "policy.toml"
    ayarlar.POLICY_YEDEK = kok / "policy.toml.yedek"
    ayarlar.ARAYUZ_YOL = kok / "config" / "arayuz.toml"
    ayarlar.CALISMA_VARSAYILAN = calisma
    ayarlar._ev = lambda: ev
    return ev


def main() -> int:
    print("\n1) Sablon: kum yok, calisma klasoru yer tutucusu")
    sablon = (KAYNAK_KOK / "policy.example.toml").read_text(encoding="utf-8")
    dogrula("{PROJE}/kum" not in sablon and "{CALISMA}" in sablon, "sablonda proje ici kum yok, {CALISMA} var")
    dogrula(kurulum.CALISMA == Path.home() / "Limina", "varsayilan calisma klasoru ~/Limina")
    dogrula("{CALISMA}" not in kurulum._doldur("{CALISMA}"), "kurulum yer tutucuyu dolduruyor")

    print("\n2) Calisma klasoru degistirilir: her yer (okuma, yazma, yerel kok, profiller) tasinir")
    ev = ortam()
    pol = Politika(ayarlar.POLICY)
    dogrula(pol.calisma == (ev / "Limina").resolve(), "baslangic calisma klasoru ~/Limina")
    dogrula(pol.profiller["gozetimsiz"]["yazma_koklari"] == [(ev / "Limina").resolve()],
            "profil calisma klasorunu kapsiyor")
    yeni = ev / "Projelerim"; yeni.mkdir()
    dogrula(ayarlar.calisma_klasoru_degistir(str(yeni)) is None, "baska klasor secildi")
    pol = Politika(ayarlar.POLICY)
    metin = ayarlar.POLICY.read_text(encoding="utf-8")
    dogrula(pol.calisma == yeni.resolve() and yeni.resolve() in pol.okuma, "yeni klasor okuma+yazma koku")
    dogrula((ev / "Limina").resolve() not in pol.okuma + pol.yazma, "eski klasor hicbir kokte kalmadi")
    dogrula(pol.profiller["gozetimsiz"]["yazma_koklari"] == [yeni.resolve()]
            and pol.profiller["eval_testi"]["yazma_koklari"] == [yeni.resolve()],
            "gorev profilleri de yeni klasore tasindi")
    dogrula(str(yeni.resolve()) in tomllib.loads(metin)["browser"]["izinli_yerel_kokler"],
            "yerel dosya acma koku de tasindi")
    dogrula("# Ajanın okuyabileceği klasörler" in metin, "yorumlar korundu")
    dogrula(pol.karar("write_file", {"path": str(yeni / "a.txt"), "content": "x"},
                      profil="gozetimsiz").sonuc == ALLOW, "profil yeni klasorde calisiyor")

    print("\n3) Calisma klasoru ZORUNLU DEGIL")
    dogrula(ayarlar.calisma_klasoru_degistir("") is None, "calisma klasoru kaldirildi (bos yol)")
    pol = Politika(ayarlar.POLICY)
    dogrula(pol.calisma is None, "calisma klasoru yok (indirme klasoru calisma sayilmaz)")
    dogrula(yeni.resolve() not in pol.okuma, "okuma kokunden de cikti")
    dogrula(pol.profiller["gozetimsiz"]["yazma_koklari"] == [], "profil bos kapsamla yuklendi (patlamadi)")
    dogrula(yeni.is_dir(), "klasorun kendisine dokunulmadi")
    dogrula(ayarlar.calisma_klasoru_degistir(str(ev / "Limina")) is None, "sonradan yeniden eklendi")
    pol = Politika(ayarlar.POLICY)
    dogrula(pol.calisma == (ev / "Limina").resolve() and (ev / "Limina").resolve() in pol.okuma,
            "geri eklenen klasor okuma+yazma")
    dogrula(ayarlar.calisma_klasoru_degistir(str(ev / "olmayan")) is not None, "olmayan klasor reddedildi")
    dogrula(ayarlar.calisma_klasoru_degistir(str(ayarlar.KOK)) is not None,
            "proje (kod) koku calisma klasoru olamaz")

    print("\n4) Yazma kokunu Ayarlar'dan silmek artik geri alinmiyor (profil kilitlemiyor)")
    hata = ayarlar.kok_sil("yazma", str(ev / "Limina"))
    dogrula(hata is None, f"sablondaki (ileri egik cizgili) yazma koku panelden silindi: {hata}")
    dogrula(Politika(ayarlar.POLICY).calisma is None, "silindi")

    print("\n5) Ilk kurulum: durum + uygula")
    ev = ortam()
    d = ayarlar.kurulum_durumu()
    dogrula(d["ok"] and d["gerekli"], "yeni kurulumda ekran gerekli")
    dogrula(d["dil"] == "en", "varsayilan dil Ingilizce")
    dogrula(d["calisma"] == str((ev / "Limina").resolve()), "calisma klasoru gosterildi")
    ek = {k["ad"]: k["secili"] for k in d["ek_klasorler"]}
    dogrula(ek == {"Downloads": True, "Desktop": True, "Documents": False}, f"ek okuma klasorleri: {ek}")
    paket = {p["ad"]: p["acik"] for p in d["paketler"]}
    dogrula("tarayici" in paket and "ekip" not in paket, f"secilebilir paketler (gizli yok): {sorted(paket)}")
    (ev / "Limina" / ".gitkeep").unlink(missing_ok=True)
    hatalar = ayarlar.kurulum_uygula({
        "dil": "tr", "tema": "acik", "ekip_gorunumu": "kart",
        "calisma": {"tur": "yok"},
        "ek_klasorler": {"Downloads": False, "Desktop": True, "Documents": True},
        "paketler": {"tarayici": False},
    })
    dogrula(hatalar == [], f"uygulandi: {hatalar}")
    a = ayarlar.arayuz_oku()
    dogrula(a["genel"]["dil"] == "tr" and a["gorunum"]["tema"] == "acik"
            and a["gorunum"]["ekip_gorunumu"] == "kart", "dil/tema/ekip gorunumu yazildi")
    dogrula(a["genel"]["kurulum_tamam"] and not ayarlar.kurulum_gerekli(), "kurulum tamam isaretlendi")
    pol = Politika(ayarlar.POLICY)
    dogrula(pol.calisma is None, "calisma klasoru yok secildi")
    dogrula(not (ev / "Limina").exists(), "kendiliginden acilmis BOS varsayilan klasor kaldirildi")
    dogrula((ev / "Downloads").resolve() not in pol.okuma and (ev / "Documents").resolve() in pol.okuma
            and (ev / "Desktop").resolve() in pol.okuma, "ek okuma klasorleri secime gore")
    dogrula("tarayici" in pol.kaldirilan, "tarayici paketi kapatildi")

    print("\n6) Ilk kurulum: ozel klasor; dolu varsayilan klasor silinmez")
    ev = ortam()
    (ev / "Limina" / "notum.txt").write_text("x", encoding="utf-8")
    ozel = ev / "Isler"; ozel.mkdir()
    hatalar = ayarlar.kurulum_uygula({"calisma": {"tur": "ozel", "yol": str(ozel)}})
    dogrula(hatalar == [] and Politika(ayarlar.POLICY).calisma == ozel.resolve(), f"ozel klasor: {hatalar}")
    dogrula((ev / "Limina" / "notum.txt").exists(), "icinde dosya olan eski klasore dokunulmadi")
    hatalar = ayarlar.kurulum_uygula({"calisma": {"tur": "ozel", "yol": ""}})
    dogrula(hatalar != [] and ayarlar.arayuz_oku()["genel"]["kurulum_tamam"],
            "secilmemis ozel klasor hata verir ama kurulum kilitlenmez")
    hatalar = ayarlar.kurulum_uygula({"calisma": {"tur": "varsayilan"}})
    dogrula(hatalar == [] and Politika(ayarlar.POLICY).calisma == (ev / "Limina").resolve(),
            "varsayilana geri donuldu")

    print("\n7) Mevcut kurulumda kurulum.politikayi_hazirla klasor ACMAZ")
    eski = (kurulum.POLICY, kurulum.PERSONA)
    kurulum.POLICY, kurulum.PERSONA = ayarlar.POLICY, ayarlar.KOK / "config" / "persona.md"
    kurulum.PERSONA.parent.mkdir(parents=True, exist_ok=True); kurulum.PERSONA.write_text("", encoding="utf-8")
    try:
        kurulum.politikayi_hazirla(sessiz=True)
        dogrula(not (Path.home() / "Limina").exists() or (Path.home() / "Limina").stat().st_mtime < _BASLANGIC,
                "mevcut policy.toml varken ~/Limina olusturulmadi")
    finally:
        kurulum.POLICY, kurulum.PERSONA = eski

    print(f"\nSonuc: {'HEPSI GECTI' if HATA == 0 else f'{HATA} KALDI'}")
    return 1 if HATA else 0


if __name__ == "__main__":
    import time
    _BASLANGIC = time.time()
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(_GECICI, ignore_errors=True)
