# gunluk_eszamanli_testi.py — ayni gunluge birden fazla SUREC yazinca kayit bozulmamali.
#
# Ekip iscileri ayri surecler ve hepsi ayni journal.jsonl'e yazar. Windows'ta
# "a" kipinde acilan dosyaya ekleme atomik degil (CRT once sona gider, sonra
# yazar): iki surec ayni anda yazinca biri otekinin satirinin ustune yazdi,
# ekip_orkestra_testi arada bir "JSONDecodeError: Extra data" ile kaldi.
# Bozuk satir _kayitlar()'da atlanir — yani o yazmanin GERI ALMA kaydi kaybolur.
# Ayni yaris istek sayacinda (kota.json) da vardi: sayim eksik kaliyordu.
#
#   python tests/gunluk_eszamanli_testi.py
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
SUREC, KAYIT = 6, 150
HATA = 0

YAZICI = f"""
import sys
sys.path.insert(0, {str(KOK)!r})
from pevrai import journal
kimlik = sys.argv[1]
for i in range({KAYIT}):
    journal.yaz({{"tip": "yazma", "yol": "C:/deneme/" + kimlik + "_" + str(i) + ".txt",
                 "bayt": i, "yedek": None, "ajan": kimlik, "dolgu": "x" * 300}})
    journal.kota_artir("varsayilan")
"""


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


def main() -> int:
    print(f"\n1) {SUREC} surec ayni anda {KAYIT}'er kayit yaziyor")
    with tempfile.TemporaryDirectory(prefix="pevrai_gunluk_") as d:
        ortam = dict(os.environ, PEVRAI_VEKIL_KOK=d)
        surecler = [subprocess.Popen([sys.executable, "-c", YAZICI, f"s{n}"], env=ortam)
                    for n in range(SUREC)]
        kodlar = [s.wait(timeout=120) for s in surecler]
        dogrula(all(k == 0 for k in kodlar), f"butun yazicilar bitti ({kodlar})")
        satirlar = [s for s in (Path(d) / "journal.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
        bozuk = 0
        kayitlar = []
        for s in satirlar:
            try:
                kayitlar.append(json.loads(s))
            except ValueError:
                bozuk += 1
        dogrula(bozuk == 0, f"bozuk satir yok ({bozuk})")
        dogrula(len(kayitlar) == SUREC * KAYIT, f"hicbir kayit kaybolmadi ({len(kayitlar)} / {SUREC * KAYIT})")
        tekil = {k.get("yol") for k in kayitlar}
        dogrula(len(tekil) == SUREC * KAYIT, f"her kayit bir kez var ({len(tekil)})")
        kimlikler = {k.get("kayit_kimligi") for k in kayitlar}
        dogrula(None not in kimlikler and len(kimlikler) == SUREC * KAYIT,
                "farkli sureclerde kayit kimlikleri cakismiyor")

        sys.path.insert(0, str(KOK))
        os.environ["PEVRAI_VEKIL_KOK"] = d
        from pevrai import journal
        dogrula(len(journal._kayitlar()) == SUREC * KAYIT, "geri alma gecmisi hepsini goruyor")
        sayac = journal.kota_sayaclari().get("varsayilan", 0)
        dogrula(sayac == SUREC * KAYIT, f"istek sayaci eksik saymadi ({sayac} / {SUREC * KAYIT})")
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
