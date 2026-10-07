# 3B Ofis — Ekip alanının yeniden tasarımı

> **Uygulandı (2026-09).** Faz 1–6 tamam; kullanıcı kararları: three.js r159 (depoda, klasik
> betik — arayüz `file://` ile açıldığı için ES modülü değil), low-poly koddan karakterler, §3.1
> masa listesi aynen, tek ajana görev Faz 5'te, limit dolunca önce ajanın kendi bağlantısı sonra
> genel zincir. Sonradan (kullanıcı denemesiyle): `mkdir` masası `yerinde` (ajan yerinden oynamaz),
> masa başında oturma pozu, eşyalara tıklama. Sonuç ve güncel davranış: [EKIP.md](EKIP.md) "Ekip ofisi (3B)".

> Bu belge bir **uygulama görevidir**. Bu depoda çalışan yeni bir Claude Code oturumu için
> yazıldı. Önceki konuşmaların hiçbirini görmedin; ihtiyacın olan her şey burada ve belgenin
> gösterdiği dosyalarda. Önce **§0**'ı oku ve uygula, sonra fazları sırayla yap.

---

## 0. Başlamadan önce

**Kullanıcıyla dil:** Kullanıcıya her zaman **Türkçe** yaz. Değişiklikleri anlatırken kısa ve
somut ol; "ne yaptım, nasıl doğruladım, bilmen gereken ne" düzeninde yaz.

**Önce oku (bu sırayla):**

1. `docs/EKIP.md`: bugünkü ekip sistemi (planlayıcı, işçi süreçleri, pano, birleştirici, güvenlik).
2. `pevrai/ekip.py`: orkestrasyon. Özellikle `ekip_gorevi`, `planla`, `isci_hazirla`,
   `isci_politikasi`, `_olaylari_aktar` ve olayların nasıl yayınlandığı.
3. `pevrai/arayuz/ekip.js`: bugünkü Ekip alanı (`window.Ekip`, `olay()`, sekmeler).
4. `pevrai/arayuz/ag.js`: projedeki tek 3B sahne (Düşünce Ağı). Kendi yazılmış perspektif
   izdüşümü, sürükleme/döndürme/yakınlaştırma, `iskelet()` bir kez kurulur, `dongu()` rAF.
   Etkileşim dersleri buradan alınır (bkz. §9).
5. `pevrai/arayuz/index.html`: `gorunum()`, `olayIsle()`, `t()` / `CEVIRI.en`, `el()`, `ikon()`,
   `IKON` sözlüğü, `menuAc`, `toast`, CSS değişkenleri (`--vurgu`, `--yuzey`, …).
6. `pevrai/olaylar.py` (`OlayTipi`), `pevrai/pencere.py` (köprü; `ekip_*` metotları),
   `pevrai/model_zinciri.py` (API bağlantıları ve model zinciri).
7. `tests/hepsi.py` ve Ekip testleri: `ekip_testi`, `ekip_isci_testi`, `ekip_orkestra_testi`,
   `ekip_arayuz_testi`.

**Taban çizgisi:** kod yazmadan önce `python tests/hepsi.py` çalıştır ve hepsinin geçtiğini gör.
Geçmeyen varsa önce kullanıcıya söyle; kendi değişikliğinle karıştırma.

**Kullanıcıya sor (kodlamaya başlamadan, tek mesajda, önerilen seçenek önde).** Aşağıdakiler
kullanıcının kararı; her birinde önerilen varsayılan var, kullanıcı "sen karar ver" derse onu uygula:

1. **3B kütüphane:** three.js'in tek dosyalık sürümünü depoya koymak (`pevrai/arayuz/vendor/`,
   MIT lisansı, sürüm sabit, çevrimdışı). *Öneri: evet.* Alternatif: ag.js gibi kendi
   izdüşümümüz. Bu, masa ve karakter gibi katı nesneler için çok zahmetli ve kötü görünür.
2. **Görsel üslup:** düşük poligonlu, sade, uygulamanın koyu ve sıcak renk paletinde.
   Karakterler hazır model dosyası değil, basit geometrilerden (kapsül gövde, küre baş)
   kodla üretilir. *Öneri: evet* (lisans sorunu yok, dosya boyutu küçük, çevrimdışı).
3. **Masa listesi** (§3.1'deki varsayılan set) uygun mu, eklemek istediği var mı?
4. **Tek ajana doğrudan görev:** Ofiste bir ajana tıklayıp *yalnızca ona* görev verebilmek
   (planlayıcısız, tek işçi). *Öneri: evet, Faz 5'te.*

---

## 1. Amaç

Ekip alanı bugün sekmeli bir form ve kart listesi. Kullanıcı bunu **canlı bir 3B ofise**
dönüştürmek istiyor:

- Ofiste **masalar** var. Her masa, bir ajanın yapabileceği **bir iş türünü** temsil ediyor:
  kod masası, dosya düzenleme masası, okuma/araştırma masası, ortak istişare masası vb.
- Kullanıcının tanımladığı her ajan ofiste **3B bir karakter**. Ajan bir iş yaparken **canlı
  olarak** o işin masasına yürüyor ve orada çalışıyor. Ajanlar birbirine mesaj atınca
  istişare masasında buluşuyor.
- Kullanıcı ofisten **ajan ekleyebiliyor**, ajanlara **görev verebiliyor** ve her ajanın
  ne yaptığını, nerede olduğunu görebiliyor.

Bu bir **görselleştirme ve etkileşim** katmanı. Ekip sisteminin güvenlik modeli (plan onayı,
dar işçi politikası, kapı) **aynen kalır**. Ofis hiçbir yetki vermez, hiçbir kontrolü atlatmaz.
Ekranda görünen her hareket gerçek bir olaydan gelir; **uydurma animasyon yok** (bkz. §6.3).

---

## 2. Bugünkü sistem: bilmen gereken olgular

- **Akış:** kullanıcı görevi verir → **planlayıcı** (tek model çağrısı, `plan_yaz` zorlanır)
  görevi 2–6 alt göreve ve **yazma yollarına** böler → kullanıcı **tek onay kartıyla** planı
  onaylar → her alt görev **ayrı bir işletim sistemi sürecinde** çalışır (`python -m pevrai
  --isci`), dar bir politikayla → işçiler **pano** üzerinden birbirine yazabilir → hepsi bitince
  **birleştirici** ana süreçte sonucu toparlar.
- **Olaylar** (`pevrai/olaylar.py`, `OlayTipi`) arayüze `olaylari_cek` yoklamasıyla gelir ve
  `index.html` içindeki `olayIsle()` → `window.Ekip.olay(o)` yoluyla Ekip alanına ulaşır.
  Ekiple ilgili bugünkü olaylar:
  - `ekip_mesaj {durum: planlaniyor|calisiyor|birlestiriliyor|bitti, kimlik, uyeler?}`
  - `ekip_mesaj {kimden, kime, metin}`: pano mesajı
  - `onay_gerekli {istek: {arac: "ekip_plan", …}}`: plan onayı
  - `arac_cagrildi {arac: "ekip_isci", args: {ad, ajan}, ajan}`: işçi başladı
  - `arac_cagrildi {arac, args, ajan}`: işçinin bir araç çağrısı (işçinin `olaylar.jsonl`'ünden
    ana akışa aktarılır, `ajan` = alt görev adı)
  - `arac_sonucu {arac: "ekip_isci", ajan, …}`: işçi bitti
  - `gorev_bitti`, `hata`
  - Ana süreç işçi olay dosyasından **yalnızca** `ARAC_CAGRILDI, ARAC_SONUCU, HATA,
    EKIP_MESAJ` aktarıyor (`ekip.py` sonundaki aktarıcı). "Düşünüyor" durumu için
    `ADIM_BASLADI` ve `OLCUM` de aktarılmalı (Faz 1).
- **Ajan tanımı:** `policy.toml [ajanlar.<ad>]` içinde `saglayici, model, anahtar_yuvasi, rol,
  taban_url` alanları var. Uygulama artık **API bağlantıları** kullanıyor
  (`[baglantilar.<kimlik>]`, `pevrai/model_zinciri.py`; Ayarlar > Model). Ajanlar hâlâ eski,
  tek sağlayıcılı alanları kullanıyor. Faz 1'de ajanlar bağlantılara bağlanacak.
- **İşçi araçları:** `read_file, list_dir, search, read_document, degisiklik_gecmisi,
  write_file, edit_file, mkdir, ekip_mesaj, ekip_gelen`. İşçilerde **tarayıcı, MCP, taşıma,
  çöpe atma ve açma yok**. Kabuk/komut çalıştırma aracı **uygulamanın hiçbir yerinde yok**
  (bilinçli karar). "Kod masası" kod **çalıştırmaz**, yalnızca kod dosyası okur ve yazar.
- **Proje** = ekibin çalışma klasörü (`~/.vekil/ekip/projeler.json`); yazma köklerinin içinde
  olmak zorunda. **Koşu kaydı**: `~/.vekil/ekip/<kimlik>/kosu.json`, pano: `pano.jsonl`.

---

## 3. Kavramsal model

### 3.1 Masalar (iş türleri)

Masa = bir **yetenek kümesi**. Bir araç çağrısı hangi masada yapılıyorsa ajan o masaya gider.
Eşleme **tek bir yerde** tanımlanır (Python: `pevrai/ofis.py` içinde `MASALAR` ve
`masa_bul(arac, args) -> masa_kodu`) ve arayüze köprüyle verilir. JS aynı tabloyu kopyalamaz.

| Kod | Ad (TR / EN) | Ne olur | Araçlar (varsayılan eşleme) |
|---|---|---|---|
| `kod` | Kod masası / Code desk | Kod dosyası okuma ve yazma. Çalıştırma yok. | `write_file`, `edit_file`, `read_file`: yol uzantısı kod ise (`.py .js .ts .html .css .json .toml …`) |
| `dosya` | Dosya masası / File desk | Belge ve metin dosyası yazma, düzenleme, klasör | `write_file`, `edit_file`, `mkdir`: kod olmayan yollar |
| `arsiv` | Arşiv / Library | Okuma, arama, belge çıkarma, geçmiş | `read_file` (kod dışı), `list_dir`, `search`, `read_document`, `degisiklik_gecmisi` |
| `istisare` | İstişare masası / Meeting table | Ajanlar arası konuşma, planlama, birleştirme | `ekip_mesaj`, `ekip_gelen`; **planlayıcı** ve **birleştirici** burada çalışır |
| `ag` | Düşünce Ağı köşesi / Thought network corner | Ağ okuma ve ateşleme | `ag_*` araçları (şimdilik yalnızca ana süreçte) |
| `web` | Web masası / Web desk | Tarayıcı işleri | `browser_*` (işçilerde yok; yalnızca ana süreç, ileride) |
| `kapi` | Onay kapısı / Approval gate | Kullanıcı onayı beklenirken | `onay_gerekli` olayı; ajan kapıda bekler |
| `bekleme` | Dinlenme alanı / Lounge | Boşta, görevi yok | Ajanın varsayılan yeri |

- Eşlenmeyen araç → `arsiv` (okuma) ya da `dosya` (yazma), risk seviyesine göre. **Bilinmeyen
  araç sessizce kaybolmaz:** masası `diger` olur ve karakter yerinde çalışır.
- Masaların sahnedeki konumu Python'da değil JS'te (`OFIS_DUZENI`): bu bir sunum kararı.
  Python yalnızca masa **kodlarını ve adlarını** bilir.

### 3.2 Karakterler

- Her **tanımlı ajan** (`[ajanlar.<ad>]`) bir karakter. Ayrıca iki **sistem karakteri** var:
  **Planlayıcı** ve **Birleştirici**. Bunlar istişare masasında çalışır; kullanıcı onları
  silemez ve düzenleyemez.
- Karakter görünüşü koddan üretilir: ajanın `renk` alanı (yoksa adından belirlenimli bir renk)
  ve basit bir `gorunum` tohumu (saç/aksesuar varyantı). Aynı ajan her açılışta aynı görünür.
- Karakterin üstünde her zaman **ad etiketi** var; altında küçük bir **durum rozeti**.

### 3.3 Ajan durum makinesi (tek doğruluk kaynağı: olaylar)

```
bosta ──(ekip_isci başladı)──▶ planda_bekliyor ──(arac_cagrildi)──▶ yuruyor ──(vardı)──▶ calisiyor
  ▲                                                          │                                 │
  │                               (adim_basladi, araç yok)──▶ dusunuyor ◀───────────────────────┘
  │                                                          │
  └──(ekip_isci sonucu / gorev_bitti)── bitti ◀──────────────┘   hata ──▶ (kırmızı rozet, yerinde)
```

- `yuruyor` yalnızca bir **animasyon** durumu. Mantık "hedef masa değişti" olayıdır. Yürüme
  sürerken yeni olay gelirse hedef güncellenir. Olaylar **asla** animasyonu beklemek için
  kuyrukta tutulmaz: ekran gerçeğin gerisinde kalamaz. Gerekirse karakter ışınlanır ve
  bunu kısa bir solma efektiyle yapar.
- `dusunuyor`: modele istek gitti, cevap bekleniyor (işçiden aktarılan `ADIM_BASLADI`).
  Görsel: masada, başının üstünde yavaş dönen küçük bir halka.
- Pano mesajı (`ekip_mesaj {kimden, kime}`): gönderen istişare masasına yürür ve üstünde
  kısa bir **konuşma balonu** çıkar (mesajın ilk ~60 karakteri; tamamı tıklayınca). `kime`
  belirli bir ajansa alıcının üstünde kısa bir "zarf" işareti belirir.
- Plan onayı beklerken planlayıcı **kapıda** bekler; onay kartı ofisin üstünde bir panel
  olarak açılır (bugün Ekip alanına düşen kart; bkz. `ekip.js`).

---

## 4. Mimari

```
Python (gerçek)                              JS (sunum)
────────────────                             ─────────────────────────────
ekip.py olaylari  ──► olaylari_cek ──► olayIsle ──► Ofis.olay(o)
pevrai/ofis.py                                        │
  MASALAR, masa_bul()   ◄── ofis_duzeni() ─────────   ├─ durum.js   saf durum makinesi (test edilir)
  ajan görünüşü                                       ├─ sahne.js   three.js sahnesi, render
                                                      └─ ofis.js    DOM panelleri, etkileşim, window.Ofis
```

**Dosyalar (öneri):**

- `pevrai/ofis.py`: `MASALAR`, `masa_bul(arac, args)`, `ajan_gorunumu(ad, tanim)`. Saf
  fonksiyonlar, model ya da ağ çağrısı yok. `tests/ofis_testi.py` ile test edilir.
- `pevrai/arayuz/ofis/durum.js`: **DOM ve three.js'e dokunmayan** saf durum makinesi:
  `durumUygula(durum, olay) -> yeniDurum`. Bütün olay→durum mantığı burada. Playwright
  `evaluate` ile tablo testleri yazılır.
- `pevrai/arayuz/ofis/sahne.js`: three.js sahnesi. Durumu okur ve çizer; **karar vermez**.
- `pevrai/arayuz/ofis/ofis.js`: `window.Ofis = {ac, kapat, olay}`. Paneller (ajan kartı,
  masa kartı, görev çubuğu, plan onayı, pano), köprü çağrıları.
- `pevrai/arayuz/vendor/three.module.min.js` + `vendor/THREE_LICENSE`: sürüm sabit, dosyanın
  başına yorumla sürüm ve kaynak yazılır.
- Mevcut `ekip.js`: **silinmez**. Ajanlar, Projeler ve Geçmiş formları ofisin **yan
  çekmecesine** taşınır (aynı fonksiyonlar yeniden kullanılır). Görev sekmesinin canlı kısmı
  ofisle değişir.

**Köprü (pencere.py) eklemeleri:** `ofis_duzeni()` → `{masalar: [{kod, ad, aciklama}],
ajanlar: [{ad, renk, gorunum, baglanti, model, rol}]}`; `ofis_arac_masasi(arac, args)` gerekmez,
masa bilgisini olayın içinde gönder (Faz 1). Mevcut `ekip_*` metotları aynen kullanılır.

---

## 5. Fazlar

Her faz **kendi başına çalışır ve test edilir**, sonra kaydedilir (commit). Bir fazı
bitirmeden sonrakine geçme. Her fazın sonunda kullanıcıya kısa bir durum raporu ver.

### Faz 1: Arka uç: masa eşlemesi, zengin olaylar, bağlantı tabanlı ajanlar

1. `pevrai/ofis.py`: `MASALAR` (§3.1), `masa_bul()`. Kod uzantıları listesi tek yerde.
2. **Olay zenginleştirme:** `arac_cagrildi` olayına `masa` alanı ekle. Hem ana süreçte hem
   işçi aktarımında olsun; ekleme tek bir yardımcıda yapılsın. Eski istemciler bu alanı
   görmezden gelir, geriye uyumlu.
3. **İşçi aktarımı:** `ADIM_BASLADI` ve `OLCUM` da aktarılsın (`ajan` etiketiyle). Olay
   seli olmasın diye ekip alanı kapalıyken de sorun çıkmamalı (olaylar zaten kuyruğa gidiyor).
4. **Planlayıcı/birleştirici olayları:** `ekip_mesaj {rol: "planlayici"|"birlestirici",
   durum: "calisiyor"|"bitti"}` gibi açık olaylar. Karakterlerin ne zaman istişare masasına
   gideceği tahmin edilmesin.
5. **Ajanlar bağlantılara bağlansın:** `[ajanlar.<ad>]` içine `baglanti` (bağlantı kimliği)
   ve `model` (o bağlantının modellerinden biri) alanları. Eski alanlar (`saglayici`,
   `anahtar_yuvasi`, `taban_url`) **okunmaya devam eder** (geriye uyum, fail-closed doğrulama
   `gate.Politika`'da). İşçi, ajanın bağlantısından `model_zinciri.Halka` kurar
   (`Halka.ajan()`). Limit dolunca zincir davranışı işçide de geçerli olsun: ajanın modeli
   dolarsa ajanın **kendi bağlantısının** diğer modelleri, sonra genel zincir. Bu davranışı
   kullanıcıya sor, varsayılan olarak öner.
   Ajan formu (Faz 4) sağlayıcı/yuva yerine **bağlantı + model** seçer.
6. `renk` ve `gorunum` alanları (isteğe bağlı; yoksa addan türetilir).
7. Testler: `tests/ofis_testi.py` (masa eşleme tablosu, bilinmeyen araç, kod uzantıları,
   görünüşün belirlenimli olması), `ekip_orkestra_testi`'ne olay alanları için kontroller.
   Ajan–bağlantı geçişi için `ekip_testi`'ne vakalar ekle.

### Faz 2: Statik 3B ofis

1. three.js'i depoya koy. `index.html` modül yüklemesi: `<script type="module">` ya da mevcut
   betik düzeniyle uyumlu bir yol. **Uzak kaynak yok**: `tests/arayuz_testi.py` bunu denetler.
2. Sahne: zemin, duvarlar (kamera tarafı açık), masalar (masa + sandalye + masa türünü anlatan
   basit nesne: kodda monitör, arşivde raf, istişarede yuvarlak masa, kapıda çerçeve), her
   masanın üstünde **DOM etiketi** (CSS2D ya da kendi izdüşümün; metin DOM'da kalsın ki çeviri
   ve seçilemezlik kuralları geçerli olsun).
3. Karakterler: bekleme alanında, ad etiketleriyle.
4. **Kamera:** yörünge (sürükle döndür), tekerlekle **imlecin olduğu yere** yakınlaş (ag.js'te
   aynı davranış var, kullanıcı bunu özellikle istedi), sağ tık/orta tık kaydır, çift tıkla
   masaya/ajana odaklan, "Ofise dön" düğmesi. Döndürme merkezi sahnenin ortası, dünya
   orijini değil (bkz. §9).
5. **Performans (zorunlu):**
   - Render **talep üzerine**: sahnede hareket yoksa kare çizilmez. Yürüyen karakter,
     animasyon ya da kamera hareketi varken çizilir.
   - Ofis görünür değilken (`gorunum` başka panel, Ayarlar açık, pencere gizli)
     `requestAnimationFrame` **durur**. Bu uygulamada logo animasyonunun arka planda bütün
     pencereyi yeniden çizdiği bir hata ölçülüp düzeltildi; aynısını tekrarlama.
   - Hedef: 1280×860'ta, CPU 4× yavaşlatılmış headless Chrome'da hareketli sahnede kare
     süresi ortalama < 33 ms. Chrome izi (trace) ile ölç, sonucu kullanıcıya rakamla bildir.
   - `body.animasyon-kapali` / `animasyon-az` ayarlarına uy: yürüme yerine ışınlanma, nefes yok.
6. **WebGL yoksa:** sahne yerine bugünkü kart görünümüne düş, üstte tek satır bilgi göster.
   Uygulama hiçbir durumda boş ekran göstermez.
7. Dar pencere (≤ 760 px): paneller alta iner, sahne küçülür; yatay taşma yok
   (`tests/arayuz_testi.py` 390×640'ta taşma denetliyor).

### Faz 3: Canlı: olaylardan animasyon

1. `durum.js`: §3.3 durum makinesi. Girdi olay, çıktı her ajanın `{masa, durum, balon?,
   hedef}` bilgisi. **Saf**: aynı olay dizisi her zaman aynı durumu verir.
2. `sahne.js`: durum değişince karakteri hedef masaya **yürüt**. Basit ızgara ve bekleme
   noktaları: her masanın 2–4 çalışma noktası var, dolu noktaya ikinci ajan oturmaz. Yol
   bulma için masalar arası sabit ara noktalar yeter; A* gerekmez.
3. Animasyonlar (hepsi prosedürel): yürüme (bacak salınımı), çalışma (kollar/ekran ışığı),
   düşünme (baş üstü halka), konuşma (balon), bitti (yeşil tik rozeti, bekleme alanına dönüş),
   hata (kırmızı rozet, olduğu yerde).
4. **Geçmişi oynatma:** Geçmiş'ten bir koşu seçilince aynı durum makinesi kayıtlı olaylarla
   oynatılır (hızlandırılmış, duraklat/ileri). Kayıtta olay yoksa kart görünümü gösterilir.
   Oynatma **hiçbir köprü yazma çağrısı yapmaz**.
5. Olay gecikmesi: işçi olayları ana sürece dosya yoklamasıyla geliyor (saniyeler). Ekranda
   bu gecikmeyi gizlemek için **uydurma hareket yapma**; karakter gerçekten olay geldiğinde
   hareket eder.

### Faz 4: Etkileşim

1. **Ajana tıkla** → sağda ajan kartı: ad, rol, bağlantı · model (limit durumu dahil,
   `model_zinciri`), şu anki masa ve durum, son 5 araç çağrısı, bu koşuda yazdığı dosyalar
   (günlükten, `ajan` etiketiyle), panoya ona özel mesaj yazma kutusu.
2. **Masaya tıkla** → masa kartı: ne işe yaradığı, şu an kimin çalıştığı, bu koşuda o
   masada yapılan son işler.
3. **Ajan ekle** ("İşe al"): ofisten açılan form: ad, rol, bağlantı + model (Ayarlar >
   Model'deki bağlantılardan), renk. Kaydedince karakter kapıdan girip bekleme alanına yürür.
   **Sil**: onaylı, karakter kapıdan çıkar.
4. **Görev çubuğu:** ofisin altında görev kutusu, proje seçici, ekip üyesi seçimi (sahnede
   karakterlere tıklayarak da seçilebilir: seçili karakter hafif parlar). "Ekibi başlat" =
   mevcut `ekip_gorev_baslat`.
5. **Plan onayı:** ofisin üstünde panel; planlayıcı kapıda bekler. Onay/ret mevcut akış.
6. **Pano:** istişare masasına tıklayınca bütün pano; kullanıcı "herkese" ya da tek ajana
   yazabilir (mevcut `ekip_pano_yaz`).
7. **Durdur:** görev çalışırken görünür; işçileri durdurur (mevcut akış).

### Faz 5: Tek ajana doğrudan görev (kullanıcı onaylarsa)

- Ajan kartında "Bu ajana görev ver". Planlayıcı yok; **tek alt görevli** bir koşu: ajan,
  seçili projede, ajanın bağlantısı ve modeliyle çalışır. Güvenlik aynı: kullanıcı yazma
  yolunu (klasör) onay kartında görür; işçi dar politikayla çalışır. Birleştirici yok, ajanın
  raporu doğrudan sonuç olur.
- Uygulama: `ekip.py`'de planı elle kuran bir giriş (`tek_ajan_gorevi`), sonrası mevcut işçi
  yolu. Plan doğrulama (`plan_dogrula`) **atlanmaz**.

### Faz 6: Bitiş

- Belgeler: `docs/EKIP.md` güncellenir (ofis bölümü), `docs/OFIS_TASARIM.md` "uygulandı"
  notu alır, `README.md` Ekip satırı.
- Bütün testler; İngilizce taraması; görsel kontrol (ekran görüntüleri, §7).

---

## 6. Değişmezler (pazarlık dışı)

### 6.1 Güvenlik

- Ofis **hiçbir izni** değiştirmez. Plan onayı, işçi dar politikası, "işçi onay isteyemez"
  kuralı, `plan_dogrula`, yazma yollarının kesişmemesi aynen kalır (`docs/EKIP.md`).
- Arayüzde **HTML enjeksiyonu yok**: `innerHTML`, `outerHTML`, `insertAdjacentHTML`,
  `document.write`, `eval`, `new Function` yasak. `tests/arayuz_testi.py` bütün arayüz
  dosyalarını denetler; yeni dosyalar da bu denetime girmeli. Ajan adları, pano mesajları
  ve model çıktıları **veridir**: `textContent` / `el()` ile basılır.
- **Uzak kaynak yok**: bütün betik, font ve doku diskten. three.js depoda.
- Ajanın yazdığı pano mesajı balonda gösterilirken kısaltılır ve düz metin kalır; bağlantı
  tıklanmaz.
- API anahtarı arayüze hiç gelmez (yalnızca maskeli son 4 hane, mevcut köprü gibi).

### 6.2 Proje kuralları

- **Dokunma:** Codex'in dosyaları: `pevrai/eklentiler/`, `pevrai/arayuz/eklentiler*`,
  `tests/eklentiler_*`, `docs/PRODUCTIVITY*`, `pevrai/okuma.py`, `docs/OKUMA_INTEGRATION.md`.
- **Kişisel dosyalar asla kaydedilmez:** `policy.toml`, `config/persona.md`,
  `config/arayuz.toml`. Testler kullanıcının gerçek `policy.toml`'una **yazmaz**: geçici kopya
  kullan ve `ayarlar.POLICY` / `POLICY_YEDEK`'i test boyunca oraya yönlendir
  (`tests/model_zinciri_testi.py` örnek). Gerçek politikadan türetilen test politikasında
  kullanıcının kendi `[baglantilar]` bölümünü **temizle**; yoksa test sahte sunucu yerine
  kullanıcının gerçek API'sine gider (bu oldu, bkz. `tests/ekip_orkestra_testi.py`).
- **Kabuk yok:** kod çalıştıran bir araç ekleme. "Kod masası" yalnızca dosya işidir.
- **Çeviri:** her yeni kullanıcı metni `t("…")` ile yazılır ve `CEVIRI.en` (index.html) ile
  Python'daki `pevrai/ceviri.py` `EN` sözlüğüne İngilizcesi eklenir.
  `tests/ceviri_arayuz_testi.py` İngilizce modda ekranları açıp eksik çeviriyi yakalar;
  **ofisi ve panellerini de bu teste ekle**. Kullanıcı verisi (ajan adı, model adı) `t()`'den
  geçmez.
- **Metin üslubu:** kısa, profesyonel, açıklayıcı ama uzun değil. "Çocuğa anlatır gibi" değil.
  Açıklama bir cümleyi geçmesin.
- **Seçilemezlik:** arayüz metni seçilemez, yalnızca içerik seçilir (`index.html` başındaki
  `user-select` kuralı). Ofis etiketleri seçilemez; pano mesajı metni seçilebilir.
- **Kod stili:** çevredeki kod gibi. Yorumlar Türkçe ve ASCII (ş, ğ yerine s, g); **neden**
  yazılır, ne yapıldığı değil. Tanımlayıcılar Türkçe (`masa_bul`, `durumUygula`).
- **Commit:** yazar e-postası `237491655+ledaronn@users.noreply.github.com`
  (`git -c user.email=… commit`). Mesaj Türkçe ASCII, "neden"i anlatan gövde, sonda
  oturumunun verdiği `Co-Authored-By` satırı. Kullanıcı istemeden push yok, exe/kurulum yok.
- **Testler:** her yeni test dosyası `tests/hepsi.py` listesine girer. Her fazın sonunda
  `python tests/hepsi.py` tamamen geçer. Bir test "bir kez kaldı" ise tekrar çalıştırıp
  geçiştirme; nedenini bul (bu projede bir "arada bir kalan test" gerçek bir yarış hatası çıktı).

### 6.3 Dürüstlük

- Ekrandaki her hareket gerçek bir olaydan gelir. Ajan "çalışıyor" görünüyorsa gerçekten bir
  model isteği ya da araç çağrısı sürüyordur.
- Durum bilinmiyorsa (olay gelmedi, süreç koptu) karakter **gri** ve "durum bilinmiyor" der;
  çalışıyormuş gibi yapmaz.
- Geçmiş oynatması canlı değildir ve ekranda bunu açıkça söyler.

---

## 7. Test ve doğrulama planı

- **Python:** `tests/ofis_testi.py`: masa eşlemesi, görünüşün belirlenimli olması, olaylarda
  `masa` alanı, işçi aktarımında yeni olay türleri, ajan–bağlantı geçişi ve eski tanımların
  okunması.
- **Durum makinesi:** `tests/ofis_arayuz_testi.py` (Playwright, headless Chrome, sahte köprü):
  olay dizisi → beklenen `{ajan: {masa, durum}}` tablosu. En az: plan → onay → iki işçi farklı
  masalarda → pano mesajı (istişare) → biri hata → birleştirici → bitti.
- **WebGL headless:** Chrome'u `--use-angle=swiftshader --enable-unsafe-swiftshader` ile başlat.
  WebGL yine de yoksa test "WebGL yok → kart görünümü" yolunu doğrular; sessizce atlamaz.
- **Görsel:** ekran görüntüleri: boş ofis, 3 ajan çalışırken, ajan kartı açık, dar pencere,
  İngilizce. Görüntülere bak ve kullanıcıya en az bir tanesini göster.
- **Performans:** §5 Faz 2'deki hedef; Chrome izi ile boyama sayısı ve kare süresi. Ofis
  kapalıyken rAF çalışmıyor olmalı (test: ofisten çıkınca 1 sn boyunca kare sayısı 0).
- **Uçtan uca:** `tests/ekip_orkestra_testi.py` desenini kullan (sahte OpenAI-uyumlu sunucu,
  gerçek işçi süreçleri). Olaylarda `masa` alanı gelsin ve ofis durum makinesi bunları doğru
  masalara yerleştirsin.
- **İngilizce:** `tests/ceviri_arayuz_testi.py` ofisi, çekmeceleri, ajan kartını, masa kartını,
  işe alma formunu açsın; eksik çeviri 0.

---

## 8. Kapsam dışı (şimdilik)

- Ajanların gerçek zamanlı ses/konuşma sentezi, dış 3B model dosyaları (GLTF), çok katlı ofis.
- İşçilere tarayıcı/MCP vermek (tek CDP portu, günlüğe girmeyen MCP yazmaları; ayrı karar).
- Ajanların kendi başlarına, kullanıcı görev vermeden iş yapması.
- Mobil/dokunmatik özel etkileşim (temel dokunma çalışsın, özel jest yok).

---

## 9. Bu projede öğrenilmiş dersler (tekrarlama)

- **3B etkileşim (ag.js):** Tuval her çizimde yeniden kurulursa sürükleme kopar; iskelet
  **bir kez** kurulur. `setPointerCapture` hata atabilir, try/catch içinde. Döndürme dünya
  orijini etrafında olursa "dönmüyor" gibi hissettirir; pivot sahnenin merkezi olmalı ve kare
  başına yeniden hesaplanmamalı. Sağ tık hem `pointerdown` hem `contextmenu` tetikler; sol
  tık dışındaki düğmeleri `pointerdown`'da yok say. Yakınlaştırma imlecin olduğu noktaya
  doğru yapılır.
- **Performans:** SVG ve katmansız animasyonlar her karede bütün pencereyi yeniden çizdi.
  Görünmeyen animasyon durdurulmalı, animasyonlu küçük öğe kendi katmanında olmalı.
  Ölçmeden "kasma düzeldi" deme.
- **Paralel süreçler:** birden çok süreç aynı dosyaya yazıyorsa (günlük, sayaç, pano) dosya
  kilidi şart (`journal._gunluk_kilidi`). Ofis yeni bir ortak dosya eklerse aynı kilidi kullan.
- **Model uyumluluğu:** OpenAI-uyumlu ve Anthropic API'leri araç adında nokta kabul etmez;
  adaptörler kodluyor (`taban.arac_adi_kodla`). Yeni araç adlarını buna göre seç.
- **Kullanıcı ekranı:** her panel açıkken sohbete dönülebilmeli, kenar çubuğu başka bir işlemde
  kapanmalı, görev arka planda sürmeli. Ofis bu gezinme kurallarını bozmamalı
  (`tests/gezinme_testi.py`).

---

## 10. Kullanıcıya teslim

Her faz sonunda Türkçe, kısa rapor ver: ne yapıldı, nasıl doğrulandı (test adları, ölçülen
rakamlar), bilinen sınırlar, sıradaki faz. Görsel fazlarda bir ekran görüntüsü göster.
Tasarımdan sapman gerekirse **önce** kullanıcıya nedeniyle birlikte sor.
