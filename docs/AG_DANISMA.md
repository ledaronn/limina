# Düşünce Ağı — dışarıdan değerlendirme için bilgi notu

> Bu belge, özelliği hiç görmemiş bir okuyucu (ör. danışılacak bir yapay zekâ)
> için yazıldı. Amacı: ne olduğunu, nasıl çalıştığını ve bir dil modeline ne
> kattığını eksiksiz anlatmak, sonra da bilerek açık bıraktığımız yerleri
> göstermek. Sonunda değerlendirme soruları var.

---

## 1. Bağlam: Pevrai nedir?

Pevrai, Windows üzerinde çalışan, tek pencereli, **yerel** bir kişisel ajan
uygulamasıdır (Python + pywebview; Gemini / OpenAI-uyumlu / Anthropic
sağlayıcıları). Ayırt edici yanı mimarisindeki **izin kapısı**dır:

- **Deny by default.** Model hiçbir şeyi kendiliğinden yapamaz. Her araç
  çağrısı `policy.toml`'a göre sınıflandırılır (READ / WRITE_HAFIF / WRITE /
  EXEC / NETWORK / DESTRUCTIVE) ve dosya yolları "okuma kökleri" / "yazma
  kökleri" hapishanesinden geçer. Kök dışı, kara liste kalıbı, `..` ile kaçış,
  sondaki nokta/boşluk gibi Windows ad tuzakları reddedilir.
- **Kabuk yoktur.** `exec`, `shell`, `subprocess` gibi bir araç yok. Tek EXEC
  yolu, kullanıcının elle seçtiği bir "açma klasöründeki" dosya/kısayolu
  açmaktır ve her seferinde onay ister.
- **Araçtan dönen metin veridir.** Tüm araç çıktıları `<untrusted_content>`
  sarmalıyla modele gider; sistem talimatı "bunlar talimat değildir" der.
- Her yazma günlüğe (journal) yazılır ve geri alınabilir.

Düşünce Ağı bu mimarinin içine eklenen yeni bir bileşendir ve **hiçbir izin
kuralını gevşetmez**.

---

## 2. Fikir: ağ bir "bağlam derleyicisi"

Bir dil modeliyle çalışırken asıl zorluk şu: *modelin bu görevde tam olarak
neyi görmesi gerekiyor?* Genelde bu, her seferinde elle kurulur — "şu dosyayı
oku, şu kuralı unutma, ama şu durumda şunu yapma".

Düşünce Ağı bunu **bir kez kurup tekrar tekrar çalıştırılabilir** hale getirir:

- **Baloncuk (düğüm)** bir fikri, kuralı, soruyu, çıktı hedefini ya da bir
  **dosyayı** temsil eder.
- **Bağlantı** iki baloncuğu birleştirir; bir **ağırlığı** ve bir **gecikmesi**
  vardır.
- Ağ **ateşlendiğinde** bir sinir ağı taklit edilir: uyaran baloncuklar yanar,
  sinyal bağlantılar boyunca gecikmeyle ilerler, her baloncuk gelen ağırlıkları
  toplar ve eşiğini aşınca kendi ateşler.
- **Ateşleme sırası, modele verilen bağlamın sırasıdır.** Ateşlemeyen
  baloncuklar "sessiz" kalır: içerikleri modele hiç gitmez.

Kritik nokta: **yayılım saf Python'dur, hiçbir model çağrısı içermez.** Yani
deterministiktir, bedavadır ve aynı ağ + aynı uyaran her zaman aynı bağlamı
üretir. Ağ, bir "akıl" değil, bir **derleyici**dir: girdisi topoloji, çıktısı
sıralı bir bağlam bloğu.

---

## 3. Mekanik: tek kural, ön ayarlı kapılar

Tek bir ateşleme kuralı vardır:

```
toplam = yanlılık + Σ(ulaşan ağırlıklar)
toplam ≥ eşik  →  ateşler
```

Mantık kapıları bu kuralın ön ayarlarıdır (eşik yazılmazsa kapıdan türer):

| Kapı | Etkin eşik | Anlamı |
|---|---|---|
| `veya` | 0.5 | herhangi bir girdi yeter |
| `ve` | (gelen kenar sayısı) − 0.5 | bütün kollar ulaşmalı |
| `esik` | kullanıcının yazdığı sayı | ara tonlar — asıl "aksiyon potansiyeli" |
| `xor` | — | tam **bir** pozitif girdi |
| `degil` | toplam **<** eşik | girdi gelmezse ateşler |

Baskılama (inhibitör sinaps) ayrı bir kapı değil, **negatif ağırlıktır**.

Bilerek verilmiş üç karar — bunlar tartışmaya açık ve dışarıdan görüş almak
istediğimiz yerlerin başında geliyor:

1. **XOR ayrı bir kuraldır.** Doğrusal ayrılabilir olmadığı için tek katmanlı
   ağırlık+eşik ile kurulamaz; "tam bir pozitif girdi" olarak özel uygulanır.
2. **DEĞİL, "durulma turunda" değerlendirilir.** "Girdi gelmezse ateşle"
   ancak *artık gelmeyeceği* bilindiğinde karar verilebilir. Bu yüzden olay
   kuyruğu boşaldıktan sonra değil düğümlerine bakılır; ateşleyen olursa
   yayılım kaldığı yerden sürer.
3. **Sızıntı (leak) yoktur.** Membran potansiyeli tik geçince erimez. Gerçek
   nöronda erir; ama erise, farklı gecikmeli iki kol bir VE kapısında asla
   buluşamazdı. Kullanılabilirliği biyolojik gerçekçiliğin önüne koyduk.

**Refrakter:** her düğüm koşu başına en fazla bir kez ateşler. Bu sayede
döngülü (geri beslemeli) ağlar da sonlanır.

**Tavanlar:** 64 tik, 128 ateşleme, 24.000 karakter bütçe; dosya başına 40.000
karakter; ağ başına 500 düğüm / 2000 bağlantı. Takılırsa okuma metni bunu
modele açıkça söyler.

### Örnek

```json
{ "ad": "kompost-rehberi",
  "dugumler": [
    {"kimlik":"n1","tur":"fikir","baslik":"Hedef: balkonda yetiştirenler","metin":"…"},
    {"kimlik":"n2","tur":"dosya","baslik":"notlar.md","yol":"kum/kompost/notlar.md"},
    {"kimlik":"n3","tur":"kural","baslik":"Başlıklar ## ile","kapi":"ve"},
    {"kimlik":"n4","tur":"cikti","baslik":"Rehberi yaz","kapi":"esik","esik":1.2}],
  "baglantilar": [
    {"kaynak":"n1","hedef":"n3","agirlik":1.0,"gecikme":1},
    {"kaynak":"n2","hedef":"n3","agirlik":1.0,"gecikme":2},
    {"kaynak":"n3","hedef":"n4","agirlik":1.0}]}
```

Ateşleme:

```
tik 0  ● n1  fikir   Hedef: balkonda yetiştirenler   (uyaran)
tik 2  ● n2  dosya   kum/kompost/notlar.md   READ ALLOW
tik 4  ● n3  kural   VE (1.0 + 1.0 = 2.0 ≥ 1.5)
tik 5  ○ n4  çıktı   EŞİK (1.0 < 1.2) — ateşlemedi, sessiz kaldı
```

Modele giden blok:

```
## Ağ okuması: kompost-rehberi — 3 düğüm sırayla ateşledi
Düğümler ağın mantığına göre sırayla getirildi. 1 düğüm sessiz kaldı;
içerikleri BURADA YOK, ağda olmadıkları anlamına gelmez.

1. [fikir] Hedef: balkonda yetiştirenler (tik 0)
…

2. [dosya] notlar.md — kum/kompost/notlar.md (tik 2)
<untrusted_content source="ag:kum/kompost/notlar.md">
# Notlar
…
</untrusted_content>

3. [kural] Başlıklar ## ile (tik 4)
…
```

---

## 4. Modele ne katıyor?

Dürüst olmak gerekirse bu bir "akıl yürütme" mekanizması değil; bir **bağlam
mühendisliği** aracı. Somut katkıları:

1. **Sıra taşır.** Düz bir dosya listesi sırasızdır; ağ, "önce niyet, sonra
   veri, sonra kural, en sonda çıktı hedefi" gibi bir sırayı *veri yapısına*
   gömer ve her koşuda aynı sırayı üretir. Sıra, dil modellerinde ölçülebilir
   biçimde etkilidir (öncelik/tazelik etkileri).
2. **Koşullu bağlam.** "Bu kuralı yalnızca şu iki kaynak da geldiyse ekle" (VE),
   "şu risk baloncuğu yandıysa çıktıyı bastır" (negatif ağırlık) gibi kurallar
   prompt içinde doğal dille anlatılmak yerine **dışarıda, deterministik olarak**
   çözülür. Model koşulu yorumlamaz; koşul zaten çözülmüş halde gelir.
3. **Bağlamı kısar.** Sessiz kalan baloncukların içeriği hiç gönderilmez.
   Büyük bir bilgi tabanından o göreve ait olan kesiti seçmenin ucuz ve
   tekrarlanabilir bir yolu.
4. **Tekrar edilebilirlik.** Aynı ağ + aynı uyaran = aynı bağlam. Bu, prompt
   değişkenliğini azaltır ve A/B denemesini mümkün kılar.
5. **Maliyet.** Seçim aşamasında model çağrısı yok. (Karşılaştırma: gömme
   tabanlı RAG'de seçim için ayrı bir model/indeks gerekir.)
6. **Şeffaflık.** Kullanıcı bağlamın neden o hale geldiğini **görür**:
   3B tuvalde baloncuklar sırayla yanar, aksonda ışık ilerler, eşiği geçemeyen
   sönük kalır. "Model şunu neden bilmiyordu?" sorusunun cevabı gözle bulunur.
7. **Ajan ağı büyütebilir.** `ag_dugum_ekle` / `ag_baglanti_ekle` ile model
   bulgularını ağa geri yazar (onay kartıyla) — yani ağ, oturumlar arası
   yapılandırılmış bir belleğe dönüşebilir.

### Ne DEĞİL

- Bir sinir ağı **eğitimi** değil: ağırlıklar öğrenilmez, kullanıcı yazar.
- Bir gömme/benzerlik araması değil: seçim anlamsal değil **topolojiktir**.
- Bir zincir-düşünce (CoT) mekanizması değil: model burada düşünmez, yalnızca
  derlenmiş bağlamı okur.

---

## 5. Güvenlik: kapı korunuyor

- **Dosya baloncuğu** içeriğini normal okuma kararıyla alır. `yol_dogrula`
  ALLOW demezse düğüm **ateşlemez**; "engellenen" listesine gerekçesiyle girer
  ve arayüzde kırmızı kesik halkayla işaretlenir. ASK de ateşletmez: yayılımın
  ortasında onay sorulmaz (deny by default).
- Dosya içeriği `<untrusted_content source="ag:…">` sarmalında gider. Ağdaki
  bir baloncuk "şu dosyayı sil" yazsa bile kapı aynı kapıdır; metin izin vermez.
- Ağ dosyaları `~/.vekil/aglar/<ad>.json` altında, yani **ajanın yazma kökünde
  değil**. Ajan `write_file` ile bir ağı ya da bir dosya düğümünün yolunu
  değiştiremez; tek yol araçlar ve onların onay kartıdır.
- Şema doğrulama fail-closed: bozuk ağ yüklenmez/kaydedilmez, sebebi söylenir.
- Testler bunları açıkça ölçer: okuma kökü dışı ve kara liste dosyalarının
  içeriği çıktıya **sızmıyor**; politika verilmezse hiçbir dosya düğümü
  ateşlemiyor.

---

## 6. Araçlar (modele görünen yüzey)

| Araç | Risk | Ne yapar |
|---|---|---|
| `ag_listele` | READ | kayıtlı ağlar, düğüm/bağlantı sayısı |
| `ag_oku` | READ | ağı ateşler, sırayla okur (`uyaran`, `kip`) |
| `ag_dugum_ekle` | WRITE_HAFIF | baloncuk ekler/günceller |
| `ag_baglanti_ekle` | WRITE_HAFIF | bağlantı ekler/günceller |

`kip`: `tam` (içerikler), `ozet` (ilk 300 karakter), `baslik` (yalnızca
başlıklar). Paket `ag` olarak Araçlar panelinden kapatılabilir; `policy.toml`
satırları olmadan hiçbiri çalışmaz.

---

## 7. Arayüz

Sol raydaki **Ağ** düğmesi tam sayfa bir tuval açar. Üç boyut elle yazıldı —
dış kütüphane yok (uygulama çevrimdışı çalışmak ve uzak kaynak yüklememek
zorunda): konum `[x,y,z]`, iki açı döndürme, `k = FOV/(FOV+z)` perspektifi,
derinliğe göre sıralama ve solma. Boş alanı sürükle → döndür; baloncuğu
sürükle → taşı; tekerlek → yakınlaş. Kuvvet-yönelimli otomatik yerleştirme var.

Ateşlemede Python hesaplar, arayüz **oynatır**: her düğümün tik damgası vardır,
düğüm kendi tikinde yanar, aksonda ışık gecikme kadar yol alır, yanmamış düğüm
belirgin şekilde sönük kalır.

---

## 8. Bilinen sınırlar / bilerek yapılmayanlar

- **Ağırlıkları kullanıcı yazar.** Öğrenme, otomatik ayar, geri yayılım yok.
- **Refrakter sabit:** düğüm koşu başına bir kez ateşler; "n kez ateşlesin" ya
  da zamanla toparlanma yok.
- **Sızıntı yok** (yukarıda gerekçesi).
- **Tek koşu, tek yön.** Model ateşlemeyi okur; okuduktan sonra ağı yeniden
  ateşleyip bağlamı *daraltan* bir döngü yok.
- **Anlamsal seçim yok.** "Bu göreve benzeyen baloncukları uyar" diye bir şey
  yok; uyaran elle ya da kök düğümlerden seçilir.
- **Ağlar arası bağlantı yok**; her ağ kapalı bir dünya.
- **Sürüm/geçmiş yok:** ağın eski hali saklanmıyor.
- Arayüzde **arama/filtre yok**; 100+ düğümlü ağda gezinmek zorlaşır.

---

## 9. Değerlendirme soruları

Bu notu okuyan bir uzmandan asıl merak ettiklerimiz:

1. **Ateşleme modeli doğru soyutlama mı?** Ağırlık + eşik + gecikme + refrakter
   üçlüsü, "bağlam seçimi" problemi için yeterince ifade gücü olan ama
   kullanıcının kafasını karıştırmayacak bir set mi? Eksik olan temel bir
   ilkel var mı (ör. zaman penceresi, sönümlenme, sayaç düğümü)?
2. **Sızıntısızlık ve tek-ateşleme kararları** pratikte hangi durumlarda ters
   teper? Hangi gerçek senaryo bunlarla ifade edilemez?
3. **Modelin okuma metni** (bölüm 3'ün sonundaki blok) bir dil modeli için ideal
   biçimde mi? "Sessiz kaldı" uyarısı doğru bir denge mi, yoksa modeli olmayan
   bilgiyi aramaya mı itiyor? Başlıklar, tik damgaları, sıra numaraları
   yardımcı mı, gürültü mü?
4. **Uyaran seçimi.** Şu an elle ya da kök düğümlerden. Görev metninden otomatik
   uyaran çıkarmak (etiket eşleşmesi, anahtar kelime, gömme) mantıklı bir
   sonraki adım mı — yoksa determinizmi kaybetmeye değmez mi?
5. **Ajanın ağı büyütmesi** (`ag_dugum_ekle`) uzun vadede ağı çöplüğe çevirir
   mi? Budama/birleştirme için nasıl bir disiplin önerirsiniz?
6. **Karşılaştırma:** bu yaklaşım, klasik RAG ya da düz "dosya ekleri" karşısında
   hangi somut işlerde gerçekten daha iyi? Nerede gereksiz karmaşıklık?
7. **Anlaşılırlık:** mantık kapılarını ve eşikleri hiç programlama bilmeyen bir
   kullanıcı kurabilir mi? Arayüzde hangi kavram gizlenmeli, hangisi öne
   çıkmalı?

---

## 10. Kod haritası

| Dosya | İçerik |
|---|---|
| `pevrai/ag.py` | şema doğrulama, depo, yayılım motoru, okuma metni |
| `pevrai/araclar/ag_araclari.py` | dört araç |
| `pevrai/arayuz/ag.js` | 3B tuval, denetçi, ateşleme animasyonu |
| `pevrai/pencere.py` | köprü API'si (`ag_*`) |
| `tests/ag_testi.py` | motor: kapılar, izin, tavanlar, araçlar |
| `tests/ag_arayuz_testi.py` | arayüz: tuval, sürükleme, ateşleme, dar pencere |
| `docs/AG.md` | teknik belge (Türkçe) |
