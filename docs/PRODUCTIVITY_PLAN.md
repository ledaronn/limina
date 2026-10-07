# Study & Focus, Smart Notes ve Workspace uygulama planı

Durum: Kullanıcı planı onayladı. Uygulama ve doğrulama ayrıntıları [PRODUCTIVITY.md](PRODUCTIVITY.md) belgesinde.

## Mevcut mimaride doğrulanan noktalar

- Python masaüstü uygulaması; pywebview arayüzü `pevrai/arayuz/index.html`, Python API'si `pevrai/pencere.py` içinde.
- Yerel araçlar `pevrai/vekil_v0.py` içindeki `ARAC_TABLOSU` ve JSON şemalarıyla sunuluyor. MCP araçları `pevrai/mcp_bridge.py` üzerinden aynı araç döngüsüne katılıyor.
- `pevrai/gate.py` araç sınıflandırmasını, izinleri, dosya köklerini ve profil sınırlarını denetliyor. Tanımsız araçlar reddediliyor.
- `pevrai/paketler.py` ve `pevrai/ayarlar.py` paketleri kaldırma/geri ekleme ve araç görünürlüğünü yönetiyor.
- Kalıcı uygulama verileri için mevcut yaklaşım kullanıcı dizinindeki `.vekil` klasörü; dosya değişiklikleri `journal.py` ile kaydediliyor. İncelenen uygulama kodunda SQLite tabanlı eklenti deposu yok.
- Çalışma ağacında model, arayüz, politika ve test değişiklikleri mevcut. Bunlar korunacak. `pevrai/model/` ve sağlayıcıdan bağımsız araç şemaları mevcut olduğundan belgelerdeki eski tek sağlayıcı anlatımı tasarım temeli alınmayacak.
- Paketleme şu anda yalnızca `pevrai` paketini açıkça listeliyor. Yeni alt paketler ve arayüz varlıkları dağıtıma dahil edilecek.

## Önerilen yapı ve sınırlar

Üç özellik `pevrai/eklentiler/study`, `pevrai/eklentiler/notes` ve `pevrai/eklentiler/workspace` altında ayrı modüller olacak. Her birinin veri/migration, servis, araç şeması ve UI katmanı ayrılacak. Küçük bir ortak yükleyici, mevcut yerel araç tablosuna ve paket yönetimine bağlanacak; yeni model veya sohbet sistemi kurulmayacak.

Her eklenti bağımsız etkinleştirilebilecek ve yüklenebilecek. Modül bulunmadığında veya devre dışıyken araçları sunulmayacak, paneli erişilebilir görünmeyecek ve ana asistan çalışacak. Kurulum/kaldırma kullanıcı verisini silmeyecek. Paket varlığını belirlemek için eklenti iş mantığını koşulsuz içe aktarmak gerekmeyecek.

Varsayılan veri konumu `Path.home() / '.vekil' / 'eklentiler'` olacak; testler geçici dizin kullanacak. Her eklenti kendi sürümlü SQLite veritabanını yönetecek. Eklentiler arası ilişkiler tür + ID referansları olacak; veritabanları arasında zorunlu foreign key veya import bağımlılığı kurulmayacak. Eksik/devre dışı eklenti referansları kullanıcıya açıkça bildirilecek.

AI çağrıları mevcut izin kapısından geçecek. UI temel işlemleri model çağırmadan aynı servis/doğrulama katmanından yapacak. Dosya erişiminde UI dahil mevcut yol ve izin denetimleri korunacak; workspace ilişkisi bir dosyaya erişim yetkisi vermeyecek. Veri değişikliklerinin kaynağı, zamanı ve nesne kimliği izlenebilir olacak; not sürümleri geri alınabilecek.

## Uygulama aşamaları

1. **Study & Focus çekirdeği.** Ders, sınav ve konu CRUD; çalışma kayıtları, günlük/haftalık istatistikler ve tarih bazlı planlar. Plan güncellemeleri geçmiş çalışma kayıtlarından ayrılacak. UTC zaman damgalarıyla kalıcı Pomodoro/serbest odak motoru; duraklatma, devam ve bitirme. Mola süreleri çalışma süresine eklenmeyecek; tamamlanma kaydı tekrar çağrıda çoğalmayacak. Her adım geçici veritabanıyla test edilecek.
2. **Study & Focus araçları ve arayüzü.** Küçük ve açık JSON şemaları, tür/aralık/ilişki doğrulaması ve anlamlı hatalar. Ders/konu düzenleme, sınav oluşturma, yaklaşan sınavlar, bugünün planı, geçmiş ve istatistikler; büyük sayaç ve Pomodoro ayarları. Sayaç görüntüsü kalıcı durumdan hesaplanacak, sohbetin açık kalmasına bağlı olmayacak.
3. **Smart Notes.** Başlık, gövde, etiketler, zamanlar; oluşturma/okuma/güncelleme, arşiv ve geri alınabilir silme. Tam metin arama, not bağlantıları ve ders/sınav/workspace referansları. Sürüm geçmişi ve eski sürümü geri yükleme; AI ile UI eşzamanlı düzenlemelerinde sessiz veri kaybını önleyen sürüm kontrolü. Liste, arama ve basit editör paneli. Temel kullanım embedding veya API gerektirmeyecek.
4. **Workspace.** Proje adı/açıklaması, amaç/talimatlar, dosya/klasör referansları, notlar, görevler, çalışma günlüğü, çıktılar ve sonraki adımlar. Dosya içerikleri veritabanına kopyalanmayacak; proje köküne göre göreli referanslar ve Windows yol doğrulaması kullanılacak. Dosya okumak/yazmak mevcut araçlardan yapılacak. Devam bağlamı sınırlandırılmış özet ve isteğe bağlı ayrıntı sorgularıyla sağlanacak; tüm geçmiş otomatik olarak modele gönderilmeyecek. Proje ve görev yönetim paneli eklenecek.
5. **Birlikte çalışma ve dağıtım.** Workspace–ders/sınav, not–proje ve odak–görev ilişkileri. Eksik eklenti, bozuk referans ve devre dışı paket davranışları. Araç kurulum/sınıflandırma, paketleme ve UI varlıklarının dağıtımı. README ve geliştirici belgelerine kurulum, araç listesi ve örnek kullanım eklenecek.

## Kabul ve regresyon doğrulaması

- Aynı sınavı UI üzerinden oluşturup araç üzerinden okumak ve tersini yapmak.
- Saat ilerletilen testlerde kapanıp açılma, duraklatma, mola geçişleri ve tekrar bitirme; gerçek çalışma süresinin istatistiklerde yalnızca bir kez görünmesi.
- Plan güncellemelerinin geçmiş çalışma kayıtlarını değiştirmemesi.
- Not oluşturma, tam metin arama, güncelleme, sürüm geri alma ve eşzamanlı güncelleme çakışması.
- Workspace dosya/not/görev ilişkileri ve yeni oturumda devam bağlamının okunması.
- Kök dışı yollar, Windows yol tuzakları, izin değişikliği sonrası dosya erişimi ve güvenilmeyen metnin UI'da güvenli gösterimi.
- Eklentilerin tek tek eksik veya kapalı olması halinde ana uygulamanın çalışması; kapalı araçların modele sunulmaması ve çağrılarının reddedilmesi.
- Şema migration'ları, hatalı girdiler, işlem geri alma ve kalıcı değişikliklerin izlenebilirliği.
- Mevcut izin, köprü, model ve arayüz regresyon testleri; kurulan dağıtımda alt paketlerin ve UI dosyalarının bulunması.
- Temel akışlar model çağrısı yapmadan sınanacak. Canlı model testi yapılırsa sonuç ayrıca belirtilecek; yapılmayan görsel/canlı doğrulamalar yapılmış sayılmayacak.

## İlk sürüm varsayımları

- Mevcut tek kullanıcı/yerel masaüstü çalışma biçimi korunacak; sunucu veya hesap gerekmeyecek.
- Zamanlar UTC saklanacak; kullanıcıya yerel saatle gösterilecek. Saat dilimi olmayan sınav girişlerinin hangi yerel saati ifade ettiği UI'da belirtilecek.
- Uygulama kapalıyken otomatik ilerleyen Pomodoro döngüsü zaman damgalarından yeniden hesaplanacak; kullanıcı duraklatırsa süre ilerlemeyecek. Bu davranış ayarlarda açıklanacak.
- İlk sürümde semantik arama eklenmeyecek; zorunlu olmayan bu katman temel not sisteminden bağımsız tutulacak.
- Sağlayıcı ayarları, API anahtarları ve kişisel veriler eklenti veritabanlarına veya repoya eklenmeyecek.
