# Pevrai ad geçişi

Pevrai, **Personal Evolving Versatile Reasoning Artificial Intelligence**
ifadesinin kısaltmasıdır; "pev-ray" diye okunur.

Python paketi `pevrai`, masaüstü komutu `pevrai`, terminal komutu `pevrai-cli`
ve Windows uygulaması `Pevrai.exe` adını kullanır. Kaynaktan başlatma:

```sh
python -m pevrai
```

## Mevcut veriler

Ad değişikliği sohbet, günlük, yedek, izin ve API anahtarı dosyalarını taşımaz.
Yeni Windows kurulumları `%LOCALAPPDATA%/Pevrai` kullanır. Eski kurulumun veri
klasörü varsa uygulama onu okumaya devam eder; yeni klasörde ayar dosyaları
oluşturulmuşsa yeni klasör tercih edilir. Ortak kişisel veri kökü `~/.vekil`
olarak kalır. Mevcut politikadaki çalışma klasörleri aynen korunur.

Yeni ortam değişkenleri `PEVRAI_POLICY`, `PEVRAI_VEKIL_KOK` ve `PEVRAI_DIL`'dir.
Önceki adın aynı son ekli değişkenleri geriye uyumluluk için okunur; yeni ad
tanımlanmışsa önceliklidir. API anahtarları eski Credential Manager kaydından
da okunabilir; yeniden kaydedilen anahtar yeni adla saklanır. Tarayıcıdaki eski
dil, görünüm, model ve not taslağı tercihleri mevcut yeni tercihlerin üstüne
yazılmadan yeni ad alanına kopyalanır.

Kurulumun AppId değeri aynı kalır; eski kurulum güncellenebilir. Kullanıcı
verilerine dokunulmadan eski uygulama kısayolları kaldırılır.

## GitHub

GitHub deposu 7 Ekim 2026'da `pevrai` olarak yeniden adlandırıldı:
https://github.com/ledaronn/pevrai. Yerel kaynak, belgeler ve paketleme bu adresi
kullanır. Yalnızca depo adı değiştirildi; depo kimliği, `main` dalı ve `v0.1.0`
etiketinin commit özetleri aynı kaldı. Yerel dosya veya Git geçmişi gönderilmedi.
Yayınlanabilir kaynak ve README Pevrai adını kullanır. Eski adın uyumluluk için
okunan ayar anahtarları mevcut kullanıcı verilerini korur.

Bu geçiş commit, push, etiketleme veya Git geçmişini değiştirme işlemi gerektirmez.
Yayınlama ayrıca yetkilendirilmelidir; yerel geçmişin özel veri içerebileceği
durumlarda güvenli yayın akışı korunmalıdır.
