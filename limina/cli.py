"""cli.py — komut satiri: python -m limina.vekil_v0 / limina-cli.

vekil_v0'dan ayrildi. Site yonetimi (--siteler/--site-ekle/--site-sil), gecmis
ve geri alma, gorev calistirma ve durumdan devam.
"""
from __future__ import annotations

import re
import shutil
import sys
import tomllib

from limina import PROJE_KOKU, journal
from limina.baglam import B
from limina.olaylar import Durduruldu

from limina import POLICY_DOSYASI as POLICY_PATH  # noqa: E402


# --- Site yönetimi: policy.toml'daki [browser].izinli_alanlar'ı düzenler. ---
# Ajan döngüsünden bağımsızdır, model çağırmaz.

def _site_gecerli_mi(alan: str) -> str | None:
    """Geçersizse sebep döndürür, geçerliyse None."""
    if not alan or any(c in alan for c in " /:"):
        return f"'{alan}' geçersiz alan adı: boşluk, '/', ':' içeremez."
    if "." not in alan:
        return f"'{alan}' geçersiz alan adı: en az bir nokta içermeli (örn. example.com)."
    return None


def _raw_izinli_alanlar() -> list[str]:
    with open(POLICY_PATH, "rb") as f:
        ham = tomllib.load(f)
    return ham.get("browser", {}).get("izinli_alanlar", [])


def _izinli_alanlar_guncelle(yeni_liste: list[str]) -> str | None:
    """policy.toml'daki izinli_alanlar dizisini yeniden yazar.
    Önce policy.toml.yedek adıyla yedek alır; yazdıktan sonra tomllib ile geri okuyup
    doğrular, bozuksa yedekten geri yükler. Başarılıysa None, değilse hata metni döner."""
    yedek_yolu = POLICY_PATH.with_name(POLICY_PATH.name + ".yedek")
    shutil.copy2(POLICY_PATH, yedek_yolu)

    orijinal = POLICY_PATH.read_text(encoding="utf-8")
    satirlar = "\n".join(f'    "{a}",' for a in yeni_liste)
    yeni_blok = f"izinli_alanlar = [\n{satirlar}\n]"
    guncel, sayac = re.subn(r"izinli_alanlar\s*=\s*\[[^\]]*\]", yeni_blok, orijinal, count=1)
    if sayac == 0:
        return "policy.toml içinde 'izinli_alanlar' dizisi bulunamadı, hiçbir şey değiştirilmedi."

    POLICY_PATH.write_text(guncel, encoding="utf-8")

    try:
        with open(POLICY_PATH, "rb") as f:
            tomllib.load(f)
    except Exception as e:
        shutil.copy2(yedek_yolu, POLICY_PATH)
        return f"policy.toml yazıldıktan sonra bozuk çıktı ({type(e).__name__}: {e}), yedekten geri yüklendi."
    return None


def main() -> None:
    """CLI giris noktasi (pyproject: limina-cli). sys.exit ile doner."""
    # --tani / --surum: model, MCP, pencere yuklenmeden. Dondurulmus surumde
    # "acilmiyor" sikayetinin ilk adimi: limina-cli.exe --tani
    if sys.argv[1:2] in (["--tani"], ["--surum"], ["--version"]):
        from limina import baslat
        print(baslat.tanila() if sys.argv[1] == "--tani" else baslat.surum())
        sys.exit(0)
    # Dongu (ve MCP baglantisi) yalnizca burada, komut satirindan cagrilinca yuklenir.
    from limina import vekil_v0 as _vekil
    argumanlar = sys.argv[1:]
    mod = None
    if "--mod" in argumanlar:
        _i = argumanlar.index("--mod")
        if _i + 1 >= len(argumanlar):
            print("Kullanım: --mod <hizli|dengeli|derin|azami>")
            sys.exit(1)
        mod = argumanlar[_i + 1]
        del argumanlar[_i:_i + 2]

    profil = None
    if "--profil" in argumanlar:
        _i = argumanlar.index("--profil")
        if _i + 1 >= len(argumanlar):
            print("Kullanım: --profil <ad>")
            sys.exit(1)
        profil = argumanlar[_i + 1]
        del argumanlar[_i:_i + 2]

    if not argumanlar:
        print('Kullanım: python -m limina.vekil_v0 "görev metni" [--mod hizli|dengeli|derin|azami] [--profil <ad>]')
        print('          python -m limina.vekil_v0 --devam <kimlik> [--mod ...] [--profil <ad>]')
        print('          python -m limina.vekil_v0 --gecmis')
        print('          python -m limina.vekil_v0 --geri-al [dosya]')
        print('          python -m limina.vekil_v0 --siteler')
        print('          python -m limina.vekil_v0 --site-ekle <alan>')
        print('          python -m limina.vekil_v0 --site-sil <alan>')
        sys.exit(1)

    if argumanlar[0] == "--devam":
        if len(argumanlar) < 2:
            print("Kullanım: python -m limina.vekil_v0 --devam <kimlik>")
            sys.exit(1)
        try:
            print(_vekil.devam_et(argumanlar[1], mod, profil=profil))
        except (KeyboardInterrupt, Durduruldu):
            print("\n\nDurduruldu (Ctrl-C). Yapilan islemler gunlukte, geri almak icin --gecmis")
            sys.exit(130)
    elif argumanlar[0] == "--gecmis":
        print(journal.bekleyen())
    elif argumanlar[0] == "--geri-al":
        print(journal.geri_al(argumanlar[1] if len(argumanlar) > 1 else None))
    elif argumanlar[0] == "--siteler":
        liste = _raw_izinli_alanlar()
        print("\n".join(liste) if liste else "(liste boş)")
    elif argumanlar[0] == "--site-ekle":
        if len(argumanlar) < 2:
            print("Kullanım: python -m limina.vekil_v0 --site-ekle <alan>")
        else:
            alan = argumanlar[1].strip()
            hata = _site_gecerli_mi(alan)
            if hata:
                print(hata)
            else:
                mevcut = _raw_izinli_alanlar()
                if any(a.lower() == alan.lower() for a in mevcut):
                    print(f"'{alan}' zaten listede.")
                else:
                    sonuc = _izinli_alanlar_guncelle(mevcut + [alan])
                    print(sonuc or f"'{alan}' eklendi.")
    elif argumanlar[0] == "--site-sil":
        if len(argumanlar) < 2:
            print("Kullanım: python -m limina.vekil_v0 --site-sil <alan>")
        else:
            alan = argumanlar[1].strip()
            mevcut = _raw_izinli_alanlar()
            kalan = [a for a in mevcut if a.lower() != alan.lower()]
            if len(kalan) == len(mevcut):
                print(f"'{alan}' listede yok.")
            else:
                sonuc = _izinli_alanlar_guncelle(kalan)
                print(sonuc or f"'{alan}' silindi.")
    else:
        try:
            print(_vekil.calistir(argumanlar[0], mod, profil=profil))
        except (KeyboardInterrupt, Durduruldu):
            print("\n\nDurduruldu (Ctrl-C). Yapilan islemler gunlukte, geri almak icin --gecmis")
            sys.exit(130)


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
