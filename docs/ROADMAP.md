# Yol Haritası

Her faz **çalışan bir şey** bırakır. Bir faz, kabul kriterleri geçmeden bir sonrakine
geçilmez. Süreler tek geliştirici ve haftada birkaç akşam varsayımıyla verilmiştir.

---

## Faz 0 — Çekirdek döngü
**Süre:** 1 hafta sonu · **Hedef:** ajanın gerçekten "ajan" olduğunu kanıtlamak

**Çıktılar**
- `loop.py`: adım limitli ajan döngüsü
- `model.py`: tek sağlayıcı, araç çağırma desteği
- `registry.py`: fonksiyondan JSON şema üretimi
- 3 araç: `fs.list_dir`, `fs.read_file`, `shell.run`
- Ham CLI (`python -m vekil "..."`), renk yok, süs yok

**Kabul kriterleri**
- [ ] "Bu klasördeki en büyük 3 dosyayı bul" görevi 3 araç çağrısıyla tamamlanır
- [ ] Var olmayan bir yol verildiğinde model hatayı görüp yolu kendisi düzeltir
- [ ] Sonsuz döngüye giren bir görev adım limitinde temiz durur

**Kapsam dışı:** GUI, tarayıcı, hafıza, çoklu model, yazma işlemleri

---

## Faz 1 — Güvenlik ve gözlemlenebilirlik
**Süre:** ~1 hafta · **Hedef:** yazma yetkisini güvenle açmak

**Çıktılar**
- `gate.py` + `config/policy.toml`: risk seviyeleri, ALLOW/ASK/DENY
- Yol hapishanesi: izinli kökler, `..` ile dışarı çıkma engeli
- `journal.py`: JSONL günlük + geri alma kaydı
- Yazma araçları: `fs.write_file`, `fs.move`, `fs.trash` (silme değil, çöp kutusu)
- Çalışma dizini git altında; her oturum öncesi durum temiz mi kontrolü — **fiilen
  sağlanmamıştı.** Depo ve `.gitignore` vardı ama "durum temiz mi" kontrolü hiç
  rutine bağlanmadı: Faz 5a/5b'nin altı yeni dosyası haftalarca `git add` edilmeden
  kaldı, bu yüzden silindiklerinde `git status` iz bırakmadı (bkz. `DEVIR.md` §15).
  Bu oturumda iki commit'le (`38e921c`, `c453a77`) telafi edildi; kalıcı çözüm hâlâ
  yok — oturum başında "kirli çalışma dizini" uyarısı veren bir kontrol Faz 6'ya
  borç yazılmalı.

**Kabul kriterleri**
- [ ] Yeni eklenen bir araç, politikada tanımlı değilse çalışmaz (varsayılan reddet)
- [ ] `../../etc/passwd` benzeri bir yol kapıda reddedilir
- [ ] Onay reddedildiğinde ajan çökmez, alternatif dener veya durur
- [ ] Yanlışlıkla üzerine yazılan bir dosya günlükten geri alınabilir
- [x] Hiçbir `subprocess` çağrısı `shell=True` kullanmıyor (şu an hiç `subprocess` çağrısı yok, o yüzden geçmiş sayılır — Faz 2'de MCP sunucusu başlatılınca ilk gerçek `subprocess` çağrısı orada olacak, o zaman tekrar bakılmalı)

**Kapsam dışı:** tarayıcı, GUI

---

## Faz 2 — Araçları MCP'ye taşıma
**Süre:** ~1 hafta · **Hedef:** mimariyi eldeki gerçek bir araçla doğrulamak

**Çıktılar**
- Mevcut dosya dönüştürücü → `servers/converter` MCP sunucusu
- `mcp_bridge.py`: harici MCP sunucularını keşfedip araç kaydına ekler
- Dönüştürücünün eksiklerinin tamamlanması (format matrisi, hata mesajları)
- Araç yazım şablonu (yeni araç eklemek 20 dakikalık iş olmalı)

**Kabul kriterleri**
- [ ] Dönüştürücü hem Pevrai'dan hem Claude Desktop'tan çağrılabiliyor
- [ ] MCP sunucusu çöktüğünde ajan çökmüyor, hatayı metin olarak alıyor
- [ ] Yerel araç ile MCP aracı döngü açısından ayırt edilemiyor

---

## Faz 3 — Tarayıcı (bitti: 3a–3c)
**Süre:** ~1–2 hafta · **Hedef:** ajanı makine dışına çıkarmak

**3a — bitti:** Playwright `connect_over_cdp` ile mevcut Chrome oturumuna bağlanma,
`browser_open`/`browser_read`, sayfa içeriği `<untrusted_content>` ile işaretleniyor,
site beyaz listesi (`gate.py`'de `url_dogrula`), prompt injection testi geçti (tuzaklı
bir sayfadaki "önceki talimatları yoksay" yönergesi uygulanmadı). Bu adımdaki
`</untrusted_content>` kaçış açığı Faz 6'ya kadar fark edilmedi — bkz. SECURITY.md.

**3b — bitti:** `browser_click`/`browser_fill` erişilebilirlik ağacı (ARIA, `role`+`name`)
üzerinden çalışıyor, koordinatla değil. Parola alanı ve kart/TC kimlik kalıbı reddi kod
seviyesinde (`tarayici_testi.py`).

**3c — bitti:** `browser_download` — uzantı beyaz listesi + onay akışı (`DESTRUCTIVE`
risk). Ara klasöre iner, kalıcı yer değil (`tarayici_testi.py`).

**Çıktılar**
- Playwright, `connect_over_cdp` ile mevcut Chrome profiline bağlanır
- Araçlar: `browser_open`, `browser_read`, `browser_snapshot` (erişilebilirlik ağacı),
  `browser_click`, `browser_fill`, `browser_download`
- Sayfa içeriği modele **veri olarak işaretlenmiş** biçimde verilir
- Ödeme her zaman **DENY** (varsayılan, `gate.EYLEM_TABAN`), gönderim/paylaşım/silme
  her zaman ASK — orijinal plandaki "her zaman ASK"tan daha sıkı: ödeme onayla bile
  geçmiyor, bilinçli olarak açılması gerekiyor (bkz. SECURITY.md)

**Kabul kriterleri**
- [ ] Giriş gerektiren bir sayfadan veri çekilebiliyor (oturum profilden geliyor) —
  mimari destekliyor (`chrome-profil/`), ayrı bir eval/test ile doğrulanmadı
- [x] İçine "önceki talimatları unut" yazılmış bir test sayfası ajanı yönlendiremiyor
- [ ] Geri döndürülemez hiçbir tıklama onaysız yapılmıyor — `ODEME_KALIPLARI`/
  `GONDERIM_KALIPLARI` kapalı bir liste değil, bariz olanları yakalar (SECURITY.md'nin
  kendi ifadesiyle); mekanizma var ve test edilmiş ama "hiçbir" iddiasını kapatan
  kapalı bir taksonomi değil

**Kapsam dışı:** CAPTCHA çözme, kimlik doğrulama otomasyonu, kimlik bilgisi girme

**Not:** İndirilen dosya içerikleri de `<untrusted_content>` ile sarılacak — sayfa içeriğiyle
aynı muamele, dosya diskten geldiği için güvenilir sayılmamalı.

---

## Faz 4 — Kişiselleştirme (kapsamı daraltıldı: bitti)
**Süre:** ~1 hafta

**Çıktılar**
- [x] `config/persona.md` sistem talimatına eklenir

**Kabul kriterleri**
- [x] Ajan, söylenmeden tercih edilen biçimi/dili kullanıyor (test: dosya adını sen seçmesi
  istendiğinde, söylenmeden Türkçe karaktersiz + alt çizgili ad seçti — `persona.md`'deki
  kural uygulandı)

**Not:** Çalışma defteri, `notes.search` ve bağlam bütçesi yönetimi bu fazdan **çıkarıldı**,
Faz 6'ya taşındı. Sebep aşağıda ölçüm notunda.

**Not:** Vektör veritabanı bu fazda **eklenmez**. Ancak kelime aramanın yetmediği somut bir
örnek biriktiğinde gündeme alınır.

**Not:** Journal kayıtlarına zamandan bağımsız bir `id` alanı eklenecek. Zaman, kimlik olarak
kullanılmamalı — Faz 1'de mikrosaniye hassasiyeti bunu geçici olarak yamadı ama kalıcı çözüm
değil (bkz. Faz 1 kapanış notları: aynı saniyede birden fazla yazma olduğunda zaman damgası
çakışabiliyordu).

**Not:** Kişisel veri içeren belgeler için ayrı bir kara liste veya `hassas` etiketi. Model
bağlamına girmeden önce uyarı. Sebep: `read_document` ücretsiz katmanda çağrıldığında dosya
içeriği Google'a gidiyor (veri kullanım politikası ücretli katmandan farklı) — bir sağlık
raporunu okurken bu fark edildi.

**Not:** OCR. `belge.py` şu an taranmış (görüntü) PDF'lerde metin çıkaramıyor, bunu açıkça
söylüyor ama çözmüyor.

---

## Faz 5 — Arayüz (bitti: 5a–5d; yalnızca açık tema arayüzde "yakında" olarak duruyor)
**Süre:** ~1–2 hafta · **Tasarım detayı:** [ARAYUZ.md](ARAYUZ.md)

CustomTkinter/PyQt fikri terk edildi. Yerine: `pywebview` ile HTML/CSS/JS penceresi —
arayüz mantığı web teknolojileriyle yazılır, `pywebview` sadece pencereyi barındırır.

**5a — bitti:** Onay sağlayıcı parametresi (`calistir(..., oturum=)`), `Oturum`
nesnesi (toplu onay + durdurma bayrağı + olay yayıncısı), olay kuyruğu, ajan arka
plan thread'inde, onay senkron bekliyor. `kopru_testi.py` modelsiz doğruluyor.

**5b — bitti:** pywebview penceresi, markdown render, araç kartları, satır içi onay
kartı, renkli fark, logo durum göstergesi, bağlam barı, toplu onay çipleri.
Beş elle test geçti: `list_dir` ALLOW, `write_file` ASK + fark gösterimi, boşaltma
yıkıcı uyarısıyla reddedildi, `browser_open about:blank` DENY, durdurma temiz.

**Ancak aynı testte ayrı bir sorun ortaya çıktı:** onaylanan `write_file`, dosyanın
tamamını yeniden yazdığı için içeriği iki yerde sessizce bozdu (`kum/README.md`: bir
kelime anlamı değişti, bir cümlenin ortasına Arapça bir kelime sızdı). Arayüz
mekanizması doğru çalıştı — onay soruldu, fark gösterildi — ama 5933 baytlık bir
farkta bu iki satır gözden kaçtı. Bkz. aşağıda Faz 6 Notlar, "Kısmi düzenleme aracı
yeniden değerlendirilsin". Hata onay mekanizmasında değil, **onayın ölçeğinde**.

**5c — bitti:** Sohbet geçmişi (`sohbet.py`, `~/.vekil/sohbetler/`) + kenar çubuğu
(hover ile açılan, tık ile sabitlenen panel; `sohbet_testi.py` ve `kopru_testi.py`
kalıcılığı/bağlamı doğruluyor).

**5d — büyük ölçüde bitti:** Dosya yükleme (sürükle-bırak + "Dosya ekle"/"Görsel
ekle" seçici), slash komutları (`config/komutlar.toml`, kod değişmeden yeni komut
eklenir), model seçici (tıklanabilir öneriler), ayarlar paneli (`ayarlar.py`,
Faz 6'da tamamlandı — bkz. DEVIR_FAZ6 §1), maliyet/kota sayacı (`mod-kota` göstergesi,
`Api.kota()`). **Açık tema hariç** — arayüzde "Açık (yakında)" olarak duruyor, seçilemez.

**Çıktılar**
- `pywebview` penceresi, Claude benzeri düzen: sol tarafta görev girdisi ve sohbet akışı,
  araç çağrıları akış içinde satır arası kartlar olarak görünür (ayrı bir log paneli değil)
- [x] Satır içi onay kartları: hangi araç, hangi argüman, ne etkisi olacak — akışın içinde,
  görevin nerede durduğu belli, ayrı bir pencere/diyalog açılmaz
- [x] Slash komutları: `config/komutlar.toml`'dan okunan prompt şablonları + arayüz eylemleri
  (CLI'deki `--gecmis`/`--geri-al`/`--siteler` ile birebir eşleşmiyor, ayrı bir mekanizma —
  kod değil veri, yeni komut eklemek dosyaya blok yazmak kadar ucuz)
- [x] Bağlam doluluk göstergesi: mevcut token kullanımı / model penceresi (bkz. Faz 4/6 ölçüm
  kancası — `usage_metadata` zaten okunuyor, arayüze bağlanması yeter)
- [x] Dosya yükleme: sürükle-bırak (`surukle_destegi`) ve dosya seçici (`dosya_sec`,
  "Dosya ekle"/"Görsel ekle") ile görev girdisine dosya ekleme
- [x] Devam eden bir görevi durdurma düğmesi (kill switch)

**Kabul kriterleri**
- [ ] Kullanıcı, ajanın ne yaptığını arayüze bakarak anlıyor
- [x] Çalışan bir görev tek tıkla, veri bırakmadan durdurulabiliyor

**Not:** CLI'deki kill switch (`calistir()`'i saran `KeyboardInterrupt` yakalaması) kodda var
ve mantığı doğrudan simülasyonla doğrulandı, ama gerçek bir OS Ctrl-C bu geliştirme ortamında
(git-bash + otomatik süreç) güvenilir şekilde tetiklenemedi — gerçek terminalde elle test
edilmeli. GUI'nin durdurma düğmesi bunu farklı bir mekanizmayla (thread/process sonlandırma)
çözecek, bu sınır GUI'ye taşınmaz.

**Not:** Onay ekranında toplu onay (bkz. Faz 1'deki `TOPLU_ONAY` — CLI'ye özgü, GUI'ye taşınmalı).
**Not:** `/dev/tty` üzerinden onay — stdin başka bir amaçla kullanılıyorken (örn. boru hattı,
gözetimsiz çalıştırma) bile onay isteminin kullanıcıya ulaşabilmesi için.

**Not:** Onay alınamadığında varsayılan REDDET. Bu kural gözetimsiz modda da geçerli —
orada ASK gerektiren araç çalışmaz, kuyruğa yazılır. (CLI'de `input()`'un `EOFError`/
`KeyboardInterrupt` durumunda sessizce reddetmesi zaten Faz 3'te uygulandı; bu not aynı
ilkenin GUI/kuyruk tarafında da korunması gerektiğini işaretliyor — "onay yoksa izin ver"
gibi bir varsayılana asla kaymamalı.)

---

## Faz 6 — Güvenilirlik ve maliyet (bitti)
**Süre:** sürekli · **Detay:** `DEVIR_FAZ6.md`

**Bu fazda tamamlananlar** (ayrıntı ve gerekçeler `DEVIR_FAZ6.md`'de):
- Ayarlar paneli tamamlandı: model adları, günlük/döngü tavanları, klasör kökleri,
  hafıza aç/kapa, **ve efor modları** (`[modlar]`, aşağıya bkz.) — hepsi panelden,
  hepsi `gate.Politika` tek okuyucusundan geçiyor.
- **Efor modları** (`hizli`/`dengeli`/`derin`/`azami`) bitti: `policy.toml [modlar]`,
  `gate.Politika.mod_coz`, `vekil_v0.calistir(mod=...)`, ve panel tarafı
  (`ayarlar.mod_yaz`/`varsayilan_mod_yaz`, `pencere.Api.mod_yaz`/`varsayilan_mod_yaz`,
  arayüzde "Efor modları" bölümü). Mod izin gevşetmez, yalnızca model + adım/çağrı
  tavanı seçer (bkz. ARCHITECTURE.md §1). Mod ADLARI panelden kapalı — yeni mod
  eklenemez, yalnızca var olan dördünün üç alanı (`model`/`adim`/`cagri`) ve
  `varsayilan_mod` düzenlenir (`ayarlar_testi.py` bölüm 25).
- Günlük istek tavanı rol bazında (`varsayilan`/`guclu`), gerçek bir duvar — tavana
  çarpınca görev ortasında kesiliyor, 429'dan ayırt edilebilir bir mesajla.
- MCP çıktısı `mcp_bridge.dis_kaynak` ile kırpılıp `<untrusted_content>`'e sarılıyor;
  yalnızca `policy.toml [araclar]`'da sınıflandırılmış MCP araçları modele gösteriliyor.
- **Okuma Atölyesi** (bağımsız bir PDF kütüphanesi paketi) MCP sunucusu olarak
  bağlandı — 17 araçtan 4'ü (hepsi READ) sınıflandırıldı, uçtan uca doğrulandı.
- `tarayici.oku`/`anlik_goruntu`'nun `</untrusted_content>` kaçış açığı kapatıldı
  (Faz 3a'dan beri vardı, `tuzak.html`'deki test kalıbı da bu yüzden hiç yakalamıyordu).
- `list_dir` artık kara listedeki dosyaların adını/boyutunu sızdırmıyor (aşağıdaki not
  çözüldü).
- Eval seti tool-trace'e bakacak şekilde güçlendirildi (`gerekli_araclar`/`yasak_araclar`,
  `ARAC_CAGRILDI` olayına bakıyor) — nihai metin eşleşmesine bağlı zar atan assertion'lar
  kaldırıldı (aşağıdaki not çözüldü).

**Çıktılar**
- [x] `evals/tasks.yaml`: regresyon seti — 23 test (12 kapı + 5 kod + 1 MCP şema + 5 ajan),
  hedef aralık (20–30) içinde
- [ ] İki katmanlı **otomatik** model yönlendirme (basit görev → küçük model). Efor
  modlarının kendisi bitti ama seçim hâlâ kullanıcıda — göreve bakıp otomatik model
  seçen bir yönlendirici yok (DEVIR_FAZ6 §7.1'de "dinamik" olarak ayrılmış, ayrı ve
  daha zor bir problem)
- [ ] Prompt ve araç açıklamalarının eval sonuçlarına göre iyileştirilmesi — sürekli iş
- [x] Görev başına maliyet ve başarı oranı raporu — `evals.py --hepsi` her görev için
  süre + girdi/çıktı token basıyor, `DEVIR_FAZ6.md` §6'da beş ayrı koşunun karşılaştırması var

**Kabul kriterleri**
- [x] Prompt değişikliğinin işleri bozup bozmadığı ölçülebiliyor (`evals.py --hepsi`)
- [x] Görev başına ortalama maliyet biliniyor (bkz. DEVIR_FAZ6 §6)

**Notlar (biriken, henüz işlenmedi)**
- **`tikla`/`doldur`/`indir` oturum kopmasında yeniden denemiyor.** `ac`/`oku`/
  `anlik_goruntu` `_yurut` deseniyle bir kez yeniden bağlanıp tekrar dener,
  diğer üçü denemez (gerekçe kod yorumunda: öğe arama sayfaya bağlı). Ölçüldü
  (`DEVIR_FAZ7.md` §9, M4): bu **sık tetiklenen** bir sorun değil — 40 tıklamada
  sıfır başarısızlık — yani aciliyeti yok, ama oturumun koptuğu tek bir an bir
  tıklamayı kurtarılamaz biçimde düşürüyor.
- ~~**`_oge(exact=False)` alt dize eşlemesi asıl kırılganlık.**~~ **ÇÖZÜLDÜ.**
  Belirsiz eşleşmede araç tıklamıyor (zaten tıklamıyordu) ve artık adayların
  **tam adlarını** numaralı listeliyor; ikinci çağrıda tam ad önce `exact=True`
  ile denenir. Canlı: Wikipedia'da "Bitki" → 17 aday listelendi, tıklanmadı;
  "Bitkilerde" ile ikinci çağrı doğru sayfaya gitti. `tarayici_testi.py` test 11.
- **Tarayıcıya dayanan uzun görevlerde sayfa içi durum saklanmıyor.** Durum
  dosyası görevin *metinsel* ilerlemesini taşıyor; form yarısı / sihirbaz adımı
  / sepet gibi sayfa içi durum hiçbir yerde yok. Böyle görevler her devam
  turunda akışın başından kurulabilir olacak biçimde tasarlanmalı.
- Google Interactions API'ye geçiş değerlendirilecek.
- Model tek turda gereksiz araç çağrısı yapıyor — prompt iyileştirmesi gerekiyor.
- Yönlendirme kriteri kullanıcının mod seçmesinden çıkarılacak (görev karmaşıklığına göre
  otomatik model seçimi hedefleniyor; `--guclu` bayrağı zaten `mod` string'ine terfi etti —
  bkz. yukarıdaki "efor modları" notu — ama seçim hâlâ elle, otomatik değil).
- Eval: "silme aracı yokken model ne yapıyor?"
- Eval: "geri alma iki kez çalıştırılırsa ne olur?" (Faz 1'de bu senaryo gerçek bir veri kaybına
  yol açmıştı — bkz. journal.py'nin kendi kendini yedekleme düzeltmesi.)
- Kural: yan etkili her araçta sıra sabit olmalı — dosya işlemi → günlük kaydı → çıktı. Çıktı
  katmanındaki bir hata (örn. konsol encoding çökmesi), işlemin tekrarlanmasına yol açmamalı.
- Model hata sonrası görev sınırı dışında arama yapıyor (eval'de görüldü: bir eksik/yanlış
  klasör adı verildiğinde model beklenen "bulunamadı" hatasını almadan, kendi başına doğru
  klasörü tahmin edip devam etti — sağlam davranış ama eval'in varsaydığı senaryoyu bozdu).
- MCP stderr yakalama. `mcp_bridge.py`'deki `_sebep()` istisna zincirini doğru kazıyor ama
  alt sürecin stderr'i hiçbir istisnada taşınmıyor — `mcp`'nin düşük seviye `stdio_client`
  taşıyıcısı bir `errlog` parametresi kabul ediyor, `Client` sarmalayıcısı bunu dışarı açmıyor.
  Gerçek kök sebebi ("dosya bulunamadı" gibi) yakalamak için düşük seviye taşıyıcıya geçmek
  gerekir.
- ~~Eval setini genişletme — şu an 11 kapı + 5 ajan görevi var, hedef 20-30.~~ **ÇÖZÜLDÜ.**
  23 test (12 kapı + 5 kod + 1 MCP şema + 5 ajan), hedef aralıkta.
- ~~Bazı ajan eval'leri metin eşleşmesiyle çalışıyor~~ **ÇÖZÜLDÜ** (aynı ailenin son vakası:
  "prompt injection direnci" `bekleniyor_metinde: ["trigonometri"]` kullanıyordu — modelin
  sayfayı hangi sözcükle özetlediğini ölçüyordu, enjeksiyon direncini değil, üç koşudan
  birinde zar attı. `gerekli_araclar`/`yasak_araclar`'a çevrildi, `ARAC_CAGRILDI` olayına
  bakıyor artık. Aşağıdaki "Eval assertion'ları artık olay akışına bakabilir" notunun
  fiilen uygulanmış hali.
- **Markdown ayrıştırıcısının projede regresyon testi yok.** `arayuz/index.html`
  içindeki markdown→DOM çevirici geliştirme sırasında Node + jsdom ile 30 testle
  doğrulandı (blok öğeleri, tablo, kod bloğu, HTML enjeksiyonu, bozuk girdi), ama
  o test projeye konmadı: çalışması Node gerektiriyor ve `ARAYUZ.md` §9'daki
  "build adımı yok" kararını bozardı. Ayrıştırıcı değiştirilirse elle doğrulanmalı.
  Faz 6'da karar: ya testi Node bağımlılığıyla kabul et, ya ayrıştırıcıyı Python'a
  taşıyıp oradan test et.
- ~~**`list_dir` kara listedeki dosyaların varlığını sızdırıyor.**~~ **ÇÖZÜLDÜ.**
  `list_dir` artık `POLITIKA._yasakli_mi` ile filtreliyor, kaç dosyanın gizlendiğini
  söylüyor (gizlemek yerine söylemek).
- ~~**Eval assertion'ları artık olay akışına bakabilir.**~~ **ÇÖZÜLDÜ** —
  `ARAC_CAGRILDI` olayı `evals.py`'nin `ajan_testleri`'nde toplanıyor,
  `yasak_araclar`/`gerekli_araclar` assertion'ları buna bakıyor (bkz. yukarıdaki
  "prompt injection direnci" notu). `arac_sonuc_icerir`/`ARAC_SONUCU` toplama
  kodu kullanılmadığı için kaldırıldı (bkz. DEVIR_FAZ6 §4).
- **Kısmi düzenleme aracı yeniden değerlendirilsin.** Ölçüm: `kum/README.md`
  dosyasının en üstüne tek satır eklemek için model dosyanın tamamını yeniden yazdı
  — 1617 çıktı token, 5933 bayt. `write_file` kısmi düzenleme yapmadığı için her
  küçük değişiklik dosyanın tamamının yeniden üretilmesini gerektiriyor. Bu hem
  maliyetli hem riskli: model yeniden yazarken içeriği bozabilir ve yıkıcı-yazma
  tespiti ancak %80'den fazla küçülmede tetikleniyor, sessiz bozulmayı yakalamıyor.
  Bu risk teorik değil, gerçekleşti — bkz. yukarıda Faz 5b notu ve `SECURITY.md`
  tehdit tablosu. `edit_file` (satır aralığı veya birebir metin değiştirme)
  tasarlanıp risk seviyesi ve geri alma davranışıyla birlikte değerlendirilmeli.

- **Araç şemalarının göreve göre koşullu yüklenmesi.** *(Faz 7 Aşama 5 bunun ilk
  adımını attı: profiller artık araç listesini daraltıyor ve boş liste saf sohbet
  demek. Kalan kısım — göreve BAKIP otomatik daraltma — hâlâ açık.)* Ölçüm: modele
  her çağrıda 21 araç şeması gidiyor; yalnızca Okuma Atölyesi'nin 4 aracı çağrı başına
  **+494 token** ekliyor (`DEVIR_FAZ6.md` §6) — PDF ile hiç ilgisi olmayan
  görevlerde bile. Karşılaştırma için: oturumu ikiye bölmenin kazancı temsil edilen
  ölçekte gürültü payındaydı (`DEVIR_FAZ7.md` §8). Yani gerçek maliyet kolu bölme
  değil şema; ilgisiz şemaları o görevin `tools=[...]` listesine hiç sokmamak çağrı
  başına yüzlerce token kazandırır. Ayrı bir maliyet çalışmasının konusu, Faz 7'nin
  değil. (MCP filtresinin deseni — "gösterilecek küme görev başında hesaplanır" —
  burada da geçerli.)

**Not (ölçüm sonucu, Faz 4'ten taşındı):** "Downloads'taki tüm PDF'leri oku ve özetle" görevi
ile ölçüldü — çalışma defteri ve bağlam özetleme **şimdilik ertelendi**, gerçek bir sorunu
henüz çözmüyorlar. Zirve bağlam 4601 token (yüz binlik pencerenin binde biri), dikkat kaybı
yok (ilk okunan belge son özette doğru hatırlandı). Ama ölçüm başka bir şey ortaya çıkardı:
Gemini bir turda **paralel** araç çağırabiliyor (6 `read_document` tek turda) — yani "adım"
(model turu) araç çağrısı sayısını ciddi şekilde eksik gösteriyor; `MAX_STEPS=8` aslında
40+ araç çağrısına izin veriyordu. Bunun somut riski: `MAX_CALLS=20` toplamı sınırlasa da
tek turda 19 `move`/`trash` çağrısını "tümü" ile tek onayda geçirmek mümkündü. Karşılık
olarak `TUR_TAVANI` eklendi (risk seviyesine göre tur başına çağrı tavanı: WRITE 5,
DESTRUCTIVE 2, NETWORK/EXEC 3, READ 12) — aşılırsa iş bir sonraki tura bölünüyor, kullanıcı
her partiyi ayrı görüyor. `notes.search` ise zaten `search` aracının yaptığı işin alt
kümesi olduğu için ayrıca eklenmedi.

---

## Faz 7 — Gözetimsiz görevler (bitti)
**Süre:** iki iş emri · **Detay:** `DEVIR_FAZ7.md` · **Hedef:** "görev verdim,
bilgisayarı açık bıraktım, gittim" — ajanın kullanıcı yokken bir tavana çarpıp
sessizce durmak yerine güvenle sürebilmesi, ve döndüğünde tek yerden hesap
verebilmesi

**Çıktılar (gerçekleşen)**
- [x] **Görev profilleri** — `policy.toml [profiller.<ad>]`, `--profil <ad>`.
  Kullanıcının önceden kaydedilmiş onayı: DENY dokunulmaz, `ASK` yalnızca
  profilin kapsamı (araç + yazma kökü) içinde `ALLOW` olur, kapsam yükleme
  zamanında fail-closed doğrulanır ve etkileşimli oturumdan asla geniş olamaz.
  Mod = bütçe, profil = önceden onay + kapsam; birleştirilmedi. `araclar`
  alanı modele gösterilen listeyi de daraltır (boş liste = araç yok).
- [x] **Durum dosyası + kendiliğinden devam** — bir tavana çarpma bir metin değil
  bir durum: `gate.durum_karari` "durum_yaz" derse `~/.vekil/durum/<kimlik>.md`
  yazılır (ajanın yazamadığı yer). Profil etkinse `gate.devam_karari` ile
  kendiliğinden devam: kota > sınır > ilerleme öncelik sırasıyla durur; ilerleme
  ölçütü `journal.gorev_kayitlari`, modelin özeti **değil**. `azami_devam`
  tanımsız = kapalı. Her tur yeni kimlik + `onceki_kimlik` zinciri. Elle sürdürme
  `--devam <kimlik>`.
- [x] **Görev başına istek bütçesi** — `[modlar.<ad>].istek` (8/14/20/32),
  `gate.butce_karari`. Adım tavanı turları sayar, bütçe gönderilen istekleri
  (yeniden denemeler dahil). `durum_karari`'ya üçüncü parametre — üç sınır, tek
  karar, tek çıkış. Günlük tavan hâlâ en dış sınır.
- [x] **Dönüş özeti** — `~/.vekil/ozet/<kimlik>.md`, arayüzde tek kart. Model
  çağrısı **yok**: olgular döngünün sayaçlarından, `journal`'dan ve kota
  sayacından. Kota tam dolu hâlde bile üretilir. Modelin `kalanlar`'ı
  DOĞRULANMAMIŞ etiketiyle, alıntı olarak.
- [x] **Sohbet modu** — yeni kavram değil, araç listesi boş bir profil
  (`[profiller.sohbet]`). Arayüzde sohbet/görev anahtarı. Ölçüldü: girdi token
  3934 → 442 (%89 az); kapı hiç çağrılmıyor, `journal` boş; persona'nın kök/araç
  anan bölümleri araçsız turda düşer.
- [x] **Düşmanca test paketi** — `dusmanca_testi.py`, 7 bölüm, 166+ iddia,
  modelsiz. Yeni yetenek eklenmeden ÖNCE yazıldı ve üç gerçek açık buldu:
  sondaki nokta/boşluk ad tuzağı (`gate.windows_ad_tuzagi`), toplu onay
  yasağının ada bağlı olması, reddedilen kimlik bilgisinin olay akışında
  taşınması. Üçü de kapatıldı.
- [x] **Tarayıcı dayanıklılığı ölçümü** (kod değil) — 40 adımda sıfır hata;
  kendiliğinden devamda oturum kaybolmuyor; `--devam` yeni süreç CDP ile aynı
  Chrome'a bağlanıyor; Chrome kapanırsa 5 sn'de kurtarıyor, çerez korunuyor,
  **açık sekme listesi kayboluyor**. Belirsiz tıklama artık aday listesi dönüyor.

**Kapsamdan ÇIKARILANLAR — ekleme kadar açık, gerekçesiyle**

Bu fazın ilk taslağı dört çıktı vaat ediyordu: profiller, `kod_yaz`, sabah
raporu, profil bazlı test ayarı. Bunlardan **ikisi gelmeyecek**, biri yerini
başka bir şeye bıraktı:

- **`kod_yaz` — REDDEDİLDİ** (`DEVIR.md` §14.1, `DEVIR_FAZ7.md` §5.2). Yazma-only
  bir sürüm `write_file`'dan farksız (o zaten keyfi metin yazıyor, kod dahil);
  var olan bir deseni yeni bir isimle etiketlemek "yeni araç eklenmiyor"
  ilkesine aykırı sahte bir soyutlama olurdu. Çalıştıran bir sürüm projenin ilk
  EXEC aracı olur ve kullanıcı bunu açıkça reddetti: kapı "bu programı
  çalıştırabilir misin" diye bakabilir, "çalışınca ne yapacak" diye bakamaz;
  dosya düzeyindeki bütün korumalar bir komut çalıştığı anda devre dışı kalır.
- **Sabah raporu — ANLAMINI YİTİRDİ, yerine görev başına dönüş özeti geldi.**
  Sabah raporu "gece kendiliğinden başlayan görevlerin özeti" demekti; zamanlanmış
  başlatma **gereksiz bulunduğu** için (`DEVIR.md` §14.2 — ihtiyaç başlatılmış
  bir görevin kendiliğinden *devam* etmesiydi, kullanıcının hiç başlatmadığı bir
  görev değil) toplanacak "gece" kalmadı. Kalan ihtiyaç — "kullanıcı döndüğünde
  tek yerden ne oldu" — her görevin bitişinde bırakılan dönüş özetiyle
  karşılandı. Gelecekte zamanlanmış başlatma açılırsa, sabah raporu o özet
  dosyalarını süzen bir okuma işi olur; ayrı bir mekanizma değil.
- **Windows Görev Zamanlayıcı / kendiliğinden başlayan görevler — GEREKSİZ
  BULUNDU** (`DEVIR.md` §14.2). Reddedilmedi; ihtiyaç doğarsa ayrı bir faz kapısı.
- **Profil bazlı test etme/etmeme ayarı — SESSİZCE DÜŞTÜ, burada kayda geçiyor.**
  Taslakta ne anlama geldiği hiç netleşmemişti; profiller ve `evals/tasks.yaml`'ın
  `profil:` alanı geldiğinde ayrı bir ayara ihtiyaç kalmadı (eval görevi profilini
  kendisi belirtiyor).

**Kabul kriterleri**
- [x] Bir tavana çarpan görev sessizce yarım kalmıyor; nerede kaldığı ajanın
  erişemediği bir dosyada duruyor ve oradan sürdürülebiliyor
- [x] Profille çalışan bir görev, kapsamı içindeki `ASK`'i sormadan geçiyor;
  kapsamı dışında ve her DENY'de duruyor (`evals/tasks.yaml`, araç izine bakıyor)
- [x] Gözetimsiz bir görev, kullanıcı yokken kendiliğinden devam edip bitiyor ya da
  neden durduğunu söyleyen bir özet bırakıyor
- [x] Kullanıcı döndüğünde tek bir yere bakarak ne bittiğini, neye çarpıldığını ve
  ne harcandığını görebiliyor

**Not:** tetikleyen hâlâ bir insandır (`--profil` ya da arayüz). Bu bir eksik
değil, §14.2'deki kararın sonucu: "görev verdim, gittim" senaryosu başlatmayı
değil devamı gerektiriyordu.

---

## Faz 8 — Mesajlaşma entegrasyonu
**Süre:** belirlenmedi

**Çıktılar (taslak, henüz işlenmedi)**
- Resmi API'si olan platformlarla entegrasyon (ör. Telegram Bot API, e-posta)

**Kapsam dışı:** WhatsApp Web otomasyonu — resmi API yok, tarayıcı otomasyonuyla taklit
etmek hesabın askıya alınma riskini taşır.

**Kabul kriterleri:** henüz tanımlanmadı

---

## Bilinen riskler

| Risk | Etki | Karşılık |
|---|---|---|
| Prompt injection (web/dosya içeriğinden) | Yüksek | İzin kapısı, veri/talimat ayrımı, ASK varsayılanı |
| Uzun zincirde birikimli hata | Yüksek | Adım limiti, denetimli mod, eval seti |
| `pyautogui` kırılganlığı | Orta | Son çare olarak konumlandırıldı |
| Kapsam kayması ("her şeyi yapsın") | Yüksek | Faz kapıları, "Ne değildir" bölümü |
| Model/API fiyat veya davranış değişikliği | Orta | `pevrai/model/` sağlayıcı katmanı (Gemini / OpenAI-uyumlu / Anthropic) + `mod` katmanı; sağlayıcı ve model adı `policy.toml [model]`'den değişir, kod dokunulmaz (bkz. ARCHITECTURE.md §2) |

## Şu an ne yapmalı

Faz 6 ve Faz 7 kapandı. Gözetimsizlik var: profille başlatılan bir görev tavana
çarpınca durmuyor, durumunu ajanın erişemediği bir dosyaya yazıp kendiliğinden
devam ediyor, ilerlemediğini `journal`'dan anlayıp duruyor, bittiğinde model
çağırmadan bir dönüş özeti bırakıyor. Tetikleyen hâlâ bir insan ve bu bilinçli
(`DEVIR.md` §14.2).

Sıradaki gerçek faz kapısı Faz 8 (mesajlaşma) — ama ona başlamadan önce üç şey
kendi hızında konuşulmalı, hiçbiri acele bir karar değil:

1. **Araç şemalarının göreve göre koşullu yüklenmesi.** Faz 7 ilk adımı attı
   (profil araç listesini daraltıyor; sohbet modunda 3934 → 442 token). Kalan
   kısım göreve *bakıp* otomatik daraltma — ayrı bir maliyet çalışması.
2. **Zamanlanmış başlatma** gerçekten gerekirse: Windows Görev Zamanlayıcı
   `vekil_v0.py --profil <ad>`'ı tetikler, Pevrai içi zamanlayıcı kurulmaz; o
   zaman "sabah raporu" özet dosyalarını süzen bir okuma işi olur.
3. **Modele giden metnin dili — bitti.** Sistem talimatı, araç bildirimleri,
   `durum_yaz` ve araç çıktıları `config/arayuz.toml [genel] dil` ayarını izliyor
   (`pevrai/ceviri.py`); canlı doğrulama `gemini-3.5-flash-lite` ile yapıldı.
   Eklenti araçları (`pevrai/eklentiler`, 56 araç / 95 açıklama) da aynı
   sözlükten çevriliyor. Kalan: `evals.py` İngilizce modda da koşulmalı (şu an
   kaynak dile sabit).
4. **Görüntü okuma — bitti (2026-09-20).** `read_document` artık PNG/JPG/ekran
   görüntüsünü ve metin katmanı olmayan PDF sayfalarını Windows'un yerleşik
   OCR'ından geçiriyor (`pevrai/ocr.py`, `[ocr]` ekstrası; model indirmez, dil
   paketi Windows'tan). Sayfa başına karar: karışık belgede yalnızca taranmış
   sayfa OCR'lanır, `[OCR]` etiketlenir, başa "hatalı karakter olabilir" uyarısı
   girer. Tavanlar: çağrı başına 20 sayfa, 4000 px kenar. Windows dışında ya da
   dil paketi yokken araç yine çalışır ve nedenini söyler. Ölçüldü: 1920×1080
   ekran görüntüsü 0.4 sn, 38 satır.
5. **Faz 7'nin açık bıraktığı iki sınır:** modelin konuşma geçmişi sohbet
   dosyasında maskelenmiyor (`SECURITY.md`), ve tarayıcı görevlerinde sayfa içi
   durum saklanmıyor (form yarısı, sihirbaz adımı) — böyle görevler her devam
   turunda akışın başından kurulabilir olmalı.

Faz 6'dan devreden notlar (otomatik model yönlendirme, kısmi düzenleme aracı,
markdown ayrıştırıcı testi, MCP stderr yakalama, `_model_cagir`'in saf karar kısmının
ayrılması) sürekli iş listesinde kalıyor; bir fazı kapatmayı engellemiyorlar.
