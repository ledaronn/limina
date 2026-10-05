"""model_testi.py — saglayici katmani (limina.model), AGSIZ.

Uc adaptorun bicim cevirileri ve hata eslemesi sinanir. Gemini SDK nesneleri
gercek google-genai tipleriyle (kuruluysa), OpenAI-uyumlu adaptor
httpx.MockTransport ile, Anthropic adaptoru yalnizca saf cevirme
fonksiyonlariyla (SDK istege bagli). Model CAGRILMAZ, kota harcanmaz.

Calistirma: python tests/model_testi.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from limina.model import taban
from limina.model.taban import (AracCagrisi, ModelHatasi, OranSiniri, SunucuHatasi,
                                ardisik_birlestir, kullanici_mesaji, model_turu, sonuc_mesaji)

HATA = 0


def dogrula(kosul: bool, mesaj: str) -> None:
    global HATA
    print(("  GECTI  " if kosul else "  KALDI  ") + mesaj)
    if not kosul:
        HATA += 1


ARACLAR = [{"name": "list_dir", "description": "Klasoru listeler.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
           {"name": "converter.convert", "description": "Donusturur.",
            "parameters": {"type": "object", "properties": {"src": {"type": "string"}}}}]

GECMIS = [
    kullanici_mesaji("kum'u listele"),
    model_turu("Bakiyorum.", [AracCagrisi(ad="list_dir", args={"path": "kum"}, id="call_1"),
                              AracCagrisi(ad="converter.convert", args={"src": "a.pdf"}, id="call_2")]),
    sonuc_mesaji([("list_dir", "call_1", "3 dosya"), ("converter.convert", "call_2", "tamam")]),
    model_turu("Bitti.", []),
]


def bolum1_taban() -> None:
    print("\n1) Taban bicim yardimcilari")
    m = sonuc_mesaji([("a", "id1", "x")])
    dogrula(m["rol"] == "user" and m["parcalar"][0] == {"tip": "sonuc", "ad": "a", "cevap": {"result": "x"}, "id": "id1"},
            "sonuc_mesaji tek user turu, cevap {'result': ...}")
    t = model_turu(None, [AracCagrisi("a", {"k": 1}, "id1")])
    dogrula(t == {"rol": "model", "parcalar": [{"tip": "cagri", "ad": "a", "args": {"k": 1}, "id": "id1"}]},
            "model_turu metinsiz yalnizca cagri parcasi")
    b = ardisik_birlestir([kullanici_mesaji("a"), kullanici_mesaji("b"), model_turu("c", [])])
    dogrula(len(b) == 2 and len(b[0]["parcalar"]) == 2, "ardisik ayni rol tek turda birlesti")
    dogrula(taban.yeni_cagri_kimligi().startswith("call_"), "uretilen cagri kimligi")
    # Eski (Gemini donemi) sohbet: kimliksiz cagri/sonuc -> ad sirasiyla eslenir
    eski = [kullanici_mesaji("x"),
            {"rol": "model", "parcalar": [{"tip": "cagri", "ad": "a", "args": {}}, {"tip": "cagri", "ad": "a", "args": {"n": 2}}]},
            {"rol": "user", "parcalar": [{"tip": "sonuc", "ad": "a", "cevap": {"result": "1"}}, {"tip": "sonuc", "ad": "a", "cevap": {"result": "2"}}]}]
    tam = taban.kimlikleri_tamamla(eski)
    c1, c2 = tam[1]["parcalar"]; s1, s2 = tam[2]["parcalar"]
    dogrula(c1["id"] and c2["id"] and c1["id"] != c2["id"] and s1["id"] == c1["id"] and s2["id"] == c2["id"],
            "kimliksiz cagri/sonuc ciftleri sirayla eslendi")
    dogrula("id" not in eski[1]["parcalar"][0], "orijinal gecmis degismedi (kopya)")
    from limina.model.openai_uyumlu import OpenAIUyumlu
    m = OpenAIUyumlu._mesajlar(eski, "")
    dogrula(m[1]["tool_calls"][0]["id"] == m[2]["tool_call_id"] and m[1]["tool_calls"][1]["id"] == m[3]["tool_call_id"],
            "OpenAI: eski sohbetin tool_call_id'leri eslesiyor")


def bolum2_openai() -> None:
    print("\n2) OpenAI-uyumlu adaptor (MockTransport)")
    import httpx
    from limina.model.openai_uyumlu import OpenAIUyumlu

    msj = OpenAIUyumlu._mesajlar(GECMIS, "SISTEM")
    dogrula(msj[0] == {"role": "system", "content": "SISTEM"}, "sistem ilk mesaj")
    dogrula(msj[1] == {"role": "user", "content": "kum'u listele"}, "kullanici metni")
    a = msj[2]
    dogrula(a["role"] == "assistant" and a["content"] == "Bakiyorum." and len(a["tool_calls"]) == 2
            and a["tool_calls"][1]["function"]["name"] == "converter__convert"
            and json.loads(a["tool_calls"][0]["function"]["arguments"]) == {"path": "kum"},
            "assistant turu: metin + tool_calls (MCP adi kodlandi: nokta 400 doner, args JSON dizesi)")
    dogrula(msj[3] == {"role": "tool", "tool_call_id": "call_1", "content": "3 dosya"}
            and msj[4]["tool_call_id"] == "call_2", "her sonuc ayri tool mesaji, id eslesiyor")
    dogrula(msj[5] == {"role": "assistant", "content": "Bitti."}, "son model metni")
    ar = OpenAIUyumlu._araclar(ARACLAR)
    dogrula(ar[0]["type"] == "function" and ar[0]["function"]["parameters"]["required"] == ["path"],
            "arac semasi function sarmalinda")
    import re as _re
    dogrula(all(_re.match(r"^[a-zA-Z0-9_-]+$", x["function"]["name"]) for x in ar)
            and ar[1]["function"]["name"] == "converter__convert",
            "arac adlari saglayici kuralina uyuyor (NVIDIA/OpenAI: yalnizca a-z A-Z 0-9 _ -)")

    # --- sahte sunucu ---
    istekler: list[dict] = []

    def sunucu(istek: httpx.Request) -> httpx.Response:
        govde = json.loads(istek.content or b"{}")
        istekler.append({"yol": istek.url.path, "govde": govde, "yetki": istek.headers.get("authorization")})
        if istek.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gpt-x"}, {"id": "llama"}]})
        if govde.get("model") == "kota":
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        if govde.get("model") == "bozuk":
            return httpx.Response(503, text="bad gateway")
        if govde.get("model") == "yetkisiz":
            return httpx.Response(401, json={"error": {"message": "bad key"}})
        if govde.get("model") == "mcp":
            return httpx.Response(200, json={
                "choices": [{"message": {"role": "assistant", "content": None,
                                         "tool_calls": [{"id": "tc1", "type": "function",
                                                         "function": {"name": "converter__convert", "arguments": "{}"}}]}}]})
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": None,
                                     "tool_calls": [{"id": "tc9", "type": "function",
                                                     "function": {"name": "list_dir", "arguments": "{\"path\": \"kum\"}"}}]}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3}})

    s = OpenAIUyumlu("ANAHTAR", 5, "http://sahte/v1")
    s._http = httpx.Client(base_url="http://sahte/v1", transport=httpx.MockTransport(sunucu),
                           headers={"Authorization": "Bearer ANAHTAR"})
    y = s.uret("m", [kullanici_mesaji("hi")], "S", ARACLAR, zorla_arac="list_dir")
    dogrula(istekler[-1]["yol"] == "/v1/chat/completions" and istekler[-1]["yetki"] == "Bearer ANAHTAR",
            "dogru uc nokta + Bearer basligi")
    dogrula(istekler[-1]["govde"]["tool_choice"] == {"type": "function", "function": {"name": "list_dir"}},
            "zorla_arac -> tool_choice")
    dogrula(y.cagrilar[0].ad == "list_dir" and y.cagrilar[0].args == {"path": "kum"} and y.cagrilar[0].id == "tc9",
            "yanit: cagri adi/args/id cozuldu")
    dogrula(y.icerik["parcalar"][0]["tip"] == "cagri" and y.girdi_token == 12 and y.cikti_token == 3,
            "icerik model turu, token sayilari")
    y = s.uret("mcp", [kullanici_mesaji("hi")], "S", ARACLAR, zorla_arac="converter.convert")
    dogrula(y.cagrilar[0].ad == "converter.convert"
            and istekler[-1]["govde"]["tool_choice"]["function"]["name"] == "converter__convert",
            "MCP araci: giderken kodlanir, donen cagri gercek ada cozulur")
    s.uret("m", [kullanici_mesaji("hi")], "S", None)
    dogrula("tools" not in istekler[-1]["govde"], "araclar None -> govdede tools yok")
    for model, tip in [("kota", OranSiniri), ("bozuk", SunucuHatasi), ("yetkisiz", ModelHatasi)]:
        try:
            s.uret(model, [kullanici_mesaji("x")], "", None); dogrula(False, f"{model}: istisna bekleniyordu")
        except tip as e:
            dogrula(type(e) is tip, f"{model} -> {tip.__name__} (code {e.code})")
    dogrula(s.modeller() == ["gpt-x", "llama"], "modeller() /models listesini okur")
    anahtarsiz = OpenAIUyumlu("", 5, "http://localhost:11434/v1")
    dogrula("Authorization" not in anahtarsiz._http.headers, "anahtarsiz yerel sunucu: Authorization basligi yok")


def bolum3_anthropic() -> None:
    print("\n3) Anthropic adaptoru (saf cevirme)")
    from limina.model.anthropic_ import Anthropic
    msj = Anthropic._mesajlar(GECMIS)
    dogrula(msj[0] == {"role": "user", "content": [{"type": "text", "text": "kum'u listele"}]}, "kullanici blogu")
    a = msj[1]
    dogrula(a["role"] == "assistant" and a["content"][0] == {"type": "text", "text": "Bakiyorum."}
            and a["content"][1] == {"type": "tool_use", "id": "call_1", "name": "list_dir", "input": {"path": "kum"}},
            "assistant: text + tool_use bloklari")
    dogrula(msj[2]["role"] == "user" and msj[2]["content"][0] == {"type": "tool_result", "tool_use_id": "call_1", "content": "3 dosya"}
            and len(msj[2]["content"]) == 2, "tool_result bloklari TEK user mesajinda, id eslesiyor")
    ar = Anthropic._araclar(ARACLAR)
    dogrula(ar[1] == {"name": "converter__convert", "description": "Donusturur.",
                      "input_schema": {"type": "object", "properties": {"src": {"type": "string"}}}},
            "arac semasi input_schema ile")
    # ardisik user turlari birlesir (Anthropic kesin siralama ister)
    m2 = Anthropic._mesajlar([kullanici_mesaji("a"), kullanici_mesaji("b")])
    dogrula(len(m2) == 1 and len(m2[0]["content"]) == 2, "ardisik user turlari tek mesajda")


def bolum4_gemini() -> None:
    print("\n4) Gemini adaptoru (SDK tipleriyle, agsiz)")
    try:
        from google.genai import types  # noqa: F401
    except Exception:
        print("  NOT    google-genai kurulu degil, cevirme testi atlandi")
        return
    from limina.model.gemini import Gemini, _coz, _kodla
    dogrula(_kodla("converter.convert") == "converter__convert" and _coz("converter__convert") == "converter.convert",
            "nokta <-> __ kodlamasi yalnizca adaptorde")
    g = Gemini.__new__(Gemini)          # __init__ Client kurar; burada gerekmiyor
    from google.genai import types
    g._types = types
    ic = g._icerikler(GECMIS)
    dogrula(ic[0].role == "user" and ic[0].parts[0].text == "kum'u listele", "Content/Part kuruldu")
    fc = ic[1].parts[2].function_call      # parts[0] metin, [1] list_dir, [2] MCP cagrisi
    dogrula(fc.name == "converter__convert" and dict(fc.args) == {"src": "a.pdf"}, "MCP adi Gemini icin kodlandi")
    fr = ic[2].parts[0].function_response
    dogrula(fr.name == "list_dir" and dict(fr.response) == {"result": "3 dosya"}, "function_response")
    arac = g._arac(ARACLAR)
    dogrula([d.name for d in arac.function_declarations] == ["list_dir", "converter__convert"], "Tool bildirimleri")


def bolum5_anahtar_ve_kur() -> None:
    print("\n5) Anahtar deposu ve kur()")
    import os
    import tempfile
    from limina import anahtar, model
    from limina.gate import Politika

    d = Path(tempfile.mkdtemp(prefix="limina_anahtar_"))
    eski_dosya, eski_kr = anahtar.DOSYA, anahtar._keyring
    anahtar.DOSYA = d / "credentials.json"
    anahtar._keyring = lambda: None          # dosya yolunu sina
    eski_ortam = {k: os.environ.pop(k, None) for k in anahtar.ORTAM_DEGISKENI.values()}
    try:
        dogrula(anahtar.oku("openai") is None and anahtar.kaynak("openai") == "yok", "bos depo")
        dogrula(anahtar.yaz("openai", "kisa") is not None, "cok kisa anahtar reddedildi")
        dogrula(anahtar.yaz("openai", "sk-bosluk lu") is not None, "boslukl anahtar reddedildi")
        dogrula(anahtar.yaz("uydurma", "sk-xxxxxxxxxx") is not None, "taninmayan saglayici reddedildi")
        dogrula(anahtar.yaz("openai", "sk-1234567890abcd") is None and anahtar.oku("openai") == "sk-1234567890abcd",
                "dosyaya yazildi ve okundu")
        dogrula(anahtar.kaynak("openai") == "dosya" and anahtar.maskele(anahtar.oku("openai")) == "••••••••abcd",
                "kaynak 'dosya', maske son 4")
        os.environ["OPENAI_API_KEY"] = "sk-ortamdan-gelen-1"
        dogrula(anahtar.oku("openai") == "sk-1234567890abcd" and anahtar.kaynak("openai") == "dosya",
                "KAYDEDILEN anahtar ortam degiskeninin onunde (Ayarlar'a yapistirilan kazanir)")
        dogrula(anahtar.yaz("openai", "") is None and anahtar.oku("openai") == "sk-ortamdan-gelen-1"
                and anahtar.kaynak("openai") == "ortam", "kayitli silinince ortam degiskeni yedek")
        os.environ.pop("OPENAI_API_KEY")
        dogrula(anahtar.oku("openai") is None, "bos anahtar = sil")

        # kur(): saglayici secimi + anahtar yoksa 401
        class P:  # gate.Politika'nin kur()'un okudugu alanlari
            saglayici = "anthropic"; taban_url = ""
        try:
            model.kur(P()); dogrula(False, "anahtarsiz anthropic kurulmamali")
        except ModelHatasi as e:
            dogrula(e.code == 401 and "ANTHROPIC_API_KEY" in e.mesaj, "anahtar yoksa 401 + ortam degiskeni ipucu")
        P.saglayici = "openai"; P.taban_url = "http://localhost:11434/v1"
        s = model.kur(P())
        dogrula(s.ad == "openai" and "Authorization" not in s._http.headers, "yerel OpenAI-uyumlu sunucu anahtarsiz kurulur")
        P.saglayici = "uydurma"
        try:
            model.kur(P()); dogrula(False, "taninmayan saglayici")
        except ModelHatasi:
            dogrula(True, "taninmayan saglayici reddedildi")
        # gate: policy.toml [model] saglayici dogrulamasi
        pol_dosya = d / "policy.toml"
        pol_dosya.write_text('[model]\nvarsayilan = "m"\nsaglayici = "openai"\ntaban_url = "http://x/v1"\n[araclar]\n', encoding="utf-8")
        pol = Politika(pol_dosya)
        dogrula(pol.saglayici == "openai" and pol.taban_url == "http://x/v1", "gate saglayici/taban_url okur")
        pol_dosya.write_text('[model]\nvarsayilan = "m"\nsaglayici = "yok"\n[araclar]\n', encoding="utf-8")
        try:
            Politika(pol_dosya); dogrula(False, "gecersiz saglayici acilista reddedilmeli")
        except ValueError:
            dogrula(True, "gecersiz saglayici acilista reddedildi (fail-closed)")
    finally:
        anahtar.DOSYA, anahtar._keyring = eski_dosya, eski_kr
        for k, v in eski_ortam.items():
            if v is not None:
                os.environ[k] = v
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def main() -> int:
    bolum1_taban()
    bolum2_openai()
    bolum3_anthropic()
    bolum4_gemini()
    bolum5_anahtar_ve_kur()
    print("\nSonuc: " + ("TUM TESTLER GECTI" if HATA == 0 else f"{HATA} test kaldi"))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
