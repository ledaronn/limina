# MD/TXT → PDF güncellemesi

ZIP içindeki Donusturucu klasörünü projenin aynı adlı klasörüyle birleştirin.
Mevcut core_engine.py, server.py ve app_gui.py dosyalarını güncel sürümleriyle değiştirin.
Çalışan dönüştürücü/MCP sürecini yeniden başlatın. Yeni Python bağımlılığı yoktur;
mevcut requirements.txt ve LibreOffice kurulumu yeterlidir.

## Davranış

- `.md` ve `.txt` kaynaklarından PDF üretir; kaynaklar UTF-8 veya UTF-8 BOM olmalıdır.
- Markdown düz metin olarak aktarılır. `#`, `**`, bağlantı ve kod işaretleri korunur;
  başlık/kalın yazı biçimlendirmesi ve görseller işlenmez.
- GUI dosya seçicisinde iki uzantı da görünür. `list_formats` tablosunda iki dönüşüm de yer alır.
- Yollar `realpath` ile çözülür. Subprocess liste argümanla ve `shell=False` çalışır.
- LibreOffice için geçici çıktı klasörü ve ayrı profil kullanılır; işlem sonunda temizlenir.
- Yeni PDF başarıyla oluşmadan mevcut hedef PDF değiştirilmez.
- İzin kontrolü mevcut gate.py katmanında kalır.

## Doğrulama

Proje kökünden:

```sh
python -B -m unittest discover -s Donusturucu -v
```

Yedi otomatik test geçti: format listesi, argümanlar/metin dönüşümü,
başarısız dönüşümde eski PDF ve temizlik, zaman aşımı, UTF-8 hatası,
eksik LibreOffice ve sembolik bağlantı çözümleme.

Linux üzerinde LibreOfficeDev 26.8.0.0.alpha0 ile gerçek MD ve TXT dönüşümleri
çalıştırıldı. Türkçe karakterler PDF metninden doğrulandı; örnek PDF görsel olarak
incelendi. Windows ortamında çalıştırılmadı. MCP paketi test ortamında bulunmadığından
list_formats fonksiyonunun gerçek gövdesi bağımsız çalıştırıldı; MCP üzerinden
uçtan uca bağlantı ve GUI etkileşimi test edilmedi.

Yerel ortamda, Donusturucu klasöründe:

```sh
python -c "from server import list_formats; print(list_formats())"
python -c "from core_engine import DocumentConverter; print(DocumentConverter().convert_file('ornek.md'))"
```

Liste şu yeni satırları içerir:

```text
.md -> .pdf
.txt -> .pdf
```

LibreOffice metin giriş filtresi ve ayrı profil parametreleri için
[resmî komut satırı belgesi](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html).
