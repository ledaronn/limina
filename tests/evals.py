# evals.py — regresyon kosucusu.
# python tests/evals.py [--kapi]  -> kapi+kod testleri (11+5, bedava, anlik)
# python tests/evals.py --hepsi   -> yukarisi + ajan testleri (5, yavas, kota harcar)
# Bayrak verilmezse --kapi varsayilir (bedava taraf hep calisir).
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # proje koku -> 'pevrai' paketi
from pevrai import PROJE_KOKU
from pevrai.gate import Politika
from pevrai.olaylar import OlayTipi, Oturum, sabit_cevap

KOK = PROJE_KOKU
from pevrai import kurulum
# Beklenen metinler (tasks.yaml) KAYNAK DILDE; kisisel arayuz.toml ayarina bagli olamaz.
from pevrai import ceviri as _ceviri
_ceviri.dil_ayarla("tr")
kurulum.politikayi_hazirla(sessiz=True)
POLITIKA = Politika(KOK / "policy.toml")


def fixture_politikasi() -> Politika:
    """Kapi testleri icin SABIT bir politika (kisisel policy.toml'dan bagimsiz).

    Neden: kapi testleri "su kok yazilabilir, su degil" iddiasini olcuyor.
    Kullanicinin kendi policy.toml'u degisince (ornegin Downloads yazma koku
    yapilinca) test kodda hicbir sey bozulmadan kalirdi — olctugu sey makineye
    kayardi. Fixture policy.example.toml'un [araclar]/[model] bolumlerini alir,
    yalnizca koklerini sabitler: yazma = gecici kum/, okuma = kum + Downloads +
    Desktop. Boylece "okunabilen bir kok otomatik yazilabilir DEGILDIR" iddiasi
    her makinede ayni sekilde sinanir.

    mcp_semasi_testi ve ajan testleri GERCEK policy.toml ile kosmaya devam eder:
    onlarin isi zaten kurulumun kendisini dogrulamak."""
    import tempfile
    import tomllib

    from pevrai import ekip

    d = Path(tempfile.mkdtemp(prefix="pevrai_evals_"))
    kum = d / "kum"
    kum.mkdir()
    with open(KOK / "policy.example.toml", "rb") as f:
        ham = tomllib.load(f)
    ham["filesystem"] = {**ham.get("filesystem", {}),
                         "okuma_koklari": [kum.as_posix(), (Path.home() / "Downloads").as_posix(),
                                           (Path.home() / "Desktop").as_posix()],
                         "yazma_koklari": [kum.as_posix()]}
    ham["mcp"] = {}
    ham["profiller"] = {}      # sablondaki profiller {PROJE} yer tutuculu; kapi testleri profil kullanmaz
    yol = d / "policy.toml"
    yol.write_text(ekip.toml_yaz(ham), encoding="utf-8")
    return Politika(yol)


def yer_tutuculari_doldur(veri, politika=None):
    """tasks.yaml'daki {KUM}/{EV}/{PROJE} yer tutucularini doldurur. Gorevler
    kisisel yol tasimasin diye: {KUM} verilen politikanin ilk yazma koku,
    {EV} ev klasoru. politika=None -> gercek policy.toml (ajan testleri)."""
    politika = politika or POLITIKA
    kum = str(politika.calisma or Path.home() / "Pevrai")
    degerler = {"{KUM}": kum, "{EV}": str(Path.home()), "{PROJE}": str(KOK),
                # buyuk harfli kok: Windows yollari harf duyarsiz, mesru kullanim
                "{KUM_BUYUK}": kum.upper(),
                "{KUM_URI}": Path(kum).as_posix()}
    if isinstance(veri, str):
        for k, v in degerler.items():
            veri = veri.replace(k, v)
        return veri
    if isinstance(veri, list):
        return [yer_tutuculari_doldur(x, politika) for x in veri]
    if isinstance(veri, dict):
        return {k: yer_tutuculari_doldur(v, politika) for k, v in veri.items()}
    return veri


def kapi_testleri(gorevler: list[dict], politika: Politika) -> tuple[int, int]:
    gecen = 0
    for g in gorevler:
        karar = politika.karar(g["arac"], g["args"])
        ok = karar.sonuc == g["beklenen"]
        gecen += ok
        isaret = "GECTI" if ok else "KALDI"
        print(f"  [{isaret}] {g['ad']}")
        if not ok:
            print(f"          beklenen {g['beklenen']}, gelen {karar.sonuc}: {karar.gerekce}")
    return gecen, len(gorevler)


def kod_testleri(gorevler: list[dict]) -> tuple[int, int]:
    """Kapida DEGIL, arac fonksiyonunun ICINDE duran reddleri sinar.

    Neden ayri: kart/TC kalibi ve parola alani reddi gate.py'de degil,
    vekil_v0.browser_fill'in icinde. Kapi bunlari hic gormez. Daha once bu
    kontrol bir kapi testi gibi yazilmisti ve "browser_fill'in varsayilan
    riski ASK mi" diye bakiyordu — adinda iddia ettigi seyi hic olcmuyordu.
    Risk seviyesi WRITE_HAFIF'e cekilince tesaduf bozuldu ve ortaya cikti.

    Bu testler model cagirmaz ve tarayiciya dokunmaz: reddler tarayici
    cagrilmadan ONCE donuyor.
    """
    from pevrai import vekil_v0
    gecen = 0
    for g in gorevler:
        fn = getattr(vekil_v0, g["fonksiyon"], None)
        if fn is None:
            print(f"  [KALDI] {g['ad']} — '{g['fonksiyon']}' fonksiyonu yok")
            continue
        try:
            sonuc = str(fn(None, g.get("args", {})))
        except Exception as e:
            print(f"  [KALDI] {g['ad']} — istisna: {type(e).__name__}: {e}")
            continue

        hatalar = [f"'{k}' cevapta yok" for k in g.get("bekleniyor_metinde", [])
                   if k.lower() not in sonuc.lower()]
        for yasak in g.get("yasak_metinde", []):
            if yasak.lower() in sonuc.lower():
                hatalar.append(f"YASAK ifade cevapta: '{yasak}'")

        if hatalar:
            print(f"  [KALDI] {g['ad']}")
            for h in hatalar:
                print(f"          {h}")
            print(f"          gelen: {sonuc[:120]}")
        else:
            gecen += 1
            print(f"  [GECTI] {g['ad']}")
    return gecen, len(gorevler)


def mcp_semasi_testi() -> tuple[int, int]:
    """Modele gosterilen arac adlari kumesi policy.toml [araclar] ile ayni mi.

    vekil_v0 import aninda KOPRU.bagla() ile baglanan MCP sunucularini
    (su an: converter) kullanir — ekstra baglanti maliyeti yok, zaten
    kod_testleri'nin importu tetikliyor. policy.toml'da SINIFLANDIRILMAMIS
    bir MCP araci sessizce goruntude kalirsa (filtre bozulursa) burada
    yakalanir; yeni bir okuma araci siniflandirmayi unutulursa da.
    """
    from pevrai import vekil_v0
    vekil_v0.mcp_baglan(sessiz=True)      # MCP artik tembel: kesif icin acikca baglan
    # ARAC saglayicidan bagimsiz sema listesi; adlar gercek ("converter.convert").
    gosterilen = {fd["name"] for fd in vekil_v0.ARAC}
    hatalar = []
    for tam_ad in vekil_v0.KOPRU.araclar:
        siniflandirilmis = tam_ad in vekil_v0.POLITIKA.araclar
        gorunuyor = tam_ad in gosterilen
        if siniflandirilmis and not gorunuyor:
            hatalar.append(f"'{tam_ad}' policy.toml'da siniflandirilmis ama modele GORUNMUYOR")
        elif not siniflandirilmis and gorunuyor:
            hatalar.append(f"'{tam_ad}' policy.toml'da YOK ama modele gorunuyor (filtre calismiyor)")

    if hatalar:
        print("  [KALDI] MCP arac semasi policy.toml ile uyusmuyor")
        for h in hatalar:
            print(f"          {h}")
        return 0, 1
    print(f"  [GECTI] MCP arac semasi policy.toml ile uyusuyor ({len(vekil_v0.KOPRU.araclar)} arac tarandi)")
    return 1, 1


def ajan_testleri(gorevler: list[dict]) -> tuple[int, int]:
    from pevrai import vekil_v0
    gecen = 0
    # Gorev basina sure + token, sonda toplam. Faz 6'nin ikinci kabul olcutu
    # ("gorev basina maliyet biliniyor") bunu OLCUM olayindan bedavaya cikariyor —
    # _olcum_yayinla zaten her adimda girdi/cikti token sayisini yayinliyordu.
    olcum_ozeti: list[dict] = []

    # Ornek dosyalar (tuzak.html, deneme.txt...) calisma klasorune; var olana dokunulmaz.
    hedef = Path(yer_tutuculari_doldur("{KUM}"))
    for ornek in sorted((KOK / "evals" / "ornek").iterdir()):
        if ornek.is_file() and ornek.name != "README.md" and not (hedef / ornek.name).exists():
            shutil.copy2(ornek, hedef / ornek.name)
    if not (hedef / "README.md").exists():
        (hedef / "README.md").write_text("# Pevrai\n\nPevrai ajaninin calisma klasoru.\n", encoding="utf-8")

    for g in gorevler:
        print(f"  ... {g['ad']}")
        vekil_v0.CAGRILAN_ARACLAR = []
        # Arac cagrilarinin TAM ARGUMANLARI (arac_arg_esit icin). CAGRILAN_ARACLAR
        # yalnizca ad tutuyor — "hangi arac cagrildi" sorusuna yeter ama "hangi
        # argumanla cagrildi" sorusuna yetmez. ARAC_CAGRILDI olayi ikisini de tasir
        # (bkz. DEVIR_FAZ6.md §7.3: assertion'lar nihai metne degil bu olaya baksin).
        cagrilar: list[dict] = []
        olcumler: list[dict] = []

        def yayinla(olay, _c=cagrilar, _o=olcumler) -> None:
            if olay.tip == OlayTipi.ARAC_CAGRILDI:
                _c.append(olay.veri)
            elif olay.tip == OlayTipi.OLCUM:
                _o.append(olay.veri)

        # Onay artik modul bayragi degil, enjekte edilen bir saglayici.
        # Her gorev kendi oturumunu alir -> toplu onaylar gorevler arasi sizmaz.
        oturum = Oturum(onay_saglayici=sabit_cevap(g.get("onay", "h")), yayinla=yayinla)
        baslangic = time.monotonic()
        try:
            sonuc = vekil_v0.calistir(g["gorev"], oturum=oturum, profil=g.get("profil"))
        except Exception as e:
            print(f"  [KALDI] {g['ad']} — istisna: {type(e).__name__}: {e}")
            continue
        finally:
            sure = time.monotonic() - baslangic
            girdi = sum(o.get("girdi_token", 0) for o in olcumler)
            cikti = sum(o.get("cikti_token", 0) for o in olcumler)
            olcum_ozeti.append({"ad": g["ad"], "sure_sn": sure, "girdi": girdi, "cikti": cikti})
            print(f"          ({sure:.1f} sn, {girdi} girdi + {cikti} cikti token)")

        hatalar = []
        for kelime in g.get("bekleniyor_metinde", []):
            if kelime.lower() not in sonuc.lower():
                hatalar.append(f"'{kelime}' cevapta yok")
        for yasak in g.get("yasak_araclar", []):
            if yasak in vekil_v0.CAGRILAN_ARACLAR:
                hatalar.append(f"YASAK arac cagrildi: {yasak}")
        for gerekli in g.get("gerekli_araclar", []):
            if gerekli not in vekil_v0.CAGRILAN_ARACLAR:
                hatalar.append(f"GEREKLI arac cagrilmadi: {gerekli}")
        sinir = g.get("max_cagri")
        if sinir and len(vekil_v0.CAGRILAN_ARACLAR) > sinir:
            hatalar.append(f"{len(vekil_v0.CAGRILAN_ARACLAR)} cagri, sinir {sinir}")
        kural = g.get("arac_arg_esit")
        if kural:
            for c in cagrilar:
                if c["arac"] != kural["arac"]:
                    continue
                gelen = c["args"].get(kural["alan"])
                if gelen != kural["deger"]:
                    hatalar.append(
                        f"{kural['arac']} {kural['alan']}={gelen!r} ile cagrildi "
                        f"(beklenen {kural['deger']!r}) — baska dosya ikame edilmis olabilir")

        # Eval kendi artigini toplar. kum/ ayni zamanda BASKA eval'lerin
        # girdisi (list_dir, README okuma) — bir kosunun cikitisi sonrakinin
        # sonucunu degistiriyordu. Elle "rm kum/t1.txt..." yapmak surdurulemez.
        for yol in g.get("temizle", []):
            try:
                Path(yol).unlink()
            except OSError:
                pass

        if hatalar:
            print(f"  [KALDI] {g['ad']}")
            for h in hatalar:
                print(f"          {h}")
        else:
            gecen += 1
            print(f"  [GECTI] {g['ad']}")

    if olcum_ozeti:
        toplam_sure = sum(o["sure_sn"] for o in olcum_ozeti)
        toplam_girdi = sum(o["girdi"] for o in olcum_ozeti)
        toplam_cikti = sum(o["cikti"] for o in olcum_ozeti)
        print("\n  --- gorev basina sure/token ---")
        for o in olcum_ozeti:
            print(f"  {o['sure_sn']:6.1f} sn  {o['girdi']:6d} girdi + {o['cikti']:5d} cikti  {o['ad']}")
        print(f"  {toplam_sure:6.1f} sn  {toplam_girdi:6d} girdi + {toplam_cikti:5d} cikti  TOPLAM")
    return gecen, len(gorevler)


if __name__ == "__main__":
    with open(KOK / "evals" / "tasks.yaml", encoding="utf-8") as f:
        veri = yer_tutuculari_doldur(yaml.safe_load(f))

    print("\n=== KAPI TESTLERI (model cagrilmaz, sabit fixture politika) ===")
    kapi_pol = fixture_politikasi()
    with open(KOK / "evals" / "tasks.yaml", encoding="utf-8") as f:
        veri_kapi = yer_tutuculari_doldur(yaml.safe_load(f), kapi_pol)
    g1, t1 = kapi_testleri(veri_kapi.get("kapi", []), kapi_pol)

    print("\n=== KOD SEVIYESI REDDLER (model cagrilmaz) ===")
    gk, tk = kod_testleri(veri.get("kod", []))

    print("\n=== MCP ARAC SEMASI (model cagrilmaz) ===")
    gs, ts = mcp_semasi_testi()

    g2 = t2 = 0
    if "--hepsi" in sys.argv:
        print("\n=== AJAN TESTLERI (kota harcar) ===")
        g2, t2 = ajan_testleri(veri.get("ajan", []))
    else:
        print("\n(ajan testleri atlandi (--kapi) — calistirmak icin: python tests/evals.py --hepsi)")

    print(f"\nSONUC: {g1 + gk + gs + g2}/{t1 + tk + ts + t2} gecti")
    sys.exit(0 if g1 + gk + gs + g2 == t1 + tk + ts + t2 else 1)
