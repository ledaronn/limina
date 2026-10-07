from pathlib import Path, PureWindowsPath
from uuid import uuid4

from ..common import PluginError, Service as Base, stamp


class Service(Base):
    def allowed(self, path, mode="read"):
        if not self.policy:
            raise PluginError("Dosya izin sistemi bağlı değil.")
        win = PureWindowsPath(str(path))
        reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
        reserved.update(prefix + n for prefix in ("COM", "LPT") for n in "123456789¹²³")
        for part in win.parts:
            if part == win.anchor:
                continue
            if part.split(".", 1)[0].rstrip().upper() in reserved or ":" in part or "\x00" in part:
                raise PluginError("Windows aygıt adı veya alternatif veri akışı kullanılamaz.")
        decision = self.policy.yol_dogrula(str(path), "oku" if mode == "read" else "yaz")
        if decision.sonuc == "DENY":
            raise PluginError(decision.gerekce)
        return decision.yol

    def resolve(self, workspace, value, mode="read"):
        root = self.allowed(workspace["root"])
        # Reject drive-relative Windows paths even when tests run on another OS.
        win = PureWindowsPath(value)
        if win.drive and not win.is_absolute():
            raise PluginError("Sürücüye göreli yol kullanılamaz.")
        candidate = Path(value)
        candidate = candidate if candidate.is_absolute() else root / candidate
        resolved = self.allowed(candidate, mode)
        if not resolved.is_relative_to(root):
            raise PluginError("Dosya workspace kökünün dışında.")
        return resolved, resolved.relative_to(root).as_posix()

    def check_relations(self, db, kind, item):
        if kind == "workspace" and not item.get("deleted"):
            root = self.allowed(item["root"])
            if not root.is_dir():
                raise PluginError("Workspace kökü mevcut bir klasör olmalı.")
            item["root"] = str(root)
        if kind == "task" and not item.get("deleted"):
            self.store.get(db, "workspace", item["workspace_id"])

    def touch(self, db, workspace_id, actor, action):
        item = self.store.get(db, "workspace", workspace_id)
        return self.store.save(db, "workspace", item, actor, action, self.clock())

    def execute(self, name, args, actor="user"):
        with self.store.transaction() as db:
            if name.startswith("task_"):
                if name == "task_create":
                    args = {"status": "todo", **args}
                result = self.generic(db, "task", name[5:], args, actor)
                if name in ("task_create", "task_update", "task_delete"):
                    self.touch(db, result["workspace_id"], actor, name)
                return result
            action = name[len("workspace_"):]
            if action in ("create", "get", "list", "update", "delete"):
                return self.generic(db, "workspace", action, args, actor)
            item = self.store.get(db, "workspace", args["id"])
            if action == "attach":
                path, relative = self.resolve(item, args["path"])
                if not path.exists():
                    raise PluginError("Bağlanacak dosya/klasör bulunamadı.")
                if (args["kind"] == "folder") != path.is_dir():
                    raise PluginError("Seçilen dosya/klasör türü yol ile uyuşmuyor.")
                files = item.setdefault("files", [])
                if any(f["path"] == relative for f in files):
                    raise PluginError("Bu yol zaten projeye bağlı.")
                if len(files) >= 500:
                    raise PluginError("Workspace başına en fazla 500 dosya referansı.")
                files.append({"id": uuid4().hex, "path": relative, "kind": args["kind"], "label": args.get("label", path.name)})
            elif action in ("detach", "resolve"):
                ref = next((f for f in item.get("files", []) if f["id"] == args["file_id"]), None)
                if not ref:
                    raise PluginError("Dosya referansı bulunamadı.")
                if action == "resolve":
                    path, _ = self.resolve(item, ref["path"], args["mode"])
                    return {"path": str(path), "exists": path.exists(), "hint": "Mevcut read_file/read_document/write_file araçlarını kullanın; onların izin ve onay denetimleri ayrıca uygulanır."}
                item["files"].remove(ref)
            elif action == "note_link":
                notes = set(item.get("note_ids", []))
                if args.get("remove"):
                    notes.discard(args["note_id"])
                else:
                    if len(notes) >= 500:
                        raise PluginError("Çok fazla not referansı.")
                    notes.add(args["note_id"])
                item["note_ids"] = sorted(notes)
            elif action == "log":
                log = self.store.save(db, "log", {"workspace_id": item["id"], "message": args["message"], "category": args.get("category", "progress"), "source": actor}, actor, name, self.clock())
                self.touch(db, item["id"], actor, name)
                return log
            elif action in ("context", "log_list"):
                logs = [x for x in self.store.items(db, "log") if x["workspace_id"] == item["id"]]
                start, limit = args.get("offset", 0), args.get("limit", 10)
                if action == "log_list":
                    return {"items": logs[start:start + limit], "total": len(logs)}
                tasks = [x for x in self.store.items(db, "task") if x["workspace_id"] == item["id"]]
                tasks.sort(key=lambda x: x.get("status") == "completed")
                files = item.get("files", [])
                safe_files = []
                for f in files[start:start + limit]:
                    try:
                        path, _ = self.resolve(item, f["path"])
                        safe_files.append({**f, "accessible": path.exists()})
                    except PluginError as e:
                        safe_files.append({**f, "accessible": False, "error": str(e)})
                return {"workspace": {k: v for k, v in item.items() if k not in ("files", "note_ids")},
                        "tasks": tasks[start:start + limit], "files": safe_files, "note_ids": item.get("note_ids", [])[start:start + limit],
                        "recent_log": logs[start:start + limit], "totals": {"tasks": len(tasks), "files": len(files), "log": len(logs), "notes": len(item.get("note_ids", []))},
                        "reference_hint": "Not/ders/sınav kimlikleri bağımsız referanslardır; ilgili eklentinin get aracıyla varlığını doğrulayın. Kapalı eklenti verisi otomatik okunmaz."}
            else:
                raise PluginError("Bilinmeyen workspace işlemi")
            return self.store.save(db, "workspace", item, actor, name, self.clock(), args["expected_revision"])
