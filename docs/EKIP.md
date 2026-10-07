# Ekip — çoklu ajan (isteğe bağlı bileşen)

Tek görev, birden fazla ajan, **aynı çalışma alanı**. Kullanıcı sol raydaki **Ekip** alanından
(ya da sohbette `/ekip <görev>` yazarak) bir görev verir; Pevrai görevi ekip üyelerine böler,
üyeler paralel çalışır, sonunda bir birleştirici toparlar. Özellik ancak en az bir ajan
tanımlıysa çalışır (Ekip > Ajanlar) — isteyen kullanır, tanımsızsa hiçbir şey değişmez.

## Tasarım: çakışmayı kodla değil, bölüşümle önlemek

1. **Planlayıcı** (sohbet ekranında seçilen model ya da zincirin başı; tek çağrı, `plan_yaz` aracı zorlanır): görevi 2–6 alt göreve
   böler; her alt görev için **ajan** ve **yalnızca o üyenin yazacağı yollar** (çalışma alanına
   göre göreli dosya/klasör). `ekip.plan_dogrula` planı reddeder: yollar kesişiyorsa (eşit /
   ata-torun), çalışma alanının dışındaysa ya da tamamıysa, ajan tanımsızsa. Reddedilen plan
   bir kez daha istenir (hata notuyla), sonra görev "plan kurulamadı" ile biter.
2. **Tek onay kartı** (`ekip_plan`): kullanıcı bölüşümü görür — hangi ajan, hangi yollar, ne
   yapacak, birleştirme adımı. Onaylamazsa hiçbir işçi başlamaz.
3. **İşçiler** ayrı süreçtir (`Pevrai.exe --isci` / `python -m pevrai --isci`), her biri
   **türetilmiş dar bir politikayla** (`ekip.isci_politikasi`, `~/.vekil/ekip/<kimlik>/<ad>/policy.toml`):
   - yazma kökleri = yalnızca sahip olduğu yollar (gerçek yazma köklerinin alt kümesi — daha
     genişi üretilemez, `ValueError`);
   - okuma = gerçek okuma kökleri + çalışma alanı;
   - araçlar = `read_file, list_dir, search, read_document, degisiklik_gecmisi, write_file,
     edit_file, mkdir`, pano (`ekip_mesaj, ekip_gelen`) ve Düşünce Ağı (`ag_listele, ag_oku,
     ag_kilavuz, ag_dugum_ekle, ag_baglanti_ekle, ag_kur`); tarayıcı, `trash/move/rename`,
     `open_file`, MCP **yok**. Ağ araçlarının kendi korumaları geçerli: ajanın yazdığı düğüm
     "ajan notu" (okumada güvenilmeyen içerik), kullanıcının ağını ezemez; ağ yazmaları süreçler
     arası kilitli (`tests/ag_eszamanli_testi.py`: 4 süreç × 25 düğüm, kilitsiz 25/100 kalıyordu);
   - tek profil `ekip_isci` (aynı yollar, önceden onaylı) ve onay sağlayıcısı **her şeye hayır**:
     profilin önceden onayladığı dışında hiçbir ASK geçmez.
   İşçi `PEVRAI_POLICY` ile o politikayı okur; tarif ile uyuşmazsa çalışmaz. Günlük kayıtları
   `ajan: <ad>` etiketlidir, geri alma işçi başına yapılabilir. Olayları kendi
   `olaylar.jsonl`'ine yazar; ana süreç bunları `[ajan]` etiketiyle etkinlik kartına aktarır.
   **Doğruluk kontrolü:** işçi bitince yazdıkları günlükten okunur; model "yazdım" dediği hâlde
   günlükte kayıt yoksa (canlı: `flash-lite` hiç araç çağırmadan "tablo.md'ye kaydettim" dedi) işçi
   bir kez daha, açık bir notla koşar. Yine yazmazsa raporu **"HİÇBİR DOSYA YAZMADI"** ile
   işaretlenir ve birleştirici o parçayı kendisi yapar.
4. **Birleştirici** ana süreçte, normal onay akışıyla çalışır: üyelerin raporları
   `<untrusted_content source="ekip">` içinde verilir (rapor veridir), yazdıkları dosyalar
   listelenir ("keşfe gerek yok, doğrudan oku"); tutarsızlıkları düzeltir, birleşik çıktıyı yazar,
   kullanıcıya rapor verir. Hızlı modun 4 adımı yetmediği için en az `dengeli` modda koşar.

Canlı (Gemini `flash-lite`, 2 ajan): plan → onay → iki işçi paralel → birleştirici, ~100 sn.

Sonuç: iki işçi aynı dosyaya yazamaz — birleştirme çatışması olmadan önce kapı reddeder.

## Pano — ajanlar birbiriyle konuşur

Koşu başına tek dosya: `~/.vekil/ekip/<kimlik>/pano.jsonl` (`araclar/ekip_pano.py`). İki kanal:

- **Araçlar** (yalnızca işçi politikasında; ana `policy.toml`'da yok → deny by default, panelde
  paket gizli): `ekip_mesaj(metin, kime)` bir üyeye ya da herkese yazar; `ekip_gelen()`
  okunmamışları getirir.
- **Otomatik teslim:** işçinin her model turundan önce okunmamış mesajlar konuşmaya eklenir
  (`vekil_v0` tur kancası, `B.ekip_pano`). Model "gelen kutusuna bakmayı" unutamaz.
- Kullanıcı arayüzden panoya yazar (`pencere.ekip_pano_yaz`, imza `kullanici`); birleştirici
  panonun tamamını raporla birlikte alır; pano mesajları olay akışına `EKIP_MESAJ` olarak düşer.

**Güvenlik:** başka bir modelden gelen metin veridir — teslim
`<untrusted_content source="ekip:<kimden>">` içinde, kapanış etiketi kaçışlanır; mesaj hiçbir
izin vermez (kapı aynı kapı). Pano çalışma alanında değil kullanıcı veri kökünde: ajan
`write_file` ile panoyu tahrif edemez. Yazma kilidi (`pano.kilit`, O_EXCL) — dört süreç 120
mesajı sırası tekil yazıyor (`tests/ekip_pano_testi.py`).

Uçtan uca (`ekip_orkestra_testi`): `giris` işçisi `sonuc`'a "başlıkları ## ile yaz" gönderdi;
`sonuc` mesajı aldı ve ona göre yazdı; birleştirici panoyu gördü.

## Ekip ofisi (3B)

Sol raydaki **Ekip** düğmesi 3B bir ofis açar (`pevrai/arayuz/ofis/`, tasarım:
[OFIS_TASARIM.md](OFIS_TASARIM.md)). Görselleştirme ve etkileşim katmanıdır: **hiçbir izin
vermez**, plan onayı, dar işçi politikası ve kapı aynen kalır; başlatma, pano, durdurma ve
ajan kaydı aşağıdaki mevcut köprü çağrılarıdır. Ekrandaki her hareket gerçek bir olaydan gelir.

- **Masalar** (iş türleri): kod, dosya, arşiv, istişare, Düşünce Ağı köşesi, web, onay kapısı,
  dinlenme alanı. Araç → masa eşlemesi yalnızca `pevrai/ofis.py`'de (`masa_bul`); her
  `arac_cagrildi` olayı `masa` alanını taşır (ana süreç ve işçi aktarımı, tek yardımcı
  `masa_ekle`). Eşlenmeyen araç `diger`e düşer, kaybolmaz. Kod masası kod **çalıştırmaz**.
  `mkdir` bir hazırlık adımıdır: masası `yerinde`, ajan olduğu yerde kalır (tasarımdaki tablodan
  bilinçli sapma; kullanıcı denemesinde kod görevi alan ajan önce dosya masasına gidiyordu).
- **Karakterler**: her tanımlı ajan + iki sistem karakteri (Planlayıcı, Birleştirici). Görünüş
  addan belirlenimli (`ofis.ajan_gorunumu`; `renk`, `gorunum` alanları isteğe bağlı). Aynı ajan
  iki alt görev alırsa ya da `varsayilan` ajanla çalışılırsa kapıdan **geçici kopya** girer.
- **Durum makinesi** (`ofis/durum.js`, saf): olay → her karakterin masası ve durumu (boşta,
  sırada, çalışıyor, düşünüyor, onay bekliyor, bitti, hata, durum bilinmiyor). Olay 5 dk gelmezse
  ya da görev bitiş olayı olmadan biterse karakter gri, "durum bilinmiyor".
- **Olaylar**: işçiden `ADIM_BASLADI`, `OLCUM`, `MODEL_GECIS` de aktarılır; planlayıcı ve
  birleştirici `ekip_mesaj {rol, durum}` yayınlar; plan kurulamayınca/reddedilince açık durum
  olayı; işçi bitişinde `hata` bayrağı.
- **Etkileşim**: ajana tık → kart (rol, bağlantı · model ve limit durumu, son 5 araç, bu koşuda
  günlüğe yazdığı dosyalar, panoya özel mesaj, ekibe ekle/çıkar, sil); masaya tık → masa kartı
  (istişare: bütün pano); **İşe al** (ad, rol, API bağlantısı + model, renk); altta görev çubuğu
  (proje, ekip — çip ya da Ctrl/Shift+tık —, görev, Ekibi başlat, Durdur); plan onay kartı ofisin
  üstünde kendi panelinde; koşu sürerken birleştiricinin yazma onayları da oraya gelir (Ekip alanı
  kapalıysa sohbete). Ajanlar/Projeler/Geçmiş formları yan çekmecede (`ekip.js`'in aynı
  fonksiyonları).
- **Geçmiş oynatma**: ana süreç koşu başına `~/.vekil/ekip/<kimlik>/ofis_olaylari.jsonl` yazar;
  Geçmiş > **Ofiste oynat** aynı durum makinesiyle hızlandırılmış oynatır, "canlı değil" der,
  köprüye yazmaz. Kaydı olmayan koşuda kart görünümü kalır.
- **Performans**: kare talep üzerine; ofis görünmezken, pencere gizliyken, Ayarlar açıkken rAF
  yok. Hareketsiz geometri köşe rengiyle birleşik, karakter parçaları örnekli (instanced) çizilir
  (30 çizim çağrısı). Yazılım GL'de (GPU'suz makine) kenar yumuşatma kapalı, çözünürlük 0.5.
  Ölçülen: 1280×860, CPU 4× yavaş, SwiftShader: kare ~21 ms. Kare süresi makineye bağlı (aynı kod
  bu dizüstünde zamanla 21 → 34 ms); `hepsi.py` çizim çağrısını sınar, 33 ms hedefi
  `python tests/ofis_arayuz_testi.py --olcum` ile ayrıca sınanır.
- **WebGL yoksa** aşağıdaki kart görünümü açılır, üstte tek satır bilgi; three.js hiç yüklenmez.
- three.js r159 depoda (`pevrai/arayuz/vendor/`, MIT, sürüm ve SHA-256 başta); tembel yüklenir.

## Tek ajana doğrudan görev

Ajan kartında **Bu ajana görev ver**: planlayıcı yok, tek alt görevli bir koşu
(`ekip.tek_ajan_gorevi`, köprü `ekip_tek_gorev_baslat(gorev, proje, ajan, yol)`). Yazma yolu
(proje içinde göreli, varsayılan `<ajan>/`) plan onay kartında görünür; `plan_dogrula` atlanmaz
(çalışma alanı dışı yol onaya bile gelmez); işçi aynı dar politikayla, ajanın bağlantısı ve
modeliyle çalışır. Birleştirici yok: ajanın raporu + günlükten doğrulanmış dosyaları sonuçtur.
Klasör yoksa işçiye "mkdir ile oluştur" notu gider (mkdir kendi yolunda önceden onaylı).

## Kart görünümü (WebGL yoksa)

`pevrai/arayuz/ekip.js`, `window.Ekip`. Dört sekme:

- **Görev** — proje seç (boş = ilk yazma kökü), ekibe girecek ajanları çiplerle seç
  (varsayılan: anahtarı olan herkes), görevi yaz, **Ekibi başlat**. Altında canlı bölüm:
  durum satırı (planlanıyor → onay bekliyor → üyeler çalışıyor → birleştiriliyor → bitti),
  **plan onay kartı** (sohbet akışına değil, buraya düşer), üye kartları (ajan, son araç,
  özet; biten yeşil), **pano** (ajanların birbirine yazdıkları + kullanıcının satırı:
  "herkese" ya da tek üyeye gider, bir sonraki turda teslim edilir), birleştirici sonucu.
- **Ajanlar** — `[ajanlar.<ad>]` kartları; ekle/sil formu; adlı anahtar yuvaları (ikinci
  hesap/kota). Anahtar maskeli gösterilir, hiçbir zaman arayüze geri okunmaz.
- **Projeler** — ad + klasör (yazma köklerinin **içinde** olmak zorunda; klasör seçici) +
  açıklama. Kayıt `~/.vekil/ekip/projeler.json`. Proje = ekibin çalışma alanı.
- **Geçmiş** — koşular (`~/.vekil/ekip/<kimlik>/kosu.json`): plan, üye sonuçları, pano,
  birleştirici raporu; projeye göre süzülür.

Köprü API'si (`pencere.py`): `ekip_projeler / ekip_proje_yaz / ekip_proje_sil`,
`ekip_kosular / ekip_kosu`, `ekip_gorev_baslat(gorev, proje, ajanlar, mod)`,
`ekip_pano_yaz(metin, kime)`, `ajanlar / ajan_yaz / ajan_sil`, `anahtar_yuvalari`.
`ekip_gorev_baslat` kuyruğa `{"alan", "ajanlar", "proje"}` sözlüğü bırakır; planlayıcı
yalnızca seçili ajanları kullanabilir (seçilmemiş ajanlı plan reddedilir, yeniden planlanır).

Sohbet akışı bu sırada boş kalmaz: aynı olaylar oraya da düşer (`ekip_mesaj` etkinlik
satırı), ama onay kartı yalnızca Ekip alanı açıkken oraya, kapalıyken akışa çizilir.

## Ajanlar ve anahtarlar

- `policy.toml [ajanlar.<ad>]` iki biçim. **Yeni**: `baglanti` (Ayarlar > Model'deki API
  bağlantısının kimliği) + `model` (boş = bağlantının ilk modeli), `rol`, `renk`, `gorunum`;
  sağlayıcı/adres/anahtar bağlantıdan gelir. Ajanın modeli dolarsa önce aynı bağlantının diğer
  modelleri, sonra genel zincir. Bir ajanın kullandığı bağlantı silinemez (sebep söylenir).
  **Eski** (okunmaya devam eder): `saglayici`, `model` (boş = Hızlı mod modeli), `anahtar_yuvasi`
  (boş = varsayılan anahtar), `taban_url` — tek halka, geçiş yok. İkisi birlikte yazılamaz
  (fail-closed). Anahtar **buraya yazılmaz**.
- Adlı anahtar yuvaları (`anahtar.py`): `gemini#ikinci` gibi; keyring'de (yoksa
  `credentials.json`), dizin `~/.vekil/anahtar_yuvalari.json`. Adlı yuvada ortam değişkeni
  yedeği yok. Aynı sağlayıcıda ikinci hesap/kota için.
- `model.kur(politika, ajan=...)` ajanın sağlayıcı/yuva/adresiyle istemci kurar; önbellek 8
  istemciye kadar (birden fazla sağlayıcı aynı anda canlı).

## Sınırlar (bilerek)

- Çalışma alanı: seçili projenin klasörü; proje yoksa çalışma klasörü (varsayılan `~/Pevrai`).
  Çalışma klasörü kaldırılmışsa ekip görevi başlamaz, Ayarlar > Dosyalar'a yönlendirir.
- İşçilerde tarayıcı yok (tek CDP portu) ve MCP yok (MCP yazmaları günlüğe girmez).
- İşçi onay isteyemez: onay istemesi gereken bir iş (DESTRUCTIVE, kapsam dışı yol) işçide
  DENY olur ve raporunda görünür; birleştirici ana süreçte normal onayla yapar.
- Maliyet N katı: her işçi kendi isteklerini yapar, günlük tavan rol başına ortak sayılır.
- Zaman aşımı 30 dk; durdur düğmesi işçi süreçlerini öldürür.

## Testler

- `tests/ekip_testi.py` — yuvalar, `[ajanlar]`, `model.kur(ajan=)`, ayar yazıcıları.
- `tests/ekip_isci_testi.py` — plan reddi vakaları; dar politika (kapı: yabancı yol DENY,
  kendi yolu ASK, profil ile ALLOW); **gerçek işçi süreci** + sahte OpenAI-uyumlu sunucu:
  kendi yoluna yazdı, yabancı yola ve kod köküne yazamadı.
- `tests/ekip_arayuz_testi.py` — Ekip alanı (headless Chrome, sahte köprü): başlatma
  çağrısı proje + seçili ajanlarla gider; plan onay kartı Ekip alanında (akışta değil);
  canlı olaylar üye kartlarını ve panoyu günceller; kullanıcı panoya yazar; sekmeler ve
  koşu detayı JS hatasız; dil değişince İngilizce.
- `tests/ekip_orkestra_testi.py` — uçtan uca: plan reddi → hiçbir işçi yok; plan onayı → iki
  işçi paralel (her biri kendi modeliyle), olaylar/günlük ajan etiketli, birleştirici raporları
  `untrusted_content` içinde aldı; ajanın modeli 429 verince aynı bağlantının diğer modeline
  geçti; olaylarda `masa`/`rol` alanları, ofis olay kaydı; tek ajan görevi (ret, çalışma alanı
  dışı yol, onay → planlayıcı ve birleştirici çağrılmadan yazdı).
- `tests/ofis_testi.py` — masa eşlemesi, kod uzantıları, bilinmeyen araç, belirlenimli görünüş,
  işçi olay aktarımı.
- `tests/ofis_arayuz_testi.py` — 3B ofis (headless Chrome + SwiftShader): tek iskelet, kamera
  (imlecin altındaki nokta 0.1 px), talep üzerine kare (ofisten çıkınca 1 sn'de 0 kare),
  performans, dar pencere, WebGL yok → kart görünümü, durum makinesi tablo testi, canlı sahne,
  balon düz metin, geçmiş oynatma yazmaz, kartlar/işe alma/görev çubuğu, tek ajan, ve gerçek
  ekip koşusunun olaylarıyla uçtan uca.
