# Araçlar

## Araç yazım sözleşmesi

Bir araç = **tek bildirim** (`limina/araclar/*.py`, `@arac` dekoratörü) + fonksiyon.
Şema, risk, yol argümanları, paket ve panel adı bildirimden türer; başka hiçbir yere
dokunulmaz. `policy.toml [araclar]` yine son söz: bildirim varsayılan riski söyler,
politika sıkılaştırabilir ya da aracı tanımayabilir (deny by default).

```python
from limina.araclar.kayit import arac

@arac(ad="write_file", paket="dosya_duzenleme", risk="WRITE",
      baslik="Dosya yazma",                       # panelde görünen ad (kullanıcıya)
      aciklama="Dosya oluşturur ya da tam içeriğini değiştirir; önce yedek alır.",
      modele="Bir metin dosyası oluşturur veya VAR OLANIN ÜZERİNE YAZAR. ...",   # modele
      yollar={"path": "yaz"},                     # kapı: 'path' yazma köklerinde olmalı
      sema={"type": "object", "properties": {...}, "required": ["path", "content"]})
def write_file(yol: Path, args: dict) -> str:
    ...
```

`yol`: kapının doğruladığı (çözümlenmiş) birincil yol argümanı — `yollar` boşsa `None`.
Kayıt defterinden türeyenler: `vekil_v0.ARAC_TABLOSU` / `ARAC` (şemalar), `gate.YOL_BILDIRIMLERI`
(hangi argüman yol, hangi modda), `paketler.YERLESIK` / `ARAC_BILGI` (panel), sistem talimatındaki
"okuyan araçlar" listesi (`okuyan=True`).

**Kurallar**

1. **Docstring modele yazılır, geliştiriciye değil.** Model bu metne bakarak aracı seçer.
   Ne zaman kullanılacağını, ne zaman kullanılmayacağını ve sınırlarını yaz.
2. **Dönüş her zaman metindir.** Nesne değil, model okuyacak.
3. **İstisna dışarı sızmaz.** Yürütücü yakalar ve metne çevirir, ama araç kendi hata
   mesajını yazarsa daha iyi olur: `"'rapor.pdf' bulunamadı. X içindekiler: Y, Z."`
4. **Çıktı kırpılır.** `MAX_OUTPUT` (8000 karakter) üstü kesilir ve kaç satır olduğu
   notuyla birlikte döner.
5. **Argüman az olsun.** 5'ten fazla parametreli araçlarda model hata yapmaya başlar.
6. **Araç sayısı kontrollü tutulur.** Çok sayıda araç model için gürültüdür. Benzer işler
   tek araçta birleştirilir.
7. **Modele giden her metin Türkçe yazılır ve `ceviri.EN`'e İngilizcesi eklenir.** `modele=`
   ve şemadaki `description`'lar kaynak dilde durur; `kayit.semalar()` her çağrıda `t()`'den
   geçirir, dil ayarı (`config/arayuz.toml [genel] dil`) neyse modele o gider. Aracın
   **dönüş metinleri** de `t("...", ad=deger)` içinden yazılır. `tests/ceviri_testi.py`
   `@arac` bildirimlerini ve `t()` çağrılarını tarar: sözlükte karşılığı olmayan bir
   metin testi kırar. CLI parçaları (`--geri-al`), araç ve argüman adları çevrilmez.

### İyi ve kötü hata mesajı

```
kötü:  Error: [Errno 2] No such file or directory: '/home/u/rapor.pdf'
iyi:   'rapor.pdf' bulunamadı. /home/u/ içindekiler: rapor_v2.pdf, rapor_eski.pdf
```

İkincisi modelin bir sonraki adımda doğru şeyi yapmasını sağlar. Hata mesajı bir arayüzdür.

---

## Risk seviyeleri

| Seviye | Anlam | Varsayılan | Tur başına tavan |
|---|---|---|---|
| `READ` | Yan etkisiz okuma | ALLOW | 12 |
| `WRITE` | Dosya oluşturma/değiştirme/taşıma, geri alınabilir | ASK (oturumda toplu onay verilebilir) | 5 |
| `EXEC` | Komut çalıştırma (henüz hiçbir araç bu seviyede değil) | ASK, her seferinde | 3 |
| `NETWORK` | Dışarıya istek giden işlem | ASK, her seferinde | 3 |
| `DESTRUCTIVE` | Kalıcı etkili/riskli işlem, toplu onay yok | ASK, toplu onay yok | 2 |

Politika `policy.toml` içinde araç bazında sıkılaştırılabilir, gevşetilemez. "Tur başına
tavan" (`TUR_TAVANI`), modelin **tek bir turda** aynı risk seviyesinden bu sayıdan fazla
işlem yapmasını engeller — aşılırsa kalan işler bir sonraki tura ertelenir, kullanıcı her
partiyi ayrı görür. Ayrıntı: [SECURITY.md](SECURITY.md).

---

## Araç sayısı — modele ne gösteriliyor

Model her çağrıda **21 araç şeması** görüyor. Bu sayı üç kaynaktan geliyor ve
üçü farklı kurallara tabi:

| Kaynak | Sayı | Not |
|---|---|---|
| Yerel araçlar (`vekil_v0.ARAC_TABLOSU`) | 15 | Şemaları `vekil_v0.py`'de elle yazılı |
| `converter` MCP sunucusu | 2 | İkisi de `policy.toml [araclar]`'da sınıflandırılmış |
| `okuma` (Okuma Atölyesi) MCP sunucusu | 11 | Güncel sunucu 21 araç bildirir; etkin küme kurulumun politikasına bağlıdır. Bkz. OKUMA_INTEGRATION.md. |
| **Modele gösterilen toplam** | **21** | `len(vekil_v0.ARAC.function_declarations)` |

**19 ile karıştırılmamalı.** `KOPRU.araclar` 19 taşır (2 `converter` + 17 `okuma`)
— bu MCP'den **keşfedilen** araç sayısıdır, modele gösterilen değil.
`evals.py --kapi`'nin `mcp_semasi_testi` çıktısındaki "19 arac tarandi" bu sayıyı
yazar ve bir belgede "araç sayısı" diye alıntılanırsa yanıltır. Ölçmek için tek
doğru yer: `len(vekil_v0.ARAC.function_declarations)` (21) ve
`len(vekil_v0.POLITIKA.araclar)` (21, aynı küme).

Bu sayı bir maliyet kalemidir: araç şemaları her model çağrısının girdi token'ına
giriyor (ölçüm: Okuma Atölyesi'nin 4 aracı çağrı başına +494 token,
`DEVIR_FAZ6.md` §6). Yeni araç eklemek ücretsiz değil.

### Listede olmayan bir araç: `durum_yaz`

`durum_yaz` yukarıdaki 21'e **dahil değil** ve sistem talimatında hiç tanıtılmıyor.
Yalnızca bir tavana (adım ya da çağrı) çarpıldığında, `vekil_v0._durum_kaydet`
içinde, tek bir zorlanmış çağrıda (`FunctionCallingConfigMode.ANY`, başka hiçbir
araç sunulmadan) kullanılır. İki gerekçe: (a) normal listede olsaydı modelin onu
kendi isteğiyle çağırmasına güvenmek gerekirdi — modelin kendi ilerleme özetinin
yanlış olabildiği ölçüldü (`DEVIR_FAZ7.md` Aşama 1); (b) her sıradan çağrının
girdi token'ına bir şema daha eklerdi. "Varsayılan kapalı" ilkesinin araç
tarafındaki uygulaması.

---

## Katalog

### Dosya sistemi

| Araç | Risk | Not |
|---|---|---|
| `list_dir(path)` | READ | Ad + boyut listeler, içerik okumaz |
| `read_file(path, start_line?)` | READ | Düz metin/kod dosyası, 400 satırlık sayfalar; çıktı sonunda `start_line=N` ipucu. 50 MB üstü reddedilir |
| `read_document(path, start_page?, end_page?)` | READ | PDF/DOCX/PPTX/XLSX/TXT/MD/CSV — `belge.py`. **Görüntü** (PNG/JPG/ekran görüntüsü) ve metin katmanı olmayan PDF sayfaları Windows yerleşik OCR'dan geçer (`ocr.py`, `[ocr]` ekstrası): sayfa başına karar, `[OCR]` etiketi, çağrı başına 20 sayfa. OCR yoksa araç nedenini söyler |
| `search(path, query, glob?)` | READ | Dosya adında + düz metin içeriğinde arar — `ara.py`. PDF/DOCX/PPTX içeriğini taramaz |
| `degisiklik_gecmisi(adet?)` | READ | Ajanın daha önce ne değiştirdiğini listeler (`journal.py`), içerik göstermez |
| `write_file(path, content)` | WRITE | Kısmi düzenleme yapmaz, tam içerik ister. Boşaltma/büyük küçültme "yıkıcı" sayılır, toplu onayı atlar |
| `edit_file(path, old_text, new_text)` | WRITE | Yerinde düzenleme: `old_text` dosyada **tam olarak bir kez** geçmeli (0 ya da 2+ → hata, dosya değişmez). Yedek + günlük, `--geri-al` çalışır. Onay kartı uygulanmış hâlin farkını gösterir |
| `mkdir(path)` | WRITE_HAFIF | Yazma kökleri altında klasör (ara klasörler dahil). Geri alma yalnızca klasör boşsa kaldırır; içinde dosya varsa dokunmaz |
| `move(path, dst)` | WRITE | Kaynak ve hedef ikisi de doğrulanır; hedefte dosya varsa üzerine yazmaz |
| `rename(path, new_name)` | WRITE | Sadece ad değişir, klasör aynı kalır |
| `trash(path)` | DESTRUCTIVE | Kendi çöp klasörümüze (`~/.vekil/cop/`) taşır, zaman damgalı ad. Kalıcı silme aracı **yok** |

### Açma (`araclar/acma.py`) — paket `acma`, kaldırılabilir

| Araç | Risk | Not |
|---|---|---|
| `open_file(path)` | EXEC | **Açma klasöründeki** bir ögeyi açar: belge ilişkili programla, kısayol (.lnk) kullanıcının yazdığı hedef ve argümanlarla, program doğrudan. Öge adıyla istenir (sistem talimatı klasörün içeriğini listeler). Her seferinde onay, toplu onay yok, tur başına 3 |

**Tasarım:** izin listesi bir dizi değil, **diskteki tek bir klasör** (`policy.toml [acma] klasor`,
Ayarlar > Dosyalar > Açma klasörü). Kullanıcı Explorer'da ne koyarsa o açılabilir. Üç değişmez
(`tests/acma_testi.py`):
1. Klasör ajanın yazabildiği hiçbir yerle kesişemez (içinde, dışında, eşit) — kesişirse kapı klasörü
   yok sayar ve nedenini söyler; panel seçim anında reddeder. Aksi hâlde ajan kısayol yazıp açardı.
2. Kısayolun **hedefi** de ajanın yazabildiği bir yerde ya da Limina'nın kodunda olamaz
   (`kısayol → kum/x.bat` zinciri kapalı). Kısayol → kısayol açılmaz.
3. Klasör dışındaki hiçbir yol açılmaz; `.url` (internet kısayolu) reddedilir — adresler yalnızca
   tarayıcı araçlarıyla, site listesinden açılır.
Onay kartı gerçek hedefi gösterir: `.exe` ve kısayol→`.exe` için **ÇALIŞTIRILACAK**, belge için
"ilişkili programla açılacak". Araç argüman geçiremez, komut kuramaz (`os.startfile`); "kabuk yok"
ilkesi korunur.

### Tarayıcı (`tarayici.py`)

| Araç | Risk | Not |
|---|---|---|
| `browser_open(url)` | NETWORK | Chrome kapalıysa kendi profiliyle (`chrome-profil/`) otomatik başlatır. Site beyaz listesine ve (yerel dosya için) izinli köklere karşı kapıda ayrıca doğrulanır |
| `browser_read()` | READ | Görünür sayfa metni, `<untrusted_content>` ile sarılı |
| `browser_snapshot()` | READ | ARIA erişilebilirlik ağacı — `browser_click`/`browser_fill` için gereken `role`/`name` buradan alınır |
| `browser_click(role, name)` | WRITE | Koordinatla tıklamaz. Ad önce TAM eşleşir, sonra alt dize; birden fazla eşleşirse **tıklamaz**, adayların tam adlarını numaralı listeler (azami 10) — model ikinci çağrıda tam adla seçer. Tıkladıktan sonra sayfanın yeni halini görmez, gerekiyorsa `browser_snapshot` tekrar çağrılır |
| `browser_fill(role, name, text)` | WRITE | Parola alanına yazmaz (kod seviyesinde reddedilir, model isterse de). Kart/TC kimlik numarası kalıbı içeren metni reddeder |
| `browser_download(role, name)` | DESTRUCTIVE | Sadece uzantı beyaz listesindeki dosyalar iner (`indirilebilir_uzantilar`), çalıştırılabilir dosyalar reddedilir. Ara klasöre (`~/.vekil/indirilen/`) iner, kalıcı yer değil |

### Dönüştürücü (`converter`) — MCP sunucusu, `Donusturucu/server.py`

| Araç | Risk | Not |
|---|---|---|
| `converter.convert(src, target_format, dst_dir)` | WRITE | Sadece: PPTX/PPT/DOCX→PDF (LibreOffice headless), PDF→PPTX/PNG (PyMuPDF), PNG/JPG→PDF (Pillow). Kendi izin kontrolünü yapmaz, `src` ve `dst_dir` kapıda doğrulanır |
| `converter.list_formats()` | READ | Desteklenen kaynak→hedef matrisini döndürür |

### Okuma Atölyesi (`okuma`) — MCP sunucusu, `Araclar/OkumaAtolyesi` (kendi `.venv`'i)

Bağımsız bir PDF kütüphanesi paketi; ana ortama kurulu değil, kendi `python.exe`'siyle alt
süreç olarak başlatılır. İlk bağlantıda aşağıdaki dört READ aracı sınıflandırılmıştı.
Güncel entegrasyon açma/kapatma, işlem doğrulama, parçalı okuma ve içindekiler araçlarını
da sağlar. Güncel riskler ve kullanım: [Okuma Atölyesi bağlantısı](OKUMA_INTEGRATION.md).

| Araç | Risk | Not |
|---|---|---|
| `okuma.list_documents()` | READ | Kütüphanedeki belgeleri listeler |
| `okuma.search_documents(query)` | READ | Belge içeriğinde arar, sonuç `document_id` taşır — model bunu tahmin etmez, önce arar |
| `okuma.read_pages(document_id, ...)` | READ | Bir belgenin belirli sayfalarını okur |
| `okuma.get_reader_context()` | READ | Okuyucunun canlı bağlamı (açık belge, seçili metin/sayfa) |

Sınıflandırılmamış araçlar (`import_pdf`, `add_note`, `export_pdf` vb.) modele
gösterilmez. Güncel çalışma alanında açma/kapatma ve OCR ayrıca sınıflandırılmıştır;
başka kurulumlarda etkin araçlar kendi `policy.toml [araclar]` kayıtlarına bağlıdır. Veri
klasörü bilerek kod kökünün dışında — paketin kendi GUI'si de aynı
klasörü kullanıyor, kod köküne almak "korunan yol" sınırını gereksiz genişletirdi.

MCP araçları yerel araçlarla aynı kod yolundan geçer (`mcp_bridge.py`) — kapı, onay, tur
tavanı hepsi aynı. Sunucu çökerse ajan çökmez, "BAGLANAMADI" metni döner. Çıktı
`mcp_bridge.dis_kaynak` ile kırpılır ve `<untrusted_content>` içine sarılır — yerel
`read_document`/`browser_read` ile aynı güvenlik muamelesi, çünkü döndürdüğü çoğu şey
kullanıcının kendi dosyalarının içeriği (bkz. [SECURITY.md](SECURITY.md)).

### Yalnızca sınıflandırılmış MCP araçları modele gösterilir

Bir MCP sunucusu keşfedilen **her** aracı otomatik sunar, ama `vekil_v0` bunların yalnızca
`policy.toml [araclar]`'da satırı olanları modelin şemasına ekler — geri kalanı `vekil_v0`
içe aktarılırken bir **UYARI** olarak basılır, sessizce gizlenmez. Gerekçe: sınıflandırılmamış
her araç modele görünseydi hem gereksiz girdi token'ı hem de çağrılırsa zaten kapıdan
`DENY` alacak ölü bir yol eklerdi. `evals.py --kapi`'deki `mcp_semasi_testi`, modele
gösterilen ad kümesinin `policy.toml` ile aynı kaldığını doğrular — yeni bir MCP sunucusu
bağlanıp araçları sınıflandırmayı unutursa bu test onu yakalar.

---

## Paketler — kullanıcının gördüğü gruplar

Araçlar arayüzde **paket** halinde sunulur (`limina/paketler.py`): `cekirdek`
(list_dir, read_file, search, degisiklik_gecmisi), `belge` (read_document),
`dosya_duzenleme` (write_file, edit_file, mkdir, move, rename, trash), `acma` (open_file), `tarayici` (browser_*) ve her
MCP sunucusu kendi paketi (`mcp:<ad>`). Her aracın insan dilinde adı ve açıklaması
`paketler.ARAC_BILGI`'de; teknik ad panelde açıklama satırında görünür.

| İşlem | Nereye yazar | Etkisi |
|---|---|---|
| Aracı **kapat/aç** (sohbet başına) | Hiçbir dosyaya (Oturum) | Yalnızca bu sohbette modele gösterilmez; kapı değişmez |
| Paketi **kaldır** (yerleşik, çekirdek hariç) | `policy.toml [paketler] kaldirilan` | `gate.Politika` o araçları `[araclar]`'dan düşürür → kapı DENY, şema modele gitmez, sistem talimatındaki cümle kurulmaz, profillerden düşer. `[araclar]` satırları silinmez ("Geri ekle" aynı seviyelerle döner) |
| **Eksik araçları ekle** (kurulu paket, yeni sürümle gelen araç) | `policy.toml [araclar]` — yalnızca satırı olmayanlar, varsayılan riskle | Deny-by-default gereği yeni araç eski policy.toml'da yoktur; panel eksik sayısını gösterir, tek tık `paket_geri_ekle` ile yazar. Çekirdek dahil |
| MCP sunucusu **ekle** | `policy.toml [mcp.<ad>] komut` | Bir sonraki açılışta bağlanır; araçları sınıflandırılana kadar modele görünmez |
| MCP aracını **sınıflandır / çıkar** | `policy.toml [araclar] "<ad>.<arac>"` | `vekil_v0.arac_semalarini_tazele` ile yeniden başlatmadan modele girer/çıkar |
| MCP sunucusu **sil** | `[mcp.<ad>]` bölümü + o sunucunun `[araclar]` satırları + profillerdeki anılmalar | Tamamen silinir; yeniden eklenebilir |

Kaldırma listesi **yalnızca daraltır**: hiçbir araca izin ekleyemez. Çekirdek
listede yazılsa bile yok sayılır (uyarı basılır). Bütün yazmalar `ayarlar._guvenli_yaz`
protokolünden geçer (yedek, atomik yazma, geri okuma, yeniden yükleme, korunan yol
kontrolü).

---

## Yeni araç ekleme kontrol listesi

**Yerel araç:**
- [ ] `limina/araclar/` altında bir modülde `@arac` ile bildirildi mi (ya da mevcut modüle
      eklendi mi)? Yeni modülse `limina/araclar/__init__.py`'deki import listesine girdi mi?
- [ ] `modele` metni model gözüyle yazıldı mı? (ne zaman kullanılmaz da yazılı mı?)
- [ ] Yol argümanı varsa `yollar={...}` bildirildi mi? Bildirilmeyen yol argümanı kapıda
      **denetlenmez**.
- [ ] Hata mesajları modelin düzeltebileceği bilgiyi içeriyor mu? Çıktı `ortak.kirp` ile
      kırpılıyor mu? Yan etkiliyse `ortak.journal_yaz` ile geri alma kaydı yazılıyor mu?
- [ ] `policy.example.toml [araclar]`'a satırı eklendi mi? (Kullanıcının `policy.toml`'unda
      yoksa araç çalışmaz — deny by default; "Geri ekle" paket tanımından yazar.)
- [ ] Test: kapı kararı `evals/tasks.yaml` `kapi` bölümüne, fonksiyon içi reddler `kod`
      bölümüne; kayıt defteri tutarlılığı `tests/kayit_testi.py`'de.

**MCP aracı:**
- [ ] `policy.toml [araclar]`'da sınıflandırıldı mı (panelden ya da elle)? Aksi halde modele
      hiç gösterilmez.
- [ ] Yol argümanı varsa **tablo biçimiyle** bildirildi mi?
      `"sunucu.arac" = { risk = "WRITE", yollar = { path = "oku" } }` — panel yol-benzeri
      argümanlar için seçici gösterir; bildirilmeyen argümanı kapı denetlemez ve panel bunu
      turuncu uyarıyla söyler.
