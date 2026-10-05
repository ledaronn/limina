"""limina.model — saglayici katmani.

    from limina import model
    s = model.kur(POLITIKA)            # policy.toml [model] saglayici + anahtar.oku
    yanit = s.uret(model_adi, gecmis, sistem, araclar)

policy.toml [model]:
    saglayici = "gemini" | "openai" | "anthropic"     (varsayilan gemini)
    taban_url = ""                                     (openai icin; bos = api.openai.com)
    varsayilan = "<model adi>", guclu = "<model adi>"
"""
from __future__ import annotations

from limina import anahtar as _anahtar
from limina.model.taban import (AracCagrisi, ModelHatasi, OranSiniri, Saglayici,
                                SunucuHatasi, Yanit, ZamanAsimi, kullanici_mesaji,
                                sonuc_mesaji)

SAGLAYICILAR = ("gemini", "openai", "anthropic")
SAGLAYICI_ADI = {"gemini": "Google Gemini", "openai": "OpenAI-uyumlu (OpenAI, OpenRouter, Ollama, LM Studio…)",
                 "anthropic": "Anthropic Claude"}
# Anahtarsiz calisabilen saglayici: yerel OpenAI-uyumlu sunucular (Ollama vb.)
ANAHTARSIZ_OLABILIR = {"openai"}
MODEL_ZAMAN_ASIMI = 90.0     # saniye; vekil_v0 ile ayni


_ONBELLEK: dict[tuple, Saglayici] = {}


def yerel_adres_mi(url: str) -> bool:
    """Bu makinede calisan sunucu mu (Ollama, LM Studio)? Anahtarsiz calisabilen
    yalnizca bunlar; DeepSeek/Groq gibi uzak OpenAI-uyumlu sunucular anahtar ister."""
    from urllib.parse import urlparse
    try:
        host = (urlparse(url or "").hostname or "").lower()
    except ValueError:
        return False
    return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost")


def kur(politika, zaman_asimi_sn: float = MODEL_ZAMAN_ASIMI, ajan: dict | None = None) -> Saglayici:
    """Politikadaki saglayiciyi anahtarla kurar. Anahtar yoksa ModelHatasi(401).

    ajan: policy.toml [ajanlar.<ad>] tanimi (gate.Politika.ajanlar[ad]) — ekip
    isci sureci kendi saglayici/anahtar yuvasi/taban adresiyle kurulur; None ise
    [model] ayarlari (tek ajan, eski davranis).

    Ayni (saglayici, taban_url, anahtar, zaman asimi) icin ayni nesne doner:
    her gorevde yeni HTTP istemcisi acmak baglanti/soket sizdiriyordu; ayar
    degisince anahtar farkli olur, yeni istemci kurulur.
    """
    ajan = ajan or {}
    ad = ajan.get("saglayici") or getattr(politika, "saglayici", "gemini") or "gemini"
    if ad not in SAGLAYICILAR:
        raise ModelHatasi(0, f"Taninmayan saglayici: {ad!r}. Gecerli: {', '.join(SAGLAYICILAR)}")
    yuva = ajan.get("anahtar_yuvasi") or ""
    anahtar = _anahtar.oku(ad, yuva)
    # API baglantisi (model_zinciri.Halka): adres KESIN — bos adres resmi
    # sunucu demek, eski [model] taban_url'ine dusmez.
    if ajan.get("baglanti"):
        taban_url = ajan.get("taban_url") or ""
    else:
        taban_url = ajan.get("taban_url") or getattr(politika, "taban_url", "") or ""
    # Baglanti halkasinda anahtarsiz yalnizca YEREL sunucu: uzak bir OpenAI-uyumlu
    # sunucu anahtarsiz denenirse 401 alir ve zincir o halkayi atlayamazdi.
    anahtarsiz = ad in ANAHTARSIZ_OLABILIR and bool(taban_url) and (
        not ajan.get("baglanti") or yerel_adres_mi(taban_url))
    if not anahtar and not anahtarsiz:
        if ajan.get("baglanti"):
            from limina.ceviri import t
            raise ModelHatasi(401, t("'{ad}' bağlantısında API anahtarı yok. Ayarlar > Model'den gir.",
                                     ad=ajan.get("ad") or ajan["baglanti"]))
        if yuva:
            raise ModelHatasi(401, f"{SAGLAYICI_ADI[ad]} '{yuva}' yuvasinda anahtar yok. "
                                   f"Ayarlar > Model > Anahtarlar'dan gir.")
        raise ModelHatasi(401, f"{SAGLAYICI_ADI[ad]} icin API anahtari yok. Ayarlar > Model'den gir "
                               f"ya da {_anahtar.ORTAM_DEGISKENI[ad]} ortam degiskenini ayarla.")
    kilit = (ad, taban_url, anahtar or "", float(zaman_asimi_sn))
    if kilit in _ONBELLEK:
        return _ONBELLEK[kilit]
    if ad == "gemini":
        from limina.model.gemini import Gemini
        s = Gemini(anahtar or "", zaman_asimi_sn)
    elif ad == "openai":
        from limina.model.openai_uyumlu import OpenAIUyumlu
        s = OpenAIUyumlu(anahtar or "", zaman_asimi_sn, taban_url)
    else:
        from limina.model.anthropic_ import Anthropic
        s = Anthropic(anahtar or "", zaman_asimi_sn)
    # Ekip: birden fazla saglayici/anahtar ayni anda canli olabilir; onbellek
    # sinirli tutulur (8), en eskisi dusurulur.
    if len(_ONBELLEK) >= 8:
        _ONBELLEK.pop(next(iter(_ONBELLEK)))
    _ONBELLEK[kilit] = s
    return s


__all__ = ["kur", "Saglayici", "Yanit", "AracCagrisi", "ModelHatasi", "OranSiniri",
           "SunucuHatasi", "ZamanAsimi", "kullanici_mesaji", "sonuc_mesaji",
           "SAGLAYICILAR", "SAGLAYICI_ADI"]
