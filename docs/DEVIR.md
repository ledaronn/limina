# Devir Belgesi — Limina

Bu belge, projeye yeni katılan bir teknik ortağın (insan ya da model) önceki sohbetin
tamamını okumadan devam edebilmesi için yazıldı. Durum, alınan kararlar ve gerekçeleri
burada. Detay için diğer belgelere bakılır.

**Güncellik notu (4 Ekim 2026):** Bu belge erken geliştirme döneminin kararlarını saklar; aşağıdaki faz ve eksik iş listeleri tarihsel kayıttır. Sohbet geçmişi, ekip/ofis, düşünce ağı ve yerel eklentiler artık mevcut. Güncel kullanım için [README](../README.md), [PRODUCTIVITY](PRODUCTIVITY.md), [EKIP](EKIP.md) ve [AG](AG.md); son düzeltmeler için [uygulama kaydı](DUZELTMELER_2026-10-04.md) esas alınmalı.

---

## 1. Proje nedir

Yerelde çalışan, araç çağırabilen kişisel bir ajan. Bir LLM API'sini akıl yürütme motoru
olarak kullanır; dosya sistemi, tarayıcı ve kişisel araçları tek bir **denetimli** döngü
üzerinden kontrol eder.

**Çalışma adı `Vekil` idi, ürün adı `Limina` oldu.** Kod içindeki dosya adları
(`vekil_v0.py`) ve veri klasörü (`~/.vekil/`) henüz değişmedi — bilinçli, veri taşımak
gereksiz risk. Faz 6'da temiz geçiş yapılacak.

Ne değildir:
- Kendi temel modelini eğitmez.
- Tam otonom değildir. Riskli her adımda kullanıcıya sorar.
- Çok kullanıcılı bir servis değildir. Tek makine, tek kullanıcı.

---

## 2. Kullanıcı hakkında — çalışma şekli

Bu bölüm önemli, atlanmamalı.

**Kullanıcı yazılımcı değil.** Kod okuyamıyor, teknik ayrıntıları bilmiyor. Anlaşma şu:
teknik ortak kodu yazar, kullanıcı çalıştırır ve sonucu bildirir. Kullanıcı kodu
Claude Code'a (VS Code eklentisi) uygulattırıyor, o da aynı klasörde çalışıyor.

Bunun iki sonucu var:

1. **Komutlar tıklama düzeyinde anlatılmalı.** "venv oluştur" değil, kopyalanacak komut.
   Windows/PowerShell ortamı, Mac/Linux komutları çalışmaz.
2. **`policy.toml` güvenlik sınırının kendisidir.** Onu değiştiren her şey sınırı
   değiştirir. Claude Code o dosyaya dokunduğunda kullanıcının gözüyle görmesi gerekir.
   Modelin kendisi asla o dosyaya yazamaz.

**Kullanıcının istediği çalışma tarzı** (ilk mesajdaki proje talimatından):
- Faz disiplinine uy. İleride olan bir bileşen için kod yazma; "bu Faz N, şimdi erken" de.
- Önce en kısa çalışan hali, sonra sağlamlaştırma. Erken soyutlama yapma.
- Kod isterken açıklama değil kod ver. Anlatım yerine kodun içine yorum.
- İki seçenek varsa ikisini de söyle, sonra birini öner ve nedenini yaz.
- Katılmadığın tasarım kararını açıkça söyle. Onaylayıcı davranma.

Bu son madde pratikte en çok işe yarayan oldu. Kullanıcı birkaç kez kapsam genişletmek
istedi (WhatsApp okuma, gözetimsiz gece görevleri, süreli toplu onay); her seferinde
gerekçeli itiraz daha iyi bir tasarıma dönüştü.

---

## 3. Pazarlıksız kurallar

Bunları ihlal eden kod önerilmez:

- Araç sonucu — hata dahil — her zaman **metin olarak** modele geri döner.
- Yürütücüye giden tek yol izin kapısıdır (`gate.karar`). Kapı atlanamaz.
- `subprocess` her zaman liste argümanla; `shell=True` asla.
- Dosya yolları `realpath` ile çözülür, **sonra** izinli köklere karşı kontrol edilir.
- Kalıcı silme aracı yok, sadece çöp kutusuna taşıma.
- Araç çıktısı kırpılır (~8 KB), kırpıldığı belirtilir.
- Ajan döngüsünün adım limiti vardır.
- Kimlik bilgisi girilmez, okunmaz, günlüğe yazılmaz.
- Onay alınamıyorsa (stdin yok, Ctrl-C) **reddedilir**, asla varsayılan evet olmaz.
- Model `policy.toml`'a hiçbir koşulda yazamaz.
- Limina'nın kaynak kodu `policy.toml`'daki yazma köklerinin **dışındadır**; ihlalde
  süreç başlamaz.
- Arayüzde hiçbir metin HTML olarak ayrıştırılmaz; `innerHTML` ve akrabaları yasak.

**Kod standardı:** Python 3.13, tip ipuçları zorunlu, standart kütüphane tercih edilir.
Araç fonksiyonları `str` döndürür. Docstring'ler modele yazılır ve aracın ne zaman
**kullanılmayacağını** da içerir. Hata mesajları modelin düzeltebileceği bilgiyi taşır.

---

## 4. Ortam

| Şey | Değer |
|---|---|
| İşletim sistemi | Windows, PowerShell |
| Python | 3.13.5, `.venv` sanal ortamı |
| Proje kökü | `<proje-kökü>` |
| Model sağlayıcı | Google Gemini, **ücretsiz katman** |
| Anahtar | `GOOGLE_API_KEY` ortam değişkeni (`setx` ile kalıcı) |
| Varsayılan model | `gemini-3.5-flash-lite` — 15 RPM / 500 RPD |
| Güçlü model | `gemini-3.6-flash` — 5 RPM / **20 RPD** (çok dar, `--guclu` ile) |
| LibreOffice | 26.8.0.3, headless dönüşüm için |
| Tarayıcı | Chrome, ayrı profil: `AI\chrome-profil` |

**Kota uyarısı:** Flash modellerinin günlük limiti 20 istek. Testler art arda
çalıştırılırsa kota biter. Flash-Lite 500 istek verir, ana eksen odur.

**Gizlilik uyarısı:** Ücretsiz katmanda Google girdi/çıktıyı model geliştirmek için
kullanabiliyor. Ajanın okuduğu her belge oraya gidiyor. Test sırasında gerçek bir
sağlık raporu (`MRG.pdf`) okundu ve bu fark edildi; kullanıcı bilgilendirildi.

---

## 5. Dosyalar ve ne yaptıkları

Kaynak kod `limina/` paketinde, testler `tests/` altında; kullanıcının ellediği
şeyler (`policy.toml`, `config/`, `kum/`, `evals/`, `Donusturucu/`) proje kökünde.
Yerleşim iki sabitten okunur: `limina.PAKET` (kod) ve `limina.PROJE_KOKU`
(policy/config). Hiçbir modül kendi konumundan proje kökü türetmez. Giriş
noktaları proje kökünden: `python -m limina` (pencere), `python -m
limina.vekil_v0 "görev"` (CLI), `python tests/<ad>.py` (testler).


| Dosya | Sorumluluk |
|---|---|
| `limina/vekil_v0.py` | Ajan döngüsü, araç fonksiyonları, araç şemaları, onay, CLI |
| `limina/gate.py` | İzin kapısı: yol/URL doğrulama, risk→karar, `policy.toml` okuma |
| `limina/journal.py` | JSONL günlük, yedekleme, geri alma, çöp kutusu |
| `limina/belge.py` | PDF/DOCX/PPTX/XLSX → metin |
| `limina/ara.py` | Dosya adı + metin içeriği araması (saf Python, ripgrep yok) |
| `limina/tarayici.py` | Playwright, Chrome otomatik başlatma, ARIA etkileşim |
| `limina/mcp_bridge.py` | MCP sunucularını alt süreç olarak bağlar, senkron sarmalar |
| `limina/modeller.py` | `policy.toml`'daki model adları hâlâ geçerli mi kontrol eder |
| `tests/evals.py` | Regresyon koşucusu |
| `evals/tasks.yaml` | Regresyon görevleri |
| `policy.toml` | **Güvenlik sınırı.** İzinler, risk seviyeleri, modeller, MCP sunucuları |
| `config/persona.md` | Kullanıcı tercihleri, sistem talimatına eklenir |
| `Donusturucu/` | MCP sunucusu (`server.py`), motor (`core_engine.py`), GUI (`app_gui.py`) |
| `limina/olaylar.py` | Olay tipleri, `Oturum`, `OnayIstegi`, `onay_iste`, hazır sağlayıcılar |
| `limina/gui_kopru.py` | Ajan thread'i ↔ UI thread'i köprüsü, olay kuyruğu, onay bekleme |
| `limina/pencere.py` | pywebview penceresi, JS'e açılan `Api` yüzeyi |
| `limina/arayuz/index.html` | Tek dosya HTML/CSS/JS arayüz |
| `tests/kopru_testi.py` | Köprüyü modelsiz sınar |
| `tests/arayuz_testi.py` | Kaçışlama, uzak kaynak ve yerleşim kurallarını denetler |

`.gitignore` eklendi.

**Kalıcı veri:** `~/.vekil/journal.jsonl`, `~/.vekil/yedek/`, `~/.vekil/cop/`,
`~/.vekil/indirilen/`.

---

## 6. Araç kataloğu (15 araç)

| Araç | Risk | Not |
|---|---|---|
| `list_dir` | READ | Ad + boyut |
| `read_file` | READ | Düz metin, ilk 400 satır |
| `read_document` | READ | PDF/DOCX/PPTX/XLSX → metin |
| `search` | READ | Ad + metin içeriği. Belge içi taramaz |
| `degisiklik_gecmisi` | READ | Ajanın kendi günlüğünü okur |
| `write_file` | WRITE | Yazmadan önce yedek. Boşaltma = yıkıcı sayılır |
| `move` | WRITE | Kaynak ve hedef ayrı doğrulanır. Üzerine yazmaz |
| `rename` | WRITE | Yerinde ad değişimi, klasörlerde de çalışır |
| `trash` | DESTRUCTIVE | `~/.vekil/cop/`. Sadece dosya, klasör değil |
| `browser_open` | NETWORK | Site beyaz listesine tabi |
| `browser_read` | READ | Metin, `<untrusted_content>` ile sarılır |
| `browser_snapshot` | READ | ARIA ağacı, click/fill referansları buradan |
| `browser_click` | WRITE | Rol+ad ile, koordinatla değil |
| `browser_fill` | WRITE | Parola alanı reddedilir, kart/TC kalıbı reddedilir |
| `browser_download` | DESTRUCTIVE | Uzantı beyaz listesi, ara klasöre iner |
| `converter.convert` | WRITE | MCP. PPTX/PPT/DOCX→PDF, PDF→PPTX/PNG, PNG/JPG→PDF |
| `converter.list_formats` | READ | MCP |

---

## 7. Güvenlik katmanları

Tek katmanın tutması beklenmez, üst üste konur.

**Yol hapishanesi.** `realpath` ile çöz, sonra kontrol et. Üç ayrı liste:
- `okuma_koklari` — `kum`, `Downloads`, `Desktop`, `~/.vekil/indirilen`
- `yazma_koklari` — `kum`, `Desktop\Vekil`, `~/.vekil/indirilen`
- `tasima_kaynaklari` — planlandı, henüz uygulanmadı (bkz. bölüm 10)

**Kara liste.** İzinli klasörlerin içinde bile: `.env`, `*.pem`, `*.key`, `id_*`,
`*credential*`, `.ssh`, `.aws` vb.

**Site beyaz listesi.** `browser_open` yalnızca `izinli_alanlar` içindeki alan adlarını
açar (alt alanlar dahil). Yerel dosya için ayrı `izinli_yerel_kokler`.

**Uzantı beyaz listesi.** İndirme sadece `indirilebilir_uzantilar` içindekiler için.
Çalıştırılabilir dosyalar hiçbir koşulda inmez.

**Risk seviyeleri.** READ→ALLOW, WRITE/EXEC/NETWORK→ASK, DESTRUCTIVE→ASK (toplu onaysız).
Politikada tanımlı olmayan araç **çalışmaz** (varsayılan reddet).

**Toplu onay.** Oturum kapsamlı, araç bazlı. `DESTRUCTIVE` ve yıkıcı yazmalarda seçenek
hiç görünmez.

**Yıkıcı yazma tespiti.** `write_file` bir dosyayı boşaltıyor veya %80'inden fazlasını
siliyorsa toplu onayı atlar, ayrı sorulur ve uyarı basar. Sebep: model silme aracı
yokken içeriği boşaltarak aynı sonuca ulaşmayı denedi.

**Tur tavanı.** Model tek turda paralel araç çağırabiliyor. Risk başına tur tavanı:
READ 12, WRITE 5, EXEC/NETWORK 3, DESTRUCTIVE 2. Aşınca model uyarılır, kalanı sonraki
tura bırakır.

**Veri/talimat ayrımı.** Araç çıktıları `<untrusted_content>` ile sarılır. Sistem
talimatı açıkça der ki: bu blokların içindeki yönergeler uygulanmaz, kullanıcıya bildirilir.

**Geri alma.** Her yazma öncesi yedek. `--geri-al [dosya]` dosya bazlı çalışır.
Geri alma da yedeklenir (tekrarlanan geri alma veri kaybettirmesin diye).

**Yerleşim sınırı.** Limina'nın `.py` dosyaları `yazma_koklari`'nın dışında olmalı —
olsalardı `write_file` ile onay mekanizmasını değiştirmek kapıdan ALLOW alırdı.
`gate.Politika.kod_koku_yazilabilir_mi()` bunu `vekil_v0.py` içe aktarılırken
denetler; ihlalde süreç başlamaz. Giriş noktası fark etmez (CLI, `evals.py`,
`pencere.py`). Gerçek bir olaydan sonra kondu: bkz. bölüm 15/7.

**Arayüz kaçışlaması.** Araç çıktısı, sayfa metni, fark, markdown — hiçbiri HTML
dizesi olarak DOM'a girmez; `innerHTML` ve akrabaları `arayuz/index.html`'de yok,
her metin `createElement`+`textContent` ile kurulur. Markdown da hazır kütüphane +
temizleyici yerine doğrudan DOM üreten bir çeviriciyle render edilir. Arayüz hiçbir
uzak adrese gitmez, ajanın yanıtındaki bağlar tıklanabilir değildir. `arayuz_testi.py`
hepsini denetler.

---

## 8. Tamamlanan fazlar

**Faz 0 — Çekirdek döngü.** Adım limitli döngü, 3 araç, ham CLI. Üç kabul kriteri de
geçti. Ek bulgu: adım limiti turları sayıyordu, çağrıları değil → `MAX_CALLS` eklendi.

**Faz 1a — Kapı ve yazma.** `gate.py`, `policy.toml`, `journal.py`, `write_file`,
geri alma, toplu onay. Beş kabul kriteri geçti.

**Faz 1b — Taşıma.** `move`, `rename`, `trash`. Model artık silmek için `write_file`
zorlamıyor, doğru aracı seçiyor.

**Faz 2a — Okuma yüzeyi.** `read_document`, `search`.

**Faz 2c — MCP.** `Donusturucu` yeniden yazıldı (COM kaldırıldı, LibreOffice headless
geldi), `server.py` MCP sunucusu oldu, `mcp_bridge.py` bağladı. Kritik test geçti:
**MCP araçları da kapıdan geçiyor**, sunucu kendi izin kontrolü yapmıyor.

**Faz 3a — Tarayıcı okuma.** `browser_open`, `browser_read`, site beyaz listesi,
`<untrusted_content>`. **Prompt injection testi geçti** — üç katmanlı tuzak sayfa
(HTML yorumu, beyaz-üstüne-beyaz metin, ajana hitap eden blok) modeli yönlendiremedi,
model ayrıca durumu kullanıcıya bildirdi.

**Faz 3b — Etkileşim.** `browser_snapshot` (ARIA), `browser_click`, `browser_fill`.
Parola alanı reddi test edildi ve tuttu.

**Faz 3c — İndirme.** `browser_download`, ara klasör, uzantı beyaz listesi. Tam zincir
çalıştı: web → indir → oku → içeriğe göre adlandır → taşı.

**Faz 4 — Kişiselleştirme.** Kapsamı `config/persona.md`'ye daraltıldı. Çalışma defteri,
`notes.search` ve bağlam bütçesi Faz 6'ya ertelendi — **ölçüm sonucu:** 6 PDF okuyan bir
görevde bağlam zirvesi 4601 token, pencerenin binde biri. Çözülecek bir sorun yoktu.

**Faz 5a — Mimari.** `onay_al` kaldırıldı, yerine enjekte edilen onay sağlayıcı.
Toplu onay ve durdurma bayrağı `Oturum`'a taşındı (modül seviyesindeki `TOPLU_ONAY`
ve `OTOMATIK_ONAY` silindi). Olay yayıncısı eklendi. Ajan arka plan thread'inde,
onay senkron bekliyor, pencere kapanınca RED. `kopru_testi.py` 13/13.

**Faz 5b — Pencere.** pywebview, markdown→DOM çevirici, araç/onay kartları, renkli
fark, logo durum göstergesi, bağlam barı, toplu onay çipleri. Beş elle test geçti.

---

## 9. Ölçüm sonuçları

**Adım ≠ araç çağrısı.** Gemini tek turda birden fazla aracı paralel çağırıyor. 6 dosyalık
bir görev 3 model turunda, 7 araç çağrısıyla bitti. Adım limiti gerçek iş yükünü ciddi
şekilde eksik gösteriyor. Bu yüzden hem `MAX_CALLS` hem `TUR_TAVANI` var.

**Bağlam büyümesi.** Ölçülen zirve 4601 token. Sentetik kısa PDF'lerle yapıldı; gerçek
çok sayfalı belgelerle farklı olabilir. Dikkat dağılması gözlenmedi — model ilk okuduğu
belgeyi son özette doğru temsil etti.

**Model kalitesi.** Flash-Lite araç çağırmada bozulmadı. Uzun zincirlerde şema bozma
endişesi şimdilik doğrulanmadı.

---

## 10. Bilinen açıklar ve borçlar

| Konu | Durum |
|---|---|
| `tasima_kaynaklari` | Tasarlandı, uygulanmadı. Downloads'tan dosya çıkarabilme; kaynak taşıma listesinde, hedef yazma köklerinde olmalı. Uzantı beyaz listesiyle birlikte |
| MCP `stderr` | Sunucu bağlanamazsa kök sebep görünmüyor (`MCPError: Connection closed`). Alt sürecin stderr'i `Client` sarmalayıcısı tarafından açılmıyor |
| `journal` kimliği | Kayıtlar zamanla tekilleştiriliyor. Mikrosaniye yamalandı ama doğrusu ayrı bir `id` alanı |
| Model aşırı arama | Bir araç "bulunamadı" dediğinde model kullanıcının belirtmediği klasörleri taramaya devam ediyor VE başka bir dosyayla ikame edebiliyor — canlı koşuda kanıtlandı: `ornek.md` bulunamayınca model dört adım dolanıp `kum/README.md`'yi dönüştürdü, onay kartı "dönüştürülecek -> kum" diyordu ve kaynak adı hiç görünmüyordu. `converter.convert` için düzeltildi: sistem talimatına ikame-etmeme cümlesi + `evals/tasks.yaml`'da `ARAC_CAGRILDI` olayına bakan `arac_arg_esit` regresyon testi. Genel okuma/arama taşkınlığı için ayrı bir sınır hâlâ yok |
| MCP araçlarının yazdıkları geri alınamıyor | `write_file` `journal.yedekle()` ile yedekleniyor, `--geri-al` ile dönüyor. `converter.convert` gibi MCP araçlarının ürettiği dosyalar journal'a hiç girmiyor — yedeği yok, değişiklik geçmişinde görünmüyor, geri alınamıyor. Bu asimetri yüzünden `converter.convert` toplu onaydan çıkarıldı (her dönüşüm ayrı sorulur); doğru uzun vadeli çözüm MCP araç sonuçlarını journal'a yazdırmak — köprünün "hangi dosya yazıldı" bilgisiyle journal'ın "yazmadan önce yedek al" sözleşmesini buluşturan ayrı bir mimari iş |
| `~/.vekil` → `~/.limina` | Ad değişikliği ertelendi; veri taşımak risk |
| Belgeler eski | `README`, `ARCHITECTURE`, `TOOLS`, `SECURITY` gerçekle uyuşmuyor (bkz. bölüm 11) |
| Markdown ayrıştırıcı testi | Projede yok; Node + jsdom ile dışarıda doğrulandı |
| `list_dir` kara liste sızıntısı | `.env` adı ve boyutu listeleniyor |
| Kısmi düzenleme aracı yok | Tek satır için tüm dosya yeniden yazılıyor (ölçüldü: 1617 token, ve gerçek bozulmaya yol açtı — bkz. `ROADMAP.md` Faz 5b notu) |
| Belgeler `kum/` altında | Ajan kendi spesifikasyonunu değiştirebilir; kod için sınır kondu, belgeler için bilinçli olarak konmadı |

---

## 11. Güncellenmesi gereken belgeler

**`README.md`** — ad `Vekil`→`Limina`. Dizin yapısı bölümü gerçek değil: `vekil/` paketi
ve `tools/` alt klasörü yok, her şey kökte düz. Belgeyi gerçeğe uydur (dosyaları taşıma,
kazanç yok). "Başlarken" komutları güncellenmeli.

**`ARCHITECTURE.md`** — döngü sözde kodunda eksikler: `MAX_CALLS`, `TUR_TAVANI`, 429/503
yeniden deneme, `OTOMATIK_ONAY` kancası. Bileşenlere `belge.py`, `ara.py`, `tarayici.py`
eklenmeli. Kalıcı durum tablosuna `cop/` ve `indirilen/` eklenmeli.

**`TOOLS.md`** — katalog 8 araç eksik: `read_document`, `search`, `rename`,
`degisiklik_gecmisi`, `browser_snapshot`, `browser_click`, `browser_fill`,
`browser_download`. `edit_file` belgede var ama kodda yok. `trash` açıklaması
`send2trash` diyor; kendi çöp klasörümüz seçildi.

**`SECURITY.md`** — en çok gerileyen belge. Eklenecekler: site beyaz listesi, indirme
uzantı beyaz listesi, `tasima_kaynaklari`, yıkıcı yazma tespiti, tur tavanı, "onay
alınamazsa reddet", parola alanı reddi, kart/TC kalıp kontrolü. Tehdit tablosuna
"ücretsiz katmanda içerik sağlayıcıya gidiyor" satırı.

**`ROADMAP.md`** — Faz 5 yeniden yazılmalı (pywebview, `ARAYUZ.md`'ye referans).

---

## 12. Sıradaki iş: Faz 5c — sohbet geçmişi + kenar çubuğu

`calistir()` şu an her görevde `gecmis` listesini sıfırdan kuruyor; geçmiş `Oturum`'a
taşınmalı. Bu bir mimari iş ve kenar çubuğunun ön koşulu — çubuğun içeriği geçmiş.

---

## 13. Sonraki fazlar

**Faz 6 — Güvenilirlik ve maliyet.** Eval setini genişletme, iki katmanlı model
yönlendirme (kriteri kullanıcının `--guclu` dediği görevlerden çıkar), maliyet raporu.
Ertelenmiş işler: çalışma defteri, bağlam bütçesi, `notes.search`, `~/.limina` geçişi,
MCP stderr, `journal` id alanı, Interactions API değerlendirmesi.

**Faz 7 — Gözetimsiz görevler (bitti; gerçekleşen çıktılar `ROADMAP.md`'de).** Görev
profilleri: `policy.toml [profiller.<ad>]`, izinli araçlar + yazma kökleri alt kümesi;
kapsam içi ASK önceden onaylı, DENY dokunulmaz, kapsam dışı normal davranış. **Süre
sınırlı toplu onay yok** — kapsam bir duvar, süre bir zamanlayıcı; duvar zaten
çizildiyse zamanlayıcı gereksiz ve zayıflatıcı. Durum dosyası + kendiliğinden devam,
istek bütçesi, dönüş özeti, sohbet modu, düşmanca test paketi. ~~`kod_yaz` aracı~~ —
**reddedildi** (§14.1). ~~Sabah raporu~~ — zamanlanmış başlatma gereksiz bulununca
(§14.2) anlamını yitirdi; yerine görev başına dönüş özeti geldi.

**Faz 8 — Mesajlaşma.** Resmi API'si olan platformlar üzerinden. **WhatsApp Web
otomasyonu kapsam dışı:** ToS ihlali ve hesap yasağı riski, tüm sohbetlere erişim,
injection yüzeyi. Kullanıcının asıl ihtiyacı (dosya ayıklama) Faz 3c ile zaten çözüldü.

---

## 14. Reddedilen fikirler ve gerekçeleri

Bunlar tekrar gündeme gelirse, gerekçeler burada:

**Süreli toplu onay ("1 saat her şeye evet").** Kapsam tabanlı profil aynı sonucu daha
güvenli verir. Süre penceresi içinde politika ne derse desin her şey geçer; kapsam
duvarında ise sınır dışı istek gece 3'te de reddedilir.

**Modelin `policy.toml`'u güncellemesi.** Kapı, kapıyı açan tarafından düzenlenemez.
Model adı güncellemek için `modeller.py` raporu var; değişikliği kullanıcı yapar.

**Tarayıcıyla üst modele kod yazdırma.** Otomasyon sırası API > CLI > tarayıcı. Sohbet
arayüzü sürmek ToS ihlali, arayüz değişince sessizce bozulur, ve sayfa metni injection
yüzeyi açar. (Bu maddenin ilk hâli "doğrusu API çağıran bir `kod_yaz` aracı" diyordu;
`kod_yaz` da §14.1'de reddedildi. Kod yazdırmak gerekiyorsa `write_file` zaten keyfi
metin yazıyor; çalıştırmak ise hiçbir yoldan yok.)

**Sanal fare imleci animasyonu.** Playwright ARIA ile tıklıyor, koordinatla değil.
Animasyon olmuş bir olayın süslemesi ve yanlış bilgi verir. Arayüzdeki adım günlüğü
daha kesin bilgi veriyor.

**"Halüsinasyon riski" barı.** Token sayısı halüsinasyon riskini ölçmez. Doğrusu
**bağlam doluluk göstergesi** + maliyet sayacı.

**Klasör silme/taşıma.** `trash` ve `move` sadece dosyalarda çalışır. Tek onayla yüzlerce
dosyayı hareket ettirmek, onayın anlamını yok eder. `rename` klasörlerde çalışır (yerinde
kalır, içindekilere dokunmaz).

**`shell.run` (Faz 2d).** Yazıldı ama uygulanmadı — LibreOffice doğrudan dönüştürücünün
içinden çağrıldığı için genel bir komut çalıştırıcıya ihtiyaç kalmadı. Beyaz listeli
(`git`, `rg`, `ffmpeg`, `pandoc`) olarak tasarlanmıştı. **"Faz 6'da yeniden
değerlendirilir" satırı aşağıdaki §14.1 ile KAPANDI** — yeniden değerlendirildi ve
reddedildi, tekrar açılmıyor.

---

### 14.1 Kod çalıştırma — REDDEDİLDİ (Faz 7, kullanıcı kararı)

**Kapsam:** genel bir komut çalıştırıcı, `shell.run`, kabuk erişimi, model tarafından
üretilmiş kodun çalıştırılması, çalıştıran bir `kod_yaz`. Beyaz listeli bir komut
kümesi de dahil. Hiçbiri eklenmeyecek.

**Gerekçe — teknik.** Kapı "bu programı çalıştırabilir misin" diye bakabilir, "bu
program çalışınca ne yapacak" diye bakamaz. Bu ayrım bu projedeki her savunmanın
dayandığı varsayımı yıkar: dosya düzeyindeki korumaların TAMAMI — izinli kökler,
`realpath` sonrası kontrol, kara liste, onay kartı, `journal` yedeği, geri alma,
kalıcı silme yasağı, `korunan_yol_ihlali` — bir komut çalıştığı anda devre dışı kalır.
Çalışan süreç kapıya hiç uğramadan dosya yazar, siler, ağa çıkar. `gate.py`'nin
`EXEC` seviyesi tanımlı ama boş olması bir eksiklik değil, bilinçli bir durum.

**Gerekçe — gözetimsiz mod.** Faz 7'nin konusu kullanıcının olmadığı çalışmadır.
Orada `ASK`'in ne anlama geldiği ayrıca düşünülmemiş bir sorudur; bir profilin
`kod_yaz`'ı kapsaması, gözetimsiz bir görevin keyfi kod çalıştırmasına ÖNCEDEN onay
vermek olurdu. Mod/profilin "izin gevşetmez" ilkesine bugüne kadarki en ağır baskı.

**Gerekçe — kullanıcı.** Kullanıcı açıkça reddetti: "Herhangi bir yazılım kesinlikle
çalıştırmamalı."

**Bunun bir sonucu:** `kod_yaz` da yazılmıyor. Çalıştırmayan bir `kod_yaz`'ın
`write_file`'dan gerçek bir farkı yok (`write_file`'ın sözleşmesi zaten keyfi metin
yazıyor, kod dahil) — var olan bir deseni yeni bir isimle etiketlemek olurdu,
"yeni araç eklenmiyor" ilkesine aykırı sahte bir soyutlama. Ayrıntı: `DEVIR_FAZ7.md`
§5.2.

**Tekrar gündeme gelirse:** bu bir optimizasyon tartışması değil, bir kategori
değişimi — dosya yazma izninden YÜRÜTME iznine geçiş. Ayrı ve derinlemesine bir faz
kapısı gerektirir (sandbox mı, beyaz liste mi, EXEC'in gözetimsiz modda hiç
açılmaması mı), bir aşama içinde karara bağlanamaz.

### 14.2 Windows Görev Zamanlayıcı / kendiliğinden başlayan görevler — GEREKSİZ BULUNDU

**Reddedilmedi, gereksiz bulundu.** Aradaki fark önemli: güvenlik gerekçesiyle
kapatılmadı, ihtiyacın yanlış teşhis edildiği anlaşıldı.

Kullanıcının tarif ettiği senaryo şu: "Ona görev atadım, bilgisayarı açık bıraktım ve
gittim." Bu **zamanlanmış başlatma** değil, başlatılmış bir görevin **kendiliğinden
devam etmesi**. Zamanlayıcı yanlış eksende bir çözüm olurdu: tetiklenecek bir görev
zaten var, eksik olan onun bir tavana çarpınca durup beklemesi. Bunu çözen şey
`devam_karari` + kendiliğinden devam (Faz 7), bir zamanlayıcı değil.

Ayrıca zamanlayıcı yeni bir yüzey açardı ve hiçbiri bu ihtiyaç için gerekli değil:
kim tetikliyor, hangi profille, çıktıyı kim görüyor, kullanıcı makinenin başında
değilken çıkan onay isteğine ne oluyor.

**Tekrar gündeme gelirse:** gerçek bir ihtiyaç doğarsa (ör. "her sabah 7'de şu raporu
hazırla" — kullanıcının hiç başlatmadığı bir görev) ayrı bir faz kapısı olarak açılır.
O zaman da doğru çağrı Windows Görev Zamanlayıcı'nın `vekil_v0.py`'yi CLI üzerinden
tetiklemesidir; Limina'nın kendi iç zamanlayıcısı KURULMAZ (sürekli açık kalmayı
gerektirir, uyku/kapatma sessiz atlama demektir, ve kendi thread/hata sınıfını getirir).

---

## 15. Öğrenilen dersler

Bunlar test sırasında ortaya çıktı ve tekrar etmemesi için yazıldı:

1. **Araç yokluğu davranışı değiştirmez.** Silme aracı yokken model dosyayı `write_file`
   ile boşalttı. Riski düşüren bir araç vermek, aracı kaldırmaktan iyi.
2. **Geri alma aracının kendisi veri kaybettirebilir.** Bir geri alma başarılı oldu ama
   çıktı basılırken çöktü; dışarıdan bakan tekrarladı ve bir katman daha tüketti.
   Kural: dosya işlemi → günlük kaydı → çıktı. Çıktıdaki hata işlemin tekrarlanmasına
   yol açmamalı.
3. **Zaman damgası kimlik değildir.** Aynı saniyede yazılan üç dosya aynı damgayı aldı,
   biri geri alınınca üçü de "geri alınmış" sayıldı.
4. **Testin başarısızlığı modelin hatası olmayabilir.** İki eval, kötü assertion yüzünden
   kaldı; mekanizmalar doğru çalışıyordu.
5. **Model işbirlikçi olduğunda güvenlik testi yapılmaz.** DENY yolu, sistem talimatından
   izinli klasör listesi geçici olarak çıkarılana kadar hiç tetiklenemedi.
6. **Aynı klasörde iki ajan var, sadece birinde kapı kurulu.** Claude Code bir test
   dosyasını zararlı sanıp haber vermeden sildi.
7. **Testin geçmesi, doğru dosyanın test edildiği anlamına gelmez.** Faz 5a testleri
   bir süre `kum/` içindeki kopyalarla geçti; kökteki gerçek dosyalar eskiydi. Kimse
   fark etmedi çünkü çıktı yeşildi.
8. **İzlenmeyen dosya git'te iz bırakmaz.** Silinen beş dosya `git status`'ta
   görünmedi, çünkü hiç `git add` edilmemişlerdi. "Depo var" ile "yedek var" aynı
   şey değil.
