"""Bundled converter: aşamalı çıktı, yazma öncesi yedek ve geri alma kaydı."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from pevrai import journal
from pevrai.araclar.ortak import journal_yaz
from pevrai.ceviri import t
from pevrai.sonuc import AracSonucu, hata


def donustur(cagir, args: dict, politika) -> str:
    decision = politika.yol_dogrula(str(args.get("dst_dir", "")), "yaz")
    if decision.sonuc == "DENY":
        return hata(decision.gerekce)
    destination = decision.yol
    # Dönüşüm kendi geçici klasörüne yazar; kullanıcının çıktısı hata halinde değişmez.
    if not destination.is_dir():
        return hata(t("Çıktı klasörü mevcut olmalı."))
    try:
        with tempfile.TemporaryDirectory(prefix="pevrai_convert_", dir=destination) as stage_name:
            stage = Path(stage_name)
            response = cagir({**args, "dst_dir": str(stage)})
            if not getattr(response, "basarili", True):
                return response
            outputs = sorted(stage.iterdir())
            if not outputs or any(not p.is_file() or p.is_symlink() or p.suffix.lower() not in {".pdf", ".pptx", ".png"} for p in outputs):
                return hata(t("Dönüştürücü geçerli bir çıktı üretmedi."))
            plan = []
            for source in outputs:
                target = destination / source.name
                check = politika.yol_dogrula(str(target), "yaz")
                if check.sonuc == "DENY" or target.is_symlink():
                    return hata(check.gerekce if check.sonuc == "DENY" else t("Çıktı yolu bir bağlantı olamaz."))
                existed = target.exists()
                plan.append((source, target, journal.yedekle(target), existed))
            for source, target, backup, existed in plan:
                # Günlük yazılamıyorsa kullanıcı dosyasına dokunma. Kaydın
                # ardından replace başarısız olsa da geri alma güvenlidir.
                journal_yaz({"tip": "yazma", "yol": str(target), "yedek": backup,
                             "bayt": source.stat().st_size, "uzerine_yazildi": existed,
                             "arac": "converter.convert"})
                os.replace(source, target)
            return AracSonucu(t("Dönüştürüldü; çıktılar geri alınabilir: {liste}", liste=", ".join(str(target) for _, target, _, _ in plan)))
    except Exception as exc:
        return hata(t("Dönüştürme tamamlanamadı: {hata}", hata=str(exc)))
