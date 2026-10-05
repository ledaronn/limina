from ..schema import ID, REV, TAGS, DATE, TIME, REFS, PAGE, text, number, choice, crud, tool

FIELDS = {
    "course": {"name": text("Ders adı", required=True), "description": text("Açıklama", 4000), "tags": TAGS},
    "exam": {"name": text("Sınav adı", required=True), "course_id": ID, "at": TIME,
             "description": text("Açıklama", 4000), "priority": choice("low normal high", "Öncelik"),
             "status": choice("upcoming completed cancelled", "Durum")},
    "topic": {"name": text("Konu adı", required=True), "course_id": ID, "exam_id": ID,
              "progress": number("İlerleme (%)", 0, 100), "difficulty": number("Zorluk (1–5)", 1, 5), "note": text("Not", 4000)},
    "study_plan": {"date": DATE, "course_id": ID, "topic_id": ID, "minutes": number("Planlanan dakika", 1, 1440),
                   "status": choice("planned completed skipped", "Durum"), "note": text("Plan notu", 4000)},
}
TOOLS = []
for kind, label, required in [("course", "Ders", ["name"]), ("exam", "Sınav", ["name", "course_id", "at"]),
                              ("topic", "Konu", ["name", "course_id"]), ("study_plan", "Çalışma planı", ["date", "course_id", "minutes"])]:
    filters = {k: v for k, v in FIELDS[kind].items() if k in ("course_id", "exam_id", "date", "status")}
    TOOLS += crud(kind, label, FIELDS[kind], required, filters)
LINKS = {"course_id": ID, "topic_id": ID, "references": REFS}
TOOLS += [
    tool("study_session_log", "Geçmiş çalışma oturumu ekle. Kayıtlar değiştirilemez; planlar ayrı tutulur.",
         {**LINKS, "start": TIME, "end": TIME, "type": choice("study review practice"), "completed": {"type": "boolean"}}, ["start", "end"], "WRITE"),
    tool("study_session_list", "Çalışma geçmişini oku.", {**PAGE, "course_id": ID}),
    tool("study_stats", "Günlük/haftalık gerçek çalışma süresi. Mola ve duraklama hariçtir.",
         {"date": DATE, "offset_minutes": {"type": "integer", "minimum": -720, "maximum": 840}}),
    tool("focus_start", "Kalıcı Pomodoro veya serbest odak başlat. Uygulama kapalıyken süre ilerler; aynı anda tek oturum.",
         {**LINKS, "mode": choice("pomodoro free"), "work_minutes": number("Çalışma (dakika)", 1, 240),
          "break_minutes": number("Mola (dakika)", 1, 120), "rounds": number("Tur sayısı", 1, 20)}, ["mode"], "WRITE"),
    tool("focus_status", "Odak durumunu zaman damgalarından hesapla; biten sayacı bir kez çalışma geçmişine kaydet.", {"id": ID}),
]
for action, label in [("pause", "Duraklat"), ("resume", "Devam ettir"), ("finish", "Bitir")]:
    TOOLS.append(tool("focus_" + action, label + ": kalıcı odak oturumu.", {"id": ID}, ["id"], "WRITE"))
