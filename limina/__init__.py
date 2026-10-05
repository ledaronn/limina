# limina — ajan paketi. Kaynak kodun tamami bu klasorde; kullanicinin
# elledigi seyler (policy.toml, config/) proje kokunde kalir. Yerlesim
# buradaki sabitlerden okunur, hicbir modul kendi konumundan "proje koku"
# turetmez.
#
# IKI YERLESIM:
#   Kaynaktan (git klonu, pip -e):  kod ve kisisel dosyalar ayni klasorde.
#       PAKET      = .../AI/limina        (kod)
#       KAYNAK_KOK = .../AI               (sablonlar, Donusturucu/)
#       PROJE_KOKU = .../AI               (policy.toml, config/)
#   Dondurulmus (PyInstaller .exe):  kod Program Files'ta, salt okunur ve
#       kullanici basina ayrilmamis; kisisel dosyalar oraya YAZILAMAZ ve
#       yazilmamali (kapi "kod koku yazma koku icinde olamaz" der).
#       PAKET      = <kurulum>/_internal/limina
#       KAYNAK_KOK = <kurulum>/_internal   (sys._MEIPASS: sablonlar, Donusturucu/)
#       PROJE_KOKU = %LOCALAPPDATA%/Limina (ilk acilista sablondan kurulur)
import os
import sys
from pathlib import Path

DONMUS = bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")

PAKET = Path(__file__).resolve().parent      # .../limina  (kod)
if DONMUS:
    KAYNAK_KOK = Path(sys._MEIPASS).resolve()
    PROJE_KOKU = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "Limina"
else:
    KAYNAK_KOK = PAKET.parent
    PROJE_KOKU = PAKET.parent

# policy.toml: normalde proje kokunde. LIMINA_POLICY ortam degiskeni bir ekip
# ISCI surecinin uretilmis, DAR politikasini gosterir (ekip.py); isci hicbir
# zaman kullanicinin gercek policy.toml'unu okumaz/yazmaz. Kurulum sablonu
# uretimi (kurulum.py) bu dosya icin YAPILMAZ — yoksa hata.
POLICY_DOSYASI = Path(os.environ["LIMINA_POLICY"]) if os.environ.get("LIMINA_POLICY") else PROJE_KOKU / "policy.toml"
