"""Araç çıktısı metin kalır; yürütme durumu izin kararından bağımsızdır."""
from __future__ import annotations


class AracSonucu(str):
    basarili: bool

    def __new__(cls, metin: str, basarili: bool = True):
        sonuc = super().__new__(cls, metin)
        sonuc.basarili = basarili
        return sonuc


def hata(metin: str) -> AracSonucu:
    return AracSonucu(metin, False)
