"""hepsi.py — butun modelsiz test paketlerini sirayla kosar, tek satir ozet verir.

    python tests/hepsi.py            # hepsi
    python tests/hepsi.py --hizli    # tarayici (headless Chrome) gerektirenler atlanir

Her paket ayri surecte kosar (import aninda MCP baslatanlar birbirini
etkilemesin diye). Cikis kodu: kalan paket sayisi. CI bunu cagirir.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent
PAKETLER = [
    ("paket_dogrulama_testi.py", False),
    ("surum_testi.py", False),
    ("guncelleme_testi.py", False),
    ("guncelleme_arayuz_testi.py", True),
    # (dosya, tarayici_gerekir)
    ("kimlik_gecis_testi.py", True),
    ("model_testi.py", False),
    ("kayit_testi.py", False),
    ("ceviri_testi.py", False),
    ("ocr_testi.py", False),
    ("acma_testi.py", False),
    ("ag_testi.py", False),
    ("ekip_testi.py", False),
    ("ekip_pano_testi.py", False),
    ("ekip_isci_testi.py", False),
    ("ekip_orkestra_testi.py", False),
    ("ofis_testi.py", False),
    ("ag_eszamanli_testi.py", False),
    ("gunluk_eszamanli_testi.py", False),
    ("model_zinciri_testi.py", False),
    ("evals.py", False),
    ("dusmanca_testi.py", False),
    ("ayarlar_testi.py", False),
    ("ilk_kurulum_testi.py", False),
    ("kopru_testi.py", False),
    ("sohbet_testi.py", False),
    ("tarayici_testi.py", False),
    ("eylem_testi.py", False),
    ("eklentiler_testi.py", False),
    ("okuma_baglanti_testi.py", False),
    ("islev_regresyon_testi.py", False),
    ("arayuz_testi.py", True),
    ("ekip_arayuz_testi.py", True),
    ("ofis_arayuz_testi.py", True),
    ("ag_arayuz_testi.py", True),
    ("gezinme_testi.py", True),
    ("ceviri_arayuz_testi.py", True),
    ("eklentiler_ui_testi.py", True),
    ("arayuz_regresyon_testi.py", True),
    ("kurulum_arayuz_testi.py", True),
]


def main() -> int:
    hizli = "--hizli" in sys.argv
    kalan: list[str] = []
    for ad, tarayici in PAKETLER:
        if hizli and tarayici:
            print(f"{ad:24} ATLANDI (tarayici gerekir)")
            continue
        bas = time.monotonic()
        r = subprocess.run([sys.executable, str(KOK / ad)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        sure = time.monotonic() - bas
        durum = "GECTI" if r.returncode == 0 else f"KALDI (cikis {r.returncode})"
        print(f"{ad:24} {durum:14} {sure:5.1f} sn")
        if r.returncode != 0:
            kalan.append(ad)
            # Kalan paketin ciktisi: yalniz KALDI/hata satirlari, tam dokum degil
            satirlar = [s for s in (r.stdout + r.stderr).splitlines()
                        if "KALDI" in s or "Traceback" in s or "Error" in s or "FAIL" in s]
            # Hicbiri yoksa (sessiz cikis 1) sebep gorunmez kalmasin: son satirlar
            if not satirlar:
                satirlar = ["(KALDI satiri yok; ciktinin sonu:)"] + (r.stdout + r.stderr).splitlines()[-15:]
            for s in satirlar[-25:]:
                print("    " + s)
            # Istisnayla bittiyse hangi satirda patladigi da gorunsun (CI'da
            # yalniz bu ozet var; "element(s) not found" tek basina yetmiyor).
            if "Traceback" in r.stderr:
                iz = r.stderr[r.stderr.rindex("Traceback"):].splitlines()
                print("    --- son istisna ---")
                for s in [x for x in iz if x.strip().startswith(("File ", "Call log", "- ")) or "Error" in x][-12:]:
                    print("    " + s.strip()[:220])
    print("\n" + ("TUM PAKETLER GECTI" if not kalan else f"KALAN: {', '.join(kalan)}"))
    return len(kalan)


if __name__ == "__main__":
    sys.exit(main())
