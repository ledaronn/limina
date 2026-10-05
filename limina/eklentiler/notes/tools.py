from ..schema import ID, REV, TAGS, REFS, PAGE, text, number, crud, tool

FIELDS = {"title": text("Başlık", required=True), "body": text("Not metni", 50000), "tags": TAGS,
          "references": REFS, "archived": {"type": "boolean", "description": "Arşivlendi"}}
TOOLS = crud("note", "Not", FIELDS, ["title"], {"archived": {"type": "boolean"}, "deleted": {"type": "boolean"}}) + [
    tool("note_read", "Uzun not gövdesini kayıpsız parçalarla oku. Gövdeyi değiştirmeden önce bütün parçaları oku; note_get/list uzun metni kısaltabilir.",
         {"id": ID, "offset": number("Karakter başlangıcı", 0, 50000), "length": number("Parça uzunluğu", 1, 6000)}, ["id"]),
    tool("note_search", "Başlık, gövde ve etiketlerde tam metin ara; tüm sözcükleri içeren aktif notları döndür.",
         {"query": text("Aranacak sözcükler", 300, True), "scope": {"type": "string", "enum": ["active", "archived", "deleted"]}, **PAGE}, ["query"]),
    tool("note_link", "Bir nota başka not bağlantısı ekle veya kaldır.",
         {"id": ID, "target_id": ID, "remove": {"type": "boolean"}, "expected_revision": REV}, ["id", "target_id", "expected_revision"], "WRITE"),
    tool("note_archive", "Notu arşivle veya arşivden çıkar.", {"id": ID, "archived": {"type": "boolean"}, "expected_revision": REV}, ["id", "archived", "expected_revision"], "WRITE"),
    tool("note_history", "Notun önceki sürümlerini oku; silinen notlar dahil.", {"id": ID, **PAGE}, ["id"]),
    tool("note_restore", "Eski not sürümünü yeni sürüm olarak geri yükle; silmeyi geri alabilir.",
         {"id": ID, "revision": number("Geri yüklenecek sürüm", 1), "expected_revision": REV}, ["id", "revision", "expected_revision"], "WRITE"),
]
