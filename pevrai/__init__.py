# pevrai — ajan paketi. Kaynak kodun tamami bu klasorde; kullanicinin
# elledigi seyler (policy.toml, config/) proje kokunde kalir. Yerlesim
# buradaki sabitlerden okunur, hicbir modul kendi konumundan "proje koku"
# turetmez.
#
# IKI YERLESIM:
#   Kaynaktan (git klonu, pip -e):  kod ve kisisel dosyalar ayni klasorde.
#       PAKET      = .../AI/pevrai        (kod)
#       KAYNAK_KOK = .../AI               (sablonlar, Donusturucu/)
#       PROJE_KOKU = .../AI               (policy.toml, config/)
#   Dondurulmus (PyInstaller .exe):  kod Program Files'ta, salt okunur ve
#       kullanici basina ayrilmamis; kisisel dosyalar oraya YAZILAMAZ ve
#       yazilmamali (kapi "kod koku yazma koku icinde olamaz" der).
#       PAKET      = <kurulum>/_internal/pevrai
#       KAYNAK_KOK = <kurulum>/_internal   (sys._MEIPASS: sablonlar, Donusturucu/)
#       PROJE_KOKU = %LOCALAPPDATA%/Pevrai (ilk acilista sablondan kurulur)
import os
import sys
from pathlib import Path
from pevrai.uyumluluk import ortam, veri_koku

DONMUS = bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")

PAKET = Path(__file__).resolve().parent      # .../pevrai  (kod)
if DONMUS:
    KAYNAK_KOK = Path(sys._MEIPASS).resolve()
    PROJE_KOKU = veri_koku(Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")))
else:
    KAYNAK_KOK = PAKET.parent
    PROJE_KOKU = PAKET.parent

# policy.toml: normalde proje kokunde. PEVRAI_POLICY ortam degiskeni bir ekip
# ISCI surecinin uretilmis, DAR politikasini gosterir (ekip.py); isci hicbir
# zaman kullanicinin gercek policy.toml'unu okumaz/yazmaz. Kurulum sablonu
# uretimi (kurulum.py) bu dosya icin YAPILMAZ — yoksa hata.
_policy = ortam("POLICY")
POLICY_DOSYASI = Path(_policy) if _policy else PROJE_KOKU / "policy.toml"
