import json
import re

from ..common import PluginError, Service as Base


class Service(Base):
    def execute(self, name, args, actor="user"):
        with self.store.transaction() as db:
            if name == "note_read":
                item = self.store.get(db, "note", args["id"])
                start, length = args.get("offset", 0), args.get("length", 4000)
                body = item.get("body", "")
                return {"id": item["id"], "revision": item["revision"], "body": body[start:start + length],
                        "total_characters": len(body), "next_offset": min(start + length, len(body)), "done": start + length >= len(body)}
            if name == "note_search":
                words = re.findall(r"\w+", args["query"], re.UNICODE)
                if not words:
                    return {"items": [], "total": 0}
                query = " AND ".join('"' + word + '"' for word in words)
                scope = args.get("scope", "active")
                filters = {
                    "active": "coalesce(json_extract(r.data,'$.deleted'),0)=0 AND coalesce(json_extract(r.data,'$.archived'),0)=0",
                    "archived": "coalesce(json_extract(r.data,'$.deleted'),0)=0 AND json_extract(r.data,'$.archived')=1",
                    "deleted": "json_extract(r.data,'$.deleted')=1",
                }
                if scope not in filters:
                    raise PluginError("Bilinmeyen arama kapsamı")
                base = "FROM note_search JOIN records r ON r.id=note_search.id WHERE r.kind='note' AND note_search MATCH ? AND " + filters[scope]
                total = db.execute("SELECT count(*) " + base, (query,)).fetchone()[0]
                rows = db.execute("SELECT r.data " + base + " ORDER BY rank LIMIT ? OFFSET ?", (query, args.get("limit", 50), args.get("offset", 0))).fetchall()
                return {"items": [json.loads(r[0]) for r in rows], "total": total}
            if name == "note_history":
                self.store.get(db, "note", args["id"], deleted=True)
                rows = db.execute("SELECT r.data, a.actor FROM revisions r LEFT JOIN audit a ON a.id=r.id AND a.revision=r.revision WHERE r.id=? ORDER BY r.revision DESC LIMIT ? OFFSET ?",
                                  (args["id"], args.get("limit", 50), args.get("offset", 0))).fetchall()
                total = db.execute("SELECT count(*) FROM revisions WHERE id=?", (args["id"],)).fetchone()[0]
                return {"items": [{**json.loads(r[0]), "change_source": r[1]} for r in rows], "total": total}
            if name in ("note_restore", "note_link", "note_archive"):
                item = self.store.get(db, "note", args["id"], deleted=name == "note_restore")
                if name == "note_restore":
                    row = db.execute("SELECT data FROM revisions WHERE id=? AND revision=?", (args["id"], args["revision"])).fetchone()
                    if not row:
                        raise PluginError("Not sürümü bulunamadı.")
                    item = json.loads(row[0])
                    item["deleted"] = False
                elif name == "note_link":
                    self.store.get(db, "note", args["target_id"])
                    if args["id"] == args["target_id"]:
                        raise PluginError("Not kendisine bağlanamaz.")
                    links = set(item.get("links", []))
                    if args.get("remove"):
                        links.discard(args["target_id"])
                    else:
                        if len(links) >= 100 and args["target_id"] not in links:
                            raise PluginError("Bir not en fazla 100 başka nota bağlanabilir.")
                        links.add(args["target_id"])
                    item["links"] = sorted(links)
                else:
                    item["archived"] = args["archived"]
                return self.store.save(db, "note", item, actor, name, self.clock(), args["expected_revision"])
            if name == "note_create":
                args = {"body": "", "tags": [], "references": [], "archived": False, **args}
            result = self.generic(db, "note", name[5:], args, actor)
            if name == "note_get":
                row = db.execute("SELECT actor FROM audit WHERE id=? AND revision=?", (result["id"], result["revision"])).fetchone()
                result["change_source"] = row[0] if row else None
            return result
