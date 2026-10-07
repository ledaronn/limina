# acma_testi.py — open_file ve acma klasoru: degismezler.
#
# Ozelligin guvenligi UC degismeze dayanir; her biri burada ayri ayri
# saldiriya ugrar:
#   1. Acma klasoru ajanin yazabildigi hicbir yerle KESISEMEZ (icinde, disinda, esit).
#   2. Kisayolun HEDEFI ajanin yazabildigi bir yerde olamaz (kisayol -> kum/x.bat).
#   3. Klasor disindaki hicbir sey acilamaz; ad cozumlemesi klasore gore yapilir.
# Ayrica: .url reddi, zincir kisayol reddi, EXEC = her seferinde onay,
# kara liste, onay karti cumlesi gercek hedefi soyler, sistem talimati
# icerigi listeler. Gercek program BASLATILMAZ: os.startfile mock'lanir.
#
#   python tests/acma_testi.py
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pevrai import kurulum
kurulum.politikayi_hazirla(sessiz=True)
from pevrai import ceviri, PROJE_KOKU
from pevrai.araclar import acma
from pevrai.gate import ALLOW, ASK, DENY, Politika, acma_klasoru_ihlali
import pevrai.vekil_v0 as v

ceviri.dil_ayarla("tr")
HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


def not_dus(mesaj: str) -> None:
    print("  NOT    " + mesaj)


def _politika(d: Path, acma_klasoru: Path | None, yazma: list[Path]) -> Politika:
    """Gecici bir policy.toml: okuma/yazma kokleri ve [acma] klasor."""
    def toml_liste(yollar):
        return "[" + ", ".join(f'"{p.as_posix()}"' for p in yollar) + "]"
    metin = f"""
[filesystem]
okuma_koklari = {toml_liste([d])}
yazma_koklari = {toml_liste(yazma)}
yasak_kaliplar = ["*.pem", ".env", "*gizli*"]
[model]
varsayilan = "test-model"
[araclar]
open_file = "EXEC"
write_file = "WRITE"
[acma]
klasor = "{acma_klasoru.as_posix() if acma_klasoru else ''}"
"""
    yol = d / "policy.toml"
    yol.write_text(metin, encoding="utf-8")
    return Politika(yol)


def _kisayol(lnk: Path, hedef: Path, argumanlar: str = "") -> bool:
    """Gercek bir .lnk (WScript.Shell). PowerShell yoksa False."""
    betik = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
             f"$s.TargetPath='{hedef}';" + (f"$s.Arguments='{argumanlar}';" if argumanlar else "") + "$s.Save()")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", betik],
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0 and lnk.exists()
    except Exception:
        return False


def main() -> int:
    d = Path(tempfile.mkdtemp(prefix="pevrai_acma_"))
    try:
        kum = d / "kum"; kum.mkdir()
        klasor = d / "Kisayollar"; klasor.mkdir()
        (klasor / "rapor.pdf").write_bytes(b"%PDF-1.4 test")
        (klasor / "notlar.txt").write_text("x", encoding="utf-8")
        (klasor / "gizli_belge.pdf").write_bytes(b"%PDF")            # kara liste kalibi
        (klasor / "site.url").write_text("[InternetShortcut]\nURL=https://ornek.com\n", encoding="utf-8")
        (kum / "ajanin_dosyasi.txt").write_text("x", encoding="utf-8")

        print("\n1) Degismez 1: acma klasoru ajanin yazabildigi yerle kesisemez")
        dogrula(acma_klasoru_ihlali(klasor, [kum], d) is None, "ayri klasor: kabul")
        dogrula(acma_klasoru_ihlali(kum / "alt", [kum], d) is not None, "yazma kokunun ICINDE: red")
        dogrula(acma_klasoru_ihlali(kum, [kum], d) is not None, "yazma kokune ESIT: red")
        dogrula(acma_klasoru_ihlali(d, [kum], d) is not None, "yazma koku klasorun ICINDE (ust klasor): red")
        dogrula(acma_klasoru_ihlali(PROJE_KOKU / "pevrai" / "x", [], PROJE_KOKU) is not None, "kod paketinin icinde: red")
        dogrula(acma_klasoru_ihlali(PROJE_KOKU / "config", [], PROJE_KOKU) is not None, "config klasoru: red")
        dogrula(acma_klasoru_ihlali(PROJE_KOKU / "Kisayollar", [], PROJE_KOKU) is None, "proje kokunun yaninda (kod degil): kabul")
        pol_kotu = _politika(d, kum / "alt", [kum])
        dogrula(pol_kotu.acma_klasoru is None and pol_kotu.acma_hatasi, "policy.toml'da kesisen klasor -> YOK sayilir, neden kayitli")
        k = pol_kotu.karar("open_file", {"path": "rapor.pdf"})
        dogrula(k.sonuc == DENY and "kesişiyor" in k.gerekce, f"kesisen klasorle open_file DENY: {k.gerekce[:60]}")

        print("\n2) Degismez 3: klasor disi hicbir sey acilmaz; ad klasore gore cozulur")
        pol = _politika(d, klasor, [kum])
        dogrula(pol.acma_klasoru == klasor.resolve(), "klasor yuklendi")
        k = pol.karar("open_file", {"path": "rapor.pdf"})
        dogrula(k.sonuc == ASK and k.yol == (klasor / "rapor.pdf").resolve(), f"adla istek -> klasore cozuldu, EXEC=ASK ({k.sonuc})")
        dogrula(pol.karar("open_file", {"path": str(klasor / "rapor.pdf")}).sonuc == ASK, "tam yolla da ayni")
        dogrula(pol.karar("open_file", {"path": str(kum / "ajanin_dosyasi.txt")}).sonuc == DENY, "yazma kokundeki dosya: DENY")
        dogrula(pol.karar("open_file", {"path": str(d / "policy.toml")}).sonuc == DENY, "okuma kokunde ama acma klasoru disinda: DENY")
        dogrula(pol.karar("open_file", {"path": "../kum/ajanin_dosyasi.txt"}).sonuc == DENY, "..' ile disari: DENY")
        dogrula(pol.karar("open_file", {"path": "gizli_belge.pdf"}).sonuc == DENY, "kara liste kalibi klasor icinde bile DENY")
        dogrula(pol.karar("open_file", {"path": "C:x.txt"}).sonuc == DENY, "surucu-goreli yol: DENY")
        dogrula(pol.karar("write_file", {"path": str(klasor / "yeni.lnk"), "content": "x"}).sonuc == DENY,
                "ajan acma klasorune YAZAMAZ (yazma koku degil)")
        pol_bos = _politika(d, None, [kum])
        k = pol_bos.karar("open_file", {"path": "rapor.pdf"})
        dogrula(k.sonuc == DENY and "ayarlanmamış" in k.gerekce, "klasor ayarsiz: DENY + yol tarifi")

        print("\n3) Hedef cozumleme ve onay karti cumlesi")
        tur, acik, hata = acma.hedef_cozumle(klasor / "rapor.pdf", pol)
        dogrula(tur == "belge" and hata is None and "ilişkili" in acik, f"belge: {acik}")
        tur, acik, hata = acma.hedef_cozumle(klasor / "site.url", pol)
        dogrula(hata is not None and "internet" in hata, ".url reddedilir (site listesi bypass olmasin)")
        (klasor / "calistir.exe").write_bytes(b"MZ")
        tur, acik, hata = acma.hedef_cozumle(klasor / "calistir.exe", pol)
        dogrula(tur == "calistir" and "ÇALIŞTIRILACAK" in acik, "dogrudan .exe: kart buyuk harfle CALISTIRILACAK der")
        tur, acik, hata = acma.hedef_cozumle(klasor, pol)
        dogrula(tur == "klasor" and hata is None, "klasorun kendisi: Explorer")

        print("\n4) Kisayollar (gercek .lnk) — degismez 2")
        notepad = Path(os.environ.get("WINDIR", r"C:\Windows")) / "notepad.exe"
        if sys.platform == "win32" and notepad.exists() and _kisayol(klasor / "Not Defteri.lnk", notepad, "/A"):
            bilgi = acma.kisayol_hedefi(klasor / "Not Defteri.lnk")
            dogrula(bilgi and Path(bilgi["hedef"]).resolve() == notepad.resolve(), f"lnk ayristirildi: {bilgi and bilgi['hedef']}")
            dogrula(bilgi and bilgi.get("argumanlar") == "/A", f"kisayol argumanlari okundu: {bilgi and bilgi.get('argumanlar')!r}")
            tur, acik, hata = acma.hedef_cozumle(klasor / "Not Defteri.lnk", pol)
            dogrula(hata is None and "ÇALIŞTIRILACAK" in acik and "notepad.exe" in acik.lower() and "/A" in acik,
                    f"kart gercek hedefi ve argumani soyluyor: {acik}")
            # Degismez 2: hedef yazma kokunde
            (kum / "betik.bat").write_text("@echo zarar", encoding="utf-8")
            _kisayol(klasor / "Zarar.lnk", kum / "betik.bat")
            tur, acik, hata = acma.hedef_cozumle(klasor / "Zarar.lnk", pol)
            dogrula(hata is not None and "yazabildiği" in hata, f"hedef yazma kokunde -> RED: {hata[:70]}")
            # zincir
            _kisayol(klasor / "Zincir.lnk", klasor / "Not Defteri.lnk")
            tur, acik, hata = acma.hedef_cozumle(klasor / "Zincir.lnk", pol)
            # WScript.Shell kisayol->kisayol hedefini olustururken DUZLESTIRIR
            # (Zincir.lnk dogrudan notepad.exe'yi gosterir): o zaman mesru.
            # Elle yazilmis bir .lnk baska bir .lnk'ye isaret ederse kod reddeder
            # (suffix kontrolu); burada olculen: hangi durumda olursa olsun bir
            # .lnk hedefi ASLA "acilacak" diye gecmez.
            zincir = acma.kisayol_hedefi(klasor / "Zincir.lnk")
            duz = bool(zincir and not zincir["hedef"].lower().endswith(".lnk"))
            dogrula((duz and hata is None and "notepad" in acik.lower()) or (hata is not None),
                    f"kisayol -> kisayol: {'Windows duzlestirdi -> notepad' if duz else 'RED: ' + str(hata)[:40]}")
            # hedef yok
            _kisayol(klasor / "Yok.lnk", d / "olmayan.exe")
            tur, acik, hata = acma.hedef_cozumle(klasor / "Yok.lnk", pol)
            dogrula(hata is not None and "yok" in hata, "hedefi olmayan kisayol: RED")
            # kod koku
            _kisayol(klasor / "Kod.lnk", PROJE_KOKU / "pevrai" / "gate.py")
            tur, acik, hata = acma.hedef_cozumle(klasor / "Kod.lnk", pol)
            dogrula(hata is not None, "hedef Pevrai'nin kendi klasorunde: RED")
            # COM yedegi ayni sonucu veriyor mu
            com = acma._lnk_com(klasor / "Not Defteri.lnk")
            dogrula(com and Path(com["hedef"]).resolve() == notepad.resolve() and com["argumanlar"] == "/A",
                    "WScript.Shell yedegi ayristiriciyla ayni hedefi veriyor")
        else:
            not_dus("Windows/PowerShell/notepad yok; gercek .lnk vakalari olculemedi")

        print("\n5) open_file araci (os.startfile mock)")
        with patch.object(v.B, "politika", pol), patch.object(os, "startfile", create=True) as sf:
            r = v.open_file((klasor / "rapor.pdf").resolve(), {"path": "rapor.pdf"})
            dogrula("açıldı" in r and sf.call_count == 1 and sf.call_args[0][0] == str((klasor / "rapor.pdf").resolve()),
                    f"belge acildi: {r[:70]}")
            sf.reset_mock()
            r = v.open_file((klasor / "site.url").resolve(), {"path": "site.url"})
            dogrula(sf.call_count == 0 and "internet" in r, ".url: startfile HIC cagrilmadi")
            r = v.open_file((klasor / "yok.pdf").resolve(), {"path": "yok.pdf"})
            dogrula(sf.call_count == 0 and "bulunamadı" in r, "olmayan oge: komsular listelenir, acilmaz")
            if (klasor / "Zarar.lnk").exists():
                r = v.open_file((klasor / "Zarar.lnk").resolve(), {"path": "Zarar.lnk"})
                dogrula(sf.call_count == 0 and "yazabildiği" in r, "zararli kisayol: startfile HIC cagrilmadi")
            sf.side_effect = OSError("iliskili program yok")
            r = v.open_file((klasor / "notlar.txt").resolve(), {"path": "notlar.txt"})
            dogrula("açılamadı" in r, "startfile hatasi metne doner, istisna sizmaz")

        print("\n6) Onay karti etki cumlesi ve sistem talimati")
        with patch.object(v.B, "politika", pol):
            e = v._etki_cumlesi("open_file", {"path": "rapor.pdf"}, (klasor / "rapor.pdf").resolve())
            dogrula("ilişkili" in e, f"etki: {e}")
            e = v._etki_cumlesi("open_file", {"path": "calistir.exe"}, (klasor / "calistir.exe").resolve())
            dogrula("ÇALIŞTIRILACAK" in e, f"etki (.exe): {e}")
            ogeler = acma.acilabilir_ogeler(pol)
            dogrula("rapor.pdf" in ogeler and "gizli_belge.pdf" not in ogeler,
                    f"talimat listesi: kara listedeki gizlendi ({len(ogeler)} oge)")
            from pevrai.talimat import talimat_cumleleri, _erisim
            c = " ".join(talimat_cumleleri(frozenset({"open_file", "list_dir"}), _erisim(frozenset({"list_dir"})),
                                           [d], [], kismi=False, acilabilir=ogeler))
            dogrula("Açabildiğin ögeler" in c and "rapor.pdf" in c, "sistem talimati ogeleri adiyla listeliyor")
            c2 = " ".join(talimat_cumleleri(frozenset({"open_file"}), _erisim(frozenset()), [], [], kismi=False, acilabilir=[]))
            dogrula("boş ya da ayarlanmamış" in c2, "klasor bos/ayarsiz: talimat kullaniciya yolu soyler")

        print("\n7) Ayarlar yazici: kesisen klasoru YAZMADAN reddeder")
        from pevrai import ayarlar
        with patch.object(ayarlar, "POLICY", d / "policy.toml"), patch.object(ayarlar, "KOK", d):
            (kum / "alt2").mkdir(exist_ok=True)
            hata = ayarlar.acma_klasoru_yaz(str(kum / "alt2"))
            dogrula(hata is not None and "kesişiyor" in hata, f"yazma koku icindeki klasor: {hata[:60]}")
            hata = ayarlar.acma_klasoru_yaz(str(d / "olmayan_klasor"))
            dogrula(hata is not None and "yok" in hata, "diskte olmayan klasor reddedilir")
            yeni = d / "Baska"; yeni.mkdir()
            hata = ayarlar.acma_klasoru_yaz(str(yeni))
            dogrula(hata is None and Politika(d / "policy.toml").acma_klasoru == yeni.resolve(), "ayri klasor yazildi ve geri okundu")
            hata = ayarlar.acma_klasoru_yaz("")
            dogrula(hata is None and Politika(d / "policy.toml").acma_klasoru is None, "bos = kapatildi")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
