"""limina.araclar — yerel arac paketi.

Ice aktarmak butun yerlesik araclari kayit defterine yazar (dekoratorler
modul yuklenirken calisir). Yeni yerel arac eklemek: bu klasore bir modul
koy, fonksiyonu @arac ile bildir, buradaki listeye ekle. Baska hicbir yere
dokunulmaz — sema, risk, yol modu, paket ve panel adi bildirimden turer;
policy.example.toml'daki [araclar] satiri kurulum sablonu icin gerekir
(deny by default: politikada olmayan arac calismaz).
"""
from limina.araclar import acma, ag_araclari, dosya, ekip_pano, tarayici_araclari  # noqa: F401  (kayit icin)
from limina.araclar import kayit

__all__ = ["kayit", "dosya", "tarayici_araclari", "acma", "ekip_pano", "ag_araclari"]
