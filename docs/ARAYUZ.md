# Arayüz Tasarımı — Limina

Faz 5 spesifikasyonu. Bu belge **ne yapılacağını** tanımlar, kodu içermez.

---

## 1. Kimlik

**Ad:** Limina — Latince *limen* (eşik) kelimesinin çoğulu, "eşikler".

Seçim gerekçesi: ürünün gerçeğini söylüyor. Bu ajan her adımda bir eşikten geçiyor —
izin kapısı, onay, risk sınırı. Aynı zamanda kullanıcının "insan çağından makine çağına
ara form" temasını taşıyor. *Liminal* (arada olma hali) kelimesinin köküyle aynı yerden
geliyor. Kısa, her dilde okunur, `limina` paket adı olarak temiz, ve kendini övmüyor —
Claude, Copilot, Gemini gibi bir role ya da kaynağa işaret ediyor.

**Logo:** Minimal, geometrik. Yuvarlatılmış kare bir robot başı, iki nokta göz, ağız yok.
Baş, altı açık ince dikdörtgen bir çerçevenin içinde durur — eşik/kapı eşiği.
Tek renk, düz vektör, 2px eşit çizgi kalınlığı, gradyan yok, gölge yok.
24×24 pikselde okunur olmalı. Lucide/Feather ikon dili.

**İkon sistemi:** Tek aile — Lucide'ın gerçek yolları, `index.html` içinde `IKON`
tablosuna gömülü, tek stroke (`IKON_STROKE = 1.75`). Elle çizilmiş yaklaşık ikon
eklenmez; agirlik farkı (ince artı, dolu dişli) tam bu yüzden çıkmıştı. Boyut
kademeleri: ray 20 px, kart 18 px, kutu kontrolleri 16 px. Renk hiyerarşisi:
**gezinme = gri**, **aksiyon ve aktif durum = turuncu**. Ray'de aktif sayfa
arka plan (`#24211D`) + sol kenarda turuncu çubukla gösterilir. Anlamlar sabit:
`panel-left` kenar çubuğu, `plus` yeni sohbet, `search` ara, `layout-grid` araçlar,
`history` değişiklikler, `settings` ayarlar; kutuda `wrench` görev / `message-circle`
sohbet (ikon anahtarı `konusma`; `sohbet` profil adıyla karışmasın), efor modları `zap` / `gauge` / `sparkles` / `rocket`.

**Logo animasyonun taşıyıcısıdır.** Ayrı bir yükleme göstergesi yok:

| Durum | Gözler |
|---|---|
| Boşta | Açık, sabit, sönük vurgu rengi |
| Düşünüyor (model çağrısı) | Yavaş yanıp sönme, ~1.4 sn döngü |
| Araç çalışıyor | Yatay kayma (sola-sağa bakıyor) |
| Yanıt akıyor | Sabit ve parlak, tam vurgu rengi |
| Onay bekliyor | Yatay çizgi (kısılmış gözler), duraklamış |
| Hata / DENY | Kırmızıya döner, tek nabız |

---

## 2. Renk ve tipografi

**Tema:** Koyu varsayılan, açık tema opsiyonel (ayarlardan).

| Rol | Koyu tema | Açık tema |
|---|---|---|
| Zemin | `#1A1815` | `#FAF8F5` |
| Yüzey (kart, panel) | `#232019` | `#FFFFFF` |
| Kenarlık | `#3A342A` | `#E5DFD5` |
| Ana metin | `#EDE8E0` | `#221F1A` |
| İkincil metin | `#9A9188` | `#6B645C` |
| **Vurgu (Limina bronzu)** | `#C8873E` | `#A66A28` |
| ALLOW | `#5B9E6B` | `#3D7A4C` |
| ASK | `#C8873E` | `#A66A28` |
| DENY / hata | `#C05252` | `#A63D3D` |
| Satır içi kod | `#D98E6A` zemin `rgba(216,142,106,.13)` | (açık tema değeri henüz belirlenmedi) |

Vurgu rengi bilinçli olarak bronz/amber. Sebep: mavi-mor doygunluğundaki AI arayüzlerinden
ayrışır, ve sıcak bir "eşikte duran lamba" hissi verir. Satır içi kod ayrı renk alır ki
dosya yolları ve araç adları metnin içinde anında seçilebilsin.

**Tipografi:**
- Ajan yanıtı (gövde metni): serif — `Georgia`, yedek `Iowan Old Style`, `Times New Roman`.
  Claude'un fontları (Copernicus/Tiempos) lisanslı, kullanılamaz; Windows'ta hazır
  bulunan en yakın karşılık Georgia.
- Arayüz (kart, düğme, kenar çubuğu, girdi, durum çubuğu): sistem sans yığını.
- Kod, yol, araç adı, günlük, fark: monospace (Cascadia Code / JetBrains Mono).
- Gövde 16px / 1.72 satır aralığı. (Serif olduğu için sans'a göre bir punto büyük ve
  satır aralığı biraz geniş.)
- İçerik sütunu maksimum 740px, ortalanmış.

---

## 3. Genel düzen

> **Durum:** Henüz uygulanmadı. Kenar çubuğunun içeriği sohbet geçmişi; geçmiş ise
> şu an mimari olarak yok — `calistir()` her görevde konuşma geçmişini sıfırdan
> kuruyor. Yani "şimdi de onları PDF'e çevir" demek mümkün değil. Önce geçmişin
> `Oturum`'a taşınması (mimari iş), sonra kenar çubuğu (görsel iş).

Tek pencere, tek kolon. **Claude'un düzeni örnek alınıyor:** sohbet akışı merkezde,
kenar çubuğu solda, girdi altta sabit.

```
┌──────────────────────────────────────────────────────────┐
│ ☰  ● Limina        gemini-3.5-flash-lite   MCP: 1   ⚙   │  durum şeridi
├────────────┬─────────────────────────────────────────────┤
│            │                                             │
│  Sohbetler │           SOHBET AKIŞI                      │
│            │                                             │
│  ▸ bugün   │   [kullanıcı mesajı]                        │
│  ▸ dün     │   [ajan yanıtı]                             │
│            │   [araç kartı — daraltılmış]                │
│            │   [onay kartı — satır içi]                  │
│            │                                             │
│            ├─────────────────────────────────────────────┤
│            │  ┌───────────────────────────────────────┐  │
│            │  │ Bir görev yaz...            📎  ⚡  ➤ │  │  girdi
│            │  └───────────────────────────────────────┘  │
│            │  ▓▓▓▓░░░░░░  bağlam %38   ₺0,04   ■ Durdur │  durum çubuğu
└────────────┴─────────────────────────────────────────────┘
```

**Kenar çubuğu** daraltılabilir. İçinde geçmiş sohbetler, altında ayarlar.

---

## 4. Sohbet akışı

Bu ajan bir sohbet botu değil — akış hem konuşma hem eylem içerir. Dört blok tipi var.

### 4.1 Kullanıcı mesajı
Sağa hizalı, yuvarlatılmış balon. Genişliği içeriğe göre, en fazla kolonun %80'i. Ajan
yanıtı ise tam genişlikte ve balonsuz — iki taraf böylece bakışta ayrılıyor. Yüklenen
dosyalar mesajın altında küçük çipler halinde.

### 4.2 Ajan yanıtı
Tam markdown render: başlık, liste, tablo, **kalın**, `satır içi kod`, kod blokları
(sözdizimi renklendirmeli, kopyala düğmeli). Sol altında küçük Limina logosu — yanıt
akarken canlı.

### 4.3 Araç kartı
Her araç çağrısı **daraltılmış** bir kart olarak akışa girer. Sohbeti boğmaz.

Kapalı hali, tek satır:
```
▸ ⬤ read_document   BT.pdf                          ALLOW   0,8sn
```
- Renkli nokta = kapı kararı (yeşil/sarı/kırmızı)
- Araç adı monospace
- En belirgin argüman kısaltılmış olarak
- Süre

Açık hali: tam argümanlar (uzun içerik kaydırılabilir bir alanda), tam sonuç, kırpıldıysa
belirtilir. Sonuç `<untrusted_content>` içeriyorsa **görsel olarak işaretlenir** — kesikli
kenarlık ve "dış kaynak, veri" etiketi. Bu, veri/talimat ayrımının kullanıcıya görünen hali.

Aynı turda paralel çağrılar tek bir grup altında toplanır: `▸ 6 araç çağrısı`.

### 4.4 Onay kartı
**Modal değil, satır içi.** Tetikleyen araç kartının hemen altında belirir, akış onunla
birlikte aşağı kayar. Kullanıcı bağlamı kaybetmez.

```
┌─ ONAY GEREKİYOR ──────────────────────────────────┐
│  write_file                          risk: WRITE  │
│  yol      D:\...\kum\rapor.txt                    │
│  etki     ÜZERİNE YAZILACAK (yedek alınır)        │
│                                                   │
│  [ Farkı göster ▾ ]                               │
│                                                   │
│         [ Reddet ]  [ Onayla ]  [ Tümü ]          │
└───────────────────────────────────────────────────┘
```

Kurallar:
- `DESTRUCTIVE` ve yıkıcı yazmalarda **"Tümü" düğmesi hiç render edilmez.**
- Yıkıcı yazmada kartın üstünde kırmızı uyarı şeridi: "bu yazma içeriği yok ediyor".
- Etki cümlesi araca özgü: `move` → "kaynaktan kaybolacak", `browser_download` → dosya adı
  ve boyut, `browser_open` → tam adres.
- Karar verilince kart yerinde kalır, sonucu gösterir (onaylandı/reddedildi) ve düğmeler
  kaybolur. Geçmiş okunabilir kalmalı.
- **Onay alınamıyorsa (pencere kapanıyor, süreç bitiyor) reddedilir.** Varsayılan asla evet.

### 4.5 Fark gösterimi
`write_file` mevcut bir dosyanın üzerine yazacaksa, onay kartında "Farkı göster" açılır:
satır bazlı fark, silinenler kırmızı zeminde, eklenenler yeşil zeminde. Değişmeyen uzun
bölgeler `⋯ 42 satır` şeklinde katlanır.

Bu, onayı anlamlı kılan tek şey. Terminalde ilk 200 karakter görünüyordu; bu yetersizdi.

---

## 5. Girdi alanı

Çok satırlı, otomatik büyüyen kutu. `Enter` gönderir, `Shift+Enter` yeni satır.

**Ekler (📎):** düğme veya sürükle-bırak. Pencerenin herhangi bir yerine bırakılabilir;
bırakma sırasında tüm akış üzerine yarı saydam bir hedef katmanı gelir.

Yüklenen dosya **yerinde kalır**, kopyalanmaz. Ajana tam yolu verilir. Dosya izinli okuma
köklerinin dışındaysa arayüz bunu hemen söyler: "bu dosya izinli klasörlerin dışında,
`policy.toml`'a eklenebilir" — ve tek tıkla ekleme önerir (kullanıcı onaylar, model değil).

**Model seçici (⚡):** Lite / Flash. `--guclu` bayrağının görsel karşılığı. Flash seçiliyken
kalan günlük kota gösterilir (20 çok dar).

**Slash komutları:** girdi kutusuna `/` yazınca açılan menü. Sık görevlerin kısayolu.
Menü öğeleri, `config/komutlar.toml` benzeri bir dosyadan okunur; her komut bir prompt
şablonudur, kod değil.

Başlangıç seti:
| Komut | Ne yapar |
|---|---|
| `/donustur` | Seçili dosyayı hedef formata çevirir |
| `/ozetle` | Dosya veya sayfayı özetler |
| `/tasi` | Dosyayı hedef klasöre taşır |
| `/duzenle` | Klasörü içeriğe göre sınıflandırıp adlandırır |
| `/oku` | Belgeyi okur ve içeriğini gösterir |
| `/gecmis` | Geri alınabilir işlemleri listeler |
| `/geri-al` | Son işlemi geri alır |
| `/siteler` | İzinli site listesini gösterir/düzenler |

---

## 6. Durum çubuğu

Pencerenin altında, girdinin altında ince şerit.

**Bağlam doluluk göstergesi.** Yeşilden kırmızıya giden bar. Gösterdiği şey: mevcut
bağlamın model penceresine oranı.

> Etiket bilinçli olarak "bağlam doluluğu", "halüsinasyon riski" değil. Token sayısı
> halüsinasyon riskini ölçmez; öyle sunmak yanıltıcı olur. Bar dolduğunda söylediği şey
> "eski adımlar yakında özetlenecek", "model yalan söylemeye başlayacak" değil.

**Maliyet sayacı.** Oturum başına tahmini maliyet. Ücretsiz katmanda kalan kota da burada.

**Adım / çağrı sayacı.** `adım 3 · 12 çağrı`. İkisi ayrı gösterilir çünkü aynı şey değil —
model tek turda paralel çağrı yapabiliyor.

**Durdur düğmesi.** Görev çalışırken kırmızı ve aktif, boştayken gri. Basıldığında:
çalışan araç çağrısı biter ve sonucu günlüğe yazılır, ama **bir sonraki adım başlamaz**.
Onay bekleniyorsa bekleme anında kırılır ve işlem reddedilir. Yarım kalan durum her
adımda zaten günlüğe yazıldığı için ayrı bir kapanış kaydı gerekmez.

---

## 7. Sohbet geçmişi ve oturum

> **Durum:** Henüz uygulanmadı. Kenar çubuğunun içeriği sohbet geçmişi; geçmiş ise
> şu an mimari olarak yok — `calistir()` her görevde konuşma geçmişini sıfırdan
> kuruyor. Yani "şimdi de onları PDF'e çevir" demek mümkün değil. Önce geçmişin
> `Oturum`'a taşınması (mimari iş), sonra kenar çubuğu (görsel iş).

Geçmiş **varsayılan olarak korunur** — kullanıcı "şimdi de onları PDF'e çevir" diyebilmeli.

Ayarlardan kapatılabilir. Kapalıyken her görev bağımsız bir oturumdur (CLI davranışı).

Geçmiş açıkken iki şey değişir ve arayüz bunları göstermek zorunda:
- Bağlam her turda birikir → doluluk barı bunu yansıtır.
- **Toplu onay oturum kapsamlıdır.** "Oturum" burada = sohbet penceresi açık olduğu süre.
  Yeni sohbet açmak toplu onayları sıfırlar. Kenar çubuğunda aktif toplu onaylar
  görünmeli ve tek tıkla iptal edilebilmeli.

---

## 8. Ayarlar

Ayrı bir panel, kenar çubuğunun altından açılır.

- **Tema:** koyu / açık / sistem
- **Sohbet geçmişi:** açık / kapalı
- **Model:** varsayılan ve güçlü model seçimi
- **İzinli siteler:** liste, ekle/sil. `policy.toml`'un `[browser].izinli_alanlar`
  bölümünü düzenler
- **İzinli klasörler:** okuma / yazma kökleri, salt görüntüleme + ekle/sil
- **Araç riskleri:** hangi araç hangi seviyede, salt görüntüleme

**Politika düzenleme güvenlik kuralları:**
1. Yazmadan önce `policy.toml.yedek` alınır.
2. Yazdıktan sonra `tomllib` ile geri okunur; ayrıştırma hatası varsa yedek geri yüklenir.
3. Girdi doğrulanır (alan adı biçimi, yolun varlığı).
4. **Bu paneli yalnızca kullanıcı kullanır. Model `policy.toml`'a hiçbir koşulda yazamaz.**

**Dil (Ayarlar > Genel):** `config/arayuz.toml [genel] dil = "en" | "tr"`, varsayılan İngilizce. Arayüzdeki
her kullanıcıya görünen metin `t("Türkçe kaynak metin", {yer_tutucu})` içinden geçer;
kaynak dil Türkçe, çeviri `index.html` içindeki `CEVIRI.en` sözlüğünde, anahtar
Türkçe metnin kendisi (gettext deseni). Çevirisi olmayan anahtar Türkçe düşer,
boş kalmaz. Yeni bir metin eklerken kural: literal'i `t()` içine al ve `CEVIRI.en`'e
satırını yaz. Dil değişimi anında uygulanır (statik metinler, kutu kontrolleri,
karşılama, kenar çubuğu, açık ayarlar sekmesi); akışta zaten çizilmiş kartlar
sohbet yeniden açılınca çevrilir.

**Python tarafı aynı ayarı izler** (`limina/ceviri.py`). Aynı desen, aynı kural:
`t("Türkçe kaynak metin", yer_tutucu=deger)`, çeviri `ceviri.EN` sözlüğünde.
Kapsam: onay kartındaki etki cümlesi ve fark başlıkları, kapı red gerekçeleri,
döngü/model hataları, dönüş özeti (`ozet_metni`), `--gecmis` ve geri alma
çıktıları. Dil Ayarlar'dan değiştiğinde `pencere.Api.arayuz_ayari_yaz`
`ceviri.dil_ayarla()` çağırır, yani aynı ekranda iki dil görünmez.
`tests/ceviri_testi.py` kaynağı AST ile tarar: sözlükte karşılığı olmayan bir
`t()` anahtarı, sözlükte kullanılmayan ölü bir anahtar ya da TR/EN arasında
uyuşmayan bir yer tutucu testi kırar — sessizce Türkçe'ye düşmek bir testin
yakalaması gereken şeydir.

**Çevrilmeyenler, bilerek:**
- **Durum dosyası** (`durum.py`, `## Hedef` / `## Kalanlar` başlıkları): bir
  BİÇİM, mesaj değil — `_durum_oku` onu geri okuyor. Çevrilse dili değiştiren
  kullanıcının yarım kalan görevi sürdürülemez olurdu. Özet dosyası çevrilir,
  çünkü onu yalnızca insan okur.
- **Günlük (journal) alan adları** (`"tip": "yazma"`): veri.
- **MCP sunucularının kendi araç açıklamaları:** sunucudan geldiği gibi gider.
  (Eklenti araçları — `limina/eklentiler` — ÇEVRİLİR: bildirimler `tools.py`'de
  Türkçe durur, `registry._cevrilmis` çıkışta aynı sözlükten çevirir; test
  `registry.TOOLS`'u da tarar.)

**Modele giden metinler de aynı ayarı izler:** sistem talimatı
(`talimat.py`, cümle cümle), araç bildirimleri (`araclar/kayit.py`
`semalar()` her çağrıda `modele=` ve şema `description`'larını çevirir; dil
değişince `arac_semalarini_tazele` yeniden kurar), tavan anındaki `durum_yaz`
aracı ve bütün araç çıktıları. Canlı doğrulandı: İngilizce talimat +
bildirimlerle `gemini-3.5-flash-lite` read → write → edit_file zincirini
doğru kurdu. `tests/ceviri_testi.py` `@arac` bildirimlerini de tarar.

---

## 9. Teknoloji ve mimari

| Dosya | Sorumluluk |
|---|---|
| `limina/olaylar.py` | Olay tipleri, `Oturum`, `OnayIstegi`, `onay_iste`, hazır sağlayıcılar |
| `limina/gui_kopru.py` | Ajan thread'i ↔ UI thread'i köprüsü, olay kuyruğu, onay bekleme |
| `limina/pencere.py` | pywebview penceresi, JS'e açılan `Api` yüzeyi |
| `limina/arayuz/index.html` | Tek dosya HTML/CSS/JS arayüz |
| `tests/kopru_testi.py` | Köprüyü modelsiz sınar |
| `tests/arayuz_testi.py` | Kaçışlama, uzak kaynak ve yerleşim kurallarını denetler |

**pywebview.** Arayüz HTML/CSS/JS, kendi masaüstü penceresinde açılır. Tarayıcı değil —
ajanın kontrol ettiği Chrome ile hiçbir ilgisi yok.

Gerekçe: Claude benzeri bir arayüz markdown render, akıcı animasyon ve iyi tipografi
gerektiriyor. CustomTkinter bunların hiçbirini yapamaz. PyQt için `QWebEngineView`
(gömülü Chromium, 150+ MB) gerekir — aynı yere daha ağır paketle gidilir.

**Bağımlılıklar minimum:** pywebview + markdown render kütüphanesi + sözdizimi
renklendirme. Build adımı yok, framework yok — düz HTML/CSS/JS. Sebep: kullanıcı kod
okuyamıyor; bir build zinciri bozulduğunda teşhis edemez.

### Mimari kurallar

**1. Ajan döngüsü arayüzü bilmez.** `vekil_v0.py` şu an `onay_al` içinde doğrudan
`input()` çağırıyor. Bu bir **onay sağlayıcı** parametresine çevrilmeli:

```
calistir(gorev, guclu=False, onay_saglayici=terminal_onayi)
```

Terminal kendi sağlayıcısını verir, GUI kendininkini, `evals.py` otomatik olanı.
Böylece CLI çalışmaya devam eder ve mevcut testler kırılmaz.

**2. Ajan arka plan thread'inde çalışır.** UI thread'i asla bloke olmaz. Ajan döngüsü
bir olay yayıncısı (callback) çağırır. GUI köprüsü bu yayıncıyı bir kuyruğa bağlar;
CLI'de yayıncı boştur, `evals.py` isterse olayları listeye toplar. Olay tipleri:
`gorev_basladi`, `adim_basladi`, `olcum`, `arac_cagrildi`, `onay_gerekli`, `onay_sonucu`,
`arac_sonucu`, `yanit_parcasi`, `gorev_bitti`, `hata`. `olcum` olayı spesifikasyonda
yoktu, sonradan eklendi — §6'daki bağlam doluluk barının ve adım/çağrı sayacının veri
kaynağı o. UI olayları **çekerek** alır (polling, 120ms): pywebview'de arka plan
thread'inden `evaluate_js` çağırmak platforma göre güvenilir değil.

**3. Onay senkron bekler.** Ajan thread'i onay sağlayıcıyı çağırır ve bloke olur; UI
thread'i kartı render eder, kullanıcı karar verir, sonuç ajan thread'ine döner. Bu,
framework'ten bağımsız olarak Faz 5'in en zor teknik parçasıdır — önce bu çözülmeli,
görsel tasarım sonra.

**4. Araç çıktısı asla ham HTML olarak basılmaz.** Sayfa metni, dosya içeriği, komut
çıktısı — hepsi kaçışlanır. Aksi halde okunan bir web sayfası arayüze script enjekte
edebilir. Prompt injection savunmasının arayüz tarafındaki karşılığı budur.

**5. Uzak kaynak yok.** Arayüz hiçbir `http`/`https` adresine gitmez: CDN yok, uzak
font yok, uzak script yok. Bütün varlıklar diskten gelir. İki gerekçe: pencere
çevrimdışı çalışmalı, ve bir CDN bağımlılığı tedarik zinciri saldırı yüzeyi açar.
`arayuz_testi.py` bu kuralı denetler.

**6. Markdown, HTML dizesi üretmeden render edilir.** Hazır bir markdown kütüphanesi +
temizleyici (sanitizer) yerine, doğrudan DOM düğümü üreten bir çevirici yazıldı.
Gerekçe: kütüphane yolu `innerHTML`'i kod tabanına sokar ve güvenlik temizleyicinin
doğruluğuna bağlanır; DOM yolunda tarayıcının HTML ayrıştırıcısı hiç devreye girmez,
dolayısıyla enjeksiyon yüzeyi yoktur. Ek olarak iki bağımlılık ve ~120 KB gelmez.
Maliyeti: egzotik markdown (iç içe alıntı, referans bağlar, gömülü HTML) desteklenmez.

Ayrıca: **bağlar tıklanabilir değildir.** Ajanın yanıtındaki bir adres metin olarak
gösterilir, `<a>` üretilmez — bir tık pencereyi izin kapısının denetlemediği bir
adrese götürebilirdi.

---

## 10. Kabul kriterleri

- [ ] Kullanıcı, ajanın ne yaptığını arayüze bakarak anlıyor (kenar çubuğu ve sohbet
      geçmişi gelmeden tam değerlendirilemez)
- [x] Çalışan bir görev tek tıkla, veri bırakmadan durdurulabiliyor
- [x] Onay kartı satır içi açılıyor, `DESTRUCTIVE` işlemlerde "Tümü" görünmüyor
- [x] Üzerine yazma onayında fark görüntülenebiliyor
- [x] `<untrusted_content>` çıktıları görsel olarak işaretli
- [x] Araç çıktısındaki HTML/script arayüzde çalışmıyor (kaçışlama testi)
- [ ] Sürükle-bırak ve düğmeyle dosya yükleme çalışıyor (henüz yapılmadı)
- [x] Bağlam doluluk barı canlı güncelleniyor
- [ ] Maliyet sayacı canlı güncelleniyor (henüz yapılmadı; bağlam barı çalışıyor)
- [x] CLI hâlâ çalışıyor, `evals.py` kırılmadı
- [x] Logo animasyonu ajanın durumunu doğru yansıtıyor

---

## 11. Faz 5 kapsam dışı

- Çoklu eşzamanlı görev (tek görev, tek pencere)
- Sohbet dışa aktarma
- Klavye kısayolları (temel olanlar dışında)
- Mobil / duyarlı düzen — sabit masaüstü penceresi
- Tema özelleştirme (koyu/açık dışında)
- Zamanlanmış görev arayüzü → **Faz 7**
