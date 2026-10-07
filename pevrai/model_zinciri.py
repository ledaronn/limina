"""model_zinciri.py — API baglantilarindan kurulan sirali model zinciri.

Kullanici birden fazla API baglantisi ekler (policy.toml [baglantilar.<kimlik>]:
saglayici, sunucu adresi, sirali model listesi; anahtar anahtar.py deposunda
adli yuvada) ve baglantilari siralar ([model] zincir). Zincir bu siranin
duzlestirilmis halidir: baglanti 1'in modelleri, sonra baglanti 2'ninkiler...

Gorev zincirin basindaki MUSAIT halkayla baslar. O modelin kullanimi dolunca
(429 / RESOURCE_EXHAUSTED / 402 bakiye) ayni gorev siradaki halkayla, kaldigi
yerden surer — gecmis saglayicidan bagimsiz bicimde (model/taban.py).

Limiti dolan halka bir sure atlanir: dakikalik limitte kisa, gunluk limitte
gun sonuna kadar. Durum ~/.vekil/model_durumu.json'da — ANAHTAR YOK, yalnizca
"kimlik|model" -> bitis zamani. Kullanici Ayarlar > Model'den sifirlayabilir.

[baglantilar] hic yoksa zincir tek halkadir: eski [model] ayari (saglayici,
taban_url, varsayilan/guclu). Mevcut kurulumlar hicbir sey yapmadan calisir.
Ekip iscisi: baglantiya bagli ajan once kendi baglantisinin modellerini, sonra
genel zinciri kullanir; eski bicim ajan tanimi tek halkadir.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from pevrai import journal
from pevrai.model import ModelHatasi, OranSiniri

# Kisa bekleme: dakikalik oran siniri. Uzun: gunluk kota / bakiye — gun sonuna kadar.
KISA_BEKLEME = timedelta(seconds=90)
BILINMEYEN_BEKLEME = timedelta(minutes=5)

SAGLAYICI_KISA_AD = {"gemini": "Gemini", "openai": "OpenAI", "anthropic": "Claude"}

# Arayuzdeki hazir secenekler. Yalnizca KOLAYLIK: kaydedilen baglanti
# saglayici + sunucu adresi + addan ibarettir, hazirin kodu saklanmaz.
# "ornek" model adlari yer tutucudur; gercek adlar "Hesaptaki modelleri
# getir" ile saglayicidan alinir. anahtarsiz: yerel sunucu, anahtar gerekmez.
HAZIRLAR = [
    {"kod": "gemini", "ad": "Google Gemini", "saglayici": "gemini", "taban_url": "",
     "ornek": ["gemini-2.5-flash", "gemini-2.5-pro"]},
    {"kod": "openai", "ad": "OpenAI", "saglayici": "openai", "taban_url": "",
     "ornek": ["gpt-4o-mini", "gpt-4o"]},
    {"kod": "anthropic", "ad": "Anthropic Claude", "saglayici": "anthropic", "taban_url": "",
     "ornek": ["claude-sonnet-5", "claude-opus-5"]},
    {"kod": "deepseek", "ad": "DeepSeek", "saglayici": "openai", "taban_url": "https://api.deepseek.com/v1",
     "ornek": ["deepseek-chat", "deepseek-reasoner"]},
    {"kod": "kimi", "ad": "Kimi (Moonshot)", "saglayici": "openai", "taban_url": "https://api.moonshot.ai/v1",
     "ornek": ["kimi-k2-0905-preview"]},
    {"kod": "qwen", "ad": "Qwen (Alibaba)", "saglayici": "openai",
     "taban_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "ornek": ["qwen-plus", "qwen-max"]},
    {"kod": "mistral", "ad": "Mistral", "saglayici": "openai", "taban_url": "https://api.mistral.ai/v1",
     "ornek": ["mistral-large-latest", "mistral-small-latest"]},
    {"kod": "groq", "ad": "Groq", "saglayici": "openai", "taban_url": "https://api.groq.com/openai/v1",
     "ornek": ["llama-3.3-70b-versatile"]},
    {"kod": "xai", "ad": "xAI Grok", "saglayici": "openai", "taban_url": "https://api.x.ai/v1",
     "ornek": ["grok-4"]},
    {"kod": "openrouter", "ad": "OpenRouter", "saglayici": "openai", "taban_url": "https://openrouter.ai/api/v1",
     "ornek": ["deepseek/deepseek-chat", "openai/gpt-4o"]},
    {"kod": "together", "ad": "Together AI", "saglayici": "openai", "taban_url": "https://api.together.xyz/v1",
     "ornek": ["meta-llama/Llama-3.3-70B-Instruct-Turbo"]},
    {"kod": "ollama", "ad": "Ollama", "saglayici": "openai", "taban_url": "http://localhost:11434/v1",
     "ornek": ["llama3.1:8b", "qwen2.5:7b"], "anahtarsiz": True},
    {"kod": "lmstudio", "ad": "LM Studio", "saglayici": "openai", "taban_url": "http://localhost:1234/v1",
     "ornek": [], "anahtarsiz": True},
    {"kod": "ozel", "ad": "Özel (OpenAI-uyumlu)", "saglayici": "openai", "taban_url": "", "ornek": []},
]


def _durum_yolu():
    return journal.KOK / "model_durumu.json"


@dataclass(frozen=True)
class Halka:
    """Zincirin bir halkasi: hangi baglantinin hangi modeli."""
    kimlik: str          # baglanti kimligi; "" = eski tek-saglayici ayari ya da ekip ajani
    ad: str              # arayuzde gorunen baglanti adi
    saglayici: str       # gemini | openai | anthropic
    taban_url: str
    yuva: str            # anahtar.py yuvasi ("" = varsayilan)
    model: str

    @property
    def anahtar(self) -> str:
        return f"{self.kimlik}|{self.model}"

    @property
    def etiket(self) -> str:
        return f"{self.ad} · {self.model}"

    def ajan(self) -> dict:
        """model.kur(ajan=) icin tanim. Baglanti halkasinda taban_url KESINDIR:
        bos adres eski [model] taban_url'ine DUSMEZ (resmi OpenAI baglantisi
        yerel Ollama adresine gitmesin)."""
        d = {"saglayici": self.saglayici, "anahtar_yuvasi": self.yuva, "taban_url": self.taban_url}
        if self.kimlik:
            d["baglanti"] = self.kimlik
            d["ad"] = self.ad
        return d


ESKI_KIMLIK = "ana"      # eski tek-saglayici ayarinin secicideki kimligi (ayarlar.ESKI_BAGLANTI)


def secim_anahtari(h: Halka) -> str:
    """Sohbet ekranindaki model secicinin degeri: "kimlik/model"."""
    return f"{h.kimlik or ESKI_KIMLIK}/{h.model}"


def zincir(politika, rol: str = "varsayilan", ajan: dict | None = None,
           ajan_adi: str = "", secili: str = "") -> list[Halka]:
    """Sirali halkalar.

    Modlar (Hizli/Dengeli/Derin/Azami) MODEL SECMEZ, yalnizca calisma
    sinirlarini (adim, cagri, istek) belirler. Modeli kullanici sohbet
    ekranindan secer (secili = "kimlik/model"): o halka basa alinir, geri
    kalanlar zincir sirasiyla arkasindan gelir — secilen modelin limiti
    dolarsa gorev yine durmaz. Bos = otomatik (zincirin basi).

    Ekip ajani BAGLANTIYA bagliysa (ajan["baglanti"]): once ajanin modeli,
    sonra ayni baglantinin diger modelleri, sonra genel zincir — ajanin
    modeli dolunca isci durmaz, once kendi hesabinda kalir.

    rol yalnizca eski bicim ajanda kullanilir: model yazilmamis ajan modun
    eski modelini alir (tek halka, gecis yok)."""
    if ajan and ajan.get("baglanti"):
        genel = zincir(politika, rol)
        kimlik = ajan["baglanti"]
        # Baglantisiz eski ayarda 'ana' kimligi zincirde "" olarak durur.
        esit = (lambda h: h.kimlik == kimlik) if getattr(politika, "baglantilar", {}) else (lambda h: not h.kimlik)
        kendi = [h for h in genel if esit(h)]
        if kendi and ajan.get("model") and not any(h.model == ajan["model"] for h in kendi):
            ornek = kendi[0]
            kendi.insert(0, Halka(ornek.kimlik, ornek.ad, ornek.saglayici, ornek.taban_url, ornek.yuva, ajan["model"]))
        kendi.sort(key=lambda h: h.model != ajan.get("model"))      # ajanin modeli basa, gerisi sirasiyla
        return kendi + [h for h in genel if not esit(h)]
    if ajan:
        model_adi = (politika.model_guclu if rol == "guclu" else politika.model_varsayilan) or ""
        return [Halka("", ajan_adi or SAGLAYICI_KISA_AD.get(ajan.get("saglayici", ""), "?"),
                      ajan.get("saglayici") or politika.saglayici, ajan.get("taban_url") or "",
                      ajan.get("anahtar_yuvasi") or "", ajan.get("model") or model_adi)]
    baglantilar = getattr(politika, "baglantilar", {}) or {}
    if not baglantilar:
        # Eski ayar: iki model adi da ayni saglayicinin zinciri olur.
        ad = SAGLAYICI_KISA_AD.get(politika.saglayici, politika.saglayici)
        adlar = [m for m in dict.fromkeys([politika.model_varsayilan, politika.model_guclu]) if m]
        halkalar = [Halka("", ad, politika.saglayici, getattr(politika, "taban_url", "") or "", "", m)
                    for m in adlar]
    else:
        halkalar = [Halka(k, b["ad"], b["saglayici"], b["taban_url"], b["anahtar_yuvasi"], m)
                    for k in politika.zincir for b in [baglantilar[k]] for m in b["modeller"]]
    if secili:
        for i, h in enumerate(halkalar):
            if secim_anahtari(h) == secili:
                halkalar.insert(0, halkalar.pop(i))
                break
    return halkalar


# ---------------------------------------------------------------------------
# Limit durumu
# ---------------------------------------------------------------------------

def kota_hatasi_mi(e: ModelHatasi) -> bool:
    """Bu hata 'kullanim doldu' mu? Oran siniri (429), gunluk kota, bakiye/kredi
    bitti (402 ya da saglayicinin metni). Anahtar/model adi hatalari DEGIL —
    onlar ayar hatasi, sessizce atlanmamali."""
    if isinstance(e, OranSiniri) or e.code == 402:
        return True
    ust = str(e.mesaj).upper()
    return any(k in ust for k in ("RESOURCE_EXHAUSTED", "INSUFFICIENT_QUOTA", "INSUFFICIENT BALANCE",
                                  "CREDIT BALANCE", "QUOTA EXCEEDED", "EXCEEDED YOUR CURRENT QUOTA"))


def bitis_hesapla(e: ModelHatasi, simdi: datetime | None = None) -> datetime:
    """Halka ne zamana kadar atlanir. Saglayici metnindeki ipucu belirler:
    dakikalik -> kisa; gunluk / bakiye -> gun sonu; bilinmeyen -> 5 dk."""
    simdi = simdi or datetime.now()
    kucuk = str(e.mesaj).lower().replace(" ", "")
    gun_sonu = (simdi + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    # Gunluk ipucu ONCE: Gemini'nin gunluk kota mesaji da "retry in 30s" tasiyabiliyor.
    if e.code == 402 or any(k in kucuk for k in ("perday", "daily", "insufficient", "creditbalance",
                                                 "exceededyourcurrentquota")):
        return gun_sonu
    if "minute" in kucuk:
        return simdi + KISA_BEKLEME
    return simdi + BILINMEYEN_BEKLEME


def _oku() -> dict[str, str]:
    try:
        yol = _durum_yolu()
        if yol.exists():
            veri = json.loads(yol.read_text(encoding="utf-8"))
            if isinstance(veri, dict):
                return {str(k): str(v) for k, v in veri.items()}
    except Exception:
        pass
    return {}


def _yaz(veri: dict[str, str]) -> None:
    yol = _durum_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_name(yol.name + ".yeni")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
    gecici.replace(yol)


def dolu_bitis(h: Halka, simdi: datetime | None = None) -> datetime | None:
    """Halka su an atlaniyorsa bitis zamani, degilse None."""
    deger = _oku().get(h.anahtar)
    if not deger:
        return None
    try:
        bitis = datetime.fromisoformat(deger)
    except ValueError:
        return None
    return bitis if bitis > (simdi or datetime.now()) else None


def dolu_isaretle(h: Halka, e: ModelHatasi) -> datetime:
    bitis = bitis_hesapla(e)
    try:
        with journal._gunluk_kilidi():
            veri = _oku()
            simdi = datetime.now()
            # suresi gecmis kayitlari da temizle: dosya buyumesin
            veri = {k: v for k, v in veri.items() if _gelecekte(v, simdi)}
            veri[h.anahtar] = bitis.isoformat(timespec="seconds")
            _yaz(veri)
    except OSError:
        pass                     # durum yazilamazsa yalnizca bu gorevde gecis olur
    return bitis


def _gelecekte(deger: str, simdi: datetime) -> bool:
    try:
        return datetime.fromisoformat(deger) > simdi
    except ValueError:
        return False


def sifirla(kimlik: str | None = None) -> None:
    """Dolu isaretlerini kaldirir. kimlik verilirse yalnizca o baglantinin."""
    try:
        with journal._gunluk_kilidi():
            veri = _oku()
            if kimlik is None:
                veri = {}
            else:
                veri = {k: v for k, v in veri.items() if k.split("|", 1)[0] != kimlik}
            _yaz(veri)
    except OSError:
        pass


def sirala(halkalar: list[Halka], simdi: datetime | None = None) -> list[Halka]:
    """Musait halkalar once (kendi sirasiyla), dolu olanlar SON CARE olarak
    arkada (bitisi en yakin once). Hepsi doluysa yine denenir: isaret eski
    olabilir, saglayici limiti erken acmis olabilir."""
    simdi = simdi or datetime.now()
    musait, dolu = [], []
    for h in halkalar:
        b = dolu_bitis(h, simdi)
        (dolu if b else musait).append((b, h))
    dolu.sort(key=lambda x: x[0])
    return [h for _, h in musait] + [h for _, h in dolu]


def durum_listesi(politika) -> list[dict]:
    """Arayuz icin: her halkanin dolu olup olmadigi (anahtar YOK)."""
    simdi = datetime.now()
    cikti = []
    for h in zincir(politika):
        b = dolu_bitis(h, simdi)
        cikti.append({"kimlik": h.kimlik, "model": h.model, "dolu_bitis": b.isoformat(timespec="minutes") if b else ""})
    return cikti
