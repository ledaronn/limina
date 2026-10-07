"""araclar/ortak.py — arac fonksiyonlarinin paylastigi yardimcilar.

Cikti kirpma, "bulunamadi" mesaji, journal sarmalayicisi, hassas kalip
maskeleme. Dongu (vekil_v0) da hassas maskelemeyi buradan alir: reddedilen
deger olay akisina/konsola da maskeli gitmeli (Faz 7 Asama 1 olcumu).
"""
from __future__ import annotations

import re
from pathlib import Path

from pevrai import journal
from pevrai.baglam import B
from pevrai.ceviri import t
from pevrai.sonuc import AracSonucu, hata

MAX_OUTPUT = 8000
MAX_SATIR = 400


def kirp(metin: str, satir_sayisi: int) -> str:
    if len(metin) > MAX_OUTPUT:
        return AracSonucu(metin[:MAX_OUTPUT] + "\n" + t("[... çıktı kırpıldı, kaynakta toplam {satir} satır vardı]",
                                             satir=satir_sayisi), getattr(metin, "basarili", True))
    return metin


def bulunamadi(yol: Path) -> str:
    """'Bulunamadi' mesaji komsu dosyalari sayar ki model dogru adi bulsun.
    Kara listedekiler LISTELENMEZ — list_dir ile ayni kural: `.env`'in adi
    da bir sizinti (dogrulandi: eski hali `.env`'i listeliyordu)."""
    komsular: list[str] = []
    try:
        if yol.parent.exists():
            komsular = [p.name for p in sorted(yol.parent.iterdir())
                        if not B.politika._yasakli_mi(p)][:15]
    except OSError:
        pass
    return hata(t("'{yol}' bulunamadı. {klasor} içindekiler: {liste}",
             yol=yol, klasor=yol.parent, liste=", ".join(komsular) or t("(boş)")))


def journal_yaz(kayit: dict) -> None:
    """journal.yaz'in ince sarmalayicisi: aktif profil doluysa kayida
    profil: "<ad>", kendiliginden devam turundaysak devam: N alanini ekler.

    devam alani neden gerekli: gozetimsiz bir gorev birden fazla turda
    calisiyor ve "hangi tur neyi yazdi" sorusunun cevabi kayitta DURMALI —
    yoksa donus ozeti yedi yazmayi tek bir turun isi gibi gosterir."""
    ek = {}
    if B.aktif_profil is not None:
        ek["profil"] = B.aktif_profil
    if B.aktif_devam:
        ek["devam"] = B.aktif_devam
    if B.ajan_adi:
        ek["ajan"] = B.ajan_adi           # ekip iscisi: hangi ajan yazdi
    journal.yaz({**kayit, **ek} if ek else kayit)


# --- hassas kaliplar: tespit ve maskeleme TEK yerde --------------------------
_KART = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_TCKN = re.compile(r"\b[1-9]\d{10}\b")


def hassas_mi(metin: str) -> str | None:
    """Kart numarasi / TC kimlik kalibi. Kapali liste degil, bariz olanlari yakalar."""
    if _KART.search(metin):
        return t("kart numarasına benzeyen bir dizi")
    if _TCKN.search(metin):
        return t("kimlik numarasına benzeyen bir dizi")
    return None


def hassas_maskele(metin: str) -> str:
    """hassas_mi'nin ikizi: TESPIT etmez, DEGISTIRIR. Ayni iki kalip — biri
    guncellenip digeri unutulursa reddedilen bir deger maskelenmeden kayda
    girerdi, o yuzden kaliplar TEK yerde."""
    metin = _KART.sub("[GIZLENDI: kart numarasi kalibi]", metin)
    return _TCKN.sub("[GIZLENDI: kimlik numarasi kalibi]", metin)


def args_gizle(args: dict) -> dict:
    """Arac argumanlarinin GUNLUGE/OLAY AKISINA giden kopyasi: hassas kaliba
    uyan degerler maskelenir. Aracin KENDISINE giden args'a DOKUNMAZ.

    NOT (bilinen ve KAPATILMAYAN sinir): modelin kendi konusma gecmisi cagriyi
    oldugu gibi tasir ve sohbet.kaydet onu diske yazar — SECURITY.md'de isaretli.
    """
    temiz = {}
    for anahtar, deger in (args or {}).items():
        if isinstance(deger, str):
            temiz[anahtar] = hassas_maskele(deger)
        elif isinstance(deger, int) and not isinstance(deger, bool):
            temiz[anahtar] = hassas_maskele(str(deger))
        else:
            temiz[anahtar] = deger
    return temiz
