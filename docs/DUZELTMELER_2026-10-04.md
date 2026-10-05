# İşlev ve arayüz düzeltmeleri — 4 Ekim 2026

Son doğrulama: 5 Ekim 2026.

[İnceleme raporundaki](INCELEME_2026-10-04.md) 11 işlevsel bulgu ve uygulanabilir arayüz önerileri ele alındı.

## Kullanıcıya görünen değişiklikler

- Gönderim reddedildiğinde mesaj ve ekler korunur; devam eden gönderim sırasında ikinci gönderim ve sohbet değiştirme engellenir. Yazı alanına bu sırada girilen yeni metin korunur.
- Modelin kota, sunucu hatası ve zaman aşımı sonrasında yeniden denemesi durdurulabilir. Bekleme arayüzde gösterilir. Çalışan model isteği veya dış araç, mevcut zaman aşımına kadar devam edebilir.
- Araç sonuçları izin kararından ayrı başarı bilgisi taşır. İzin verilen ama başarısız olan işlem kırmızı hata işareti ve ayrıntısıyla görünür. Eski arşivlerde bu bilgi yoksa eski gösterim korunur.
- Açık tema, mesaj genişliği, otomatik kaydırma, teknik ayrıntılar ve test modu çalışır. Test modu adım, araç ve token sayılarını gösterir. Animasyon kapalı veya azaltılmışsa yanıt metni hemen görünür.
- Pano kopyalama hatası başarı olarak bildirilmez. Canlı ve geçmiş yanıtlarda ortak kopyalama / nota kaydetme işlemleri kullanılır.
- Not araması etkin, arşiv ve silinen sekmelerinin kapsamını izler. SQLite arama dizini eski kayıtlardan yeniden oluşturulur; not içerikleri ve sürümleri korunur.
- Not taslakları uygulamanın yerel veri klasöründe `eklentiler/not_taslaklari.json` dosyasına atomik yazılır; ayrıca tarayıcıda hemen saklanır. Taslak, kaydedilmiş notun sürümünü değiştirmez. Kaydetme veya değişiklikleri bırakma taslağı temizler.
- Proje bağlantısı sohbet başına saklanır. Yeni sohbet temiz başlar; eski sohbet açıldığında kendi bağlantısı döner. “Sohbette devam et” proje kimliği, özet, talimatlar, sonraki adımlar, görevler, dosya referansları ve son günlük kayıtlarını sınırlı bir bağlam olarak getirir. Proje metni dış içerik olarak işaretlenir; dosya içerikleri otomatik okunmaz. Model bu bağlamı alırken sohbet balonunda kullanıcının mesajı ve dosya ekleri gösterilir; ham proje JSON'u gösterilmez.
- Ekip ve Workspace ortak proje kaydını kullanır; ekranlar arasında geçiş düğmeleri vardır. Ekip görünümü ayarlardan 3B ofis veya sade kartlar olarak seçilebilir. Ekip ve düşünce ağına kullanım açıklamaları eklendi.
- Dosya ve görsel ekleme tek seçenek oldu. Başlangıç önerileri mevcut araçlara, sohbet kısıtlarına ve gerçek izinli klasörlere göre üretilir.

## Veri geçişi ve geri alma

Eski ekip projeleri, erişilebilir klasörleri varsa ekip proje listesi ilk açıldığında ortak Workspace deposuna aktarılır. Eski ekip kimliği ortak kayıtta saklanır; klasör değişse de koşularla bağlantısı korunur. Eski JSON dosyası saklanır. Erişilemeyen eski kayıtlar yerinde kalır. Silinen ortak kayıtlar eski JSON'dan tekrar içeri alınmaz. Ekipte yeni görev başlatılırken dosya izinleri yeniden denetlenir.

Dağıtılan dönüştürücünün çıktıları önce geçici klasöre hazırlanır. Son hedeflerin izinleri denetlenir, mevcut dosyalar yedeklenir ve yazmalar geri alma günlüğüne kaydedilir. Yeni çıktılar da geri alınabilir. Çıktı klasörü mevcut olmalıdır. Çok sayfalı dönüşümde son dosyalardan birinin yazılması başarısız olursa daha önce yazılmış çıktılar günlükten ayrı ayrı geri alınabilir.

Bu sözleşme yalnızca dağıtılan `Donusturucu/server.py` sunucusunun `convert` aracına uygulanır. Diğer dış MCP araçlarının onay kartında Limina geri alma kapsamına girmediği açıkça belirtilir.

## Doğrulama

Mevcut modelsiz test paketlerine [işlev regresyon testi](../tests/islev_regresyon_testi.py) ve [tarayıcı regresyon testi](../tests/arayuz_regresyon_testi.py) eklendi. Testler geçici dosyalar, SQLite veritabanları, sahte sağlayıcılar ve headless Chrome kullanır. Gerçek sağlayıcı çağrısı, gerçek dönüşüm motoru ve masaüstü pywebview etkileşimi bu yeni regresyon testlerinde kullanılmaz.

Mevcut 30 paketin tamamı ve yeni 2 paket geçti. Toplu çalıştırma sonrasında yapılan değişikliklerin etkilediği paketler ayrıca yeniden çalıştırıldı. Yeni işlev paketi 11 senaryoyu kapsar: gönderim reddi, iptal, kota sonrası tekrar isteği, araç hatası, not arama geçişi, taslak deposu, sohbet bağlamı, proje aktarımı/silinmesi ve dönüştürücü geri alması. Python derleme kontrolü ve `git diff --check` de geçti.

Kullanım sıklığı ve görev tamamlama süresi henüz ölçülmedi. Bu çalışma bunları ölçmüş gibi bir ürün kararı vermez; isteğe bağlı sade görünüm ve açıklamalar sunar.
