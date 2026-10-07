# ag_eszamanli_testi.py — ayni Dusunce Agina AYNI ANDA yazan surecler (ekip iscileri).
#
# ag_dugum_ekle agi okuyup degistirip geri yazar. Ekip iscileri ayri surecler;
# kilitsiz halde iki isci ayni anda dugum eklerse biri otekinin eklemesini
# siliyordu. Burada 4 surec x 25 dugum: hepsi kalmali. Kilit gercekten is
# goruyor mu diye ayni deneme kilitsiz de kosulur ve kayip beklenir (kayip
# gorulmezse yalnizca bilgi verilir: yaris zamanlamaya bagli).
#
#   python tests/ag_eszamanli_testi.py
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
HATA = 0
SUREC, ADET = 4, 25


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


YAZICI = r'''
import sys
sys.path.insert(0, sys.argv[1])
from pevrai.araclar import ag_araclari as aa
if sys.argv[4] == "kilitsiz":
    aa.ag_dugum_ekle = aa.ag_dugum_ekle.__wrapped__        # kilidi atla (karsilastirma icin)
for i in range(int(sys.argv[3])):
    sonuc = aa.ag_dugum_ekle(None, {"ad": "ortak", "kimlik": f"s{sys.argv[2]}_{i}", "baslik": f"not {i}",
                                    "tur": "not", "metin": "x"})
    if "eklendi" not in sonuc and "added" not in sonuc:
        print("HATA", sonuc); sys.exit(1)
'''


def kostur(kok: Path, kip: str) -> int:
    vekil = kok / kip
    (vekil / "aglar").mkdir(parents=True)
    (vekil / "aglar" / "ortak.json").write_text(json.dumps({
        "ad": "ortak", "aciklama": "", "tetik": "", "baglantilar": [],
        "dugumler": [{"kimlik": "kok", "tur": "fikir", "baslik": "Kok", "metin": "x", "yol": "", "kapi": "herhangi",
                      "esik": None, "k": None, "kaynak": "kullanici", "konum": [0, 0, 0]}]}), encoding="utf-8")
    betik = kok / "yazici.py"; betik.write_text(YAZICI, encoding="utf-8")
    ortam = dict(os.environ, PEVRAI_VEKIL_KOK=str(vekil), PYTHONIOENCODING="utf-8")
    surecler = [subprocess.Popen([sys.executable, str(betik), str(KOK), str(n), str(ADET), kip], env=ortam,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE) for n in range(SUREC)]
    for s in surecler:
        cikti, hata = s.communicate(timeout=300)
        if s.returncode:
            print("      surec hatasi:", (cikti + hata).decode("utf-8", "replace")[-400:])
    veri = json.loads((vekil / "aglar" / "ortak.json").read_text(encoding="utf-8"))
    return len([d for d in veri["dugumler"] if d["kimlik"] != "kok"])


def main() -> int:
    kok = Path(tempfile.mkdtemp(prefix="pevrai_ag_eszamanli_"))
    try:
        print(f"\n1) {SUREC} surec x {ADET} dugum, ayni aga ayni anda")
        n = kostur(kok, "kilitli")
        dogrula(n == SUREC * ADET, f"kilitli: {n}/{SUREC * ADET} dugum kaldi")
        n = kostur(kok, "kilitsiz")
        print(f"      (karsilastirma) kilitsiz: {n}/{SUREC * ADET} dugum kaldi"
              + (" — kilit gercekten kaybi onluyor" if n < SUREC * ADET else " — bu kosuda yaris olmadi"))
    finally:
        shutil.rmtree(kok, ignore_errors=True)
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
