"""araclar/dosya.py — dosya sistemi araclari: cekirdek okuma, belge okuma, dosya duzenleme.

Her arac TEK bildirim (@arac): modele giden aciklama, sema, risk, hangi
argumanin yol oldugu, hangi pakete ait oldugu, panelde gorunen ad. Fonksiyon
imzasi (yol, args) -> str: `yol` kapinin dogruladigi cozumlenmis yol (yol
argumani olmayan araclarda None), donus HER ZAMAN metin.
"""
from __future__ import annotations
from pevrai.sonuc import hata as sonuc_hatasi

import shutil
from pathlib import Path

from pevrai import ara, belge, journal
from pevrai.araclar.kayit import arac
from pevrai.araclar.ortak import MAX_SATIR, bulunamadi, journal_yaz, kirp
from pevrai.baglam import B
from pevrai.ceviri import t

# ---------------------------------------------------------------------------
# cekirdek: okuma
# ---------------------------------------------------------------------------

@arac(ad="list_dir", paket="cekirdek", risk="READ", okuyan=True,
      baslik="Klasör listeleme", aciklama="Bir klasördeki dosya ve alt klasörleri ad ve boyutla listeler.",
      modele="Bir klasördeki dosya ve alt klasörleri ad ve boyutla listeler. İçerik okumaz.",
      yollar={"path": "oku"},
      sema={"type": "object", "properties": {"path": {"type": "string", "description": "Tam klasör yolu."}},
            "required": ["path"]})
def list_dir(yol: Path, args: dict) -> str:
    if not yol.exists():
        return bulunamadi(yol)
    if not yol.is_dir():
        return sonuc_hatasi(t("'{yol}' bir klasör değil, dosya. İçeriği için read_file kullan.", yol=yol))

    # Kara listedekiler LISTELENMEZ: bir dosyanın varlığı da sızıntıdır.
    # Gizlemek yerine kaç tane gizlendiğini söylüyoruz: modelin "dosya yok"
    # sanıp aramaya devam etmesi, sessiz eksiklikten daha kötü.
    satirlar = []
    gizlenen = 0
    for p in sorted(yol.iterdir()):
        if B.politika._yasakli_mi(p):
            gizlenen += 1
            continue
        try:
            tur = t("KLASÖR") if p.is_dir() else t("{bayt} bayt", bayt=p.stat().st_size)
        except OSError:
            tur = t("(erişilemedi)")
        satirlar.append(f"{p.name}\t{tur}")

    govde = "\n".join(satirlar) or t("(klasör boş)")
    if gizlenen:
        govde += "\n\n" + t("[{sayi} öge kara liste nedeniyle gizlendi (kimlik bilgisi kalıbı). "
                            "Bunlara erişilemez, sorma.]", sayi=gizlenen)
    return kirp(govde, len(satirlar))


@arac(ad="read_file", paket="cekirdek", risk="READ", okuyan=True,
      baslik="Dosya okuma", aciklama="Metin dosyasının içeriğini okur (uzun dosyada ilk 400 satır).",
      modele=("Metin dosyasının içeriğini okur; bir seferde en fazla 400 satır. Uzun dosyada "
              "devamı için start_line ver (çıktının sonunda hangi satırda kaldığı yazar). "
              "Klasörlerde ve resim/video gibi ikili dosyalarda kullanma."),
      yollar={"path": "oku"},
      sema={"type": "object", "properties": {
                "path": {"type": "string", "description": "Tam dosya yolu."},
                "start_line": {"type": "integer", "description": "Başlangıç satırı (1'den başlar, varsayılan 1)."}},
            "required": ["path"]})
def read_file(yol: Path, args: dict) -> str:
    if not yol.exists():
        return bulunamadi(yol)
    if yol.is_dir():
        return sonuc_hatasi(t("'{yol}' bir klasör. Dosya listesi için list_dir kullan.", yol=yol))
    try:
        # Boyut siniri: 2 GB'lik bir dosyayi bellege alip 400 satirini tutmak
        # yerine hic okuma; model daha kucuk bir hedef secsin.
        boyut = yol.stat().st_size
        if boyut > 50 * 1024 * 1024:
            return sonuc_hatasi(t("'{yol}' çok büyük ({mb} MB); read_file en fazla 50 MB okur.",
                     yol=yol, mb=boyut // (1024 * 1024)))
        metin = yol.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return sonuc_hatasi(t("'{yol}' okunamadı: {hata}", yol=yol, hata=e))

    satirlar = metin.splitlines()
    try:
        bas = max(1, int(args.get("start_line") or 1))
    except (TypeError, ValueError):
        bas = 1
    if bas > len(satirlar) and satirlar:
        return sonuc_hatasi(t("'{yol}' {toplam} satır; start_line={bas} dosyanın dışında.",
                 yol=yol, toplam=len(satirlar), bas=bas))
    parca = satirlar[bas - 1:bas - 1 + MAX_SATIR]
    metin = "\n".join(parca)
    son = bas - 1 + len(parca)
    if son < len(satirlar):
        metin += "\n" + t("[... {bas}-{son}. satırlar gösterildi, dosyada toplam {toplam} satır var; "
                          "devamı için start_line={sonraki}]",
                          bas=bas, son=son, toplam=len(satirlar), sonraki=son + 1)
    elif bas > 1:
        metin += "\n" + t("[... {bas}-{son}. satırlar gösterildi (dosyanın sonu), toplam {toplam} satır]",
                          bas=bas, son=son, toplam=len(satirlar))
    return kirp(metin, len(satirlar))


@arac(ad="search", paket="cekirdek", risk="READ", okuyan=True,
      baslik="Arama", aciklama="Dosya adında ve düz metin dosyalarının içeriğinde arar.",
      modele=("Bir klasorde ve alt klasorlerinde arama yapar: dosya ADLARINDA ve duz metin "
              "dosyalarinin ICERIGINDE. PDF/DOCX/PPTX icerigini TARAMAZ — o dosyalarda sadece "
              "ad eslesir. Cok sayida dosya arasindan dogru olani bulmak icin kullan; "
              "tek bir klasoru listelemek icin list_dir daha uygundur."),
      yollar={"path": "oku"},
      sema={"type": "object", "properties": {
                "path": {"type": "string", "description": "Aramanin baslayacagi klasorun tam yolu."},
                "query": {"type": "string", "description": "Aranacak kelime veya ifade."},
                "glob": {"type": "string", "description": "Dosya deseni, orn '*.pdf'. Varsayilan '*'."}},
            "required": ["path", "query"]})
def search(yol: Path, args: dict) -> str:
    sorgu = args.get("query")
    if not sorgu:
        return sonuc_hatasi(t("search için 'query' argümanı zorunlu."))
    if not yol.exists() or not yol.is_dir():
        return sonuc_hatasi(t("'{yol}' geçerli bir klasör değil. Arama kökü bir klasör olmalı.", yol=yol))
    # Kara liste ARAMAYA da uygulanir: kapi yalnizca koku denetliyor,
    # kokun altindaki dosyalari bu arac kendisi okuyor (bkz. ara.ara).
    sonuc = ara.ara(yol, sorgu, args.get("glob", "*"), yasakli=B.politika._yasakli_mi)
    return kirp(sonuc, sonuc.count("\n"))


@arac(ad="degisiklik_gecmisi", paket="cekirdek", risk="READ",
      baslik="Değişiklik geçmişi", aciklama="Ajanın daha önce hangi dosyaları değiştirdiğini listeler.",
      modele=("Bu ajanın daha önce hangi dosyaları oluşturduğunu veya değiştirdiğini listeler. "
              "Dosya İÇERİĞİNİ göstermez, sadece yol/zaman/boyut. İçerik için read_file kullan. "
              "Kullanıcı 'ne değiştirdin', 'az önce ne yaptın' gibi bir şey sorduğunda buna bak."),
      sema={"type": "object", "properties": {"adet": {"type": "integer", "description": "Kaç kayıt (varsayılan 20)."}}})
def degisiklik_gecmisi(yol, args: dict) -> str:
    return journal.son_degisiklikler(int(args.get("adet", 20)))


# ---------------------------------------------------------------------------
# belge
# ---------------------------------------------------------------------------

@arac(ad="read_document", paket="belge", risk="READ", okuyan=True,
      baslik="Belge okuma",
      aciklama="PDF/DOCX/PPTX/XLSX/CSV içeriğini metin olarak çıkarır; görüntü ve taranmış PDF'de OCR (Windows).",
      modele=("PDF, DOCX, PPTX, XLSX, TXT, MD, CSV ya da GÖRÜNTÜ (PNG/JPG/ekran görüntüsü) dosyasının "
              "içeriğini metin olarak okur. Bir belgenin ne hakkında olduğunu anlamak için kullan — "
              "dosyayı adlandırmadan veya sınıflandırmadan önce. Görüntülerde ve metin katmanı olmayan "
              "(taranmış) PDF sayfalarında OCR uygular; OCR metni '[OCR]' ile işaretlenir ve hatalı "
              "karakter içerebilir. Dosyayı değiştirmez, dönüştürmez."),
      yollar={"path": "oku"},
      sema={"type": "object", "properties": {
                "path": {"type": "string", "description": "Tam dosya yolu."},
                "start_page": {"type": "integer", "description": "PDF icin baslangic sayfasi (varsayilan 1)."},
                "end_page": {"type": "integer", "description": "PDF icin bitis sayfasi. 0 = sona kadar."}},
            "required": ["path"]})
def read_document(yol: Path, args: dict) -> str:
    if not yol.exists():
        return bulunamadi(yol)
    if yol.is_dir():
        return sonuc_hatasi(t("'{yol}' bir klasör. Dosya listesi için list_dir kullan.", yol=yol))
    metin = belge.oku(yol, int(args.get("start_page", 1)), int(args.get("end_page", 0)))
    return kirp(metin, metin.count("\n"))


# ---------------------------------------------------------------------------
# dosya duzenleme
# ---------------------------------------------------------------------------

@arac(ad="write_file", paket="dosya_duzenleme", risk="WRITE",
      baslik="Dosya yazma", aciklama="Dosya oluşturur ya da tam içeriğini değiştirir; önce yedek alır.",
      modele=("Bir metin dosyası oluşturur veya VAR OLANIN ÜZERİNE YAZAR. Kısmi düzenleme yapmaz — "
              "mevcut bir dosyayı değiştireceksen önce read_file ile oku, tam yeni içeriği yaz. "
              "Sadece yazma izinli klasörlere yazabilirsin (sistem talimatında listeli). Klasör oluşturamaz."),
      yollar={"path": "yaz"},
      sema={"type": "object", "properties": {
                "path": {"type": "string", "description": "Tam dosya yolu."},
                "content": {"type": "string", "description": "Dosyanın yeni TAM içeriği."}},
            "required": ["path", "content"]})
def write_file(yol: Path, args: dict) -> str:
    icerik = args.get("content")
    if icerik is None:
        return sonuc_hatasi(t("write_file için 'content' argümanı zorunlu. Dosyanın YENİ TAM içeriğini ver."))
    if not yol.parent.exists():
        return sonuc_hatasi(t("'{klasor}' klasörü yok. Önce var olan bir klasör seç ya da mkdir ile oluştur.",
                 klasor=yol.parent))

    vardi = yol.exists()
    yedek = journal.yedekle(yol)          # üzerine yazmadan ÖNCE yedek
    try:
        yol.write_text(icerik, encoding="utf-8")
    except OSError as e:
        return sonuc_hatasi(t("'{yol}' yazılamadı: {hata}", yol=yol, hata=e))

    journal_yaz({
        "tip": "yazma",
        "yol": str(yol),
        "yedek": yedek,
        "bayt": len(icerik.encode("utf-8")),
        "uzerine_yazildi": vardi,
    })
    durum = t("üzerine yazıldı") if vardi else t("oluşturuldu")
    return t("'{yol}' {durum} ({bayt} bayt). Geri almak için: python -m pevrai.vekil_v0 --geri-al",
             yol=yol, durum=durum, bayt=len(icerik.encode("utf-8")))


@arac(ad="move", paket="dosya_duzenleme", risk="WRITE_HAFIF",
      baslik="Taşıma", aciklama="Dosyayı başka bir klasöre taşır; hedefte dosya varsa üzerine yazmaz.",
      modele=("Bir DOSYAYI başka bir yola taşır. Kaynak ve hedefin ikisi de yazma izinli "
              "klasörlerde olmalı. Klasör taşımaz. Hedefte aynı adda dosya varsa "
              "üzerine yazmaz, hata döndürür. Sadece adını değiştireceksen rename kullan."),
      yollar={"path": "yaz", "dst": "yaz"},
      sema={"type": "object", "properties": {
                "path": {"type": "string", "description": "Taşınacak dosyanın tam yolu."},
                "dst": {"type": "string", "description": "Hedefin tam yolu, dosya adı dahil."}},
            "required": ["path", "dst"]})
def move(yol: Path, args: dict) -> str:
    hedef_ham = args.get("dst")
    if not hedef_ham:
        return sonuc_hatasi(t("move için 'dst' argümanı zorunlu (hedef tam yol)."))
    if not yol.exists():
        return bulunamadi(yol)
    if yol.is_dir():
        return sonuc_hatasi(t("'{yol}' bir klasör. move sadece dosyalarda çalışır. Klasör adı için rename kullan.", yol=yol))

    hedef = Path(hedef_ham).expanduser()
    if hedef.exists():
        return sonuc_hatasi(t("'{hedef}' zaten var. Üzerine yazmıyorum. Başka bir ad seç, ya da "
                 "önce mevcut dosyayı trash ile çöpe at.", hedef=hedef))
    if not hedef.parent.exists():
        return sonuc_hatasi(t("'{klasor}' klasörü yok. Var olan bir hedef seç ya da mkdir ile oluştur.",
                 klasor=hedef.parent))

    try:
        shutil.move(str(yol), str(hedef))
    except OSError as e:
        return sonuc_hatasi(t("Taşınamadı: {hata}", hata=e))

    journal_yaz({"tip": "tasima", "islem": "tasindi", "yol": str(yol), "yeni_yol": str(hedef)})
    return t("'{yol}' -> '{hedef}' taşındı. Geri almak için: --geri-al {ad}", yol=yol, hedef=hedef, ad=hedef.name)


@arac(ad="rename", paket="dosya_duzenleme", risk="WRITE_HAFIF",
      baslik="Yeniden adlandırma", aciklama="Dosya ya da klasörün yalnızca adını değiştirir.",
      modele=("Bir dosya veya klasörün ADINI değiştirir, yerinde kalır. Başka klasöre "
              "taşımak için move kullan. new_name sadece yeni addır, yol değil."),
      yollar={"path": "yaz"},
      sema={"type": "object", "properties": {
                "path": {"type": "string", "description": "Mevcut tam yol."},
                "new_name": {"type": "string", "description": "Yeni ad, yol içermez. Örn: 'rapor_v2.txt'"}},
            "required": ["path", "new_name"]})
def rename(yol: Path, args: dict) -> str:
    yeni_ad = args.get("new_name")
    if not yeni_ad:
        return sonuc_hatasi(t("rename için 'new_name' argümanı zorunlu (sadece yeni ad, yol değil)."))
    if any(c in yeni_ad for c in r'\/:*?"<>|'):
        return sonuc_hatasi(t("'{ad}' geçersiz ad. Yol ayracı veya özel karakter içeremez, sadece yeni ad ver.", ad=yeni_ad))
    if not yol.exists():
        return bulunamadi(yol)

    hedef = yol.parent / yeni_ad
    if hedef.exists():
        return sonuc_hatasi(t("'{hedef}' zaten var. Başka bir ad seç.", hedef=hedef))

    try:
        yol.rename(hedef)
    except OSError as e:
        return sonuc_hatasi(t("Adı değiştirilemedi: {hata}", hata=e))

    tur = t("klasör") if hedef.is_dir() else t("dosya")
    journal_yaz({"tip": "tasima", "islem": "ad degisti", "yol": str(yol), "yeni_yol": str(hedef)})
    return t("{tur} adı değişti: '{eski}' -> '{yeni}'. Geri almak için: --geri-al {yeni}",
             tur=tur, eski=yol.name, yeni=yeni_ad)


@arac(ad="trash", paket="dosya_duzenleme", risk="DESTRUCTIVE",
      baslik="Çöpe taşıma", aciklama="Dosyayı Pevrai'nın çöp klasörüne taşır; kalıcı silmez.",
      modele=("Bir DOSYAYI çöp klasörüne taşır. Kalıcı silme aracı yoktur; dosya geri "
              "getirilebilir. Klasör silmez. Bir dosyanın içeriğini temizlemek için bunu "
              "kullanma — kullanıcı silmeyi açıkça istediyse kullan."),
      yollar={"path": "yaz"},
      sema={"type": "object", "properties": {"path": {"type": "string", "description": "Çöpe atılacak dosyanın tam yolu."}},
            "required": ["path"]})
def trash(yol: Path, args: dict) -> str:
    if not yol.exists():
        return bulunamadi(yol)
    if yol.is_dir():
        return sonuc_hatasi(t("'{yol}' bir klasör. trash sadece dosyalarda çalışır; klasörleri kullanıcı elle siler.", yol=yol))

    hedef = journal.cope_tasi(yol)
    journal_yaz({"tip": "tasima", "islem": "cope atildi", "yol": str(yol), "yeni_yol": str(hedef)})
    return t("'{yol}' çöpe taşındı ({hedef}). Kalıcı silinmedi. Geri almak için: --geri-al {ad}",
             yol=yol, hedef=hedef, ad=yol.name)


@arac(ad="edit_file", paket="dosya_duzenleme", risk="WRITE",
      baslik="Dosya düzenleme", aciklama="Dosyada bir metin parçasını başka bir metinle değiştirir; tam eşleşme ister, önce yedek alır.",
      modele=("Bir metin dosyasında KÜÇÜK bir değişiklik yapar: old_text'i new_text ile değiştirir. "
              "old_text dosyada TAM OLARAK BİR KEZ geçmeli — geçmiyorsa ya da birden fazla geçiyorsa "
              "hata döner, o zaman daha fazla bağlam ekle (çevre satırları). Dosyanın tamamını yeniden "
              "yazmaz; büyük değişiklik için write_file kullan. Önce read_file ile oku ki old_text birebir olsun."),
      yollar={"path": "yaz"},
      sema={"type": "object", "properties": {
                "path": {"type": "string", "description": "Tam dosya yolu."},
                "old_text": {"type": "string", "description": "Değişecek metin, dosyadaki haliyle birebir (girinti dahil)."},
                "new_text": {"type": "string", "description": "Yerine gelecek metin. Silmek için boş bırak."}},
            "required": ["path", "old_text", "new_text"]})
def edit_file(yol: Path, args: dict) -> str:
    eski_metin = args.get("old_text")
    yeni_metin = args.get("new_text")
    if eski_metin is None or yeni_metin is None:
        return sonuc_hatasi(t("edit_file için 'old_text' ve 'new_text' zorunlu."))
    if not eski_metin:
        return sonuc_hatasi(t("old_text boş olamaz: neyin değişeceğini söyle (ekleme için çevresindeki satırları da ver)."))
    if not yol.exists():
        return bulunamadi(yol)
    if yol.is_dir():
        return sonuc_hatasi(t("'{yol}' bir klasör; edit_file dosyalarda çalışır.", yol=yol))
    try:
        icerik = yol.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return sonuc_hatasi(t("'{yol}' UTF-8 metin değil; edit_file ikili dosyalarda çalışmaz.", yol=yol))
    except OSError as e:
        return sonuc_hatasi(t("'{yol}' okunamadı: {hata}", yol=yol, hata=e))

    sayi = icerik.count(eski_metin)
    if sayi == 0:
        return sonuc_hatasi(t("old_text dosyada bulunamadı. Metin birebir aynı olmalı (boşluk, girinti, satır sonu dahil). "
                 "read_file ile dosyayı oku ve tam parçayı kopyala."))
    if sayi > 1:
        return sonuc_hatasi(t("old_text dosyada {sayi} kez geçiyor; hangisi olduğu belirsiz. Çevresindeki satırları "
                 "da ekleyerek old_text'i TEK eşleşecek kadar büyüt.", sayi=sayi))
    yeni_icerik = icerik.replace(eski_metin, yeni_metin, 1)
    yedek = journal.yedekle(yol)          # değiştirmeden ÖNCE yedek
    try:
        yol.write_text(yeni_icerik, encoding="utf-8")
    except OSError as e:
        return sonuc_hatasi(t("'{yol}' yazılamadı: {hata}", yol=yol, hata=e))
    journal_yaz({
        "tip": "yazma", "yol": str(yol), "yedek": yedek,
        "bayt": len(yeni_icerik.encode("utf-8")), "uzerine_yazildi": True, "islem": "duzenlendi",
    })
    eski_satir, yeni_satir = eski_metin.count("\n") + 1, (yeni_metin.count("\n") + 1 if yeni_metin else 0)
    return t("'{yol}' düzenlendi: {eski} satır -> {yeni} satır ({bayt} bayt). Geri almak için: --geri-al {ad}",
             yol=yol, eski=eski_satir, yeni=yeni_satir, bayt=len(yeni_icerik.encode("utf-8")), ad=yol.name)


@arac(ad="mkdir", paket="dosya_duzenleme", risk="WRITE_HAFIF",
      baslik="Klasör oluşturma", aciklama="Yazma kökleri altında yeni bir klasör oluşturur (ara klasörler dahil).",
      modele=("Yeni bir klasör oluşturur (ara klasörler de oluşturulur). Yalnızca yazma izinli "
              "klasörlerin altında. Klasör zaten varsa hata vermez, bunu söyler. Dosya oluşturmaz — "
              "dosya için write_file."),
      yollar={"path": "yaz"},
      sema={"type": "object", "properties": {"path": {"type": "string", "description": "Oluşturulacak klasörün tam yolu."}},
            "required": ["path"]})
def mkdir(yol: Path, args: dict) -> str:
    if yol.exists():
        if yol.is_dir():
            return t("'{yol}' zaten var, dokunulmadı.", yol=yol)
        return sonuc_hatasi(t("'{yol}' bir dosya; aynı adla klasör oluşturulamaz.", yol=yol))
    # En üstteki YENİ klasör kaydedilir: geri alma o noktadan aşağıyı (boşsa) kaldırır.
    ilk_yeni = yol
    while not ilk_yeni.parent.exists() and ilk_yeni.parent != ilk_yeni:
        ilk_yeni = ilk_yeni.parent
    try:
        yol.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return sonuc_hatasi(t("'{yol}' oluşturulamadı: {hata}", yol=yol, hata=e))
    journal_yaz({"tip": "klasor", "islem": "klasor olusturuldu", "yol": str(ilk_yeni)})
    return t("'{yol}' oluşturuldu. Geri almak için (boşsa): --geri-al {ad}", yol=yol, ad=ilk_yeni.name)
