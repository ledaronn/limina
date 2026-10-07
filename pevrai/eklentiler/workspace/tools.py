from ..schema import ID, REV, REFS, PAGE, text, array, choice, crud, tool

FIELDS = {"name": text("Proje adı", required=True), "description": text("Açıklama", 4000),
          "instructions": text("Proje amacı / talimatları", 6000), "root": text("İzinli proje klasörü", 2000, True),
          "references": REFS, "next_steps": array(text("Sonraki adım", 1000), "Sonraki adımlar", 30),
          "summary": text("Devam özeti", 4000)}
TASK_FIELDS = {"workspace_id": ID, "title": text("Görev başlığı", required=True), "description": text("Açıklama", 4000),
               "status": choice("todo in_progress completed blocked", "Durum")}
TOOLS = crud("workspace", "Workspace", FIELDS, ["name", "root"]) + crud("task", "Görev", TASK_FIELDS, ["workspace_id", "title"], {"workspace_id": ID, "status": TASK_FIELDS["status"]}) + [
    tool("workspace_context", "Projeye devam etmek için sınırlı bağlamı oku: özet, görevler, referanslar, dosyalar, son günlük. Dosya içerikleri ayrıca mevcut dosya araçlarıyla okunur.", {"id": ID, **PAGE}, ["id"]),
    tool("workspace_attach", "İzinli dosya/klasörü göreli referans olarak projeye bağla; içerik kopyalanmaz.",
         {"id": ID, "path": text("Dosya/klasör yolu (proje köküne göre göreli olabilir)", 2000, True), "kind": choice("file folder artifact"), "label": text("Açıklama"), "expected_revision": REV}, ["id", "path", "kind", "expected_revision"], "WRITE"),
    tool("workspace_detach", "Dosya referansını kaldır; dosyayı silmez.", {"id": ID, "file_id": ID, "expected_revision": REV}, ["id", "file_id", "expected_revision"], "WRITE"),
    tool("workspace_resolve", "Dosya referansını güncel izinlerle doğrula ve mevcut dosya araçları için yolunu döndür.", {"id": ID, "file_id": ID, "mode": choice("read write")}, ["id", "file_id", "mode"]),
    tool("workspace_note_link", "Smart Notes kimliğini projeye bağla/kaldır. Notes kapalıyken de referans saklanır.",
         {"id": ID, "note_id": ID, "remove": {"type": "boolean"}, "expected_revision": REV}, ["id", "note_id", "expected_revision"], "WRITE"),
    tool("workspace_log", "Proje çalışma günlüğüne değiştirilemeyen kısa ilerleme kaydı ekle.",
         {"id": ID, "message": text("Yapılan işlem", 2000, True), "category": choice("progress decision blocker output")}, ["id", "message"], "WRITE"),
    tool("workspace_log_list", "Proje çalışma günlüğünü sayfalı oku.", {"id": ID, **PAGE}, ["id"]),
]
