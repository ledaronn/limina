# model_zinciri_testi.py — coklu API baglantisi + sirali model zinciri.
#
# 1) Ayar yazicilari (gecici policy.toml): eski tek-saglayici ayari ilk
#    degisiklikte "ana" baglantisina cevrilir; ekle / sirala / derin / sil;
#    bozuk girdiler reddedilir, dosya bozulmaz.
# 2) Ucta uca (ayri surec, sahte OpenAI-uyumlu sunucu): limiti dolan model
#    429 doner, gorev AYNI adimdan siradaki modelle surer; arac gecmisi yeni
#    modele tasinir; anahtarsiz baglanti atlanir; dolu isareti sonraki gorevde
#    hatirlanir; hepsi doluysa acik bir mesajla biter.
#
#   python tests/model_zinciri_testi.py
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tomllib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

GECICI = Path(tempfile.mkdtemp(prefix="limina_zincir_"))
os.environ["LIMINA_VEKIL_KOK"] = str(GECICI / "vekil")      # limina ice aktarilmadan ONCE
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from limina import kurulum
kurulum.politikayi_hazirla(sessiz=True)
from limina import PROJE_KOKU, ayarlar, ceviri, ekip, model_zinciri
from limina.gate import Politika

ceviri.dil_ayarla("tr")
HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


# ---------------------------------------------------------------------------
# 1) Ayar yazicilari
# ---------------------------------------------------------------------------
def ayar_testleri() -> None:
    print("\n1) Ayar yazicilari (gecici policy.toml)")
    pol_yol = GECICI / "policy.toml"
    ham = tomllib.loads((PROJE_KOKU / "policy.toml").read_text(encoding="utf-8"))
    ham.pop("baglantilar", None)
    # Kullanicinin baglantiya bagli ajanlari da gider: baglantisi silinen ajan
    # politikayi fail-closed yuklenemez yapar (gercek bir policy.toml'da gozlemlendi).
    ham["ajanlar"] = {a: v for a, v in (ham.get("ajanlar") or {}).items() if not v.get("baglanti")}
    ham.setdefault("model", {}).update({"saglayici": "gemini", "varsayilan": "gemini-hizli", "guclu": "gemini-derin"})
    for k in ("zincir", "derin", "taban_url"):
        ham["model"].pop(k, None)
    pol_yol.write_text(ekip.toml_yaz(ham), encoding="utf-8")
    eski = (ayarlar.POLICY, ayarlar.POLICY_YEDEK)
    ayarlar.POLICY, ayarlar.POLICY_YEDEK = pol_yol, GECICI / "policy.toml.yedek"
    try:
        p = Politika(pol_yol)
        z = model_zinciri.zincir(p)
        dogrula([h.model for h in z] == ["gemini-hizli", "gemini-derin"] and z[0].kimlik == "",
                f"eski ayar: iki model tek saglayicinin zinciri ({[h.model for h in z]})")
        dogrula([h.model for h in model_zinciri.zincir(p, "guclu")] == ["gemini-hizli", "gemini-derin"],
                "mod model SECMEZ: derin rolde de ayni zincir")
        dogrula([h.model for h in model_zinciri.zincir(p, secili="ana/gemini-derin")] == ["gemini-derin", "gemini-hizli"],
                "eski ayarda da secilen model basa alinir")

        hata, kimlik = ayarlar.baglanti_yaz("", "DeepSeek (iş)", "openai", "https://api.deepseek.com/v1",
                                            ["deepseek-chat", " deepseek-reasoner ", "deepseek-chat"])
        dogrula(hata is None and kimlik == "deepseek-is", f"yeni baglanti eklendi ({hata or kimlik})")
        p = Politika(pol_yol)
        dogrula(p.zincir == ["ana", "deepseek-is"], f"eski ayar 'ana' baglantisina cevrildi, yeni sona eklendi ({p.zincir})")
        dogrula(p.baglantilar["ana"]["anahtar_yuvasi"] == "", "ana: varsayilan anahtar yuvasi (kayitli anahtar calismaya devam)")
        dogrula(p.baglantilar["ana"]["modeller"] == ["gemini-hizli", "gemini-derin"], "ana: iki eski model sirayla")
        dogrula("derin" not in (tomllib.loads(pol_yol.read_text(encoding="utf-8")).get("model") or {}),
                "[model] derin yazilmadi (model sohbet ekranindan secilir)")
        dogrula(p.baglantilar["deepseek-is"]["modeller"] == ["deepseek-chat", "deepseek-reasoner"],
                "modeller temizlendi, tekrar edeni atildi, sira korundu")
        dogrula(p.baglantilar["deepseek-is"]["anahtar_yuvasi"] == "api-deepseek-is", "yeni baglantinin kendi anahtar yuvasi")
        metin = pol_yol.read_text(encoding="utf-8")
        dogrula("sk-" not in metin and "anahtar =" not in metin, "policy.toml'da anahtar yok")
        etiketler = [h.etiket for h in model_zinciri.zincir(p)]
        dogrula(etiketler == ["Gemini · gemini-hizli", "Gemini · gemini-derin",
                              "DeepSeek (iş) · deepseek-chat", "DeepSeek (iş) · deepseek-reasoner"],
                f"zincir duzlestirildi ({etiketler})")
        secili = [h.etiket for h in model_zinciri.zincir(p, secili="deepseek-is/deepseek-reasoner")]
        dogrula(secili == ["DeepSeek (iş) · deepseek-reasoner", "Gemini · gemini-hizli", "Gemini · gemini-derin",
                           "DeepSeek (iş) · deepseek-chat"],
                "secilen model basa alindi, geri kalanlar zincir sirasiyla")
        dogrula([h.model for h in model_zinciri.zincir(p, secili="yok/model")][0] == "gemini-hizli",
                "zincirde olmayan secim yok sayilir (otomatik)")

        dogrula(ayarlar.zincir_yaz(["deepseek-is", "ana"]) is None and Politika(pol_yol).zincir == ["deepseek-is", "ana"],
                "sira degisti")
        dogrula(ayarlar.zincir_yaz(["ana"]) is not None, "eksik sira reddedildi")

        for girdi, neden in (
            (("", "Kötü", "openai", "", ["bosluklu ad"]), "gecersiz model adi"),
            (("", 'Tırnak"lı', "openai", "", ["m1x"]), "tirnakli ad"),
            (("", "Adres", "openai", "ftp://x", ["m1x"]), "gecersiz adres"),
            (("", "Bos", "openai", "", []), "modelsiz baglanti"),
            (("deepseek-is", "DeepSeek", "gemini", "", ["m1x"]), "saglayici degistirme"),
        ):
            once = pol_yol.read_text(encoding="utf-8")
            h, _ = ayarlar.baglanti_yaz(*girdi)
            dogrula(h is not None and pol_yol.read_text(encoding="utf-8") == once, f"reddedildi, dosya ayni: {neden}")

        hata, bilgi = ayarlar.baglanti_sil("deepseek-is")
        p = Politika(pol_yol)
        dogrula(hata is None and p.zincir == ["ana"] and bilgi["yuva"] == "api-deepseek-is",
                f"baglanti silindi ve siradan dustu ({p.zincir})")
    finally:
        ayarlar.POLICY, ayarlar.POLICY_YEDEK = eski


# ---------------------------------------------------------------------------
# 2) Ucta uca: sahte saglayici ile gecis
# ---------------------------------------------------------------------------
class Sahte(BaseHTTPRequestHandler):
    istekler: list[dict] = []
    kilit = threading.Lock()

    def log_message(self, *a):
        pass

    def _yanit(self, kod: int, govde: dict) -> None:
        veri = json.dumps(govde, ensure_ascii=False).encode("utf-8")
        self.send_response(kod); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(veri))); self.end_headers(); self.wfile.write(veri)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        govde = json.loads(self.rfile.read(n) or b"{}")
        with Sahte.kilit:
            Sahte.istekler.append(govde)
            onceki = sum(1 for i in Sahte.istekler if i.get("model") == govde.get("model"))
        model = govde.get("model", "")
        araclar_var = any(m.get("role") == "tool" for m in govde.get("messages", []))
        if model == "gunluk-dolu":
            return self._yanit(429, {"error": {"message": "Quota exceeded for metric: requests, limit: 20 PerDay"}})
        if model == "dakika-dolu" and onceki > 1:        # ilk istegi yanitlar, sonra doluyor
            return self._yanit(429, {"error": {"message": "Rate limit reached: requests per minute"}})
        if model == "bakiye-bitti":
            return self._yanit(402, {"error": {"message": "Insufficient Balance"}})
        if model == "dakika-dolu" and not araclar_var:
            mesaj = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
                "name": "list_dir", "arguments": json.dumps({"path": str(PROJE_KOKU / "kum")})}}]}
        else:
            mesaj = {"role": "assistant", "content": f"bitti ({model}, arac_sonucu_gordu={araclar_var})"}
        self._yanit(200, {"choices": [{"message": mesaj, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 10, "completion_tokens": 5}})


SURUCU = r'''
import json, sys
sys.path.insert(0, ".")
from limina import ceviri
ceviri.dil_ayarla("tr")
import limina.vekil_v0 as v
from limina.olaylar import Oturum, sabit_cevap
olaylar = []
def yayinla(o):
    olaylar.append({"tip": o.tip.name, "veri": {k: str(x)[:300] for k, x in (o.veri or {}).items()}})
oturum = Oturum(onay_saglayici=sabit_cevap("e"), yayinla=yayinla)
oturum.secili_model = sys.argv[2] if len(sys.argv) > 2 else ""
r = v.calistir("kum klasorunde ne var?", sys.argv[1], oturum)
print("SONUC_JSON " + json.dumps({"metin": r, "olaylar": olaylar}, ensure_ascii=False))
'''


def kostur(pol_yol: Path, vekil: Path, mod: str = "hizli", secili: str = "") -> dict:
    ortam = dict(os.environ)
    ortam.update({"LIMINA_POLICY": str(pol_yol), "LIMINA_VEKIL_KOK": str(vekil), "PYTHONIOENCODING": "utf-8"})
    for k in ("GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        ortam.pop(k, None)
    surucu = GECICI / "surucu.py"
    surucu.write_text(SURUCU, encoding="utf-8")
    r = subprocess.run([sys.executable, str(surucu), mod, secili], env=ortam, cwd=str(PROJE_KOKU), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=180)
    satir = next((s for s in r.stdout.splitlines() if s.startswith("SONUC_JSON ")), "")
    if not satir:
        print("      stdout:", r.stdout[-1500:], "\n      stderr:", r.stderr[-1500:])
        return {}
    return json.loads(satir[len("SONUC_JSON "):])


def politika_yaz(yol: Path, url: str, baglantilar: dict, zincir: list[str]) -> None:
    ham = tomllib.loads((PROJE_KOKU / "policy.toml").read_text(encoding="utf-8"))
    ham["model"] = {**ham.get("model", {}), "saglayici": "openai", "taban_url": url,
                    "varsayilan": "eski-model", "guclu": "eski-model", "zincir": zincir,
                    "gunluk_tavan_varsayilan": 0, "gunluk_tavan_guclu": 0}
    ham["model"].pop("derin", None)
    ham["baglantilar"] = baglantilar
    ham.pop("ajanlar", None)
    ham["mcp"] = {}
    yol.write_text(ekip.toml_yaz(ham), encoding="utf-8")


def gecis_testleri() -> None:
    sunucu = HTTPServer(("127.0.0.1", 0), Sahte)
    url = f"http://127.0.0.1:{sunucu.server_address[1]}/v1"
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    vekil = GECICI / "vekil_uc"
    vekil.mkdir()
    pol_yol = GECICI / "policy_uc.toml"
    try:
        print("\n2) Limit dolunca ayni gorev siradaki modelle surer")
        politika_yaz(pol_yol, url, {
            "anahtarsiz": {"ad": "Gemini yedek", "saglayici": "gemini", "modeller": ["gemini-x"],
                           "anahtar_yuvasi": "api-anahtarsiz"},
            "uzak": {"ad": "Uzak", "saglayici": "openai", "taban_url": "https://api.deepseek.com/v1",
                     "modeller": ["uzak-model"], "anahtar_yuvasi": "api-uzak"},
            "birinci": {"ad": "Birinci", "saglayici": "openai", "taban_url": url,
                        "modeller": ["gunluk-dolu", "dakika-dolu"], "anahtar_yuvasi": "api-birinci"},
            "ikinci": {"ad": "İkinci", "saglayici": "openai", "taban_url": url,
                       "modeller": ["calisan"], "anahtar_yuvasi": "api-ikinci"},
        }, ["anahtarsiz", "uzak", "birinci", "ikinci"])
        veri = kostur(pol_yol, vekil)
        modeller = [i.get("model") for i in Sahte.istekler]
        dogrula(modeller == ["gunluk-dolu", "dakika-dolu", "dakika-dolu", "calisan"],
                f"istek sirasi: gunluk dolu -> dakika (1 adim) -> dolu -> calisan ({modeller})")
        dogrula("bitti (calisan, arac_sonucu_gordu=True)" in veri.get("metin", ""),
                f"gorev tamamlandi, yeni model arac gecmisini gordu ({veri.get('metin', '')[:80]})")
        gecis = [o["veri"] for o in veri.get("olaylar", []) if o["tip"] == "MODEL_GECIS"]
        dogrula(any(g.get("sebep") == "anahtar" and "Gemini yedek" in g.get("eski", "") for g in gecis),
                "anahtari olmayan baglanti atlandi ve soylendi")
        dogrula(any(g.get("sebep") == "anahtar" and "Uzak" in g.get("eski", "") for g in gecis),
                "anahtarsiz UZAK OpenAI-uyumlu sunucu denenmeden atlandi (yalnizca yerel sunucu anahtarsiz calisir)")
        limit = [g for g in gecis if g.get("sebep") == "limit"]
        dogrula([(g["eski"], g["yeni"]) for g in limit] == [("Birinci · gunluk-dolu", "Birinci · dakika-dolu"),
                                                             ("Birinci · dakika-dolu", "İkinci · calisan")],
                f"iki gecis olayi, etiketleriyle ({[(g['eski'], g['yeni']) for g in limit]})")
        dogrula(not [o for o in veri.get("olaylar", []) if o["tip"] == "HATA"], "gorevde HATA olayi yok")
        durum = json.loads((vekil / "model_durumu.json").read_text(encoding="utf-8"))
        gun = durum.get("birinci|gunluk-dolu", ""); dak = durum.get("birinci|dakika-dolu", "")
        dogrula(gun.endswith("00:00:00") and dak and not dak.endswith("00:00:00"),
                f"gunluk limit gun sonuna, dakikalik kisa sureye isaretlendi ({gun}, {dak})")
        dogrula("sk-" not in json.dumps(durum), "durum dosyasinda anahtar yok")

        print("\n3) Sonraki gorev dolu modelleri atlar")
        Sahte.istekler.clear()
        veri = kostur(pol_yol, vekil)
        modeller = [i.get("model") for i in Sahte.istekler]
        dogrula(modeller[:1] == ["calisan"], f"dogrudan musait modelle basladi ({modeller})")

        print("\n3b) Sohbet ekranindan secilen model: mod ne olursa olsun o modelle baslar")
        (vekil / "model_durumu.json").unlink(missing_ok=True)
        for mod in ("hizli", "azami"):
            Sahte.istekler.clear()
            kostur(pol_yol, vekil, mod, secili="ikinci/calisan")
            modeller = [i.get("model") for i in Sahte.istekler]
            dogrula(modeller[:1] == ["calisan"], f"{mod} modu, secili 'calisan': ilk istek onunla ({modeller})")
        Sahte.istekler.clear()
        kostur(pol_yol, vekil, "azami")
        dogrula([i.get("model") for i in Sahte.istekler][:1] == ["gunluk-dolu"],
                "secim yoksa azami mod da zincirin basindan baslar (mod model secmez)")

        print("\n4) Hepsi doluysa acik mesaj")
        Sahte.istekler.clear()
        shutil.rmtree(vekil); vekil.mkdir()
        politika_yaz(pol_yol, url, {
            "birinci": {"ad": "Birinci", "saglayici": "openai", "taban_url": url, "modeller": ["gunluk-dolu"],
                        "anahtar_yuvasi": "api-birinci"},
            "ikinci": {"ad": "İkinci", "saglayici": "openai", "taban_url": url, "modeller": ["bakiye-bitti"],
                       "anahtar_yuvasi": "api-ikinci"},
        }, ["birinci", "ikinci"])
        veri = kostur(pol_yol, vekil)
        dogrula("bütün modellerin kullanım limiti doldu" in veri.get("metin", ""),
                f"zincir tukendi mesaji ({veri.get('metin', '')[:90]})")
        hata = [o["veri"] for o in veri.get("olaylar", []) if o["tip"] == "HATA"]
        dogrula(hata and hata[-1].get("kota") == "True" and hata[-1].get("zincir") == "True",
                "arayuze kota + zincir bayragi gitti")
        durum = json.loads((vekil / "model_durumu.json").read_text(encoding="utf-8"))
        dogrula(durum.get("ikinci|bakiye-bitti", "").endswith("00:00:00"), "402 bakiye: gun sonuna isaretlendi")
        dogrula([i.get("model") for i in Sahte.istekler] == ["gunluk-dolu", "bakiye-bitti"],
                "her model bir kez denendi, bekleme yok")
    finally:
        sunucu.shutdown()


def main() -> int:
    try:
        ayar_testleri()
        gecis_testleri()
    finally:
        shutil.rmtree(GECICI, ignore_errors=True)
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
