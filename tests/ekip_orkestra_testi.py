# ekip_orkestra_testi.py — ekip gorevi ucta uca: planlayici -> plan onayi -> 2 isci
# sureci (paralel) -> birlestirici. Model sahte (yerel OpenAI-uyumlu sunucu):
# istegin icerigine gore planlayici/isci/birlestirici rolunu oynar.
#
# Surucu ayri surecte kosar (LIMINA_POLICY = gecici politika, LIMINA_VEKIL_KOK =
# gecici kok) ki bu testin kendisi kullanicinin gercek policy.toml/gunlugune
# dokunmasin; isciler de o kokten turer.
#
#   python tests/ekip_orkestra_testi.py
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from limina import kurulum
kurulum.politikayi_hazirla(sessiz=True)
from limina import ceviri, ekip, PROJE_KOKU
from limina.gate import Politika

ceviri.dil_ayarla("tr")
HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


ALAN: Path = Path()


class SahteModel(BaseHTTPRequestHandler):
    istekler: list[dict] = []
    kilit = threading.Lock()

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        govde = json.loads(self.rfile.read(n) or b"{}")
        with SahteModel.kilit:
            SahteModel.istekler.append(govde)
        if govde.get("model") == "sahte-yazar":
            # Ajanin kendi modeli: kullanim doldu. Isci ayni baglantinin diger
            # modeline gecmeli (model_zinciri: kendi baglantisi > genel zincir).
            veri = json.dumps({"error": {"message": "Rate limit exceeded per minute"}}).encode("utf-8")
            self.send_response(429); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(veri))); self.end_headers(); self.wfile.write(veri)
            return
        metin = json.dumps(govde.get("messages", []), ensure_ascii=False)
        araclar = {a.get("function", {}).get("name") for a in govde.get("tools", [])}
        if "plan_yaz" in araclar:
            args = {"alt_gorevler": [
                {"ad": "giris", "ajan": "yazar", "gorev": "Giriş bölümünü yaz: konuyu tanıt, iki paragraf.", "yollar": ["giris.md"]},
                {"ad": "sonuc", "ajan": "varsayilan", "gorev": "Sonuç bölümünü yaz: özet ve öneri, iki paragraf.", "yollar": ["sonuc/"]},
            ], "birlestirme": "İki bölümü rapor.md içinde birleştir."}
            mesaj = {"role": "assistant", "content": None, "tool_calls": [
                {"id": "p1", "type": "function", "function": {"name": "plan_yaz", "arguments": json.dumps(args, ensure_ascii=False)}}]}
        elif "ekip üyesisin" in metin and "'giris'" in metin:
            # isci giris: once panoya baslik kurali (sonuc'a), sonra kendi dosyasina yaz, sonra bitir
            arac_sonuclari = [m for m in govde.get("messages", []) if m.get("role") == "tool"]
            if len(arac_sonuclari) == 0:
                mesaj = {"role": "assistant", "content": None, "tool_calls": [{"id": "m1", "type": "function", "function": {
                    "name": "ekip_mesaj", "arguments": json.dumps({"kime": "sonuc", "metin": "Başlıkları '## ' ile yaz."})}}]}
            elif len(arac_sonuclari) == 1:
                mesaj = {"role": "assistant", "content": None, "tool_calls": [{"id": "w1", "type": "function", "function": {
                    "name": "write_file", "arguments": json.dumps({"path": str(ALAN / "giris.md"), "content": "# Giriş\nKonu tanıtımı."})}}]}
            else:
                mesaj = {"role": "assistant", "content": "Giriş yazıldı."}
        elif "ekip üyesisin" in metin and "'sonuc'" in metin:
            # isci sonuc: giris'in pano mesaji (otomatik teslim ya da ekip_gelen) gelmeden yazmaz
            mesaj_geldi = 'ekip:giris' in metin
            yazdi = any(m.get("role") == "tool" and "sonuc.md" in json.dumps(m, ensure_ascii=False) for m in govde.get("messages", []))
            gelen_denemesi = sum(1 for m in govde.get("messages", []) if m.get("role") == "assistant" and "ekip_gelen" in json.dumps(m))
            if yazdi:
                mesaj = {"role": "assistant", "content": "Sonuç yazıldı (başlık kuralına uydum)."}
            elif mesaj_geldi or gelen_denemesi >= 6:
                icerik = "## Sonuç\nÖzet." if mesaj_geldi else "# Sonuç\nÖzet."
                mesaj = {"role": "assistant", "content": None, "tool_calls": [{"id": "w2", "type": "function", "function": {
                    "name": "write_file", "arguments": json.dumps({"path": str(ALAN / "sonuc" / "sonuc.md"), "content": icerik})}}]}
            else:
                time.sleep(0.5)
                mesaj = {"role": "assistant", "content": None, "tool_calls": [{"id": f"g{gelen_denemesi}", "type": "function", "function": {
                    "name": "ekip_gelen", "arguments": "{}"}}]}
        elif "ekip üyesisin" in metin and "'yazar'" in metin:
            # tek ajan gorevi: klasor yok -> once mkdir (isci notu), sonra yaz, sonra bitir
            arac_sonuclari = [m for m in govde.get("messages", []) if m.get("role") == "tool"]
            if len(arac_sonuclari) == 0:
                mesaj = {"role": "assistant", "content": None, "tool_calls": [{"id": "k1", "type": "function", "function": {
                    "name": "mkdir", "arguments": json.dumps({"path": str(ALAN / "yazar")})}}]}
            elif len(arac_sonuclari) == 1:
                mesaj = {"role": "assistant", "content": None, "tool_calls": [{"id": "k2", "type": "function", "function": {
                    "name": "write_file", "arguments": json.dumps({"path": str(ALAN / "yazar" / "not.md"), "content": "Kısa not."})}}]}
            elif len(arac_sonuclari) == 2:
                # Dusunce Agi: isci kendi agini kurar (isci araclarinda ag_kur var)
                mesaj = {"role": "assistant", "content": None, "tool_calls": [{"id": "k3", "type": "function", "function": {
                    "name": "ag_kur", "arguments": json.dumps({"ad": "yazar notlari", "dugumler": [
                        {"kimlik": "fikir1", "tur": "fikir", "baslik": "Konu", "metin": "Özet"},
                        {"kimlik": "kural1", "tur": "kural", "baslik": "Biçim", "metin": "Kısa yaz"}],
                        "baglantilar": [{"kaynak": "fikir1", "hedef": "kural1"}]}, ensure_ascii=False)}}]}
            else:
                mesaj = {"role": "assistant", "content": "Not yazıldı: yazar/not.md."}
        elif "birleştiricisisin" in metin:
            mesaj = {"role": "assistant", "content": "Birleştirme tamam: giris.md ve sonuc/sonuc.md tutarlı."}
        else:
            mesaj = {"role": "assistant", "content": "tamam"}
        yanit = {"choices": [{"message": mesaj, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        veri = json.dumps(yanit, ensure_ascii=False).encode("utf-8")
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(veri))); self.end_headers(); self.wfile.write(veri)


SURUCU = r'''
import json, sys
from pathlib import Path
sys.path.insert(0, ".")
from limina import ekip, ceviri
ceviri.dil_ayarla("tr")
import limina.vekil_v0 as v
from limina.olaylar import Oturum, sabit_cevap
olaylar = []
def yayinla(o):
    # yapi korunur (ofis durum makinesi args/istek sozluklerini okur), uzun metin kisalir
    olaylar.append({"tip": o.tip.name, "veri": ekip._kayit_degeri(o.veri or {})})
oturum = Oturum(onay_saglayici=sabit_cevap(sys.argv[2]), yayinla=yayinla)
if len(sys.argv) > 3 and sys.argv[3] == "tek":
    r = ekip.tek_ajan_gorevi("Kısa bir not yaz: konunun özeti, iki cümle.", "yazar", "dengeli", oturum, None,
                             Path(sys.argv[1]), yol=sys.argv[4] if len(sys.argv) > 4 else "")
else:
    r = ekip.ekip_gorevi("Konu hakkında kısa bir rapor hazırla.", "dengeli", oturum, None, Path(sys.argv[1]))
print("SONUC_JSON " + json.dumps({"metin": r, "olaylar": olaylar}, ensure_ascii=False))
'''


def main() -> int:
    global ALAN
    gercek = Politika(PROJE_KOKU / "policy.toml")
    ALAN = (Path(gercek.yazma[0]) / f"_ekip_orkestra_{os.getpid()}").resolve()   # kosu basina: paralel kosular birbirini silmesin
    shutil.rmtree(ALAN, ignore_errors=True); ALAN.mkdir(parents=True); (ALAN / "sonuc").mkdir()
    kok = Path(tempfile.mkdtemp(prefix="limina_orkestra_"))
    sunucu = HTTPServer(("127.0.0.1", 0), SahteModel)
    port = sunucu.server_address[1]
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    try:
        import tomllib
        ham = tomllib.load(open(PROJE_KOKU / "policy.toml", "rb"))
        ham["model"] = {**ham.get("model", {}), "saglayici": "openai", "taban_url": f"http://127.0.0.1:{port}/v1",
                        "varsayilan": "sahte-hizli", "guclu": "sahte-guclu"}
        # Kullanicinin kendi API baglantilari sahte sunucuyu golgelemesin
        ham.pop("baglantilar", None)
        for k in ("zincir", "derin"):
            ham["model"].pop(k, None)
        # Test kendi iki baglantisini kurar: 'ana' (planlayici, varsayilan isci,
        # birlestirici) ve 'ikinci' (yazar ajaninin baglantisi, iki model).
        adres = f"http://127.0.0.1:{port}/v1"
        ham["baglantilar"] = {
            "ana": {"ad": "Sahte", "saglayici": "openai", "taban_url": adres, "modeller": ["sahte-hizli", "sahte-guclu"]},
            "ikinci": {"ad": "Ikinci", "saglayici": "openai", "taban_url": adres, "modeller": ["sahte-yazar", "sahte-yazar2"]}}
        ham["model"]["zincir"] = ["ana", "ikinci"]
        ham["ajanlar"] = {"yazar": {"baglanti": "ikinci", "model": "sahte-yazar", "rol": "Metin yazar."}}
        ham["mcp"] = {}
        politika = kok / "policy.toml"
        politika.write_text(ekip.toml_yaz(ham), encoding="utf-8")
        vekil_kok = kok / "vekil"; vekil_kok.mkdir()
        (vekil_kok / "credentials.json").write_text(json.dumps({"openai": "sk-sahte-varsayilan-1"}), encoding="utf-8")
        ortam = dict(os.environ)
        ortam.update({"LIMINA_POLICY": str(politika), "LIMINA_VEKIL_KOK": str(vekil_kok), "PYTHONIOENCODING": "utf-8"})
        for k in ("GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            ortam.pop(k, None)
        surucu = kok / "surucu.py"; surucu.write_text(SURUCU, encoding="utf-8")

        print("\n1) Plan reddedilirse hicbir isci baslamaz")
        r = subprocess.run([sys.executable, str(surucu), str(ALAN), "h"], env=ortam, cwd=str(PROJE_KOKU),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        satir = next((s for s in r.stdout.splitlines() if s.startswith("SONUC_JSON ")), "")
        veri = json.loads(satir[len("SONUC_JSON "):]) if satir else {}
        if not veri:
            print("      stdout:", r.stdout[-800:], "\n      stderr:", r.stderr[-800:])
        dogrula(bool(veri) and "reddedildi" in veri.get("metin", ""), f"red: {veri.get('metin', '')[:80]}")
        dogrula(not (ALAN / "giris.md").exists() and not list((ALAN / "sonuc").iterdir()), "hicbir dosya yazilmadi")
        onay = [o for o in veri.get("olaylar", []) if o["tip"] == "ONAY_GEREKLI"]
        dogrula(len(onay) == 1 and "ekip_plan" in str(onay[0]), "tek onay karti: ekip_plan")
        dogrula(len([o for o in veri.get("olaylar", []) if o["tip"] == "ARAC_CAGRILDI"]) == 0, "isci baslatilmadi")
        planlar = [i for i in SahteModel.istekler if any(a.get("function", {}).get("name") == "plan_yaz" for a in i.get("tools", []))]
        dogrula(planlar and planlar[0].get("model") == "sahte-hizli",
                "planlayici zincirin basindaki modelle (mod model secmez), plan_yaz zorlanmis")
        dogrula(planlar and "yazar" in json.dumps(planlar[0]["messages"], ensure_ascii=False), "planlayici ajan listesini gordu")
        SahteModel.istekler.clear()

        print("\n2) Plan onaylanir: 2 isci paralel, sonra birlestirici")
        t0 = time.time()
        r = subprocess.run([sys.executable, str(surucu), str(ALAN), "e"], env=ortam, cwd=str(PROJE_KOKU),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        satir = next((s for s in r.stdout.splitlines() if s.startswith("SONUC_JSON ")), "")
        veri = json.loads(satir[len("SONUC_JSON "):]) if satir else {}
        if not veri:
            print("      stdout:", r.stdout[-1500:], "\n      stderr:", r.stderr[-1500:])
        if os.environ.get("LIMINA_OFIS_DOKUM"):
            # tests/ofis_arayuz_testi.py bu gercek olay dizisini ofis durum makinesine verir
            Path(os.environ["LIMINA_OFIS_DOKUM"]).write_text(json.dumps(veri.get("olaylar", []), ensure_ascii=False),
                                                             encoding="utf-8")
        kayit = sorted((vekil_kok / "ekip").glob("*/" + ekip.OFIS_OLAYLARI))[-1:]     # son kosu (onaylanan)
        kayitli = [json.loads(s) for k in kayit for s in k.read_text(encoding="utf-8").splitlines() if s.strip()]
        dogrula(len(kayit) == 1 and any(k["tip"] == "arac_cagrildi" and k["veri"].get("masa") for k in kayitli)
                and all(isinstance(k.get("t"), (int, float)) for k in kayitli),
                f"kosunun ofis olay kaydi yazildi ({len(kayitli)} olay, zaman damgali)")
        print(f"      sure {time.time() - t0:.1f} sn, metin: {veri.get('metin', '')[:100]}")
        dogrula(bool(veri) and "Birleştirme tamam" in veri.get("metin", ""), "birlestirici kostu ve sonucu dondu")
        dogrula((ALAN / "giris.md").exists() and (ALAN / "sonuc" / "sonuc.md").exists(), "iki isci kendi yollarina yazdi")
        olaylar = veri.get("olaylar", [])
        ajanli = [o for o in olaylar if o["veri"].get("ajan")]
        dogrula({o["veri"]["ajan"] for o in ajanli} >= {"giris", "sonuc"}, f"olay akisinda iki ajan etiketi ({len(ajanli)} olay)")
        aktarilan = [o for o in olaylar if o["tip"] == "ARAC_CAGRILDI" and o["veri"].get("arac") == "write_file"]
        if not aktarilan:
            print("      olaylar:", [(o["tip"], o["veri"].get("arac"), o["veri"].get("ajan")) for o in olaylar][:20])
        dogrula({o["veri"].get("ajan") for o in aktarilan} == {"giris", "sonuc"},
                "iscilerin write_file cagrilari ana akisa ajan etiketiyle aktarildi")
        modeller = [i.get("model") for i in SahteModel.istekler]
        dogrula(modeller.count("sahte-yazar") == 1, "yazar ajani once KENDI modelini denedi (429)")
        dogrula("sahte-yazar2" in modeller, "limit dolunca AYNI baglantinin diger modeline gecti")
        dogrula("sahte-hizli" in modeller, "varsayilan isci ve birlestirici zincirin basiyla")
        gecis = [o for o in olaylar if o["tip"] == "MODEL_GECIS"]
        dogrula(bool(gecis) and all(o["veri"].get("ajan") == "giris" and "sahte-yazar2" in o["veri"].get("yeni", "")
                                    for o in gecis), f"model gecisi ana akisa aktarildi, genel zincire tasmadi ({len(gecis)})")

        # Ofis: olaylarda masa ve acik rol olaylari (docs/OFIS_TASARIM.md Faz 1)
        dogrula(all(o["veri"].get("masa") for o in olaylar if o["tip"] == "ARAC_CAGRILDI"),
                "her arac_cagrildi olayinda masa alani var")
        masalar = {(o["veri"].get("ajan"), o["veri"].get("arac")): o["veri"].get("masa")
                   for o in olaylar if o["tip"] == "ARAC_CAGRILDI"}
        dogrula(masalar.get(("giris", "write_file")) == "dosya" and masalar.get(("giris", "ekip_mesaj")) == "istisare"
                and masalar.get(("giris", "ekip_isci")) == "bekleme", f"isci olaylari dogru masada ({masalar})")
        dogrula(any(o["tip"] == "ADIM_BASLADI" and o["veri"].get("ajan") == "sonuc" for o in olaylar),
                "iscinin ADIM_BASLADI olayi ajan etiketiyle aktarildi")
        dogrula(any(o["tip"] == "OLCUM" and o["veri"].get("ajan") for o in olaylar), "iscinin OLCUM olayi aktarildi")
        roller = [(o["veri"].get("rol"), o["veri"].get("durum")) for o in olaylar
                  if o["tip"] == "EKIP_MESAJ" and o["veri"].get("rol")]
        dogrula(roller == [("planlayici", "calisiyor"), ("planlayici", "bitti"),
                           ("birlestirici", "calisiyor"), ("birlestirici", "bitti")], f"planlayici/birlestirici olaylari ({roller})")
        birlestirici = [i for i in SahteModel.istekler if "birleştiricisisin" in json.dumps(i.get("messages"), ensure_ascii=False)]
        dogrula(birlestirici and "<untrusted_content" in json.dumps(birlestirici[0]["messages"], ensure_ascii=False),
                "birlestirici raporlari untrusted_content icinde aldi")
        dogrula(birlestirici and "giris.md" in json.dumps(birlestirici[0]["messages"], ensure_ascii=False),
                "birlestirici iscilerin yazdigi dosyalari gordu")
        # PANO: giris -> sonuc mesaji ulasti mi, sonuc ona gore mi yazdi
        pano_ok = (ALAN / "sonuc" / "sonuc.md").read_text(encoding="utf-8").startswith("## ")
        dogrula(pano_ok, "sonuc iscisi giris'in pano mesajini ALDI ve baslik kuralina uydu (## )")
        teslim = [o for o in olaylar if o["tip"] == "EKIP_MESAJ"]
        dogrula(any(o["veri"].get("kimden") == "giris" and o["veri"].get("kime") == "sonuc" for o in teslim),
                "pano mesaji ana olay akisina EKIP_MESAJ olarak dustu")
        dogrula(birlestirici and "[Ekip panosu]" in json.dumps(birlestirici[0]["messages"], ensure_ascii=False)
                and "Başlıkları" in json.dumps(birlestirici[0]["messages"], ensure_ascii=False),
                "birlestirici panoyu gordu")
        gunluk = [json.loads(l) for l in (vekil_kok / "journal.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        dogrula({k.get("ajan") for k in gunluk if k.get("tip") == "yazma"} >= {"giris", "sonuc"}, "gunlukte iki ajanin yazmalari etiketli")
        ekip_klasor = vekil_kok / "ekip"
        tarifler = list(ekip_klasor.rglob("tarif.json"))
        dogrula(len(tarifler) == 2, f"isci klasorleri olustu ({len(tarifler)} tarif)")
        for tf in tarifler:
            pol = Politika(tf.parent / "policy.toml")
            dogrula(len(pol.yazma) == 1 and ALAN in pol.yazma[0].parents, f"{tf.parent.name}: yazma koku tek ve alanin icinde ({pol.yazma[0].name})")

        print("\n3) Tek ajana dogrudan gorev: planlayici ve birlestirici yok, ayni isci yolu")

        def kostur(*ek):
            SahteModel.istekler.clear()
            r = subprocess.run([sys.executable, str(surucu), str(ALAN), *ek], env=ortam, cwd=str(PROJE_KOKU),
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            satir = next((s for s in r.stdout.splitlines() if s.startswith("SONUC_JSON ")), "")
            if not satir:
                print("      stdout:", r.stdout[-1200:], "\n      stderr:", r.stderr[-1200:])
            return json.loads(satir[len("SONUC_JSON "):]) if satir else {}
        veri = kostur("h", "tek")
        dogrula("reddedildi" in veri.get("metin", "") and not (ALAN / "yazar").exists(), "ret: ajan baslamadi, klasor yok")
        onay = [o for o in veri.get("olaylar", []) if o["tip"] == "ONAY_GEREKLI"]
        dogrula(len(onay) == 1 and "yazar" in str(onay[0]) and onay[0]["veri"]["istek"]["args"].get("tek") == "yazar",
                "tek onay karti: ekip_plan, yazma yolu ve ajan gorunur")
        veri = kostur("e", "tek", "../disari")
        dogrula("kurulamadı" in veri.get("metin", "") and not any(o["tip"] == "ONAY_GEREKLI" for o in veri.get("olaylar", [])),
                f"calisma alani disi yol: plan_dogrula reddetti, onay bile sorulmadi ({veri.get('metin', '')[:70]})")
        veri = kostur("e", "tek")
        print(f"      metin: {veri.get('metin', '')[:120]!r}")
        dogrula((ALAN / "yazar" / "not.md").exists(), "onay: ajan kendi klasorunu mkdir ile acip yazdi")
        dogrula("yazar/not.md" in veri.get("metin", "").replace("\\", "/") and "Not yazıldı" in veri.get("metin", ""),
                "sonuc: ajanin raporu + gunlukten dogrulanmis dosya")
        istekler = json.dumps(SahteModel.istekler, ensure_ascii=False)
        dogrula("plan_yaz" not in istekler and "birleştiricisisin" not in istekler, "planlayici ve birlestirici cagrilmadi")
        ag_dosyasi = vekil_kok / "aglar" / "yazar-notlari.json"
        ag_verisi = json.loads(ag_dosyasi.read_text(encoding="utf-8")) if ag_dosyasi.exists() else {}
        dogrula(len(ag_verisi.get("dugumler", [])) == 2 and all(d.get("kaynak") == "ajan" for d in ag_verisi["dugumler"]),
                "isci Dusunce Agi kurdu; dugumler 'ajan notu' isaretli")
        dogrula(any(o["tip"] == "ARAC_CAGRILDI" and o["veri"].get("arac") == "ag_kur" and o["veri"].get("masa") == "ag"
                    for o in veri.get("olaylar", [])), "ag_kur olayi Dusunce Agi kosesinde (masa 'ag')")
        dogrula({i.get("model") for i in SahteModel.istekler} <= {"sahte-yazar", "sahte-yazar2"},
                "isci ajanin kendi baglantisiyla calisti")
        ol = veri.get("olaylar", [])
        dogrula(any(o["tip"] == "EKIP_MESAJ" and o["veri"].get("tek") == "yazar" for o in ol)
                and any(o["tip"] == "ARAC_CAGRILDI" and o["veri"].get("arac") == "write_file" and o["veri"].get("masa") == "dosya" for o in ol),
                "olaylar: tek ajan kosusu isaretli, yazma dosya masasinda")
    finally:
        sunucu.shutdown()
        shutil.rmtree(kok, ignore_errors=True)
        shutil.rmtree(ALAN, ignore_errors=True)
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
