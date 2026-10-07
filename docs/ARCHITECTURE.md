# Mimari

## 1. Ajan döngüsü

Sistemin kalbi. Diğer her şey bu döngüye takılan parçadır.

Faz 6 itibarıyla `guclu: bool` yerine `mod: str` var; Faz 7 buna `profil` parametresini
ve döngünün çıkış noktalarını tek bir karara bağlayan `gate.durum_karari`'yı ekledi.
Aşağıdaki pseudocode gerçek `vekil_v0.calistir` imzasını yansıtıyor (`mod` yoksayılırsa
`policy.toml [modlar] varsayilan_mod`a düşer):

```python
def calistir(gorev: str, mod: str | None = None, oturum: Oturum | None = None,
             profil: str | None = None) -> str:
    if profil is not None and profil not in POLITIKA.profiller:
        return "Taninmayan profil"              # fail-closed: model hic cagrilmaz
    demet = POLITIKA.mod_coz(mod)               # {"model": "varsayilan"|"guclu", "adim": N, "cagri": N}
    model = POLITIKA.model_guclu if demet["model"] == "guclu" else POLITIKA.model_varsayilan
    azami_adim, azami_cagri, azami_istek = demet["adim"], demet["cagri"], demet["istek"]
    if profil and profil.azami_adim:
        azami_adim = min(azami_adim, profil.azami_adim)   # profil yalnizca DARALTIR
    gecmis = [ilk_mesaj(gorev)]
    toplam_cagri = 0
    istek_sayaci = {"istek": 0}                 # gorev basina GONDERILEN istek (tur degil)
    baslangic_zamani = simdi()                  # journal.gorev_kayitlari bunun SONRASINA bakar

    for adim in range(1, azami_adim + 1):
        yanit = model_cagir(model, gecmis)      # 429/503/timeout'ta otomatik yeniden dener

        if not yanit.function_calls:
            return yanit.text                   # model isi bitirdi

        gecmis.append(yanit.candidates[0].content)
        tur_sayaci: dict[str, int] = {}         # bu turda risk seviyesi basina sayac

        for call in yanit.function_calls:
            toplam_cagri += 1
            if toplam_cagri > azami_cagri:
                # DOGRUDAN return ETMEZ: modele bir yanit verilir, tur tamamlanir,
                # karar asagida durum_karari'ya baglanir. Eskiden burada bir return
                # vardi ve gozetimsiz modda sessizce olen IKINCI bir yoldu.
                sonuc = "Cagri limiti doldu, bu istek islenmedi."
                gecmis.append(arac_sonucu(call.id, sonuc)); continue

            karar = gate.karar(call.name, call.args, aktif_url, profil)  # ALLOW / ASK / DENY
            risk = POLITIKA.araclar[call.name]

            asildi = gate.tur_karari(risk, tur_sayaci)  # saf fonksiyon, gate.py'de yasar
            tur_sayaci[risk] = tur_sayaci.get(risk, 0) + 1
            if asildi:
                sonuc = f"Bu turda {risk} riskli islem sinirina ulasildi. Kalani sonraki adimda iste."
            elif karar.sonuc == DENY:
                sonuc = f"Izin reddedildi: {karar.gerekce}"
            elif karar.sonuc == ASK and not onay_al(call, risk):  # EOF/Ctrl-C -> reddet
                sonuc = "Kullanici bu islemi reddetti. Alternatif bir yol dene ya da dur."
            else:
                sonuc = arac_calistir(call)     # istisna dahil her sey metne donusur

            gecmis.append(arac_sonucu(call.id, sonuc))

        # TEK KARAR, TEK CIKIS: UC sinir da ayni saf fonksiyona sorulur.
        # Yeni bir sinir buraya PARAMETRE olarak gelir, calistir'e RETURN olarak degil.
        if gate.durum_karari(adim, azami_adim,
                             cagri_tavaninda_mi=(toplam_cagri > azami_cagri),
                             butce_doldu_mu=gate.butce_karari(
                                 istek_sayaci["istek"], azami_istek) is not None,
                             model_bitirdi_mi=False) == "durum_yaz":
            return _durum_kaydet(...)           # ~/.vekil/durum/<kimlik>.md yazar, kimligi soyler
```

**Mod izin gevşetmez.** `mod` yalnızca "ne kadar hesap harcayacağım"ı belirler (model +
adım tavanı + çağrı tavanı bir demet olarak); `azami` modu `odeme`yi açmaz, onay kartını
atlamaz — izin kararı hâlâ tamamen `gate.karar()`'ın elinde. Dört mod (`hizli`, `dengeli`,
`derin`, `azami`) `policy.toml [modlar]`'da tanımlı; kullanıcı görev başına hangisini
istediğini seçer, sistem otomatik yükseltme/indirgeme yapmaz (o "dinamik" davranış ayrı,
henüz çözülmemiş bir problem — bkz. [ROADMAP.md](ROADMAP.md)).

### Değişmez kurallar

1. **Araç sonucu her zaman modele geri döner.** Başarı da hata da. `FileNotFoundError`
   metnini gören model yolu düzeltir; istisnayı yutan bir yürütücü ajanı script'e çevirir.
2. **Üç ayrı üst sınır vardır.** Adım (model turu), çağrı (toplam araç çağrısı) ve
   **istek bütçesi** (görev başına gönderilen model isteği) —
   ikisi aynı şey değildir: Gemini bir turda paralel birden fazla araç çağırabildiği için
   birkaç turluk bir görev onlarca çağrıya çıkabilir (ölçüldü, bkz. DEVIR_FAZ5). İkisinin
   sayısı artık modül sabiti değil, seçilen `mod`un `policy.toml [modlar]`'daki adım/çağrı
   demeti (yukarı bkz.). `gate.TUR_TAVANI` bunun üstüne risk seviyesine göre **tur başına**
   bir tavan daha koyar (WRITE 5, DESTRUCTIVE 2, NETWORK/EXEC 3, READ 12): yüksek riskli
   bir araç (ör. `trash`) tek turda yığın halde çalışamaz, iş birden fazla tura bölünür ve
   kullanıcı her partiyi ayrı onaylar. Karar `gate.tur_karari` içinde saf bir fonksiyon —
   modelsiz test edilir (`ayarlar_testi.py` bölüm 19).

   **İstek bütçesi neden adım tavanından farklı bir şey sayıyor:** adım model
   TURLARINI sayar, `gate.butce_karari` gönderilen İSTEKLERİ. Bir tur 429/503/zaman
   aşımında `API_DENEME` (3) kez yeniden deneniyor ve her deneme günlük kotadan ayrı
   düşüyor — yani adım tavanı 8 olan bir görev 27 istek gönderebilir. Gözetimsiz
   modda bu, tek bir yanlış anlaşılmış görevin günün hakkını tüketmesi demek.
   Bütçe `policy.toml [modlar.<ad>].istek`'ten gelir, görev başına sıfırlanır, ve
   **günlük tavan her zaman dışındadır** (o her istekten önce bakılır, bütçe tur
   bittikten sonra).
3. **İzin kapısı atlanamaz.** Yürütücüye giden tek yol `gate.karar()` üzerindendir — yerel
   araç da, MCP köprüsünden gelen araç da aynı kapıdan geçer.
4. **Onay alınamazsa reddedilir.** `input()` EOF alırsa (stdin yok) veya kullanıcı Ctrl-C
   basarsa, "evet" değil "hayır" varsayılır. Gözetimsiz modda da geçerli olması gereken kural
   budur — ölçülmeden "varsayılan izin ver"e kaymaması için Faz 3'te kod seviyesinde kilitlendi.
5. **Her adım günlüğe yazılır.** Ajan ne yaptığını sonradan anlatabilmelidir.
6. **Döngü sessizce ölmez.** Bir tavana çarpma bir METİN mesajı değil bir DURUMDUR:
   `gate.durum_karari` "durum_yaz" derse döngü modelden tek bir zorlanmış özet alıp
   `~/.vekil/durum/<kimlik>.md` dosyasını yazar (aşağıda §2). Gözetimsiz modda
   "görev bitmedi" diyen bir metni okuyan kimse yok; dosya okunabilir.
7. **Kod çalıştıran araç yoktur.** `EXEC` risk seviyesi `gate.py`'de tanımlı ama
   hiçbir araç bu seviyede değil ve olmayacak (`DEVIR.md` §14, yazılı ret).
8. **Talimat yalnızca kullanıcının görev metnidir.** Araçtan dönen her şey —
   başarı da hata da, yerel de MCP de — veridir.

### Zincir uzunluğu gerçeği

Adım başına %95 başarı, 10 adımlık görevde ~%60 toplam başarı demektir. Bu yüzden hedef
"otonom" değil "denetimli"dir: dur, göster, onay al, devam et.

---

## 2. Bileşenler ve sözleşmeleri

> **Dosya yerleşimi (2026-09):** döngü `vekil_v0.py`'de (calistir/devam_et, `_model_cagir`,
> `_durum_kaydet`); sistem talimatı `talimat.py`; durum dosyası/özet `durum.py`; komut satırı
> `cli.py`; araçlar `araclar/` (kayıt defteri `@arac`); sağlayıcılar `model/`; çalışma zamanı
> tekilleri `baglam.py`. `vekil_v0` eski adları (POLITIKA, ARAC, DURUM_KOK…) özellik olarak
> taşır — dış çağıranlar için kırılma yok. MCP sunucuları import anında değil, ilk görevde
> ya da pencere açılırken arka planda bağlanır (`vekil_v0.mcp_baglan`).


### Model çağırma (`pevrai/model/` — sağlayıcı katmanı)

Sağlayıcı soyutlaması `pevrai/model/` altında: `taban.py` sağlayıcıdan bağımsız mesaj
biçimini (`{"rol", "parcalar": [metin | cagri | sonuc]}` — `sohbet.py`'nin diske yazdığı
biçimle aynı), araç şeması biçimini (`{"name","description","parameters"}`) ve `Saglayici`
sözleşmesini (`uret`, `modeller`) tanımlar; `gemini.py`, `openai_uyumlu.py` (OpenAI,
OpenRouter, Ollama, LM Studio… `taban_url` ile), `anthropic_.py` adaptörleri kendi
biçimlerine çevirir. Sağlayıcıya özgü opak veri (Gemini 3 `thought_signature`) `cagri`
parçasındaki `ek` alanında taşınır. Hatalar dört sınıfa eşlenir (`OranSiniri` 429,
`SunucuHatasi` 5xx, `ZamanAsimi`, `ModelHatasi`); yeniden deneme kararı
`vekil_v0._model_cagir`'da, sağlayıcıdan bağımsız. Seçim `policy.toml [model] saglayici`,
anahtar `pevrai/anahtar.py` (Ayarlar'dan kaydedilen — keyring, yoksa `~/.vekil/credentials.json` — ortam değişkeninin önünde;
policy.toml'a, journal'a, sohbete asla yazılmaz). Tek soyutlama katmanı bu değil; ikincisi `mod`: `hizli`/
`dengeli`/`derin`/`azami`, her biri `policy.toml [modlar]`'da `varsayilan`/`guclu`
rolünden birine ve bir adım/çağrı demetine bağlı (yukarı bkz.). Bu **kullanıcının görev
başına seçtiği** bir tavandır, göreve bakıp otomatik model seçen bir yönlendirici değil —
o "basit görevde ucuz model, planlama gerektiren görevde güçlü model" yönlendirmesi henüz
yok (bkz. DEVIR_FAZ6 §7.1 "dinamik", ROADMAP). **Model seçiminde belirleyici kriter ham
zeka değil, araç çağırma kalitesidir.** Zayıf modeller uzun zincirlerde şemayı bozar ve
döngüye girer.

### Araç şemaları (`vekil_v0.py` içinde, ayrı bir `registry.py` yok)

Planlanan bir "Python fonksiyonundan otomatik JSON şema üretimi" de gerçekleşmedi —
`FunctionDeclaration`'lar `vekil_v0.py`'de elle tanımlanır (bkz. [TOOLS.md](TOOLS.md)'nin
"Araç yazım sözleşmesi"). MCP sunucularından gelen araçlar farklı bir yoldan şemaya
girer: `mcp_bridge.Kopru.bagla` sunucunun kendi bildirdiği JSON şemasını keşfeder, ama
yalnızca `policy.toml [araclar]`'da sınıflandırılmış olanlar modele gösterilir —
sınıflandırılmamışlar `vekil_v0` import anında UYARI ile gizlenir (bkz. TOOLS.md).

### İzin Kapısı (`gate.py`)

Girdi bir araç çağrısı, çıktı `ALLOW | ASK | DENY` + gerekçe. Politika kök dizindeki
`policy.toml` dosyasından okunur, kodda gömülü değildir — ve panelden değişen tek yol da
`gate.Politika`'dır: `journal.py` bir ara tavanları kendi başına okuyordu, kaldırıldı
(iki okuyucu iki doğru olurdu). Ayrıntı: [SECURITY.md](SECURITY.md).

### Ayarlar (`ayarlar.py`, `pencere.py`'nin `Api`'si üzerinden arayüze açılır)

`policy.toml`/`config/arayuz.toml`'u **satır bazlı** düzenler (dizi baştan üretilmez, tek
satır eklenir/çıkarılır — dosyada elle yazılmış yorumlar, "kapı testi bunu bekliyor"
türünden, korunur). Her yazımdan önce yedek alınır; yazılan içerik geçerli TOML değilse
**ya da** `gate.Politika` onu yükleyemiyorsa (yalnızca biçim değil, anlam da doğrulanır),
yedek geri yüklenir ve panelde hata gösterilir. `korunan_yol_ihlali` hem yazmadan önce
(kullanıcıya "neden olmaz" demek için) hem yazdıktan sonra (protokol değişmezi olarak)
ayrıca çağrılır. `[modlar]` da (mod başına model rolü + adım/çağrı tavanı, ve hangi modun
varsayılan olduğu) artık bu panelden düzenlenebiliyor (`ayarlar.mod_yaz`,
`ayarlar.varsayilan_mod_yaz`) — mod adları kapalı bir liste (`hizli`/`dengeli`/`derin`/
`azami`), panelden yeni mod eklenemez, yalnızca üç alanı (`model`, `adim`, `cagri`)
düzenlenir. Bu, Faz 6'yı kapatan son kod parçasıydı.

### Araç Yürütücü

Zaman aşımı uygular, çıktıyı kırpar (örn. 8 KB üstünü kes ve "kırpıldı" notu ekle),
istisnayı yakalayıp metne çevirir. Uzun çıktıyı olduğu gibi bağlama basmak, bağlam
bütçesini tek adımda tüketen en yaygın hatadır.

### Bağlam / persona (`config/persona.md`)

Ayrı bir `context.py` modülü yok — `config/persona.md` varsa içeriği doğrudan `SISTEM`
metnine eklenir. Kullanıcı tercihleri (dil, üslup, dosya adlandırma, çalışma tarzı) her
istekte başa gider.

Görev başına çalışma defteri ve bağlam dolduğunda eski araç sonuçlarını özete indirgeme
**bilinçli olarak eklenmedi** — Faz 4'te ölçüldü: en uzun görev 3 model turu, zirve bağlam
4601 token (pencerenin binde biri), dikkat kaybı yok. Gerçek bir sorunu henüz çözmedikleri
için Faz 6'ya ertelendi (bkz. [ROADMAP.md](ROADMAP.md)).

### Belge okuyucu (`belge.py`)

PDF (PyMuPDF), DOCX (`python-docx`), PPTX (`python-pptx`), XLSX (`openpyxl`), TXT/MD/CSV'yi
düz metne çevirir. Taranmış (görüntü) PDF'lerde metin çıkaramaz, bunu açıkça söyler — OCR
yapmaz (Faz 4 notu). `read_document` aracının arkasındaki motor.

### Arama (`ara.py`)

Bağımlılıksız, saf Python: dosya adında ve düz metin dosyalarının içeriğinde arar.
PDF/DOCX/PPTX içeriğini taramaz, sadece dosya adı eşleşir — bu sınır aracın kendi
açıklamasında da yazılı. `search` aracının arkasındaki motor.

### Tarayıcı (`tarayici.py`)

Playwright, `connect_over_cdp` ile mevcut Chrome'a bağlanır; kapalıysa kendi profiliyle
(`chrome-profil/`, ana oturumlara dokunmadan) başlatır. Sayfa okuma, ARIA anlık görüntüsü,
tıklama, form doldurma (parola alanları kod seviyesinde reddedilir), indirme (uzantı beyaz
listesi). Ayrıntı: [SECURITY.md](SECURITY.md), [TOOLS.md](TOOLS.md).

### Görev durumu ve devam (`vekil_v0._durum_kaydet` / `devam_et`, `gate.durum_karari`)

Bir görev adım ya da çağrı tavanına çarptığında döngü **modelden tek bir zorlanmış
çağrıyla** (`durum_yaz`, normal araç listesinde değil — bkz. [TOOLS.md](TOOLS.md)) özet
alır ve `~/.vekil/durum/<kimlik>.md` yazar. Dosya iki bölümlüdür ve ayrımı bilinçlidir:

| Bölüm | Kaynak | Güven |
|---|---|---|
| JSON bloğu + "Doğrulanan yazmalar" | Döngünün kendisi + `journal.gorev_kayitlari()` | GÜVENİLİR |
| Hedef / Yapılanlar / Kalanlar / Engel | Modelin özeti | DOĞRULANMAMIŞ, dosyada da böyle etiketli |

Ayrım teorik değil: canlı bir denemede model hiç yapmadığı bir yazmayı "tamamlandı"
diye bildirdi (`DEVIR_FAZ7.md` Aşama 1). `journal.gorev_kayitlari(baslangic_zamani)`
o görevden sonraki gerçek yazma/taşıma kayıtlarını döner — zemin gerçeği model
özetinde değil günlükte.

`devam_et(kimlik)` **taze** bir `calistir()` çağrısıdır; eski konuşma geçmişi
yüklenmez. Üç kapıdan geçer:

1. `_durum_oku` — dosya ve JSON bloğu okunur, bozuksa metin döner.
2. `gate.kok_karari` — durum dosyası yazılırken geçerli olan yazma kökleri ŞİMDİKİ
   köklerle küme olarak aynı mı? Değilse devam reddedilir (fail-closed, hangi yönde
   değiştiği önemsiz), model hiç çağrılmaz.
3. `_devam_gorevi_kur` — modelin önceki gövdesi `<untrusted_content>` içine alınır ve
   kendi kapanış etiketi kaçırılır (`mcp_bridge.dis_kaynak` ile aynı desen);
   `_uzlastirma_satiri` günlükle eşleşmeyen iddiaları açık bir UYARI'ya çevirir.

### Kendiliğinden devam (`vekil_v0._gozetimsiz_surdur`, `gate.devam_karari`)

`calistir` artık `_gozetimsiz_surdur`'ü çağırıyor: görev bir tavana çarpıp durum
dosyası bıraktığında ve **bir profil etkinse** döngü kendiliğinden devam eder.
Profilsiz yol değişmedi (`profil is None` ilk satırda kısa devre).

Sürücü her turda `gate.devam_karari`'ya sorar — dört dönüş, öncelik sıralı:
`dur_kota` > `dur_sinir` > `dur_ilerleme_yok` > `devam`. İlerleme ölçütü
`journal.gorev_kayitlari`; **modelin özeti bu kararda kullanılmaz.** Tolerans
penceresi (iki kısır tur) çağıranın işi, `devam_karari`'nın değil — `tur_karari`'nın
"yeni tur kavramı bu fonksiyonun bilmediği bir döngü detayı" ayrımının aynısı.

Her devam turu **ayrı bir `Oturum`** ile koşar (`gecmis_koru=False`): taze bağlam
durum dosyası deseninin bütün anlamı. Durdurma bayrağı paylaşılır.

Durum dosyası `journal.KOK` altında, `policy.toml`'un HİÇBİR yazma kökünün içinde
değil — ajan `write_file`/`move`/`trash` ile oraya erişemez. Gerekçe `journal.jsonl`
ile aynı: ajanın "nerede kaldım" iddiası ancak ajan onu değiştiremiyorsa güvenilir.

### Dönüş özeti (`vekil_v0.ozet_metni`, saf)

Profilli (gözetimsiz) her çalışma sonunda `~/.vekil/ozet/<kimlik>.md`. **Model
çağrısı yok** — içerik döngünün kendi saydıkları + `journal` + kota sayaçları.
Sürücünün BÜTÜN çıkışları `_ozet_bitir`'den geçer: özet "bazen" üretilen bir şey
olsaydı tam da en çok gereken durumda (beklenmedik bir dalda durulunca, kota
bitince) eksik olurdu.

`ozet_metni` saf bir fonksiyon ve "normal tamamlandı" iddiasını **kendisi**
türetir (kaydı kimin kurduğundan bağımsız): hiçbir sınıra çarpılmamışsa normal,
çarpılmışsa son sınırın adıyla "TAMAMLANMADI". Bu mantık başta sürücüdeydi ve
canlı koşuda kota duvarına çarpan bir görevi "normal tamamlandı" diye
raporlamıştı.

### Görev profilleri (`policy.toml [profiller.<ad>]`, `gate.Politika.karar`)

Profil, kullanıcının **önceden kaydedilmiş onayıdır** — yeni bir yetki değil. Üç katman:

- **DENY dokunulmaz.** `gate.Politika.karar` ilk satırında temel karar `ASK` değilse
  profile hiç bakmadan döner. Ödeme kategorisi, kod kökü, kara liste, site beyaz
  listesi profille açılamaz.
- **`ASK` yalnızca profilin KAPSAMI içinde `ALLOW` olur.** Kapsam iki boyutlu: araç
  profilin `araclar` listesinde olmalı VE yol profilin `yazma_koklari` altında olmalı.
  Biri tutmuyorsa normal `ASK` kalır.
- **`araclar` iki iş yapar (Faz 7 Aşama 5):** modele hangi araçların
  **gösterileceği** ve hangi ASK'lerin **önceden onaylı** olduğu. Alan yok =
  daraltma yok; `[]` = hiçbir araç (saf sohbet); liste = o alt küme. Okuma
  araçlarını listeye eklemek izin gevşetmez (zaten `ALLOW`), yalnızca görünür
  kılar — bu yüzden `gozetimsiz` profili okuma araçlarını da sayar.
- **Kapsam yükleme zamanında doğrulanır, fail-closed.** `araclar` sınıflandırılmış
  araçların, `yazma_koklari` `policy.toml`'un yazma köklerinin ALT KÜMESİ olmalı;
  `mod` tanınan dörtten biri, `azami_adim` 1-50, `azami_devam` 0-20 (**tanımsız = 0
  = kendiliğinden devam KAPALI**), bilinmeyen alan reddedilir. Bir
  profil etkileşimli oturumdan daha GENİŞ bir kapsam göremez — `azami_adim` bile
  yalnızca `min()` ile daraltır.

Eksen ayrımı korunur: **mod = hesap bütçesi**, **profil = önceden onay + kapsam**.
İkisi tek yapıda birleştirilmez (birleşirse "azami mod" zamanla "her şeye izinli"ye
kayar). `vekil_v0.AKTIF_PROFIL` yalnızca `journal` kaydına `profil: "<ad>"` alanını
eklemek için vardır ve `try/finally` ile temizlenir — GUI aynı süreçte ardışık görev
çalıştırdığı için bir profilin sonraki göreve sızması kabul edilemez.

### Günlük (`journal.py`)

JSONL formatında: zaman, tip (yazma/taşıma/geri alma), yol, boyut, yedek konumu. Dosya
**içeriği** hiçbir zaman günlüğe yazılmaz. Yan etkili işlemler için **geri alma kaydı**
tutar; geri almanın kendisi de bir yedek alır (yanlış/tekrarlanan bir geri alma kalıcı
kayba yol açmasın diye). Sabit klasörler: `~/.vekil/yedek/` (üzerine yazmadan önceki
hal), `~/.vekil/cop/` (silinen dosyalar — kalıcı silme aracı yok), `~/.vekil/indirilen/`
(tarayıcıdan inen dosyalar, ara klasör).

---

## 3. Veri akışı: örnek bir tur

```
kullanıcı: "indirilenler klasöründeki faturaları pdf'e çevir ve tarihe göre adlandır"

adım 1  list_dir("~/Downloads")                        ALLOW  → 34 dosya
adım 2  read_document("~/Downloads/fatura_3.docx")     ALLOW  → metin
adım 3  converter.convert(...docx → pdf)               ASK    → kullanıcı onayı → tamam
adım 4  move(...)                                      ASK    → onay → tamam
adım 5  (araç çağrısı yok)                             → "6 fatura dönüştürüldü, ..."
```

Onaylar toplu da sunulabilir ("bu 6 dosya için hepsine izin ver"), fakat onay **oturum
kapsamlıdır**: bir onay sonraki oturuma taşınmaz.

---

## 4. Neden MCP?

Araçlar Pevrai'nın içine gömülü sınıflar yerine ayrı MCP sunucuları olarak yazılır:

- Aynı araç Pevrai, Claude Desktop, Cursor veya başka bir istemciden kullanılabilir.
- Araç çöktüğünde ajan çökmez; süreç sınırı bir izolasyon katmanıdır.
- Araç ayrı test edilir; ajan döngüsünü çalıştırmadan doğrulanabilir.

Dosya dönüştürücü (`converter`, Faz 2) ilk MCP sunucusuydu; Faz 6'da bağımsız bir üçüncü
taraf paket olan **Okuma Atölyesi** (`okuma`, PDF kütüphanesi, kendi `.venv`'i) ikinci
gerçek müşteri oldu — mimari varsayımı kendi yazmadığımız bir sunucuyla da doğruladı.

`mcp_bridge.py`, bağlı MCP sunucularının araçlarını keşfedip yerel araçlarla aynı kayda
ekler; döngü açısından ikisi arasında fark yoktur, **iki fark hariç:**

- Yalnızca `policy.toml [araclar]`'da sınıflandırılmış MCP araçları modele gösterilir
  (Okuma Atölyesi'nin 17 aracından 4'ü sınıflandırıldı, kalan 13'ü gizli — bkz. TOOLS.md).
  Sınıflandırılmamış bir aracın modele görünmesi bir bug'dır, `evals.py --kapi`'deki
  `mcp_semasi_testi` bunu yakalar.
- MCP sunucusundan dönen metin `mcp_bridge.dis_kaynak` ile kırpılır ve
  `<untrusted_content>` içine sarılır — aynen tarayıcıdan gelen metin gibi (bkz.
  [SECURITY.md](SECURITY.md)). Bu sarmalama Faz 2'de yoktu; MCP sunucularının çoğunun
  döndürdüğü şeyin kullanıcının kendi dosyalarının içeriği (PDF metni, seçili alıntı)
  olduğu, yani web sayfasıyla aynı enjeksiyon yüzeyini taşıdığı Faz 6'da netleşti.

---

## 5. Tarayıcı katmanı

- Playwright, `connect_over_cdp` ile **mevcut Chrome profiline** bağlanır → oturumlar açık
  gelir, giriş yapma sorunu ortadan kalkar.
- Etkileşim erişilebilirlik ağacı (accessibility tree) üzerinden yapılır, koordinatla değil.
- Sayfa metni modele verilirken **veri olduğu açıkça işaretlenir**. Sayfadan gelen metin
  asla talimat olarak yorumlanmaz — bkz. [SECURITY.md](SECURITY.md) prompt injection.
- `pyautogui` yalnızca başka hiçbir yolu olmayan masaüstü uygulamaları için, en son çare.

---

## 6. Kalıcı durum

| Veri | Yer | Neden |
|---|---|---|
| Tercihler / çalışma tarzı | `config/persona.md` | Elle düzenlenebilir, git'te izlenebilir |
| Politika (izinler, modlar, profiller) | `policy.toml` | Kod değişmeden izin ve harcama ayarlanabilir; tek okuyucu `gate.Politika` |
| Arayüz tercihleri (tema vb.) | `config/arayuz.toml` | Güvenlik sınırı değil, panelden `ayarlar.py` ile |
| Slash komutları | `config/komutlar.toml` | Prompt şablonu/arayüz eylemi, kod değişmeden yeni komut eklenir |
| Günlük (JSONL) | `~/.vekil/journal.jsonl` | Denetim, geri alma, hata ayıklama |
| Günlük istek kotası | `~/.vekil/kota.json` | Rol (`varsayilan`/`guclu`) başına sayaç, günde sıfırlanır |
| Sohbet geçmişi | `~/.vekil/sohbetler/` | `sohbet.py`; panel kapanınca da konuşma kaybolmasın diye |
| Dönüş özeti | `~/.vekil/ozet/<kimlik>.md` | Gözetimsiz bir görev bittiğinde bırakılan tek sayfa. Model yazmaz. **Ajan buraya yazamaz** |
| Yarım kalan görev durumu | `~/.vekil/durum/<kimlik>.md` | Tavana çarpan görevin ilerlemesi; `--devam <kimlik>` buradan sürdürür. **Ajan buraya yazamaz** — hiçbir yazma kökünün içinde değil |
| Üzerine yazma yedekleri | `~/.vekil/yedek/` | Geri almanın kaynağı |
| Çöp klasörü | `~/.vekil/cop/` | `trash` buraya taşır; kalıcı silme aracı yok |
| İndirilenler (ara klasör) | `~/.vekil/indirilen/` | `browser_download` buraya iner, kalıcı değil |
| Notlar / bilgi tabanı | Düz `.md` dosyaları + `search` aracı | Erken vektör DB gereksiz karmaşıklık |

`~/.vekil/` klasör adı bilinçli olarak değiştirilmedi — proje adı Pevrai olsa da, mevcut
günlük/yedek/çöp/indirilen verisini `~/.pevrai/`'ya taşımanın getirisi yok, riski var
(geri alma geçmişi kopabilir). İsim değişse bile Faz 6'ya kadar burası sabit kalır.

Vektör deposu (Chroma/FAISS) yalnızca "aradığımı kelimeyle bulamıyorum" problemi gerçekten
yaşandığında eklenir. Önce ölç, sonra ekle.
