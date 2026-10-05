# Study & Focus · Smart Notes · Workspace

Üç yerel eklenti, aynı masaüstü uygulamasında hem kullanıcı tarafından hem de asistanın mevcut araç çağrılarıyla kullanılabilir. Temel işlemler API anahtarı, embedding hizmeti, model çağrısı veya sunucu gerektirmez.

## Kurulum ve kullanım

```powershell
pip install -e .
python -m limina
```

Sol raydaki **beyin simgesi**, **Bugün** merkezli çalışma alanını açar. Sol menüde Bugün, Study & Focus, Smart Notes, Workspace ve Bağlantılar bulunur; dar pencerede menü üstte sıralanır. **Study & Focus**, **Smart Notes** ve **Workspace** bölümlerinde **Etkinleştir** düğmesine basın. Her eklenti ayrı etkinleştirilir; işlem mevcut ayar yazıcısıyla araçları `policy.toml` içinde sınıflandırır. Önceden değiştirilmiş risk seviyeleri korunur. Varsayılan olarak okumalar READ, değişiklikler WRITE, silindi olarak işaretleme DESTRUCTIVE seviyesindedir. Asistanın yazma/silme çağrıları mevcut izin/onay döngüsünden geçer. Formdaki Kaydet, kullanıcının doğrudan işlemidir; model çağrısı değildir.

**Devre dışı bırak** araçları ve panel erişimini kapatır, veriyi silmez. Araçlar panelindeki paket yönetimi de aynı politikayı kullanır. Sohbet başına araç kapatma mevcut biçimde yalnızca AI erişimini daraltır. Bir eklentiyi kapatmak diğer ikisini veya sohbeti kapatmaz. Eklenti servisleri ayrı `limina/eklentiler/<ad>/`, arayüzleri `limina/arayuz/eklentiler/<ad>/` klasörlerindedir; dağıtım bunları birlikte içerir, eksik bir klasör uygulamanın açılmasını engellemez. Yeni sürümü kurduktan sonra uygulamayı yeniden başlatın.

- **Study:** dersler, sınavlar, konular ve tarih bazlı çalışma planlarını oluşturun/düzenleyin. Bugün panelinde yaklaşan sınavlar, günlük plan ve çalışma toplamları bulunur. Konularda yüzde ilerleme ve 1–5 zorluk tutulur.
- **Focus:** Pomodoro veya serbest odak başlatın; ders, konu veya workspace görevi seçilebilir. Pomodoro çalışma/mola süreleri ve tur sayısı ayarlanır. Aynı anda tek aktif veya duraklatılmış oturum olabilir.
- **Notes:** not yazın, etiketleyin, arayın, başka notlara ve ders/sınav/workspace kayıtlarına bağlayın. Arşiv, silinenler ve sürüm geçmişinden geri yükleme bulunur. Arama başlık, gövde ve etiketlerdeki tüm arama sözcüklerini eşleştirir; seçili etkin, arşiv veya silinen sekmesinin kapsamını kullanır.
- **Workspace:** izinli ve mevcut bir proje klasörü seçin; amaç, talimatlar, görevler, notlar, dosyalar/çıktılar, günlük ve sonraki adımları kaydedin. Klasörün okuma izni yoksa Ayarlar → Dosyalar bölümünden izin verin. Workspace oluşturmak dosya yetkisi sağlamaz.

## Arayüz akışı

- **Bugün:** günlük/haftalık odak toplamları, bugünkü planlar, görevler, son projeler, yaklaşan sınavlar ve son notlar. Çalışmaya başla ve Bir fikir yakala kısayolları vardır.
- **Bağlantılar:** ders, sınav, konu, görev, proje ve notlar arasındaki gerçek ilişkilerin tıklanabilir haritasıdır. Her türden son 100 kayıt yüklenir; seçili kaydın en fazla sekiz komşusu çizilir, bütün komşuları alttaki bağlantı listesinde görünür. Dar pencerede bağlantılar üst üste sıralanır. Ortadaki kayıt veya Kaydı aç ilgili düzenleyiciyi açar.
- **Not editörü:** solda arama ve not listesi, sağda başlık/gövde ve bağlantılar bulunur. Kaydet veya metin alanında Ctrl/Cmd+S ile kaydedilir. Kaydedilmemiş taslaklar ekran değişimlerinde ve yeniden başlatmada korunur; not sürümünden ayrı yerel dosyaya yazılır. Değişiklikleri bırak taslağı temizleyerek son kayıtlı sürümü açar. Sürüm geçmişi önce/sonra görünümünü, düzenleyenin kullanıcı mı asistan mı olduğunu ve geri yüklemeyi sunar. Eski taslak daha yeni bir sürümün üzerine yazamaz.
- **Proje:** solda proje seçimi, sağda görevler, dosyalar, notlar ve günlük vardır. Görevler doğrudan tamamlanabilir veya durumları değiştirilebilir. Sohbette devam et proje adını sohbet kutusunun üstünde gösterir ve her gönderimde sınırlı proje bağlamını modele ekler. Bağlantıyı kaldır bu sohbetin seçimini temizler.
- **Hızlı erişim:** odak sayacı sohbet dahil diğer ekranlarda küçük bir kontrol olarak görünür. Asistan yanıtındaki Nota kaydet, yanıtı veya o yanıtta seçili metni düzenlenebilir not formuna taşır. Proje ekranından veya proje seçili sohbetten açılan hızlı not formu proje adını başlığında gösterir ve notu o projeye bağlar.
- **Sade kontroller:** ek form alanları Diğer ayrıntılar altında; silme, sürüm geçmişi ve eklentiyi kapatma gibi işlemler üç nokta menülerindedir. İkonlara metin eşlik eder. Türkçe/İngilizce metinler ve klavye odak göstergeleri desteklenir. Modele giden araç açıklamaları da dil ayarını izler: `tools.py`'deki Türkçe bildirim `limina/ceviri.py` sözlüğünden çevrilir (`registry._cevrilmis`); yeni bir araç ya da alan eklerken Türkçe metnin İngilizce karşılığını `ceviri.EN`'e yazın, `tests/ceviri_testi.py` eksikleri gösterir.

## Kalıcılık, zaman ve geçmiş

Veriler kullanıcı dizinindeki `.vekil/eklentiler/study.sqlite3`, `notes.sqlite3` ve `workspace.sqlite3` dosyalarındadır. Her veritabanı sürümlüdür (`PRAGMA user_version=2`); sürüm 1 otomatik yükseltilir ve not arama dizini mevcut notlardan oluşturulur. Daha yeni bir şemayı eski kodla açma denemesi reddedilir. SQLite işlemleri kayıt, sürüm ve denetim günlüğünü birlikte commit eder. Kaydedilmemiş not taslakları aynı klasördeki `not_taslaklari.json` dosyasında ayrı tutulur. Uygulama kapalıyken bu dört dosya birlikte yedeklenmelidir. Dosya içerikleri workspace veritabanına kopyalanmaz.

Ekip ve Workspace aynı proje deposunu kullanır. Erişilebilir eski ekip projeleri ilk ekip listelemesinde ortak kayda bağlanır; eski ekip kimliği korunur. Proje kökü değişse bile geçmiş koşuların bağlantısı kopmaz. Sohbetin proje bağlantısı sohbet kaydında saklanır; yeni sohbet temiz başlar. “Sohbette devam et” sınırlı proje bağlamını modele getirir, dosyaları kendiliğinden okumaz. Ayrıntılı değişiklik ve doğrulama kaydı: [4 Ekim düzeltmeleri](DUZELTMELER_2026-10-04.md).

Odak sayacı UTC zaman damgaları ve çalışma aralıklarıyla hesaplanır. Uygulama kapalıyken süre ve Pomodoro turları ilerler; duraklatıldığında ilerlemez. Son turdan sonra ek mola sayılmaz. Sonraki durum/istatistik okuması biten oturumu `timer` kaynağıyla **bir kez** geçmişe kaydeder. Manuel Bitir o ana kadarki çalışmayı kaydeder. Çalışma istatistikleri mola ve duraklamaları çıkarır; gece yarısını geçen aralıkları ilgili günlere böler. UI yerel UTC ofsetini iletir; API'de ofset belirtilmezse UTC kullanılır. Tarih girişinde saat dilimi zorunludur; UI yerel saati UTC'ye çevirir.

Çalışma geçmişi yalnızca eklenir; çalışma planı güncellemek geçmiş oturumları değiştirmez. Sınav/ders/konu silmek bağlı aktif akademik kayıtlar varsa reddedilir. Silme işaretlemedir, revizyonlar korunur. Notes silmesi Sürüm geçmişi → Geri yükle ile geri alınabilir.

Güncellemeler `expected_revision` gerektirir: kaydı önce okuyun ve dönen `revision` değerini kullanın. UI ile AI aynı kaydı düzenlerse eski sürümle yazma reddedilir. Not geçmişi eski gövdeyi ve etiketleri korur; geri yüklemek de yeni bir sürüm oluşturur. Diğer eklenti değişiklikleri kendi veritabanındaki `audit` ve `revisions` tablolarında zaman, kaynak (`user`, `ai`, `timer`), işlem ve kayıt kimliğiyle izlenir. Bunlar mevcut dosya `--geri-al` komutundan ayrıdır.

## AI araçları

Araç adları bütün model adaptörlerinde aynıdır. JSON şeması, doğrulama ve iş mantığı hiçbir sağlayıcıyı içe aktarmaz.

| Eklenti | Araçlar |
| --- | --- |
| Study | `course_create/get/list/update/delete`, `exam_create/get/list/update/delete`, `topic_create/get/list/update/delete`, `study_plan_create/get/list/update/delete` |
| Çalışma / Focus | `study_session_log`, `study_session_list`, `study_stats`, `focus_start/status/pause/resume/finish` |
| Notes | `note_create/get/list/update/delete`, `note_search`, `note_read`, `note_link`, `note_archive`, `note_history`, `note_restore` |
| Workspace | `workspace_create/get/list/update/delete`, `workspace_context`, `workspace_attach/detach/resolve`, `workspace_note_link`, `workspace_log`, `workspace_log_list` |
| Görevler | `task_create/get/list/update/delete` |

Liste araçları `limit` (1–100) ve `offset` kabul eder. Eksik alan, bilinmeyen alan, yanlış tür, geçersiz tarih ve çelişkili ders/konu/sınav ilişkileri reddedilir. Listeler `items` ve `total` döndürür. Uzun AI çıktıları açıkça kısaltılır; uzun notu güncellemeden önce `note_read(id, offset, length)` ile gövdenin bütün parçalarını okuyun. `note_read` en fazla 6000 karakterlik kayıpsız parçalar döndürür. Tam metin UI'da korunur.

`workspace_context` amaç, özet, görevler, dosya referansları, not kimlikleri ve son günlük kayıtlarından sınırlı bir bağlam döndürür (varsayılan 10 kayıt; `limit/offset` ile sayfalanır). Not/ders/sınav içerikleri ihtiyaç olduğunda ilgili `get`/`read` araçlarıyla alınır. Tüm proje geçmişi sistem talimatına eklenmez. Notlar ve referanslar bir eklenti kapalıyken saklanır, erişilemeyen içerik UI'da bildirilir; farklı eklentiler arasında zorunlu foreign key yoktur.

`workspace_attach` mevcut dosya veya klasörü proje köküne göre göreli yolla kaydeder. Projeyi taşıdıktan sonra `workspace_update` ile yeni kökü seçin. `workspace_resolve` her kullanımda mevcut kökü ve izinleri yeniden doğrular. Sınır dışı yollar, symlink/junction kaçışları, Windows aygıt adları ve alternatif veri akışları reddedilir. Ardından asistan mevcut `read_file`, `read_document`, `write_file` gibi araçları kullanır; bu araçların izinleri, onayları ve yedekleri aynen uygulanır. Workspace kendi dosya yürütücüsünü eklemez.

## Örnek akış

Kullanıcı: “TYT Matematik projesi oluştur, 12 Ekim 2026 saat 09.00 için deneme sınavı ekle, türev için 40 dakika çalışalım.”

1. `workspace_create(name="TYT Matematik", root=<izinli mevcut klasör>)` → proje kimliği.
2. `course_create(name="Matematik")` → ders kimliği.
3. `exam_create(name="Deneme", course_id=<ders>, at="2026-10-12T09:00:00+03:00")` → sınav kimliği.
4. `topic_create(name="Türev", course_id=<ders>, exam_id=<sınav>)` → konu kimliği.
5. `workspace_update(id=<proje>, expected_revision=1, references=[{"type":"course","id":<ders>},{"type":"exam","id":<sınav>}])`.
6. `focus_start(mode="pomodoro", work_minutes=40, break_minutes=5, rounds=1, course_id=<ders>, topic_id=<konu>, references=[{"type":"workspace","id":<proje>}])`.
7. `note_create(title="Türev notları", body="…", references=[{"type":"workspace","id":<proje>}])` ve `workspace_note_link` ile proje not listesine bağlama.
8. `workspace_log` ile ilerleme, `workspace_update` ile kısa özet/sonraki adımlar; yeni sohbette `workspace_context` ile devam.

Buradaki kimlikler örnektir; gerçek çağrıda önceki araç yanıtından alınır. Workspace'e görev, dosya veya not eklendikçe proje revizyonu artar; sonraki güncellemede güncel revizyon kullanılmalıdır.

## Geliştirici doğrulaması

```powershell
python tests/eklentiler_testi.py
python tests/eklentiler_ui_testi.py
python tests/arayuz_testi.py
python tests/ayarlar_testi.py
```

İlk test grubu geçici veritabanlarında kalıcılık, mola/duraklama, yeniden açılış, gece yarısı, eşzamanlılık, not sürümleri, arama, gerçek izin kapısı, kurulum/kapatma, eksik eklenti, Windows yolları ve işlem geri alma davranışını sınar. UI testi yerel Chrome'u headless açar; arayüzü masaüstüyle aynı pywebview HTTP sunucusundan yükler, JavaScript dosyalarının erişilebilirliğini doğrular ve gerçek eklenti servislerini geçici veriyle çağırır. Model veya kişisel veritabanı kullanmaz. Playwright ve Chrome gerekir (`pip install -e .[dev]`). Canlı model/API testi bu testlerin parçası değildir.

İlk sürümde semantik arama, uygulama kapalıyken işletim sistemi bildirimi ve bulut eşitleme yoktur. Sayaç sistem saatine dayanır; işletim sistemi saati ileri alınırsa geçen süre de ileri gider. Temel günlük/haftalık hesaplar verilen sabit UTC ofsetini kullanır; tarihsel yaz saati bölgesi dönüşümü yapılmaz.
