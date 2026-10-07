"""anahtar.py — API anahtarlarinin okunmasi ve saklanmasi.

Oncelik: Ayarlar'dan KAYDEDILEN anahtar (keyring, yoksa ~/.vekil/credentials.json)
> ortam degiskeni. Eskiden ortam degiskeni ondeydi ve kullanici Ayarlar'a yeni
anahtar yapistirinca hicbir sey degismiyordu ("api guncellenmeli", 2026-09-21):
masaustu uygulamasinda kullanicinin son yaptigi acik eylem kazanmali. Ortam
degiskeni hic anahtar kaydetmemis kullanici icin yedek yol olarak duruyor.

Dosya adi bilerek "credentials": policy.toml'un varsayilan kara listesi
(*credential*) bu adi kapsar — ~/.vekil bir okuma koku olarak eklense bile
ajan bu dosyayi okuyamaz. Anahtar hicbir zaman policy.toml'a, journal'a,
sohbet dosyasina ya da olay akisina yazilmaz; arayuze de yalnizca maskeli
(son 4 karakter) doner.

keyring istege bagli (pip install -e .[anahtar]): Windows'ta Credential
Manager'a yazar. Yoksa dosya — ve arayuz bunu acikca soyler.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pevrai import journal

DOSYA = journal.KOK / "credentials.json"
# Yuva dizini: keyring anahtarlari sayamaz (yalnizca sorar), bu yuzden
# hangi saglayicida hangi ADLI yuvalarin oldugu burada tutulur. Anahtarin
# kendisi burada DEGIL (keyring'de; keyring yoksa credentials.json'da).
YUVA_DIZINI = journal.KOK / "anahtar_yuvalari.json"
SERVIS = "pevrai"
# Credential Manager records from existing installations remain readable.
ESKI_SERVIS = "limina"
# Yuva adi: kisa, dosya/keyring adinda sorun cikarmayan karakterler.
YUVA_KALIBI = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

ORTAM_DEGISKENI = {
    "gemini": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def _keyring():
    try:
        import keyring  # type: ignore
        return keyring
    except Exception:
        return None


def _dosyadan() -> dict[str, str]:
    try:
        if DOSYA.exists():
            veri = json.loads(DOSYA.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in veri.items() if isinstance(v, str)}
    except Exception:
        pass
    return {}


def kimlik(saglayici: str, yuva: str = "") -> str:
    """Depo anahtari: varsayilan yuva 'gemini', adli yuva 'gemini#is'.

    Coklu ajan icin: ayni saglayicida birden fazla anahtar (kota, hesap).
    Varsayilan yuva ("") eski tek-anahtar davranisinin kendisi — hicbir
    mevcut kurulum degismez."""
    yuva = (yuva or "").strip()
    return f"{saglayici}#{yuva}" if yuva else saglayici


def yuvalar(saglayici: str) -> list[str]:
    """Bu saglayici icin tanimli ADLI yuvalar (varsayilan "" haric)."""
    try:
        if YUVA_DIZINI.exists():
            veri = json.loads(YUVA_DIZINI.read_text(encoding="utf-8"))
            return sorted(str(y) for y in (veri.get(saglayici) or []) if YUVA_KALIBI.match(str(y)))
    except Exception:
        pass
    return []


def _yuva_kaydet(saglayici: str, yuva: str, var: bool) -> None:
    try:
        veri = json.loads(YUVA_DIZINI.read_text(encoding="utf-8")) if YUVA_DIZINI.exists() else {}
    except Exception:
        veri = {}
    liste = set(str(y) for y in (veri.get(saglayici) or []))
    (liste.add if var else liste.discard)(yuva)
    veri[saglayici] = sorted(liste)
    YUVA_DIZINI.parent.mkdir(parents=True, exist_ok=True)
    YUVA_DIZINI.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")


def oku(saglayici: str, yuva: str = "") -> str | None:
    """Anahtar metni ya da None. Kaynak sirasi modul docstring'inde.
    Adli yuvada ortam degiskeni yedegi YOK: ortam degiskeni varsayilan yuvaya aittir."""
    k = kimlik(saglayici, yuva)
    kr = _keyring()
    if kr is not None:
        for servis in (SERVIS, ESKI_SERVIS):
            try:
                deger = kr.get_password(servis, k)
                if deger:
                    return deger
            except Exception:
                pass
    kayitli = _dosyadan().get(k)
    if kayitli:
        return kayitli
    if not yuva:
        ortam = ORTAM_DEGISKENI.get(saglayici)
        if ortam and os.environ.get(ortam):
            return os.environ[ortam]
    return None


def kaynak(saglayici: str, yuva: str = "") -> str:
    """Anahtarin nereden geldigi: 'keyring' | 'dosya' | 'ortam' | 'yok' (oku ile ayni sira)."""
    k = kimlik(saglayici, yuva)
    kr = _keyring()
    if kr is not None:
        for servis in (SERVIS, ESKI_SERVIS):
            try:
                if kr.get_password(servis, k):
                    return "keyring"
            except Exception:
                pass
    if _dosyadan().get(k):
        return "dosya"
    if not yuva:
        ortam = ORTAM_DEGISKENI.get(saglayici)
        if ortam and os.environ.get(ortam):
            return "ortam"
    return "yok"


def yaz(saglayici: str, anahtar: str, yuva: str = "") -> str | None:
    """Anahtari saklar. Hata varsa metin doner. Bos anahtar = sil (yuvayi da dizinden dusurur)."""
    saglayici = str(saglayici or "").strip()
    anahtar = str(anahtar or "").strip()
    yuva = str(yuva or "").strip()
    if saglayici not in ORTAM_DEGISKENI:
        return f"Taninmayan saglayici: {saglayici}"
    if yuva and not YUVA_KALIBI.match(yuva):
        return "Yuva adi gecersiz: 1-32 karakter, harf/rakam/_/- (ornek: is, kisisel, ikinci)."
    if anahtar and (len(anahtar) < 8 or any(c.isspace() for c in anahtar)):
        return "Anahtar bicimi gecersiz (bosluk iceriyor ya da cok kisa)."
    k = kimlik(saglayici, yuva)
    if yuva:
        try:
            _yuva_kaydet(saglayici, yuva, bool(anahtar))
        except OSError as e:
            return f"Yuva dizini yazilamadi: {e}"
    kr = _keyring()
    if kr is not None:
        try:
            if anahtar:
                kr.set_password(SERVIS, k, anahtar)
                # An old value must not reappear after the new one is deleted.
                try:
                    kr.delete_password(ESKI_SERVIS, k)
                except Exception:
                    pass
            else:
                for servis in (SERVIS, ESKI_SERVIS):
                    try:
                        kr.delete_password(servis, k)
                    except Exception:
                        pass
            return None
        except Exception:
            pass                        # keyring calismadi: dosyaya dus
    try:
        veri = _dosyadan()
        if anahtar:
            veri[k] = anahtar
        else:
            veri.pop(k, None)
        DOSYA.parent.mkdir(parents=True, exist_ok=True)
        DOSYA.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            os.chmod(DOSYA, 0o600)       # Windows'ta etkisiz ama zararsiz
        except OSError:
            pass
        return None
    except OSError as e:
        return f"Anahtar yazilamadi: {e}"


def maskele(anahtar: str | None) -> str:
    if not anahtar:
        return ""
    return "•" * 8 + anahtar[-4:]
