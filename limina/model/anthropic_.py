"""model/anthropic_.py — Anthropic Messages API adaptoru (resmi `anthropic` SDK).

Istege bagli ekstra: pip install -e .[anthropic]. SDK yoksa saglayici
kurulurken anlasilir bir hata verilir (import burada, modul yuklenirken degil).
"""
from __future__ import annotations

from typing import Any

from limina.model.taban import (AracCagrisi, ModelHatasi, OranSiniri, Saglayici, kimlikleri_tamamla,
                                arac_adi_coz, arac_adi_kodla,
                                SunucuHatasi, Yanit, ZamanAsimi, ardisik_birlestir,
                                model_turu, yeni_cagri_kimligi)

MAX_TOKENS = 16000


class Anthropic(Saglayici):
    ad = "anthropic"

    def __init__(self, anahtar: str, zaman_asimi_sn: float) -> None:
        try:
            import anthropic
        except ImportError as e:
            raise ModelHatasi(0, "anthropic paketi kurulu degil: pip install -e .[anthropic]") from e
        self._sdk = anthropic
        # SDK kendi yeniden denemesini yapiyor (429/5xx); dongu de yapiyor —
        # ikisi ust uste binmesin diye SDK'ninki kapali.
        self._client = anthropic.Anthropic(api_key=anahtar, timeout=zaman_asimi_sn, max_retries=0)

    # --- bicim cevirileri -------------------------------------------------
    @staticmethod
    def _mesajlar(gecmis: list[dict]) -> list[dict]:
        cikti: list[dict] = []
        for m in ardisik_birlestir(kimlikleri_tamamla(gecmis)):
            bloklar: list[dict] = []
            for p in m.get("parcalar", []):
                tip = p.get("tip")
                if tip == "metin" and p.get("metin"):
                    bloklar.append({"type": "text", "text": p["metin"]})
                elif tip == "cagri":
                    bloklar.append({"type": "tool_use", "id": p.get("id") or yeni_cagri_kimligi(),
                                    "name": arac_adi_kodla(p.get("ad", "")), "input": p.get("args") or {}})
                elif tip == "sonuc":
                    cevap = p.get("cevap") or {}
                    icerik = cevap.get("result") if isinstance(cevap, dict) and "result" in cevap else str(cevap)
                    bloklar.append({"type": "tool_result", "tool_use_id": p.get("id") or "",
                                    "content": str(icerik)})
            if bloklar:
                cikti.append({"role": "assistant" if m.get("rol") == "model" else "user", "content": bloklar})
        return cikti

    @staticmethod
    def _araclar(araclar: list[dict]) -> list[dict]:
        return [{"name": arac_adi_kodla(a["name"]), "description": a.get("description", ""),
                 "input_schema": a.get("parameters") or {"type": "object", "properties": {}}}
                for a in araclar]

    # --- sozlesme -------------------------------------------------------
    def uret(self, model: str, gecmis: list[dict], sistem: str,
             araclar: list[dict] | None, zorla_arac: str | None = None) -> Yanit:
        sdk = self._sdk
        ek: dict[str, Any] = {}
        if araclar is not None:
            ek["tools"] = self._araclar(araclar)
            if zorla_arac:
                ek["tool_choice"] = {"type": "tool", "name": arac_adi_kodla(zorla_arac)}
        try:
            yanit = self._client.messages.create(
                model=model, max_tokens=MAX_TOKENS, system=sistem or sdk.NOT_GIVEN,
                messages=self._mesajlar(gecmis), **ek)
        except sdk.RateLimitError as e:
            raise OranSiniri(429, str(getattr(e, "message", e))) from e
        except sdk.APITimeoutError as e:
            raise ZamanAsimi(str(e)) from e
        except sdk.APIStatusError as e:
            kod = int(getattr(e, "status_code", 0) or 0)
            mesaj = str(getattr(e, "message", e))
            if kod >= 500:
                raise SunucuHatasi(kod, mesaj) from e
            raise ModelHatasi(kod, mesaj) from e
        except sdk.APIConnectionError as e:
            raise ModelHatasi(0, f"baglanti hatasi: {e}") from e

        metin_parcalari, cagrilar = [], []
        for blok in yanit.content:
            if blok.type == "text":
                metin_parcalari.append(blok.text)
            elif blok.type == "tool_use":
                cagrilar.append(AracCagrisi(ad=arac_adi_coz(blok.name), args=dict(blok.input or {}), id=blok.id))
        metin = "".join(metin_parcalari) or None
        if yanit.stop_reason == "refusal":
            metin = (metin or "") + "\n(model bu istegi guvenlik gerekcesiyle reddetti)"
        k = yanit.usage
        return Yanit(metin=metin, cagrilar=cagrilar, icerik=model_turu(metin, cagrilar),
                     girdi_token=int(getattr(k, "input_tokens", 0) or 0),
                     cikti_token=int(getattr(k, "output_tokens", 0) or 0))

    def modeller(self) -> list[str]:
        return sorted(m.id for m in self._client.models.list())
