import os
import sys
import subprocess
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
from core_engine import DocumentConverter

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    CF_HDROP = 15


class DnDCTk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


class ConverterApp(DnDCTk):
    def __init__(self):
        super().__init__()

        self.converter = DocumentConverter()
        self.file_items = []
        self.is_processing = False
        self._next_id = 1

        self.title("Belge Dönüştürücü Studio Pro")
        self.geometry("960x740")
        self.minsize(880, 620)
        
        ctk.set_appearance_mode("dark")
        self.configure(fg_color="#0B0D13")

        self._build_ui()
        self._bind_global_events()
        self._refresh_file_view()

    def _bind_global_events(self):
        self.bind_all("<Control-v>", lambda e: self._on_paste())
        self.bind_all("<Control-V>", lambda e: self._on_paste())
        self._register_recursive_dnd(self)

    def _register_recursive_dnd(self, widget):
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass
        if hasattr(widget, "_canvas"):
            try:
                widget._canvas.drop_target_register(DND_FILES)
                widget._canvas.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass
        for child in widget.winfo_children():
            self._register_recursive_dnd(child)

    def _get_clipboard_files(self):
        files = []
        if sys.platform == "win32":
            try:
                if user32.OpenClipboard(None):
                    try:
                        h_drop = user32.GetClipboardData(CF_HDROP)
                        if h_drop:
                            count = shell32.DragQueryFileW(h_drop, 0xFFFFFFFF, None, 0)
                            for i in range(count):
                                length = shell32.DragQueryFileW(h_drop, i, None, 0)
                                buf = ctypes.create_unicode_buffer(length + 1)
                                shell32.DragQueryFileW(h_drop, i, buf, length + 1)
                                if buf.value:
                                    files.append(buf.value)
                    finally:
                        user32.CloseClipboard()
            except Exception:
                pass

        try:
            text = self.clipboard_get()
            if text:
                for line in text.splitlines():
                    clean = line.strip().strip('"').strip("'")
                    if os.path.exists(clean) and clean not in files:
                        files.append(clean)
        except Exception:
            pass

        return files

    def _on_paste(self):
        files = self._get_clipboard_files()
        if files:
            self._add_files_to_list(files)
        else:
            self.lbl_status.configure(text="Panoda geçerli bir dosya bulunamadı.")

    def _build_ui(self):
        # 1. ÜST HEADER
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(16, 8))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="⚡ Belge Dönüştürücü Studio",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#F8FAFC"
        ).pack(anchor="w")

        # İstatistik Hapları (Badges)
        stats_box = ctk.CTkFrame(title_box, fg_color="transparent")
        stats_box.pack(anchor="w", pady=(2, 0))

        self.pill_total = ctk.CTkLabel(
            stats_box, text="Toplam: 0", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#1E293B", text_color="#94A3B8", corner_radius=6, padx=8, pady=2
        )
        self.pill_total.pack(side="left", padx=(0, 6))

        self.pill_selected = ctk.CTkLabel(
            stats_box, text="Seçili: 0", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#1E3A8A", text_color="#93C5FD", corner_radius=6, padx=8, pady=2
        )
        self.pill_selected.pack(side="left", padx=(0, 6))

        self.pill_done = ctk.CTkLabel(
            stats_box, text="Tamamlanan: 0", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#064E3B", text_color="#6EE7B7", corner_radius=6, padx=8, pady=2
        )
        self.pill_done.pack(side="left")

        # Ekleme Butonları
        top_btn_box = ctk.CTkFrame(header, fg_color="transparent")
        top_btn_box.pack(side="right")

        ctk.CTkButton(
            top_btn_box, text="+ Dosya Seç", width=110, height=34, corner_radius=8,
            fg_color="#2563EB", hover_color="#1D4ED8", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._add_files_dialog
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            top_btn_box, text="+ Klasör", width=90, height=34, corner_radius=8,
            fg_color="#1E293B", hover_color="#334155", font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._add_dir_dialog
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            top_btn_box, text="📋 Yapıştır", width=90, height=34, corner_radius=8,
            fg_color="#1E293B", hover_color="#334155", font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._on_paste
        ).pack(side="left", padx=4)

        # 2. TOPLU İŞLEM VE ARAÇ ÇUBUĞU
        action_bar = ctk.CTkFrame(self, fg_color="#131722", corner_radius=8, border_width=1, border_color="#21283B")
        action_bar.pack(fill="x", padx=24, pady=(0, 6))

        self.var_select_all = ctk.BooleanVar(value=True)
        self.chk_select_all = ctk.CTkCheckBox(
            action_bar,
            text="Tümünü Seç",
            variable=self.var_select_all,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#E2E8F0",
            command=self._toggle_select_all
        )
        self.chk_select_all.pack(side="left", padx=(14, 16), pady=8)

        ctk.CTkLabel(
            action_bar, text="Toplu Hedef Belirle:", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#94A3B8"
        ).pack(side="left", padx=(0, 6))

        self.batch_target_menu = ctk.CTkOptionMenu(
            action_bar,
            values=["(Hedef Format Seçin)"] + self.converter.ALL_TARGET_FORMATS,
            width=150,
            height=28,
            corner_radius=6,
            fg_color="#1E293B",
            button_color="#3B82F6",
            command=self._apply_batch_target
        )
        self.batch_target_menu.pack(side="left", padx=(0, 10))

        self.btn_delete_selected = ctk.CTkButton(
            action_bar, text="Seçilenleri Sil", width=105, height=28, corner_radius=6,
            fg_color="transparent", hover_color="#3F1E24", text_color="#F87171", font=ctk.CTkFont(size=12),
            command=self._remove_selected_files
        )
        self.btn_delete_selected.pack(side="right", padx=(0, 10))

        self.btn_clear_all = ctk.CTkButton(
            action_bar, text="Tümünü Temizle", width=105, height=28, corner_radius=6,
            fg_color="transparent", hover_color="#27272A", text_color="#A1A1AA", font=ctk.CTkFont(size=12),
            command=self._clear_list
        )
        self.btn_clear_all.pack(side="right", padx=(0, 6))

        # 3. SABİT SÜTUNLU TABLO BAŞLIĞI (Grid Yapısı)
        table_header = ctk.CTkFrame(self, fg_color="#171C28", height=32, corner_radius=6)
        table_header.pack(fill="x", padx=24, pady=(2, 2))
        self._configure_grid_columns(table_header)

        ctk.CTkLabel(table_header, text="SEÇ", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#64748B").grid(row=0, column=0, padx=4)
        ctk.CTkLabel(table_header, text="TÜR", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#64748B").grid(row=0, column=1, padx=4)
        ctk.CTkLabel(table_header, text="DOSYA BİLGİSİ", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#64748B").grid(row=0, column=2, sticky="w", padx=8)
        ctk.CTkLabel(table_header, text="HEDEF FORMAT", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#64748B").grid(row=0, column=3, padx=6)
        ctk.CTkLabel(table_header, text="DURUM & İŞLEM", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#64748B").grid(row=0, column=4, padx=6)
        ctk.CTkLabel(table_header, text="", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#64748B").grid(row=0, column=5)

        # 4. MERKEZ KART (DOSYA LİSTESİ)
        self.center_card = ctk.CTkFrame(self, fg_color="#10131B", corner_radius=10, border_width=1, border_color="#1C2130")
        self.center_card.pack(fill="both", expand=True, padx=24, pady=(2, 8))

        # Boş Durum
        self.empty_frame = ctk.CTkFrame(self.center_card, fg_color="transparent")
        ctk.CTkLabel(self.empty_frame, text="📂", font=ctk.CTkFont(size=46)).pack(pady=(50, 10))
        ctk.CTkLabel(
            self.empty_frame,
            text="Dosyaları Buraya Bırakın veya Ctrl + V ile Yapıştırın",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#E2E8F0"
        ).pack()
        ctk.CTkLabel(
            self.empty_frame,
            text="PDF, PowerPoint, Word ve Görselleri çift yönlü dönüştürün",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#64748B"
        ).pack(pady=(4, 18))

        ctk.CTkButton(
            self.empty_frame,
            text="Dosyaları Seç",
            width=140,
            height=36,
            corner_radius=8,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            font=ctk.CTkFont(weight="bold"),
            command=self._add_files_dialog
        ).pack(pady=(0, 50))

        self.file_scroll = ctk.CTkScrollableFrame(self.center_card, fg_color="transparent")

        # 5. ALT PANEL: KAYIT YERİ & DOĞRUDAN KLASÖR AÇMA
        out_frame = ctk.CTkFrame(self, fg_color="#131722", corner_radius=8, border_width=1, border_color="#21283B")
        out_frame.pack(fill="x", padx=24, pady=(2, 6))

        ctk.CTkLabel(out_frame, text="📁 Kayıt Yeri:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#94A3B8").pack(side="left", padx=(14, 6))

        self.output_dir_var = ctk.StringVar(value="Kaynak dosyalar ile aynı klasöre kaydet")
        ctk.CTkEntry(
            out_frame, textvariable=self.output_dir_var, state="readonly",
            border_width=0, fg_color="transparent", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#CBD5E1"
        ).pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkButton(
            out_frame, text="📂 Klasörü Aç", width=95, height=26, corner_radius=6,
            fg_color="#1E293B", hover_color="#334155", font=ctk.CTkFont(size=11),
            command=self._open_output_folder
        ).pack(side="right", padx=(4, 10), pady=6)

        ctk.CTkButton(
            out_frame, text="Değiştir", width=70, height=26, corner_radius=6,
            fg_color="#1E293B", hover_color="#334155", font=ctk.CTkFont(size=11),
            command=self._select_output_dir
        ).pack(side="right", padx=(4, 2), pady=6)

        # 6. İLERLEME VE BAŞLATMA ALANI
        progress_container = ctk.CTkFrame(self, fg_color="transparent")
        progress_container.pack(fill="x", padx=24, pady=(2, 4))

        self.lbl_status = ctk.CTkLabel(progress_container, text="Hazır", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#64748B")
        self.lbl_status.pack(side="left")

        self.lbl_percentage = ctk.CTkLabel(progress_container, text="%0", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#10B981")
        self.lbl_percentage.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(self, height=6, corner_radius=3, fg_color="#1E293B", progress_color="#10B981")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=24, pady=(0, 8))

        self.btn_convert = ctk.CTkButton(
            self,
            text="⚡ Seçilen Dosyaları Dönüştür",
            height=44,
            corner_radius=8,
            fg_color="#10B981",
            hover_color="#059669",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self._start_conversion
        )
        self.btn_convert.pack(fill="x", padx=24, pady=(0, 16))

    def _configure_grid_columns(self, widget):
        """Tablo başlığı ve satırlar için ortak sütun genişlikleri."""
        widget.grid_columnconfigure(0, weight=0, minsize=44)   # Seçim Checkbox
        widget.grid_columnconfigure(1, weight=0, minsize=66)   # Tür Rozeti
        widget.grid_columnconfigure(2, weight=1)               # Dosya Bilgisi (Genişleyen)
        widget.grid_columnconfigure(3, weight=0, minsize=140)  # Hedef Format
        widget.grid_columnconfigure(4, weight=0, minsize=210)  # Durum / İşlem
        widget.grid_columnconfigure(5, weight=0, minsize=40)   # Silme Butonu

    def _get_format_badge(self, ext):
        badges = {
            ".pdf":  ("PDF", "#DC2626"),
            ".pptx": ("PPTX", "#EA580C"),
            ".ppt":  ("PPT", "#EA580C"),
            ".docx": ("DOCX", "#2563EB"),
            ".doc":  ("DOC", "#2563EB"),
            ".png":  ("PNG", "#9333EA"),
            ".jpg":  ("JPG", "#9333EA"),
            ".jpeg": ("JPEG", "#9333EA"),
            ".md":   ("MD", "#0D9488"),
            ".txt":  ("TXT", "#0D9488")
        }
        return badges.get(ext, (ext.upper().replace(".", ""), "#475569"))

    def _format_size(self, byte_count):
        kb = byte_count / 1024
        if kb < 1024:
            return f"{kb:.1f} KB"
        return f"{kb / 1024:.2f} MB"

    def _toggle_select_all(self):
        val = self.var_select_all.get()
        for item in self.file_items:
            item["selected"] = val
        self._refresh_file_view()

    def _apply_batch_target(self, choice):
        if choice == "(Hedef Format Seçin)":
            return

        target_ext = f".{choice.lower()}"
        updated = 0
        incompatible = 0

        for item in self.file_items:
            if item.get("selected", True):
                allowed = self.converter.get_supported_targets(item["path"])
                if target_ext in allowed:
                    item["target_ext"] = target_ext
                    updated += 1
                else:
                    incompatible += 1

        self.batch_target_menu.set("(Hedef Format Seçin)")
        self._refresh_file_view()

        msg = f"✓ {updated} dosyanın hedefi {choice} yapıldı."
        if incompatible > 0:
            msg += f" ({incompatible} dosya bu formatı desteklemiyor veya zaten aynı)"
        self.lbl_status.configure(text=msg)

    def _remove_selected_files(self):
        self.file_items = [it for it in self.file_items if not it.get("selected", False)]
        self._refresh_file_view()

    def _open_file(self, file_path):
        if file_path and os.path.exists(file_path):
            os.startfile(os.path.normpath(file_path))
        else:
            messagebox.showerror("Hata", "Dosya bulunamadı.")

    def _open_in_folder(self, file_path):
        if file_path:
            norm = os.path.normpath(file_path)
            if os.path.exists(norm):
                subprocess.run(f'explorer /select,"{norm}"')
                return
        messagebox.showerror("Hata", "Klasör bulunamadı.")

    def _open_output_folder(self):
        target_dir = self.output_dir_var.get()
        if target_dir == "Kaynak dosyalar ile aynı klasöre kaydet":
            if self.file_items:
                target_dir = os.path.dirname(self.file_items[0]["path"])
            else:
                target_dir = os.path.expanduser("~")
        if os.path.exists(target_dir):
            os.startfile(target_dir)

    def _refresh_file_view(self):
        for w in self.file_scroll.winfo_children():
            w.destroy()

        total = len(self.file_items)
        selected_count = sum(1 for it in self.file_items if it.get("selected", False))
        done_count = sum(1 for it in self.file_items if it.get("status") == "done")

        self.pill_total.configure(text=f"Toplam: {total}")
        self.pill_selected.configure(text=f"Seçili: {selected_count}")
        self.pill_done.configure(text=f"Tamamlanan: {done_count}")

        if total == 0:
            self.file_scroll.pack_forget()
            self.empty_frame.pack(fill="both", expand=True)
            self.btn_delete_selected.configure(state="disabled")
            self.btn_clear_all.configure(state="disabled")
            self.btn_convert.configure(state="disabled", text="⚡ Seçilen Dosyaları Dönüştür")
        else:
            self.empty_frame.pack_forget()
            self.file_scroll.pack(fill="both", expand=True, padx=4, pady=4)
            self.btn_delete_selected.configure(state="normal" if selected_count > 0 else "disabled")
            self.btn_clear_all.configure(state="normal")
            
            btn_text = f"⚡ Seçilen {selected_count} Dosyayı Dönüştür" if selected_count > 0 else "⚡ Dosya Seçiniz"
            self.btn_convert.configure(
                state="normal" if (selected_count > 0 and not self.is_processing) else "disabled",
                text=btn_text
            )

            for item in self.file_items:
                self._create_file_row(item)

        self.update_idletasks()
        self._register_recursive_dnd(self.center_card)

    def _create_file_row(self, item):
        file_path = item["path"]
        name = os.path.basename(file_path)
        src_ext = os.path.splitext(file_path)[1].lower()
        size_text = self._format_size(os.path.getsize(file_path)) if os.path.exists(file_path) else "0 KB"
        status = item.get("status", "ready")
        tag_text, tag_color = self._get_format_badge(src_ext)

        row = ctk.CTkFrame(self.file_scroll, fg_color="#151923", corner_radius=6, border_width=1, border_color="#202738")
        row.pack(fill="x", pady=2, padx=4)
        self._configure_grid_columns(row)

        # SÜTUN 0: Checkbox
        chk_var = ctk.BooleanVar(value=item.get("selected", True))
        def _on_chk_toggle():
            item["selected"] = chk_var.get()
            self._refresh_file_view()

        chk = ctk.CTkCheckBox(row, text="", width=24, variable=chk_var, command=_on_chk_toggle)
        chk.grid(row=0, column=0, padx=4, pady=8)

        # SÜTUN 1: Format Rozeti
        badge = ctk.CTkLabel(
            row, text=tag_text, width=50, height=22, corner_radius=4,
            fg_color=tag_color, font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color="#FFFFFF"
        )
        badge.grid(row=0, column=1, padx=4, pady=8)

        # SÜTUN 2: Dosya İsmi & Boyut
        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.grid(row=0, column=2, sticky="ew", padx=8, pady=6)

        display_name = name if len(name) <= 38 else name[:35] + "..."
        ctk.CTkLabel(text_frame, text=display_name, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#F8FAFC", anchor="w").pack(fill="x")
        ctk.CTkLabel(text_frame, text=size_text, font=ctk.CTkFont(family="Segoe UI", size=10), text_color="#64748B", anchor="w").pack(fill="x")

        # SÜTUN 3: Hedef Format Seçici
        targets = self.converter.get_supported_targets(file_path)
        options = [t.upper().replace(".", "") for t in targets]
        current_val = item["target_ext"].upper().replace(".", "")

        target_box = ctk.CTkFrame(row, fg_color="transparent")
        target_box.grid(row=0, column=3, padx=6, pady=8)

        ctk.CTkLabel(target_box, text="➔", font=ctk.CTkFont(size=12, weight="bold"), text_color="#64748B").pack(side="left", padx=(0, 4))

        def _on_target_change(choice, current_item=item):
            current_item["target_ext"] = f".{choice.lower()}"

        target_menu = ctk.CTkOptionMenu(
            target_box,
            values=options,
            width=90,
            height=26,
            corner_radius=5,
            fg_color="#1E293B",
            button_color="#3B82F6",
            command=_on_target_change
        )
        target_menu.set(current_val)
        target_menu.pack(side="left")

        # SÜTUN 4: Durum & Aksiyon Alanı
        status_box = ctk.CTkFrame(row, fg_color="transparent")
        status_box.grid(row=0, column=4, padx=6, pady=8)

        if status == "done":
            out_p = item.get("out_path", "")
            ctk.CTkLabel(status_box, text="✓ Tamam", font=ctk.CTkFont(size=11, weight="bold"), text_color="#10B981").pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                status_box, text="👁️ Aç", width=55, height=24, corner_radius=4,
                fg_color="#10B981", hover_color="#059669", font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda p=out_p: self._open_file(p)
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                status_box, text="📁 Klasör", width=65, height=24, corner_radius=4,
                fg_color="#1E293B", hover_color="#334155", font=ctk.CTkFont(size=11),
                command=lambda p=out_p: self._open_in_folder(p)
            ).pack(side="left", padx=2)

        elif status == "converting":
            ctk.CTkLabel(status_box, text="⏳ İşleniyor...", font=ctk.CTkFont(size=11, weight="bold"), text_color="#F59E0B").pack(side="left")

        elif status == "error":
            ctk.CTkLabel(status_box, text="⚠ Hata Oluştu", font=ctk.CTkFont(size=11, weight="bold"), text_color="#EF4444").pack(side="left")

        else:
            ctk.CTkLabel(status_box, text="Hazır", font=ctk.CTkFont(size=11), text_color="#64748B").pack(side="left")

        # SÜTUN 5: Tekli Silme Butonu
        ctk.CTkButton(
            row, text="✕", width=26, height=26, corner_radius=4,
            fg_color="transparent", hover_color="#2D3348", text_color="#94A3B8", font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda p=file_path: self._remove_single_file(p)
        ).grid(row=0, column=5, padx=(2, 6), pady=8)

    def _remove_single_file(self, file_path):
        self.file_items = [it for it in self.file_items if it["path"] != file_path]
        self._refresh_file_view()

    def _add_files_to_list(self, paths):
        existing = {it["path"] for it in self.file_items}
        added = False

        for p in paths:
            clean = p.strip('{}').strip('"').strip("'")
            if os.path.isfile(clean):
                targets = self.converter.get_supported_targets(clean)
                if targets and clean not in existing:
                    self.file_items.append({
                        "id": self._next_id,
                        "path": clean,
                        "target_ext": targets[0],
                        "selected": True,
                        "status": "ready",
                        "out_path": None,
                        "err_msg": ""
                    })
                    self._next_id += 1
                    existing.add(clean)
                    added = True
            elif os.path.isdir(clean):
                for root, _, files in os.walk(clean):
                    for file in files:
                        full = os.path.join(root, file)
                        targets = self.converter.get_supported_targets(full)
                        if targets and full not in existing:
                            self.file_items.append({
                                "id": self._next_id,
                                "path": full,
                                "target_ext": targets[0],
                                "selected": True,
                                "status": "ready",
                                "out_path": None,
                                "err_msg": ""
                            })
                            self._next_id += 1
                            existing.add(full)
                            added = True
        if added:
            self._refresh_file_view()

    def _on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        self._add_files_to_list(paths)

    def _add_files_dialog(self):
        files = filedialog.askopenfilenames(
            title="Dönüştürülecek Dosyaları Seç",
            filetypes=[
                ("Tüm Desteklenenler", "*.pptx;*.ppt;*.docx;*.md;*.txt;*.pdf;*.jpg;*.jpeg;*.png"),
                ("PDF Belgeleri", "*.pdf"),
                ("Sunumlar", "*.pptx;*.ppt"),
                ("Word Belgeleri", "*.docx"),
                ("Metin ve Markdown", "*.txt;*.md"),
                ("Görseller", "*.jpg;*.jpeg;*.png"),
                ("Tüm Dosyalar", "*.*")
            ]
        )
        if files:
            self._add_files_to_list(list(files))

    def _add_dir_dialog(self):
        folder = filedialog.askdirectory(title="Klasör Seç")
        if folder:
            self._add_files_to_list([folder])

    def _select_output_dir(self):
        folder = filedialog.askdirectory(title="Kayıt Klasörünü Belirle")
        if folder:
            self.output_dir_var.set(folder)

    def _clear_list(self):
        self.file_items.clear()
        self.progress_bar.set(0)
        self.lbl_percentage.configure(text="%0")
        self.lbl_status.configure(text="Liste temizlendi.")
        self._refresh_file_view()

    def _start_conversion(self):
        selected_items = [it for it in self.file_items if it.get("selected", False)]
        if self.is_processing or not selected_items:
            return

        self.is_processing = True
        self.btn_convert.configure(state="disabled", text="⏳ Dönüştürülüyor...", fg_color="#334155")
        self.progress_bar.set(0)
        self.lbl_percentage.configure(text="%0")

        target_dir = self.output_dir_var.get()
        if target_dir == "Kaynak dosyalar ile aynı klasöre kaydet":
            target_dir = None

        thread = threading.Thread(target=self._run_conversion, args=(selected_items, target_dir), daemon=True)
        thread.start()

    def _run_conversion(self, items_to_process, target_dir):
        total = len(items_to_process)
        success_count = 0

        for idx, item in enumerate(items_to_process, 1):
            file_path = item["path"]
            target_ext = item["target_ext"]
            name = os.path.basename(file_path)

            item["status"] = "converting"
            self._refresh_file_view()

            self.lbl_status.configure(text=f"İşleniyor ({idx}/{total}): {name} ➔ {target_ext.upper()}")
            res = self.converter.convert_file(file_path, target_ext=target_ext, output_dir=target_dir)

            if res["success"]:
                item["status"] = "done"
                item["out_path"] = res["target"]
                success_count += 1
            else:
                item["status"] = "error"
                item["err_msg"] = res["error"] or "Hata"

            progress = idx / total
            self.progress_bar.set(progress)
            self.lbl_percentage.configure(text=f"%{int(progress * 100)}")
            self._refresh_file_view()

        self.is_processing = False
        self._refresh_file_view()
        self.lbl_status.configure(text=f"Tamamlandı: {success_count}/{total} dosya dönüştürüldü.")


if __name__ == "__main__":
    app = ConverterApp()
    app.mainloop()