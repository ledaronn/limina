# ceviri_testi.py — Python mesaj katalogu (limina/ceviri.py) tutarliligi.
#
# Bu test kod tabanini AST ile tarar: her t("...") cagrisinin anahtarini
# toplar ve EN sozlugu ile karsilastirir. Neden statik tarama: bir metni
# duzenleyip sozlugu guncellemeyi unutmak, uygulamayi KIRMAZ — sessizce
# Turkce'ye duser. Sessiz dusus bir testin yakalamasi gereken seydir.
#
#   python tests/ceviri_testi.py
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # proje koku

from limina import PAKET
from limina import ceviri

HATA = 0
YER_TUTUCU = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::[^}]*)?\}")


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


def _sabit_metin(dugum: ast.AST) -> str | None:
    """t()'nin ilk argumani derleme aninda sabit mi? Bitisik dizeler dahil.

    Sabit degilse (degiskense) anahtar statik olarak bilinemez; o cagri
    listeye girmez ama asagida AYRICA raporlanir — cunku cevrilemez bir
    t() cagrisi genelde bir hatadir.
    """
    if isinstance(dugum, ast.Constant) and isinstance(dugum.value, str):
        return dugum.value
    return None


# @arac bildirimlerinden gelen metinlerin isareti (bkz. _cagrilar).
ARAC_BILDIRIMI: set[str] = set()


def _sema_aciklamalari(dugum: ast.AST) -> list[tuple[int, str]]:
    """Bir JSON Schema dict literal'indeki her "description" sabiti."""
    cikti: list[tuple[int, str]] = []
    for d in ast.walk(dugum):
        if not isinstance(d, ast.Dict):
            continue
        for k, v in zip(d.keys, d.values):
            if (isinstance(k, ast.Constant) and k.value == "description"
                    and isinstance(v, ast.Constant) and isinstance(v.value, str)):
                cikti.append((v.lineno, v.value))
    return cikti


def _cagrilar(yol: Path) -> tuple[list[tuple[int, str, set[str]]], list[int]]:
    """(satir, anahtar, kwarg adlari) listesi + sabit olmayan cagrilarin satirlari.

    t() cagrilarina ek olarak @arac(...) bildirimlerinin modele= metni ve
    sema= icindeki "description" alanlari da anahtardir: kayit.semalar()
    onlari her cagrida t()'den gecirir (degisken cagri; o dosya asagida
    muaf). Anahtarlar bildirimde durur, sozluk onlari kapsamali.
    """
    agac = ast.parse(yol.read_text(encoding="utf-8"))
    sabit: list[tuple[int, str, set[str]]] = []
    degisken: list[int] = []
    for d in ast.walk(agac):
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "arac":
            # ARAC_BILDIRIMI: semalar() bunlari KWARG'SIZ t() ile cevirir, yani
            # icindeki {sey} bicimlendirilmez — modelin gorecegi metnin
            # parcasidir (ornek: ag_kur'un "{gorev} yer tutucusu" anlatimi).
            for k in d.keywords:
                if k.arg == "modele" and (m := _sabit_metin(k.value)) is not None:
                    sabit.append((k.value.lineno, m, ARAC_BILDIRIMI))
                if k.arg == "sema":
                    for ln, m in _sema_aciklamalari(k.value):
                        sabit.append((ln, m, ARAC_BILDIRIMI))
            continue
        # t("...") ve ceviri.t("...") — ikisi de ayni sozluge bakar. Nitelikli
        # bicim taranmayinca (pencere.py boyle cagiriyor) eksik bir anahtar
        # sessizce kaynak dilde kalirdi: EN arayuzde Turkce cumle.
        if not isinstance(d, ast.Call):
            continue
        if not ((isinstance(d.func, ast.Name) and d.func.id == "t")
                or (isinstance(d.func, ast.Attribute) and d.func.attr == "t")):
            continue
        if not d.args:
            degisken.append(d.lineno)
            continue
        metin = _sabit_metin(d.args[0])
        if metin is None:
            degisken.append(d.lineno)
            continue
        adlar = {k.arg for k in d.keywords if k.arg}
        sabit.append((d.lineno, metin, adlar))
    return sabit, degisken


def main() -> int:
    dosyalar = sorted(p for p in PAKET.rglob("*.py") if p.name != "ceviri.py")
    tum: list[tuple[Path, int, str, set[str]]] = []
    degiskenler: list[str] = []
    for p in dosyalar:
        sabit, degisken = _cagrilar(p)
        for ln, metin, adlar in sabit:
            tum.append((p, ln, metin, adlar))
        # kayit.semalar() ve eklentiler/registry._cevrilmis: t(bildirim) bilincli
        # degisken cagri — anahtarlar bildirimlerden ayrica toplaniyor (asagida).
        if p.name not in ("kayit.py", "registry.py"):
            degiskenler += [f"{p.name}:{ln}" for ln in degisken]

    # Eklenti araclari (limina/eklentiler/*/tools.py): bildirimler calisma
    # zamaninda kuruluyor (crud() metin birlestiriyor), AST ile okunamaz —
    # registry.TOOLS'tan alinir. registry._cevrilmis bunlari t()'den gecirir.
    try:
        from limina.eklentiler.registry import TOOLS as _EKLENTI
    except ImportError:
        _EKLENTI = {}

    def _aciklamalar(sema, out):
        if isinstance(sema, dict):
            if isinstance(sema.get("description"), str) and sema["description"]:
                out.add(sema["description"])
            for alt in (sema.get("properties") or {}).values():
                _aciklamalar(alt, out)
            if isinstance(sema.get("items"), dict):
                _aciklamalar(sema["items"], out)
    eklenti_metinleri: set[str] = set()
    for spec in _EKLENTI.values():
        eklenti_metinleri.add(spec["description"])
        _aciklamalar(spec["parameters"], eklenti_metinleri)
    for m in sorted(eklenti_metinleri):
        tum.append((Path("limina/eklentiler/registry.py"), 0, m, set(YER_TUTUCU.findall(m))))

    print(f"\n1) Kaynakta {len(tum)} t() cagrisi bulundu ({len(dosyalar)} dosya tarandi, "
          f"{len(eklenti_metinleri)} eklenti araci aciklamasi dahil)")
    dogrula(len(tum) > 0, "t() cagrilari taranabiliyor (kod bozulmamis)")
    dogrula(not degiskenler, f"her t() cagrisinin anahtari SABIT metin (degisken: {degiskenler})")

    print("\n2) Her anahtarin Ingilizce karsiligi var")
    eksik = sorted({metin for _, _, metin, _ in tum} - set(ceviri.EN))
    for m in eksik:
        print(f"      EKSIK: {m[:90]!r}")
    dogrula(not eksik, f"eksik ceviri yok ({len(set(m for _, _, m, _ in tum))} benzersiz anahtar)")

    print("\n3) Sozlukte kullanilmayan (olu) anahtar yok")
    kullanilan = {metin for _, _, metin, _ in tum}
    olu = sorted(set(ceviri.EN) - kullanilan)
    for m in olu:
        print(f"      OLU: {m[:90]!r}")
    dogrula(not olu, "olu anahtar yok (metin degisince sozluk de guncellenmis)")

    print("\n4) Yer tutucular TR ve EN'de birebir ayni")
    for metin, ceviri_metni in sorted(ceviri.EN.items()):
        a, b = set(YER_TUTUCU.findall(metin)), set(YER_TUTUCU.findall(ceviri_metni))
        if a != b:
            dogrula(False, f"yer tutucu uyusmuyor {metin[:60]!r}: TR={sorted(a)} EN={sorted(b)}")
    dogrula(True, "yer tutucu kumeleri esit (eksik {ad} -> bicimlendirme hatasi olurdu)")

    print("\n5) Cagrilar gereken yer tutuculari veriyor")
    for p, ln, metin, adlar in tum:
        if adlar is ARAC_BILDIRIMI:
            continue            # kwarg'siz cevrilir: suslu parantez degismez
        gerekli = set(YER_TUTUCU.findall(metin))
        if gerekli - adlar:
            dogrula(False, f"{p.name}:{ln} eksik arguman: {sorted(gerekli - adlar)}")
        if adlar - gerekli:
            dogrula(False, f"{p.name}:{ln} kullanilmayan arguman: {sorted(adlar - gerekli)}")
    dogrula(True, "her cagri metnin istedigi adlari veriyor")

    print("\n6) t() davranisi")
    ceviri.dil_ayarla("tr")
    dogrula(ceviri.t("yeni ad: {ad}", ad="a.txt") == "yeni ad: a.txt", "tr: kaynak metin + bicimlendirme")
    ceviri.dil_ayarla("en")
    dogrula(ceviri.t("yeni ad: {ad}", ad="a.txt") == "new name: a.txt", "en: sozlukten")
    dogrula(ceviri.t("sozlukte olmayan metin") == "sozlukte olmayan metin",
            "karsiligi yoksa kaynak metin doner (bos dize ya da '??' DEGIL)")
    # Eksik arguman: istisna sizdirmamali. Onay karti bir bicimlendirme
    # hatasi yuzunden gosterilememektense ham metni gostersin.
    try:
        r = ceviri.t("yeni ad: {ad}")
        dogrula(isinstance(r, str) and r, f"eksik arguman istisna sizdirmiyor ({r!r})")
    except Exception as e:
        dogrula(False, f"eksik arguman istisna sizdirdi: {type(e).__name__}: {e}")
    dogrula(ceviri.t("{arac} çalıştırılacak", arac="x") == "x will run", "en: yer tutucu dolduruldu")
    ceviri.dil_ayarla("de")
    dogrula(ceviri.dil() == "tr", "taninmayan dil kodu -> kaynak dil (sessizce tr)")

    print("\n7) Dil ayari config/arayuz.toml'dan okunuyor")
    from unittest.mock import patch
    from limina import ayarlar
    for kod in ("en", "tr"):
        ceviri.dil_sifirla()
        sahte = {b: dict(a) for b, a in ayarlar.ARAYUZ_VARSAYILAN.items()}
        sahte["genel"]["dil"] = kod
        with patch.object(ayarlar, "arayuz_oku", return_value=sahte):
            dogrula(ceviri.dil() == kod, f"arayuz.toml dil={kod} -> ceviri.dil()={kod}")
    ceviri.dil_sifirla()
    with patch.object(ayarlar, "arayuz_oku", side_effect=OSError("disk")):
        dogrula(ceviri.dil() == "tr", "ayar okunamiyorsa kaynak dile dusulur (istisna sizmaz)")
    ceviri.dil_sifirla()

    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
