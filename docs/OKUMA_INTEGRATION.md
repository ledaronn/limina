# Okuma Atölyesi ve Pevrai

Okuma Atölyesi bağımsız Qt uygulaması olmaya devam eder. Asistan paneli kullanıcının seçtiği metni Pevrai'nın mevcut ajan döngüsüne gönderir; yanıt ve kaynak bilgisi okuyucuya geri gelir. Okuyucuya API anahtarı eklenmez.

## Kullanım

İki uygulamayı da yeniden başlatın. Okuyucunun üst şeridindeki iğne şeridi sabitler; **Asistan** düğmesi PDF'nin yanında panel açar. Metin seçince altta Açıkla, Özetle, Çevir ve Soru hazırla düğmeleri belirir. Aynı işlemler panelde de vardır. Seçim yoksa açık sayfanın en fazla 3000 karakterlik ilk parçası kullanılır; devamı varsa panel bunu belirtir. Metin yoksa mevcut OCR menüsünü kullanın.

Pevrai meşgulse istek bekler. Araç onaylarını ve çalışan isteğin durdurulmasını Pevrai'dan yönetin. Okuyucudaki iptal düğmesi yalnızca bekleyen isteği iptal eder. Yanıtın kaynağı istek anındaki belge/sayfadır; sonradan başka sayfaya geçmek kaynağı değiştirmez.

**Seçimi/yanıtı Smart Notes'a kaydet** doğrudan kullanıcı işlemidir; model çağırmaz. İsteğe bağlı proje seçimi notu Workspace'e bağlar. Bu eklentiler etkin olmalıdır. Sohbetteki kaynak bağlantısı veya not editöründeki **Kaynak sayfasını aç** ilgili PDF'yi açar.

## Araçlar

Bu çalışma alanının `policy.toml` dosyasına mevcut ayar yazıcısıyla aşağıdaki sınıflandırmalar eklendi. Başka kurulumlarda Araçlar panelinden etkinleştirin; okuyucu kendi başına izin değiştirmez.

| Araç | Risk | İşlev |
|---|---|---|
| `okuma.open_reader` | EXEC | Belge/sayfa açar, açık pencereyi kullanır. |
| `okuma.close_reader` | EXEC | Normal kapanış; `to_library=true` yalnızca kitaplığa döner. |
| `okuma.reader_request_status` | READ | İstek kimliğiyle pencerenin verdiği gerçek sonucu okur. |
| `okuma.read_page_chunk` | READ | Sayfa/karakter konumuyla kayıpsız devam; `next` sonraki konumu verir. |
| `okuma.get_outline` | READ | İçindekileri sayfalayarak getirir. |
| `okuma.get_reading_state` | READ | Son kaydedilmiş okuma konumunu getirir. |
| `okuma.ocr_pages` | WRITE | Mevcut yerel OCR; Tesseract ve dil verileri gerekir. |

Açma/kapatma altı saniye pencere yanıtını bekler. `status=done` tamamlanmayı, `pending` henüz doğrulanmadığını gösterir; bekleyen isteği durum aracıyla kontrol edin. Kaydedilmemiş not, modal pencere veya dosya işlemi varsa AI kontrolü hata döndürür; süreci zorla öldürmez. Komutlar 30 saniyede geçersizleşir. Normal kullanıcı kapanışında not editörü taslağı yerel okuyucu ayarlarında korunur.

`get_reader_context` sekiz saniyeden eski pencere bilgisini açık saymaz; kapanmış pencerenin seçimi boş döner. Uzun seçimde ilk 3000 karakter ve `selection_truncated` döner. Uzun belgeyi okumak için `read_page_chunk` kullanın; `read_pages` toplu okumada kesilebilir. Okuma sonuçlarındaki `source_url` yanıtın kaynak bağlantısıdır. Grafik/formülleri sayfa görüntüsü üzerinden yorumlama sonraki aşamadır.

## Yerel bağlantı ve veri

İstek/yanıt kuyruğu `%APPDATA%/OkumaAtolyesi/assistant.sqlite3` içinde tutulur (diğer sistemlerde `~/.config/OkumaAtolyesi/assistant.sqlite3`). `OKUMA_LINK_DB` testte geçici yol seçer. Kuyruk seçilmiş metin ve yanıt içerir; tamamlanmış kayıtlar yeni istek gönderilirken 30 gün sonra temizlenir. Bekleyen istek beş dakikada zaman aşımına uğrar. Kesilmiş çalışan istek otomatik tekrar yürütülmez.

Kaynak biçimi `okuma://<kütüphane-kimliği>/<belge-kimliği>/<sayfa>` şeklindedir. Bağlantı yalnızca yapılandırılmış okuyucunun sabit `app.py` dosyasını başlatır; kullanıcı verisinden program/komut yolu alınmaz. Kütüphane yolu mevcut okuma izinleriyle doğrulanır. PDF metni modele güvenilmeyen kaynak verisi olarak iletilir. Boş kuyruk model çağırmaz.

Pevrai tarafı `pevrai/okuma.py`, `pencere.py` ve kaynak bağlantısı arayüzüdür. Okuyucu tarafı `Araclar/OkumaAtolyesi/` içindedir; bu kişisel klasör zaten gitignore ile dışlanır. Okuyucu değişikliklerini ayrı paket olarak saklayın; Pevrai wheel dosyası okuyucuyu içermez.

## Doğrulama

```powershell
.venv\Scripts\python.exe tests/okuma_baglanti_testi.py
.venv\Scripts\python.exe tests/eklentiler_ui_testi.py
.venv\Scripts\python.exe tests/arayuz_testi.py
Araclar\OkumaAtolyesi\.venv\Scripts\python.exe -m pytest Araclar/OkumaAtolyesi/tests -q
```

Testler geçici PDF/veritabanları kullanır. Sağlayıcıya çağrı yapılmaz; model yanıtı kuyruk testinde taklit edilir. Gerçek stdio MCP ve Qt süreçleriyle açma/yönlendirme/kapatma ayrıca sınanır.
