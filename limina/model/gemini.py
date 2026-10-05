"""model/gemini.py — Google Gemini adaptoru (google-genai SDK).

Gemini arac adlarinda nokta kabul etmiyor: "converter.convert" giderken
"converter__convert" olur, donerken geri cevrilir. Bu cevirme YALNIZCA
burada; dongu ve gecmis gercek adi tasir.
"""
from __future__ import annotations

import base64
from typing import Any

from limina.model.taban import (AracCagrisi, ModelHatasi, OranSiniri, Saglayici, arac_adi_coz, arac_adi_kodla,
                                SunucuHatasi, Yanit, ZamanAsimi, model_turu,
                                yeni_cagri_kimligi)


_kodla = arac_adi_kodla


_coz = arac_adi_coz


def _imza_coz(ek: Any) -> bytes | None:
    """gecmisteki 'ek' sozlugunden Gemini thought_signature (base64) -> bytes."""
    if isinstance(ek, dict) and ek.get("gemini_imza"):
        try:
            return base64.b64decode(ek["gemini_imza"])
        except Exception:
            return None
    return None


# Google'in belgeledigi yer tutucu imza: gecmisteki araç cagrisi BASKA bir
# modelden (model zincirinde OpenAI/Claude/DeepSeek...) ya da imzasiz eski bir
# sohbetten geliyorsa Gemini 3 400 doner ("missing a thought_signature").
# Bu deger dogrulamayi atlatir. Yalnizca Gemini 3'te ve imza YOKSA kullanilir.
SAHTE_IMZA = b"skip_thought_signature_validator"


class Gemini(Saglayici):
    ad = "gemini"

    def __init__(self, anahtar: str, zaman_asimi_sn: float) -> None:
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise ModelHatasi(0, "google-genai paketi kurulu degil: pip install google-genai") from e
        self._types = types
        # HttpOptions.timeout MILISANIYE bekliyor.
        self._client = genai.Client(api_key=anahtar,
                                    http_options=types.HttpOptions(timeout=int(zaman_asimi_sn * 1000)))

    # --- bicim cevirileri -------------------------------------------------
    def _icerikler(self, gecmis: list[dict], model: str = "") -> list[Any]:
        t = self._types
        gemini3 = model.startswith("gemini-3")
        cikti = []
        for m in gecmis:
            parcalar = []
            for p in m.get("parcalar", []):
                tip = p.get("tip")
                imza = _imza_coz(p.get("ek"))
                if tip == "metin":
                    parca = t.Part.from_text(text=p.get("metin", ""))
                    if imza:
                        parca.thought_signature = imza
                    parcalar.append(parca)
                elif tip == "cagri":
                    fc = t.FunctionCall(name=_kodla(p.get("ad", "")), args=p.get("args") or {})
                    if p.get("id"):
                        fc.id = p["id"]
                    # Gemini 3: function_call parcasi thought_signature ile
                    # DONMELI, yoksa 400 ("missing a thought_signature").
                    if not imza and gemini3:
                        imza = SAHTE_IMZA
                    parcalar.append(t.Part(function_call=fc, thought_signature=imza)
                                    if imza else t.Part(function_call=fc))
                elif tip == "sonuc":
                    parcalar.append(t.Part.from_function_response(
                        name=_kodla(p.get("ad", "")), response=p.get("cevap") or {}))
            cikti.append(t.Content(role=m.get("rol", "user"), parts=parcalar))
        return cikti

    def _arac(self, araclar: list[dict]) -> Any:
        t = self._types
        return t.Tool(function_declarations=[
            t.FunctionDeclaration(name=_kodla(a["name"]), description=a.get("description", ""),
                                  parameters_json_schema=a.get("parameters") or {"type": "object", "properties": {}})
            for a in araclar])

    # --- sozlesme -------------------------------------------------------
    def uret(self, model: str, gecmis: list[dict], sistem: str,
             araclar: list[dict] | None, zorla_arac: str | None = None) -> Yanit:
        import httpx
        from google.genai import errors
        t = self._types
        tool_config = None
        if zorla_arac:
            tool_config = t.ToolConfig(function_calling_config=t.FunctionCallingConfig(
                mode=t.FunctionCallingConfigMode.ANY, allowed_function_names=[_kodla(zorla_arac)]))
        try:
            yanit = self._client.models.generate_content(
                model=model, contents=self._icerikler(gecmis, model),
                config=t.GenerateContentConfig(
                    system_instruction=sistem,
                    # None = arac yok; bos Tool nesnesi bile sema tasir.
                    tools=(None if araclar is None else [self._arac(araclar)]),
                    tool_config=tool_config,
                    automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True)))
        except errors.ClientError as e:
            if e.code == 429:
                raise OranSiniri(429, str(e.message)) from e
            raise ModelHatasi(int(e.code or 0), str(e.message)) from e
        except errors.ServerError as e:
            raise SunucuHatasi(int(e.code or 500), str(e.message)) from e
        except httpx.TimeoutException as e:
            raise ZamanAsimi(str(e)) from e

        # Parcalar dogrudan okunur (yanit.text/function_calls yerine): imza
        # parcada duruyor ve metin parcasi da imza tasiyabiliyor.
        cagrilar: list[AracCagrisi] = []
        metinler: list[str] = []
        metin_ek: dict = {}
        aday = (yanit.candidates or [None])[0]
        for parca in ((aday.content.parts if aday and aday.content else None) or []):
            imza = getattr(parca, "thought_signature", None)
            ek = {"gemini_imza": base64.b64encode(imza).decode("ascii")} if imza else {}
            if getattr(parca, "function_call", None) is not None:
                fc = parca.function_call
                cagrilar.append(AracCagrisi(ad=_coz(fc.name), args=dict(fc.args or {}),
                                            id=getattr(fc, "id", None) or yeni_cagri_kimligi(), ek=ek))
            elif getattr(parca, "text", None) and not getattr(parca, "thought", False):
                metinler.append(parca.text)
                if ek:
                    metin_ek = ek
        metin = "".join(metinler) or None
        k = getattr(yanit, "usage_metadata", None)
        return Yanit(metin=metin, cagrilar=cagrilar, icerik=model_turu(metin, cagrilar, metin_ek),
                     girdi_token=int(getattr(k, "prompt_token_count", 0) or 0),
                     cikti_token=int(getattr(k, "candidates_token_count", 0) or 0))

    def modeller(self) -> list[str]:
        return sorted(m.name.removeprefix("models/") for m in self._client.models.list()
                      if "generateContent" in (m.supported_actions or []))
