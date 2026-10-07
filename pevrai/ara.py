# ara.py — dosya adında ve metin içeriğinde arama. Sadece okur.
from __future__ import annotations

from pathlib import Path
from typing import Callable
from pevrai.ceviri import t

METIN_UZANTILARI = {".txt", ".md", ".csv", ".py", ".json", ".toml", ".html", ".js", ".css"}
MAX_SONUC = 60
MAX_DOSYA_BOYUTU = 2_000_000   # 2 MB üstü metin dosyası taranmaz


def ara(kok: Path, sorgu: str, glob: str = "*",
        yasakli: Callable[[Path], object] | None = None) -> str:
    """Ad eşleşmelerini ve metin dosyalarındaki satır eşleşmelerini döndürür.

    yasakli: bir yol için doğru dönerse o dosya NE ADIYLA NE İÇERİĞİYLE
    taranır. Kapı yalnızca arama KÖKÜNÜ denetler; kökün altındaki her
    dosyayı bu fonksiyon kendisi okuyor. Kara liste burada uygulanmazsa
    `read_file` ile açılamayan `db_password.txt`'nin içeriği `search`
    ile satır satır dönerdi (doğrulandı, 2026-09-18). list_dir ile aynı
    kural: dosyanın varlığı da sızıntıdır, ad eşleşmesi de gösterilmez.
    """
    q = sorgu.lower()
    ad_bulunan: list[str] = []
    icerik_bulunan: list[str] = []
    taranan = 0
    gizlenen = 0

    for p in kok.rglob(glob):
        if not p.is_file():
            continue
        if yasakli is not None and yasakli(p):
            gizlenen += 1
            continue
        taranan += 1
        if len(ad_bulunan) + len(icerik_bulunan) >= MAX_SONUC:
            break

        try:
            boyut = p.stat().st_size
        except OSError:
            continue            # kopuk baglanti / erisim yok: atla, cokme

        if q in p.name.lower():
            ad_bulunan.append(f"{p}  ({boyut} bayt)")
            continue

        if p.suffix.lower() not in METIN_UZANTILARI:
            continue
        try:
            if boyut > MAX_DOSYA_BOYUTU:
                continue
            for no, satir in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if q in satir.lower():
                    icerik_bulunan.append(f"{p}:{no}: {satir.strip()[:160]}")
                    break          # dosya başına tek eşleşme, gürültüyü keser
        except OSError:
            continue

    gizli_notu = (f" {gizlenen} dosya kara liste nedeniyle taranmadi (kimlik bilgisi "
                  f"kalibi); bunlara erisilemez, sorma." if gizlenen else "")
    if not ad_bulunan and not icerik_bulunan:
        return t("'{sorgu}' bulunamadı ({taranan} dosya tarandı, kök: {kok}).{not_} "
                 "Not: PDF/DOCX/PPTX içeriği taranmaz, sadece dosya ADI eşleşir. "
                 "Belge içeriği için read_document kullan.",
                 sorgu=sorgu, taranan=taranan, kok=kok, not_=gizli_notu)

    parcalar = []
    if ad_bulunan:
        parcalar.append("DOSYA ADINDA ESLESENLER:\n" + "\n".join(ad_bulunan))
    if icerik_bulunan:
        parcalar.append("ICERIKTE ESLESENLER:\n" + "\n".join(icerik_bulunan))
    parcalar.append(f"({taranan} dosya tarandi){gizli_notu}")
    return "\n\n".join(parcalar)
