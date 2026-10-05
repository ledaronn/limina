"""araclar/acma.py — open_file: acma klasorundeki bir ogeyi acar.

TASARIM (kullanicinin): kullanici TEK bir klasor secer. Icine koydugu her sey
— belge, resim, kisayol, dogrudan bir .exe — modelin "ac" diyebildigi seyler
listesidir. Klasoru yalnizca kullanici duzenler: kapi o klasorun ajanin
yazabildigi hicbir yerle kesismemesini garanti eder (gate.acma_klasoru_ihlali).
Yani izin listesi policy.toml'da bir dizi degil, DISKTEKI BIR KLASOR; kullanici
Explorer'da surukleyerek yonetir.

"Kabuk yok" ilkesiyle iliskisi: bu arac komut satiri kurmaz, arguman gecirmez,
program adi almaz. Windows'a "bu ogeyi ac" der (os.startfile) — bir PDF icin
ilisili programi, bir kisayol icin kullanicinin kisayola YAZDIGI hedefi ve
argumanlari. Model kisayolun icini degistiremez (klasore yazamaz), kisayolun
hedefi de ajanin yazabildigi bir yerde olamaz (zincir: kisayol -> kum/x.bat).

Risk EXEC: her cagrida onay, toplu onay yok, tur basina 3 (gate.RISK tablosu).
"""
from __future__ import annotations
from limina.sonuc import hata as sonuc_hatasi

import os
import struct
import subprocess
import sys
from pathlib import Path

from limina.araclar.kayit import arac
from limina.araclar.ortak import bulunamadi
from limina.baglam import B
from limina.ceviri import t

# Dogrudan CALISTIRMA anlamina gelen uzantilar: onay kartinda "CALISTIRILACAK"
# diye buyuk harfle soylenir. Engellenmez — klasore kullanici koydu — ama
# belge acmakla ayni cumleyle sunulmaz.
CALISTIRILABILIR = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".msi", ".com", ".scr",
                    ".reg", ".hta", ".jar", ".wsf", ".pif"}
# .url: internet kisayolu, hedef bir ADRES. Tarayici araclari zaten var ve
# site listesinden gecer; buradan acilirsa o liste bypass edilirdi.
REDDEDILEN = {".url", ".website"}


def kisayol_hedefi(lnk: Path) -> dict | None:
    """Windows .lnk dosyasini okur: hedef, argumanlar, calisma dizini.

    Once dosya bicimi (MS-SHLLINK) dogrudan ayristirilir — hizli, surec yok.
    LinkInfo yoksa (ag kisayolu, bazi eski kisayollar) WScript.Shell COM'a
    dusulur (PowerShell alt sureci, ~300 ms). Ikisi de olmazsa None: cagiran
    "hedef okunamadi" der, ACMAZ.
    """
    try:
        veri = lnk.read_bytes()
        sonuc = _lnk_ayristir(veri, lnk)
        if sonuc and sonuc.get("hedef"):
            return sonuc
    except Exception:
        pass
    return _lnk_com(lnk)


def _lnk_ayristir(v: bytes, lnk: Path) -> dict | None:
    if len(v) < 0x4C or struct.unpack_from("<I", v, 0)[0] != 0x4C:
        return None
    bayrak = struct.unpack_from("<I", v, 20)[0]
    unicode = bool(bayrak & 0x80)
    p = 0x4C
    if bayrak & 0x01:                                   # HasLinkTargetIDList
        p += 2 + struct.unpack_from("<H", v, p)[0]
    hedef = ""
    if bayrak & 0x02:                                   # HasLinkInfo
        bas = p
        boyut, bas_boyut, li_bayrak = struct.unpack_from("<III", v, bas)
        if li_bayrak & 0x01:                            # VolumeIDAndLocalBasePath
            yerel_off = struct.unpack_from("<I", v, bas + 16)[0]
            sonek_off = struct.unpack_from("<I", v, bas + 24)[0]
            if bas_boyut >= 0x24:
                yerel_u = struct.unpack_from("<I", v, bas + 28)[0]
                sonek_u = struct.unpack_from("<I", v, bas + 32)[0]
                hedef = _utf16z(v, bas + yerel_u) + _utf16z(v, bas + sonek_u)
            else:
                hedef = _ansiz(v, bas + yerel_off) + _ansiz(v, bas + sonek_off)
        p = bas + boyut
    # StringData: Name, RelativePath, WorkingDir, Arguments, IconLocation (sirayla)
    dizeler: dict[str, str] = {}
    for ad, bit in (("ad", 0x04), ("goreli", 0x08), ("dizin", 0x10), ("argumanlar", 0x20), ("ikon", 0x40)):
        if not (bayrak & bit):
            continue
        n = struct.unpack_from("<H", v, p)[0]
        p += 2
        if unicode:
            dizeler[ad] = v[p:p + 2 * n].decode("utf-16-le", "replace")
            p += 2 * n
        else:
            dizeler[ad] = v[p:p + n].decode("mbcs" if sys.platform == "win32" else "latin-1", "replace")
            p += n
    if not hedef and dizeler.get("goreli"):
        hedef = str((lnk.parent / dizeler["goreli"]).resolve())
    if not hedef:
        return None
    return {"hedef": hedef, "argumanlar": dizeler.get("argumanlar", ""), "dizin": dizeler.get("dizin", "")}


def _ansiz(v: bytes, i: int) -> str:
    son = v.find(b"\x00", i)
    return v[i:son if son >= 0 else len(v)].decode("mbcs" if sys.platform == "win32" else "latin-1", "replace")


def _utf16z(v: bytes, i: int) -> str:
    j = i
    while j + 1 < len(v) and v[j:j + 2] != b"\x00\x00":
        j += 2
    return v[i:j].decode("utf-16-le", "replace")


def _lnk_com(lnk: Path) -> dict | None:
    if sys.platform != "win32" or "'" in str(lnk):
        return None
    betik = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
             f"Write-Output $s.TargetPath; Write-Output $s.Arguments; Write-Output $s.WorkingDirectory")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", betik],
                           capture_output=True, text=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return None
    satirlar = (r.stdout or "").splitlines() + ["", "", ""]
    if r.returncode != 0 or not satirlar[0].strip():
        return None
    return {"hedef": satirlar[0].strip(), "argumanlar": satirlar[1].strip(), "dizin": satirlar[2].strip()}


def hedef_cozumle(yol: Path, politika) -> tuple[str, str, str | None]:
    """Acilacak oge icin (tur, aciklama, hata).

    tur: "belge" | "klasor" | "calistir" | "kisayol".  aciklama: onay kartinda
    ve arac sonucunda gosterilen tek cumle — kullanici NEYE evet dedigini
    gorur (kisayolda gercek hedef ve argumanlar). hata doluysa acilmaz.
    """
    uz = yol.suffix.lower()
    if uz in REDDEDILEN:
        return "kisayol", "", t("'{ad}' bir internet kısayolu; adresler yalnızca tarayıcı araçlarıyla, "
                                "izinli site listesinden açılır.", ad=yol.name)
    if uz == ".lnk":
        bilgi = kisayol_hedefi(yol)
        if not bilgi:
            return "kisayol", "", t("'{ad}' kısayolunun hedefi okunamadı; açılmadı.", ad=yol.name)
        try:
            hedef = Path(bilgi["hedef"]).expanduser().resolve()
        except (OSError, ValueError):
            return "kisayol", "", t("'{ad}' kısayolunun hedefi çözülemedi: {hedef}", ad=yol.name, hedef=bilgi["hedef"])
        if hedef.suffix.lower() == ".lnk":
            return "kisayol", "", t("'{ad}' başka bir kısayola işaret ediyor; zincir açılmaz.", ad=yol.name)
        if not hedef.exists():
            return "kisayol", "", t("'{ad}' kısayolunun hedefi yok: {hedef}", ad=yol.name, hedef=hedef)
        # ZINCIR KAPATMA: kisayol kullanicinin, ama hedef ajanin yazabildigi bir
        # yerdeyse (kum/x.bat) ajan hedefi yazar, kisayol uzerinden calistirir.
        from limina.gate import kod_kokleri
        from limina import PROJE_KOKU
        korunan = list(politika.yazma) + kod_kokleri(PROJE_KOKU)
        for k in korunan:
            if hedef == k or k in hedef.parents:
                return "kisayol", "", t("'{ad}' kısayolunun hedefi ({hedef}) ajanın yazabildiği ya da "
                                        "Limina'nın kendi klasöründe; açılmaz.", ad=yol.name, hedef=hedef)
        arg = f" {bilgi['argumanlar']}" if bilgi.get("argumanlar") else ""
        if hedef.suffix.lower() in CALISTIRILABILIR:
            return "kisayol", t("kısayol → ÇALIŞTIRILACAK: {hedef}{arg}", hedef=hedef, arg=arg), None
        return "kisayol", t("kısayol → açılacak: {hedef}{arg}", hedef=hedef, arg=arg), None
    if yol.is_dir():
        return "klasor", t("klasör Explorer'da açılacak"), None
    if uz in CALISTIRILABILIR:
        return "calistir", t("ÇALIŞTIRILACAK: {ad}", ad=yol.name), None
    return "belge", t("'{ad}' ilişkili programla açılacak ({uz})", ad=yol.name, uz=uz or "?"), None


@arac(ad="open_file", paket="acma", risk="EXEC", yollar={"path": "ac"},
      baslik="Dosya ve uygulama açma",
      aciklama=("Açma klasöründeki dosyaları ilişkili programla, kısayolları hedefleriyle açar. "
                "Her açma onay ister."),
      modele=("Açma klasöründeki bir ögeyi açar: belgeyi ilişkili programla, kısayolu (.lnk) kullanıcının "
              "ayarladığı hedefiyle, programı doğrudan. Ögeyi ADIYLA ver (sistem talimatında listeli); "
              "klasör dışındaki yollar reddedilir. Argüman geçiremez, komut kuramaz. Kullanıcı "
              "'X'i aç', 'Y'yi başlat' dediğinde kullan; kendi kararınla program başlatma."),
      sema={"type": "object", "properties": {
                "path": {"type": "string", "description": "Açma klasöründeki ögenin adı (örn. 'Not Defteri.lnk') ya da tam yolu."}},
            "required": ["path"]})
def open_file(yol: Path, args: dict) -> str:
    if sys.platform != "win32":
        return sonuc_hatasi(t("open_file yalnızca Windows'ta çalışır."))
    if not yol.exists():
        return bulunamadi(yol)
    tur, aciklama, hata = hedef_cozumle(yol, B.politika)
    if hata:
        return sonuc_hatasi(hata)
    try:
        os.startfile(str(yol))          # Windows: ilisikli program / kisayol hedefi
    except OSError as e:
        return sonuc_hatasi(t("'{ad}' açılamadı: {hata}", ad=yol.name, hata=e))
    return t("'{ad}' açıldı — {ne}", ad=yol.name, ne=aciklama)


def acilabilir_ogeler(politika, azami: int = 40) -> list[str]:
    """Sistem talimati icin: acma klasorundeki oge adlari (ilk `azami`).
    Kara listedekiler gosterilmez (list_dir ile ayni kural)."""
    k = getattr(politika, "acma_klasoru", None)
    if not k or not k.is_dir():
        return []
    try:
        adlar = sorted(p.name for p in k.iterdir() if not politika._yasakli_mi(p))
    except OSError:
        return []
    return adlar[:azami]
