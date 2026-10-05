# journal.py — yapılan işlerin kaydı ve geri alma.
# Dosya İÇERİKLERİ günlüğe yazılmaz; sadece yol, boyut ve yedek konumu.
from __future__ import annotations

import json
import os
import shutil
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from limina.ceviri import t

# Kisisel veri koku (gunluk, yedekler, cop, anahtar deposu, ekip dosyalari).
# LIMINA_VEKIL_KOK: testler ve tasinabilir kurulumlar icin; normalde ~/.vekil.
KOK = Path(os.environ["LIMINA_VEKIL_KOK"]) if os.environ.get("LIMINA_VEKIL_KOK") else Path.home() / ".vekil"
KAYIT = KOK / "journal.jsonl"
YEDEK = KOK / "yedek"
COP = KOK / "cop"
INEN = KOK / "indirilen"
KOTA = KOK / "kota.json"

ROLLER = ("varsayilan", "guclu")


def _hazirla() -> None:
    YEDEK.mkdir(parents=True, exist_ok=True)


def kota_artir(rol: str) -> None:
    """Bir istegi ROL bazinda sayar. Gun degisince sayaclar sifirlanir.

    ROL bazinda, model ADI bazinda degil: iki rol ayni model adini
    paylasabiliyor, ad bazli sayim ikisini tek kovada eritirdi.

    Hata yutulur — ama BUNUN BEDELI VAR: sayac yazilamazsa gunluk tavan
    duvari da sessizce calismaz (bkz. _model_cagir). Bilinen acik.
    """
    if rol not in ROLLER:
        return
    try:
        _hazirla()
        # Oku-artir-yaz: ekip iscileri ayri surecler; kilitsiz iki surec ayni
        # degeri okuyup ikisi de +1 yazinca bir istek sayilmazdi (tavan gevser).
        with _gunluk_kilidi():
            bugun = datetime.now().strftime("%Y-%m-%d")
            veri = {"tarih": bugun, "sayaclar": {}}
            if KOTA.exists():
                mevcut = json.loads(KOTA.read_text(encoding="utf-8"))
                if mevcut.get("tarih") == bugun:
                    veri = mevcut
            veri["sayaclar"][rol] = veri["sayaclar"].get(rol, 0) + 1
            KOTA.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def kota_sayaclari() -> dict[str, int]:
    """Bugun rol basina kac istek yapildi. SADECE SAYI.

    Tavan burada yok: tavan bir politika karari ve politikanin tek okuyucusu
    gate.Politika. Bu modul policy.toml'u okumaz — iki okuyucu iki dogru olur
    ve ayarlardan degisen tavan sessizce etkisiz kalirdi.
    """
    try:
        if not KOTA.exists():
            return {}
        veri = json.loads(KOTA.read_text(encoding="utf-8"))
        if veri.get("tarih") != datetime.now().strftime("%Y-%m-%d"):
            return {}
        return {r: int(n) for r, n in veri.get("sayaclar", {}).items() if r in ROLLER}
    except Exception:
        return {}


def cope_tasi(yol: Path) -> Path:
    """Kalıcı silme yok — dosya zaman damgalı adla çöp klasörüne taşınır."""
    COP.mkdir(parents=True, exist_ok=True)
    damga = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    hedef = COP / f"{damga}__{yol.name}"
    shutil.move(str(yol), str(hedef))
    return hedef


def yedekle(yol: Path) -> str | None:
    """Dosyanın üzerine yazmadan ÖNCE mevcut halini kopyalar.
    Dosya yoksa None döner (geri alma = silme olur)."""
    _hazirla()
    if not yol.exists():
        return None
    damga = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    hedef = YEDEK / f"{damga}__{yol.name}"
    shutil.copy2(yol, hedef)
    return str(hedef)


_KILIT = threading.Lock()


@contextmanager
def _gunluk_kilidi():
    """Gunluge yazan HER surec icin tek sira.

    Ekip iscileri ayri surecler ve ayni journal.jsonl'e yazar. Windows'ta "a"
    kipinde ekleme atomik degil (once sona gidilir, sonra yazilir): iki surec
    ayni anda yazinca biri otekinin satirinin ustune yaziyordu — olculdu:
    6 surec x 150 kayitta 200 kayit kayboldu. Kaybolan her kayit, bir
    yazmanin GERI ALMA bilgisidir. Surec ici thread'ler icin _KILIT, surecler
    arasi icin isletim sistemi dosya kilidi (journal.lock).

    Kilit alinamazsa (LK_LOCK ~10 sn dener) yine de yazilir: kaydi hic
    yazmamak, nadir bir cakisma riskinden daha kotu.
    """
    with _KILIT:
        f = open(KOK / "journal.lock", "a+b")
        kilitli = False
        try:
            try:
                if os.name == "nt":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                kilitli = True
            except OSError:
                pass
            yield
        finally:
            if kilitli:
                try:
                    if os.name == "nt":
                        import msvcrt
                        f.seek(0)
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            f.close()


def yaz(kayit: dict) -> None:
    # Mikrosaniye hassasiyeti şart: aynı turda birden fazla dosyaya yazılırsa
    # saniye çözünürlüğü tekillik garanti etmez, "zaman" kayıt kimliği olarak kullanılıyor.
    _hazirla()
    with _gunluk_kilidi():
        kayit["zaman"] = datetime.now().isoformat(timespec="microseconds")
        # Dosya yarim bir satirla bitiyorsa (cokme sonrasi) yeni kayit onun DEVAMINA
        # yazilir, bozuk satir + gecerli kayit tek satir olur ve _kayitlar ikisini
        # birden atlar: cokmeden SONRAKI ilk kayit da kaybolurdu. Once satir sonu.
        onek = ""
        try:
            if KAYIT.exists() and KAYIT.stat().st_size > 0:
                with open(KAYIT, "rb") as f:
                    f.seek(-1, 2)
                    if f.read(1) != b"\n":
                        onek = "\n"
        except OSError:
            pass
        with open(KAYIT, "a", encoding="utf-8") as f:
            f.write(onek + json.dumps(kayit, ensure_ascii=False) + "\n")


def _kayitlar() -> list[dict]:
    """Gunlugun tamami, eskiden yeniye. BOZUK SATIR ATLANIR: yazma sirasinda
    kesilen bir surec yarim satir birakabilir; tek bir bozuk satir yuzunden
    --gecmis, degisiklik_gecmisi, geri alma ve donus ozeti birden calismaz
    olmamali. Atlanan satir sayisi bilgi olarak dondurulmuyor — kayit
    zaten yazilamamis, gosterilecek bir sey yok."""
    if not KAYIT.exists():
        return []
    kayitlar: list[dict] = []
    with open(KAYIT, encoding="utf-8") as f:
        for satir in f:
            if not satir.strip():
                continue
            try:
                k = json.loads(satir)
            except ValueError:
                continue
            if isinstance(k, dict):
                kayitlar.append(k)
    return kayitlar


def _geri_alinmamis(kayitlar: list[dict]) -> list[dict]:
    """Henüz geri alınmamış yazma kayıtları, eskiden yeniye."""
    alinan = {k["hedef"] for k in kayitlar if k.get("tip") == "geri_alma"}
    return [k for k in kayitlar if k.get("tip") in ("yazma", "tasima", "klasor") and k["zaman"] not in alinan]


def gorev_kayitlari(baslangic_zamani: str) -> list[dict]:
    """Bu zamandan (ISO, mikrosaniye — yaz()'in urettigi bicimle) SONRAKI
    yazma/tasima kayitlari, eskiden yeniye.

    Faz 7 durum dosyasi icin: modelin kendi "yapilanlar" ozetine degil,
    GERCEKTEN ne yazildigina bakmak icin. Gerekce: canli bir denemede model
    hic yapmadigi bir yazmayi "tamamlandi" diye bildirmisti (bkz.
    DEVIR_FAZ7.md Asama 1 raporundaki "beklenmedik bulgu"). journal zaten
    dogru — modele sormaya gerek yok, o gorev boyunca gercekten neyin
    yazildigi burada duruyor.

    ISO 8601 mikrosaniye bicimi sabit genislikte oldugu icin string
    karsilastirmasi kronolojik siralamayla AYNI sonucu verir, ayri bir
    tarih ayristirici gerekmez.
    """
    return [k for k in _kayitlar()
            if k.get("tip") in ("yazma", "tasima") and k.get("zaman", "") >= baslangic_zamani]


def bekleyen(adet: int = 15) -> str:
    """Geri alınabilecek işlemler, yenisi üstte."""
    liste = _geri_alinmamis(_kayitlar())[-adet:]
    if not liste:
        return t("Geri alınabilecek işlem yok.")
    satirlar = []
    for k in reversed(liste):
        if k.get("tip") == "tasima":
            satirlar.append(f"{k['zaman']}  {k.get('islem', 'tasindi'):16}  {k['yol']} -> {k['yeni_yol']}")
            continue
        if k.get("tip") == "klasor":
            satirlar.append(f"{k['zaman']}  {t('klasör oluşturuldu'):16}  {k['yol']}")
            continue
        ne = t("üzerine yazıldı") if k.get("uzerine_yazildi") else t("oluşturuldu")
        satirlar.append(f"{k['zaman']}  {ne:16}  {k['yol']}  " + t("({bayt} bayt)", bayt=k.get("bayt", "?")))
    return t("Geri alınabilecek işlemler (yeniden eskiye):") + "\n" + "\n".join(satirlar)


def bekleyen_kayitlar(adet: int = 30) -> list[dict]:
    """bekleyen() ile ayni liste, ama METIN degil YAPILANDIRILMIS.

    Arayuzun "Degisiklikler" paneli her satira ayri bir "Geri al" dugmesi
    koyabilsin diye eklendi. CLI metin surumu (bekleyen) oldugu gibi duruyor.
    """
    liste = _geri_alinmamis(_kayitlar())[-adet:]
    cikti: list[dict] = []
    for k in reversed(liste):          # yenisi ustte
        if k.get("tip") == "klasor":
            cikti.append({"zaman": k["zaman"], "tip": "klasor", "islem": "klasor olusturuldu",
                          "yol": k["yol"], "geri_donus": "bossa kaldirilir"})
            continue
        if k.get("tip") == "tasima":
            cikti.append({
                "zaman": k["zaman"],
                "tip": "tasima",
                "islem": k.get("islem", "tasindi"),
                "yol": k["yol"],
                "yeni_yol": k.get("yeni_yol", ""),
            })
        else:
            cikti.append({
                "zaman": k["zaman"],
                "tip": "yazma",
                "islem": "uzerine yazildi" if k.get("uzerine_yazildi") else "olusturuldu",
                "yol": k["yol"],
                "bayt": k.get("bayt"),
                "geri_donus": "onceki hali" if k.get("yedek") else "dosya silinecek",
            })
    return cikti


def geri_al(hedef_yol: str | None = None) -> str:
    """Son yazmayı geri alır. hedef_yol verilirse SADECE o dosyanın son yazmasını.
    Eşleşme dosya adının sonundan yapılır: 'deneme.txt' yeterli, tam yol da olur."""
    adaylar = _geri_alinmamis(_kayitlar())

    if hedef_yol:
        anahtar = hedef_yol.lower().replace("/", "\\")
        adaylar = [k for k in adaylar if k["yol"].lower().endswith(anahtar)]
        if not adaylar:
            return t("'{yol}' için geri alınabilecek bir yazma kaydı yok. "
                     "Listeyi görmek için --gecmis", yol=hedef_yol)

    if not adaylar:
        return t("Geri alınacak bir işlem yok.")

    k = adaylar[-1]
    hedef = Path(k["yol"])

    if k.get("tip") == "klasor":
        # mkdir geri almasi: klasor (ve olusturulan alt klasorler) BOSSA kaldirilir.
        # Icine dosya girdiyse dokunulmaz — kullanicinin verisi silinmez.
        kok = Path(k["yol"])
        if not kok.exists():
            yaz({"tip": "geri_alma", "hedef": k["zaman"], "yol": k["yol"]})
            return t("Geri alındı: {yol} zaten yok.", yol=kok)
        for p_ in kok.rglob("*"):
            if p_.is_file():
                return t("Geri alınamadı: {yol} boş değil ({ad} var). Klasörü elle temizle.",
                         yol=kok, ad=p_.name)
        for p_ in sorted(kok.rglob("*"), key=lambda x: len(str(x)), reverse=True):
            p_.rmdir()
        kok.rmdir()
        yaz({"tip": "geri_alma", "hedef": k["zaman"], "yol": k["yol"]})
        return t("Geri alındı: {yol} kaldırıldı (boştu).", yol=kok)

    if k.get("tip") == "tasima":
        # move/trash/rename geri alması: dosyayı eski yoluna geri taşı.
        yeni = Path(k["yeni_yol"])
        eski = Path(k["yol"])
        if not yeni.exists():
            return t("Geri alınamadı: {yol} artık yok (elle taşınmış ya da silinmiş olabilir).", yol=yeni)
        if eski.exists():
            return t("Geri alınamadı: {yol} yolunda şimdi başka bir dosya var.", yol=eski)
        eski.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(yeni), str(eski))
        yaz({"tip": "geri_alma", "hedef": k["zaman"], "yol": k["yol"]})
        return t("Geri alındı: {yeni} -> {eski} yoluna döndü.", yeni=yeni, eski=eski)

    # Geri alma da bir değişikliktir: mevcut hali önce yedeklenir.
    # Böylece yanlış/tekrarlanan bir geri alma kalıcı kayba yol açmaz.
    onceki = yedekle(hedef)

    if k.get("yedek") is None:
        if hedef.exists():
            hedef.unlink()
        sonuc = t("Geri alındı: {yol} silindi (yazmadan önce mevcut değildi).", yol=hedef)
    else:
        shutil.copy2(k["yedek"], hedef)
        sonuc = t("Geri alındı: {yol} -> {zaman} tarihli yazmadan önceki hâline döndü.",
                  yol=hedef, zaman=k["zaman"])

    # Kayıt, dosya işleminden SONRA ve print'ten ÖNCE yazılır.
    yaz({"tip": "geri_alma", "hedef": k["zaman"], "yol": k["yol"], "geri_alma_yedegi": onceki})
    return sonuc


def son_degisiklikler(adet: int = 20) -> str:
    """Yapılan yazma/geri alma işlemlerini insan ve model için okunur metne çevirir."""
    kayitlar = _kayitlar()[-adet:]
    if not kayitlar:
        return t("Henüz hiçbir dosya değişikliği yapılmadı.")

    satirlar = []
    for k in kayitlar:
        if k.get("tip") == "yazma":
            ne = t("üzerine yazıldı") if k.get("uzerine_yazildi") else t("oluşturuldu")
            satirlar.append(f"{k['zaman']}  {ne}  {k['yol']}  " + t("({bayt} bayt)", bayt=k.get("bayt", "?")))
        elif k.get("tip") == "klasor":
            satirlar.append(f"{k['zaman']}  " + t("klasör oluşturuldu") + f"  {k['yol']}")
        elif k.get("tip") == "tasima":
            # move/rename/trash. Eskiden atlaniyordu: model "ne yaptin" diye
            # sorulunca tasidigi dosyalari goremiyordu (bekleyen() gosteriyordu,
            # bu fonksiyon geride kalmisti).
            satirlar.append(f"{k['zaman']}  {k.get('islem', 'tasindi')}  "
                            f"{k['yol']} -> {k.get('yeni_yol', '?')}")
        elif k.get("tip") == "geri_alma":
            satirlar.append(f"{k['zaman']}  " + t("GERİ ALINDI") + f"  {k['yol']}")
    return "\n".join(satirlar)