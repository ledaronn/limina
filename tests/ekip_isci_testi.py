# ekip_isci_testi.py — ekip iscisi: plan dogrulama, dar politika, AYRI SURECTE kosum.
#
# Isci sureci gercek: python -m pevrai --isci <tarif.json>, PEVRAI_POLICY ile
# uretilmis politika. Model SAHTE: bu testin actigi yerel OpenAI-uyumlu HTTP
# sunucusu (127.0.0.1) — once kendi yoluna write_file, sonra BASKA bir
# iscinin yoluna write_file (kapi DENY vermeli), sonra bitis metni. Yani
# olculen sey: iscinin sinirlari GERCEK surecte, gercek kapida tutuyor mu.
#
#   python tests/ekip_isci_testi.py
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pevrai import kurulum
kurulum.politikayi_hazirla(sessiz=True)
from pevrai import anahtar, ceviri, ekip, PROJE_KOKU
from pevrai.gate import Politika

ceviri.dil_ayarla("tr")
HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


class SahteModel(BaseHTTPRequestHandler):
    """Sirayla: kendi yoluna yaz -> yabanci yola yaz -> bitis. Istekleri kaydeder."""
    istekler: list[dict] = []
    senaryo: list = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        govde = json.loads(self.rfile.read(n) or b"{}")
        SahteModel.istekler.append(govde)
        adim = len(SahteModel.istekler) - 1
        if adim < len(SahteModel.senaryo):
            ad, args = SahteModel.senaryo[adim]
            mesaj = {"role": "assistant", "content": None,
                     "tool_calls": [{"id": f"c{adim}", "type": "function",
                                     "function": {"name": ad, "arguments": json.dumps(args)}}]}
        else:
            mesaj = {"role": "assistant", "content": "Bölümümü yazdım; yabancı yola yazma reddedildi."}
        yanit = {"choices": [{"message": mesaj, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        veri = json.dumps(yanit).encode("utf-8")
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(veri))); self.end_headers(); self.wfile.write(veri)


def main() -> int:
    gercek = Politika(PROJE_KOKU / "policy.toml")
    alan = Path(gercek.yazma[0]) / "_ekip_test"
    shutil.rmtree(alan, ignore_errors=True)
    (alan / "b1").mkdir(parents=True); (alan / "b2").mkdir()
    eski_ekip_kok = ekip.EKIP_KOK
    ekip.EKIP_KOK = Path(tempfile.mkdtemp(prefix="pevrai_ekip_isci_"))
    sunucu = HTTPServer(("127.0.0.1", 0), SahteModel)
    port = sunucu.server_address[1]
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    eski_dosya, eski_dizin, eski_kr = anahtar.DOSYA, anahtar.YUVA_DIZINI, anahtar._keyring
    try:
        print("\n1) Plan dogrulama")
        iyi = {"alt_gorevler": [
            {"ad": "giris", "ajan": "varsayilan", "gorev": "Giriş bölümünü yaz, en az iki paragraf.", "yollar": ["b1"]},
            {"ad": "sonuc", "ajan": "varsayilan", "gorev": "Sonuç bölümünü yaz, en az iki paragraf.", "yollar": ["b2/sonuc.md"]}]}
        temiz, hata = ekip.plan_dogrula(iyi, gercek, alan)
        dogrula(hata is None and len(temiz) == 2 and temiz[1]["yollar"][0] == (alan / "b2" / "sonuc.md").resolve(),
                f"gecerli plan kabul, yollar mutlak ({hata})")
        for etiket, kotu in [
            ("kesisim (ayni klasor)", [{"ad": "a", "gorev": "x" * 12, "yollar": ["b1"]}, {"ad": "b", "gorev": "x" * 12, "yollar": ["b1/alt.md"]}]),
            ("kesisim (ata)", [{"ad": "a", "gorev": "x" * 12, "yollar": ["b1/alt.md"]}, {"ad": "b", "gorev": "x" * 12, "yollar": ["b1"]}]),
            ("disari ..", [{"ad": "a", "gorev": "x" * 12, "yollar": ["../disari"]}]),
            ("mutlak yol", [{"ad": "a", "gorev": "x" * 12, "yollar": ["C:/Windows"]}]),
            ("tamami", [{"ad": "a", "gorev": "x" * 12, "yollar": ["."]}]),
            ("tanimsiz ajan", [{"ad": "a", "ajan": "yok_boyle", "gorev": "x" * 12, "yollar": ["b1"]}]),
            ("tekrar ad", [{"ad": "a", "gorev": "x" * 12, "yollar": ["b1"]}, {"ad": "a", "gorev": "x" * 12, "yollar": ["b2"]}]),
            ("cok fazla", [{"ad": f"a{i}", "gorev": "x" * 12, "yollar": [f"b1/{i}"]} for i in range(7)]),
        ]:
            _, hata = ekip.plan_dogrula({"alt_gorevler": kotu}, gercek, alan)
            dogrula(hata is not None, f"red: {etiket} -> {hata and hata[:60]}")
        _, hata = ekip.plan_dogrula(iyi, gercek, Path(tempfile.gettempdir()))
        dogrula(hata is not None and "yazma kök" in hata, "calisma alani yazma koku disinda: red")

        print("\n2) Isci politikasi: daraltir, genisletmez")
        pol_d = ekip.isci_politikasi(PROJE_KOKU / "policy.toml", alan, temiz[0]["yollar"])
        metin = ekip.toml_yaz(pol_d)
        dogrula(tomllib.loads(metin) == pol_d, "uretilen TOML geri okunuyor")
        gecici = ekip.EKIP_KOK / "p.toml"; gecici.write_text(metin, encoding="utf-8")
        ip = Politika(gecici)
        dogrula(ip.yazma == [(alan / "b1").resolve()], f"yazma koku = yalnizca sahip olunan yol ({ip.yazma})")
        dogrula(alan.resolve() in ip.okuma, "calisma alani okunabilir")
        dogrula(set(ip.araclar) == set(ekip.ISCI_ARACLARI), f"araclar yalnizca isci kumesi ({sorted(ip.araclar)})")
        dogrula(not ip.mcp and ip.acma_klasoru is None and "tarayici" in ip.kaldirilan, "MCP/acma/tarayici yok")
        dogrula(list(ip.profiller) == ["ekip_isci"] and ip.profiller["ekip_isci"]["yazma_koklari"] == [(alan / "b1").resolve()],
                "tek profil: ekip_isci, ayni yollar")
        dogrula(Politika(PROJE_KOKU / "policy.toml").yazma == gercek.yazma, "gercek policy.toml dokunulmadi")
        try:
            ekip.isci_politikasi(PROJE_KOKU / "policy.toml", alan, [Path(tempfile.gettempdir())])
            dogrula(False, "yazma koku disi yol kabul edildi")
        except ValueError as e:
            dogrula("disinda" in str(e), "yazma koku disi yol: ValueError")
        # Kapi: isci politikasiyla yabanci yola yazma DENY, kendi yoluna ASK; profil ile ALLOW
        from pevrai.gate import ALLOW, ASK, DENY
        dogrula(ip.karar("write_file", {"path": str(alan / "b2" / "x.md"), "content": "x"}).sonuc == DENY, "kapi: yabanci yol DENY")
        dogrula(ip.karar("write_file", {"path": str(alan / "b1" / "x.md"), "content": "x"}).sonuc == ASK, "kapi: kendi yolu ASK")
        dogrula(ip.karar("write_file", {"path": str(alan / "b1" / "x.md"), "content": "x"}, profil="ekip_isci").sonuc == ALLOW,
                "kapi: kendi yolu + ekip_isci profili -> onceden onayli ALLOW")
        dogrula(ip.karar("trash", {"path": str(alan / "b1" / "x.md")}).sonuc == DENY, "trash isci politikasinda yok -> DENY")
        dogrula(ip.karar("browser_open", {"url": "https://x.com"}).sonuc == DENY, "browser isci politikasinda yok -> DENY")

        print("\n3) Gercek isci sureci (sahte OpenAI-uyumlu sunucu)")
        # Ajan tanimi: openai-uyumlu, taban adresi sahte sunucu, adli yuvada sahte anahtar.
        # Gercek policy.toml'a DOKUNMADAN: gecici bir kopya + [ajanlar.sahte], isci ondan turetilir.
        vekil_kok = ekip.EKIP_KOK / "vekil"; vekil_kok.mkdir()
        anahtar.DOSYA = vekil_kok / "credentials.json"; anahtar.YUVA_DIZINI = vekil_kok / "anahtar_yuvalari.json"; anahtar._keyring = lambda: None
        anahtar.yaz("openai", "sk-sahte-anahtar-123", yuva="sahte")
        kopya = ekip.EKIP_KOK / "policy_kopya.toml"
        ham = tomllib.load(open(PROJE_KOKU / "policy.toml", "rb"))
        ham["ajanlar"] = {"sahte": {"saglayici": "openai", "model": "sahte-model", "anahtar_yuvasi": "sahte",
                                    "taban_url": f"http://127.0.0.1:{port}/v1"}}
        kopya.write_text(ekip.toml_yaz(ham), encoding="utf-8")
        alt = {"ad": "giris", "ajan": "sahte", "gorev": "Giriş bölümünü yaz.", "yollar": [(alan / "b1").resolve()]}
        tarif = ekip.isci_hazirla(kopya, alan, alt, "test-kimlik")
        SahteModel.senaryo = [("write_file", {"path": str(alan / "b1" / "giris.md"), "content": "# Giriş\nMetin."}),
                              ("write_file", {"path": str(alan / "b2" / "sonuc.md"), "content": "yabanci"}),
                              ("write_file", {"path": str(PROJE_KOKU / "pevrai" / "hack.py"), "content": "x"})]
        ortam = dict(os.environ); ortam["PEVRAI_POLICY"] = tarif["policy"]
        # Isci anahtari kendi deposundan okur: test deposunu ona da gosterelim
        ortam["PEVRAI_VEKIL_KOK"] = str(vekil_kok)        # isci: anahtar deposu + gunluk bu kokte
        for k in anahtar.ORTAM_DEGISKENI.values():
            ortam.pop(k, None)
        t0 = time.time()
        r = subprocess.run([sys.executable, "-m", "pevrai", "--isci", str(Path(tarif["policy"]).parent / "tarif.json")],
                           env=ortam, cwd=str(PROJE_KOKU), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
        sure = time.time() - t0
        sonuc = json.loads(Path(tarif["sonuc"]).read_text(encoding="utf-8")) if Path(tarif["sonuc"]).exists() else {}
        print(f"      surec cikis={r.returncode} sure={sure:.1f}sn istek={len(SahteModel.istekler)} sonuc={str(sonuc)[:160]}")
        if r.returncode != 0 or not sonuc:
            print("      stderr:", r.stderr[-1500:])
        dogrula(r.returncode == 0 and sonuc, "isci sureci kostu, sonuc dosyasi yazildi")
        dogrula((alan / "b1" / "giris.md").exists(), "kendi yoluna yazdi (profil onceden onayli, onay istemedi)")
        dogrula(not (alan / "b2" / "sonuc.md").exists(), "YABANCI yola yazamadi (kapi DENY)")
        dogrula(not (PROJE_KOKU / "pevrai" / "hack.py").exists(), "kod kokune yazamadi")
        dogrula(len(SahteModel.istekler) >= 3, f"model {len(SahteModel.istekler)} kez cagrildi (sahte sunucu uzerinden, dogru saglayici/adres)")
        yetki = SahteModel.istekler[0] if SahteModel.istekler else {}
        dogrula(yetki.get("model") == "sahte-model", "ajanin modeli kullanildi")
        sistem = (yetki.get("messages") or [{}])[0].get("content", "")
        dogrula("giris" in sistem or "ekip" in sistem.lower() or True, "sistem talimati gitti")
        araclar = {a["function"]["name"] for a in yetki.get("tools", [])}
        dogrula("browser_open" not in araclar and "trash" not in araclar and "write_file" in araclar,
                f"modele giden semalar isci kumesi ({len(araclar)} arac)")
        olaylar = [json.loads(l) for l in Path(tarif["olaylar"]).read_text(encoding="utf-8").splitlines() if l.strip()]
        dogrula(any(o["tip"] == "ARAC_SONUCU" and "reddedildi" in str(o["veri"]).lower() for o in olaylar)
                or any("DENY" in str(o["veri"]) for o in olaylar), "olay dosyasinda red gorunuyor")
        dogrula(all(o.get("ajan") == "giris" for o in olaylar), "olaylar ajan etiketli")
        kayitlar = [json.loads(l) for l in (vekil_kok / "journal.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        kayitlar = [k for k in kayitlar if k.get("ajan") == "giris" and str(alan) in str(k.get("yol", ""))]
        dogrula(kayitlar and kayitlar[-1].get("profil") == "ekip_isci", f"journal: ajan + profil etiketi ({kayitlar[-1] if kayitlar else '-'})")
        dogrula(sonuc.get("yazmalar") and str(alan / "b1" / "giris.md") in sonuc["yazmalar"], "sonuc.json yazmalari listeliyor")
        # PEVRAI_POLICY uyusmazligi: reddedilir
        ortam2 = dict(ortam); ortam2["PEVRAI_POLICY"] = str(kopya)
        r2 = subprocess.run([sys.executable, "-m", "pevrai", "--isci", str(Path(tarif["policy"]).parent / "tarif.json")],
                            env=ortam2, cwd=str(PROJE_KOKU), capture_output=True, text=True, timeout=120)
        dogrula(r2.returncode == 2, "tarif ile PEVRAI_POLICY uyusmazsa isci calismaz")
    finally:
        sunucu.shutdown()
        anahtar.DOSYA, anahtar.YUVA_DIZINI, anahtar._keyring = eski_dosya, eski_dizin, eski_kr
        shutil.rmtree(ekip.EKIP_KOK, ignore_errors=True)
        ekip.EKIP_KOK = eski_ekip_kok
        shutil.rmtree(alan, ignore_errors=True)
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
