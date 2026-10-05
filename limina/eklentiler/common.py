"""Transactional, versioned local storage and strict tool input validation."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class PluginError(ValueError):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat()


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise PluginError("Tarih/saat saat dilimi içermeli: 2026-10-12T09:00:00+03:00")


def validate(value, schema, path="args"):
    kind = schema["type"]
    valid = {"object": lambda: isinstance(value, dict),
             "array": lambda: isinstance(value, list),
             "string": lambda: isinstance(value, str),
             "integer": lambda: type(value) is int,
             "number": lambda: type(value) in (int, float),
             "boolean": lambda: type(value) is bool}[kind]()
    if not valid:
        raise PluginError(f"{path}: beklenen tür {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise PluginError(f"{path}: izinli değerler {schema['enum']}")
    if kind == "object":
        props = schema["properties"]
        missing = set(schema.get("required", [])) - value.keys()
        extra = value.keys() - props.keys()
        if missing or extra:
            raise PluginError(f"{path}: eksik alanlar {sorted(missing)}, bilinmeyen alanlar {sorted(extra)}")
        for key, item in value.items():
            validate(item, props[key], f"{path}.{key}")
    elif kind == "array":
        if len(value) > schema.get("maxItems", 100):
            raise PluginError(f"{path}: çok fazla öğe")
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]")
    elif kind == "string":
        if not schema.get("minLength", 0) <= len(value.strip()) <= schema.get("maxLength", 10000):
            raise PluginError(f"{path}: metin uzunluğu geçersiz")
        if schema.get("format") == "date-time":
            instant(value)
        if schema.get("format") == "date":
            try:
                if len(value) != 10:
                    raise ValueError()
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise PluginError(f"{path}: YYYY-MM-DD bekleniyor")
    elif kind in ("number", "integer"):
        if not schema.get("minimum", -1e15) <= value <= schema.get("maximum", 1e15):
            raise PluginError(f"{path}: sayı izinli aralığın dışında")


class Store:
    VERSION = 2

    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def transaction(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > self.VERSION:
                raise PluginError("Veritabanı daha yeni bir uygulama sürümüne ait.")
            if version == 0:
                db.execute("CREATE TABLE records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL)")
                db.execute("CREATE INDEX record_kind ON records(kind)")
                db.execute("CREATE TABLE revisions (id TEXT, revision INTEGER, data TEXT NOT NULL, PRIMARY KEY(id, revision))")
                db.execute("CREATE TABLE audit (sequence INTEGER PRIMARY KEY, time TEXT, actor TEXT, action TEXT, id TEXT, revision INTEGER)")
                db.execute("CREATE VIRTUAL TABLE note_search USING fts5(id UNINDEXED, title, body, tags, tokenize='unicode61')")
                db.execute("PRAGMA user_version=1")
            if version < 2:
                db.execute("DELETE FROM note_search")
                for row in db.execute("SELECT data FROM records WHERE kind='note'").fetchall():
                    item = json.loads(row[0])
                    db.execute("INSERT INTO note_search VALUES(?,?,?,?)", (item["id"], item["title"], item.get("body", ""), " ".join(item.get("tags", []))))
                db.execute("PRAGMA user_version=2")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get(db, kind, id, deleted=False):
        row = db.execute("SELECT data FROM records WHERE kind=? AND id=?", (kind, id)).fetchone()
        if row:
            item = json.loads(row[0])
            if deleted or not item.get("deleted", False):
                return item
        raise PluginError(f"{kind} kaydı bulunamadı: {id}")

    @staticmethod
    def items(db, kind, deleted=False):
        items = [json.loads(r[0]) for r in db.execute("SELECT data FROM records WHERE kind=? ORDER BY rowid DESC", (kind,))]
        return [x for x in items if deleted or not x.get("deleted", False)]

    def save(self, db, kind, item, actor, action, now, expected=None):
        item = dict(item)
        if "id" in item:
            old = self.get(db, kind, item["id"], deleted=True)
            if expected is not None and old["revision"] != expected:
                raise PluginError("Kayıt başka bir işlemde değişti. Yeniden okuyup güncelleyin.")
            revision = old["revision"] + 1
        else:
            item.update(id=uuid4().hex, created_at=stamp(now))
            revision = 1
        item.update(revision=revision, updated_at=stamp(now))
        data = json.dumps(item, ensure_ascii=False)
        db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?)", (item["id"], kind, data))
        db.execute("INSERT INTO revisions VALUES(?,?,?)", (item["id"], revision, data))
        db.execute("INSERT INTO audit(time,actor,action,id,revision) VALUES(?,?,?,?,?)",
                   (stamp(now), actor, action, item["id"], revision))
        if kind == "note":
            db.execute("DELETE FROM note_search WHERE id=?", (item["id"],))
            db.execute("INSERT INTO note_search VALUES(?,?,?,?)", (item["id"], item["title"], item.get("body", ""), " ".join(item.get("tags", []))))
        return item


class Service:
    def __init__(self, path, clock=utcnow, policy=None):
        self.store, self.clock, self.policy = Store(path), clock, policy

    def check_relations(self, db, kind, item):
        pass

    def generic(self, db, kind, action, args, actor):
        if action == "list":
            rows = self.store.items(db, kind, args.get("include_deleted", False))
            for key, value in args.items():
                if key not in ("limit", "offset", "include_deleted"):
                    rows = [r for r in rows if r.get(key) == value]
            start, limit = args.get("offset", 0), args.get("limit", 50)
            return {"items": rows[start:start + limit], "total": len(rows)}
        if action == "get":
            return self.store.get(db, kind, args["id"], args.get("include_deleted", False))
        if action == "create":
            item = {**args, "deleted": False}
        else:
            item = self.store.get(db, kind, args["id"])
            if action == "delete":
                item["deleted"] = True
            elif action == "update":
                item.update({k: v for k, v in args.items() if k not in ("id", "expected_revision")})
            else:
                raise PluginError("Bilinmeyen işlem")
        self.check_relations(db, kind, item)
        return self.store.save(db, kind, item, actor, f"{kind}_{action}", self.clock(), args.get("expected_revision"))
