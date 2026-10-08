# Pevrai ve Okuma Atölyesi — iyileştirme planı

İnceleme: 8 Ekim 2026. Bu plan kaynak kod, testler, paketleme tarifleri ve
GitHub depo/sürüm metadatasına dayanır. Gerçek sohbetler, API anahtarları ve
kitaplıklar incelenmedi. Kurulumun gerçek bir Windows kullanıcı oturumundaki
sonucu henüz doğrulanmış değildir.

## Bulgular ve öncelikler

| Öncelik | Kanıt ve kullanıcıya etkisi | Çözüm |
| --- | --- | --- |
| P0 | `pevrai.baslat.surum()` dağıtım metadatasına bağlı; `packaging/pevrai.spec` bu metadatayı açıkça paketlemiyor. PyInstaller varsayılan olarak metadatayı toplamaz. Paketlenmiş uygulama sürümünü bulamazsa yeni sürüm bildirimi devreye giremez. | Metadatayı pakete ekle; üretilen EXE'nin sürümünü kaynak sürümle karşılaştır. Kaynaktan çalışırken güncel `pyproject.toml` öncelikli olsun. |
| P0 | İki `packaging/build.py` dosyasında `readline()`/`read()` bloklayan çağrılar. Dıştaki 60 saniyelik döngü bu okumaları kesmez; yanıt vermeyen MCP/çizim süreci yayın işini takabilir. | Yanıt, başlık ve ikili veri okumalarını gerçek süre ve boyut sınırıyla yap; sadece başlatılan süreci kapatıp çıkışını bekle. Hata yolunda stderr okumak da bloklamasın. |
| P0 | Pevrai paket doğrulaması yalnızca `LOCALAPPDATA` değiştiriyor; günlük/anahtar veri kökü normalde `~/.vekil`. Yalıtım okuyucuda daha kapsamlı. | İki uygulamanın doğrulamasını ayrı geçici ev/uygulama/veri klasörlerinde çalıştır; eski ortam değişkenlerini temizle, ağ güncellemesini kapat. |
| P1 | Release iş akışları kaynak testlerini tekrar çalıştırmadan paketleyip yayımlıyor. `main` testlerinin geçmişte yeşil olması yeni etiketin doğru ağacı yayımladığını tek başına kanıtlamaz. | Release işinde ilgili kaynak testlerini EXE/kurulum üretiminden önce çalıştır; başarısızsa yükleme/yayın aşamasına geçme. |
| P1 | GitHub'da en son indirme halen `Limina-Setup-0.1.0.exe`; okuyucunun son kurulumu `1.1.0`. Yeni marka ve 7 Ekim düzeltmeleri indirilebilir kurulumlara girmedi. | Yukarıdaki engeller kapandıktan sonra Pevrai 0.1.1 ve okuyucu 1.1.1 sürümlerini temiz `yayin` ağacından GitHub Actions ile üret. |
| P1 | `journal.kota_artir()` disk/JSON hatasını yutuyor, `kota_sayaclari()` hatada boş sayaç döndürüyor; `_model_cagir()` bu davranışı bilinen fail-open sınırı olarak belgeliyor. Günlük istek tavanı hata halinde uygulanmayabilir. | Sayacı atomik ve süreçler arasında kilitli ayır; tavan etkinse bozuk/yazılamayan sayaçla yeni ücretli model isteğini durdur. Tavan kapalıyken mevcut davranışı koru. |
| P1 | `baslat.tanila()` kişisel klasör yollarını ve bazı ham istisna metinlerini yazıyor. Kullanıcı destek için çıktıyı paylaşırsa gizlilik riski doğar. | Varsayılan paylaşılabilir tanı çıktısında kullanıcı yollarını ve sırları maskele; ayrıntılı yerel tanıyı açık bir seçenek yap. Sahte sırlarla sınama ekle. |
| P2 | Eski yol haritasında bazı tamamlanmış işler hâlâ açık kutularda; Markdown için "regresyon testi yok" diyor, fakat `arayuz_testi.py` artık inline kod/yol ve kod bloğu akışlarını sınıyor. Belge ve gerçek kapsam birbiriyle uyuşmuyor. | Yol haritasını mevcut kod/test kanıtlarıyla eşleştir; eksik kalan iç içe liste, bozuk bağlantı ve hata durumlarını hedefli testlerle kapsa. |
| P2 | İki depoda Secret scanning ve push protection açık; konu etiketleri boş. Dependabot güvenlik güncellemeleri kapalı; alerts durumu ayrı doğrulanmalı. Hesap API yanıtı 2FA durumunu vermedi. | Eksik depo kontrollerini tamamla, uygun konu etiketlerini ekle. 2FA'yı kullanıcı hesap ayarından doğrulasın. |
| P1 | Bu incelemenin yerel tam koşusunda `channel="chrome"` kullanan 10 arayüz paketi ayrı profil argümanına rağmen Chrome'un remote debugging reddiyle başlayamadı. Kurulu Chromium ile ilk genel arayüz paketi geçti; bunun uygulama arızası olduğu henüz kanıtlanmadı. | Arayüz birim testlerinin tarayıcı seçimini tekrarlanabilir yap; gerçek Chrome/CDP bütünleşme doğrulamasını ayrı tut. Yeni release öncesi temiz GitHub Windows koşusunu da doğrula. |

Paket metadatası davranışının kaynağı:
[PyInstaller copy_metadata belgesi](https://pyinstaller.org/en/stable/hooks.html#PyInstaller.utils.hooks.copy_metadata).

## Uygulama sırası ve kabul ölçütleri

1. **Yayın doğrulamasını düzelt — bu çalışmanın ilk adımı.** Metadatayı ve kaynak
   sürüm önceliğini düzelt; iki paket doğrulamasına süre/boyut sınırı ve veri
   yalıtımı ekle. Gerçek fakat sentetik alt süreçlerle yanıt yok, eksik veri,
   fazla stderr ve geçerli yanıt yollarını test et. Yerelde EXE derleme.
2. **Yeni kurulum sürümlerini çıkar.** Sürüm notlarını ve numaralarını güncelle;
   release test kapısını ekle. Kişisel veri taramasından geçmiş temiz yayın
   ağacını kullan; GitHub Actions'ta EXE/sürüm/MCP/çizim doğrulaması ve SHA256
   başarılı olsun. Her iki setup dosyası doğru adla indirilebilir olsun.
3. **Maliyet sınırını ve tanılama gizliliğini güçlendir.** Bozuk sayaçta yeni
   istek gönderilmediğini, aynı anda başlayan iki görevde tavanın aşılmadığını
   ve paylaşılan tanıda sahte anahtar/yolun görünmediğini doğrula.
4. **Ürün ve bakım açıklarını kapat.** Güncel özellik/test haritası, hedefli
   Markdown testleri ve eksik GitHub depo kontrolleri. Yeni özellikleri somut
   kullanıcı akışına göre seç; mevcut onay ve yol izinlerini gevşetme.
5. **Kurulum kabulü ve kurtarma.** Ayrı test hesabı veya sanal makinede temiz
   kurulum, Limina'dan yükseltme, okuyucu güncellemesi, açma ve kaldırma yap.
   Sahte sohbet/ayar/kitaplıklar korunmalı; eski kısayollar doğru temizlenmeli.
   Tam proje yedeğini kullanıcının seçtiği harici diske alıp geri okumayı doğrula.
6. **İsteğe bağlı dağıtım kalitesi.** Kod imzalama seçeneklerini ve logo kararını
   ayrı değerlendir; otomatik güncelleme kurulumunu bu plana ekleme.

Gerçek kurulum/kaldırma, harici disk seçimi ve hesap 2FA işlemi kullanıcı
ortamı/tercihi gerektirir; bunların yapılmış olduğunu otomatik testten çıkarma.
Yerel özel `master` geçmişi hiçbir adımda gönderilmez; yayın commit'inin ebeveyni
yalnızca GitHub'ın mevcut temiz `main` commit'i olur.

## İlk adımın durumu

İlk adım kaynak düzeyinde tamamlandı:

- Pevrai dağıtım metadatası ve Null keyring backend'i paket tarifine eklendi.
  Kaynak sürüm okunurken eski editable metadatası yerine `pyproject.toml` öncelikli.
  Paket doğrulaması, EXE'nin sürümünü kurulum sürümüyle tam eşleştiriyor.
- İki uygulamada gerçek yanıt/binary okuma süresi, başlık/veri boyutu sınırı,
  sürekli sınırlı stderr drenajı ve yalnızca başlatılan süreci kapatıp bekleme var.
  Kodlar bağımsız depolarda byte olarak aynı doğrulama yardımcısını kullanıyor.
- Doğrulama ortamı ayrı geçici ev/veri/ayar klasörlerini kullanıyor; eski politika
  değişkenleri ve ortam sırları temizleniyor, güncelleme ağı kapalı, sistem
  keyring'i yalnızca bu alt süreçlerde Null backend ile devre dışı.

Doğrulama: 10 gerçek sentetik alt süreç testi ve 4 sürüm testi geçti. Güncel
yardımcı her iki Python ortamında da sınandı. Kaynak converter ve okuyucunun
gerçek MCP initialize yanıtları, sentetik PDF çizimi ve süreç kapanışı doğrulandı.
Pevrai'ın 39 paketi tek tek başarılı sonuç verdi: yerel Chrome'da başlayamayan
10 arayüz paketi ayrıca kurulu Chromium ile doğrulandı. Bu sonuç yerel Chrome
bütünleşmesinin geçtiği anlamına gelmez. Okuyucu tam koşusundaki kitaplık testi,
koşucu ortamının zorladığı veri yolu kaldırılınca geçti: toplam 77 başarılı,
1 Tesseract eksikliği nedeniyle atlanan test. Gerçek kişisel veriler kullanılmadı.

Yeni EXE, kurulum/yükseltme ve temiz GitHub Windows doğrulaması henüz yapılmadı;
bunlar ikinci adıma aittir. Bu adımda commit/push/etiket üretilmedi. Değişen
kaynakların sözdizimi, whitespace ve kişisel veri kontrolleri temiz.
