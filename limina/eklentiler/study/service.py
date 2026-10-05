from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..common import PluginError, Service as Base, instant, stamp


class Service(Base):
    def check_relations(self, db, kind, item):
        if item.get("deleted"):
            # Referenced history is retained, but live academic links cannot dangle.
            dependents = {"course": [("exam", "course_id"), ("topic", "course_id"), ("study_plan", "course_id")],
                          "exam": [("topic", "exam_id")], "topic": [("study_plan", "topic_id")]}
            for child, field in dependents.get(kind, []):
                if any(r.get(field) == item["id"] for r in self.store.items(db, child)):
                    raise PluginError("Önce bağlı sınav/konu/plan kayıtlarını kaldırın veya başka kayda bağlayın.")
            return
        for field, target in [("course_id", "course"), ("exam_id", "exam"), ("topic_id", "topic")]:
            if item.get(field):
                linked = self.store.get(db, target, item[field])
                if target != "course" and item.get("course_id") and linked["course_id"] != item["course_id"]:
                    raise PluginError("Konu/sınav ve ders ilişkisi uyuşmuyor.")
        if kind in ("topic", "exam") and item.get("id"):
            # Moving an academic parent must not invalidate its existing children.
            for child in self.store.items(db, "topic" if kind == "exam" else "study_plan"):
                if child.get(kind + "_id") == item["id"] and child["course_id"] != item["course_id"]:
                    raise PluginError("Bağlı kayıtlar varken ders değiştirilemez.")

    def execute(self, name, args, actor="user"):
        with self.store.transaction() as db:
            now = self.clock()
            if name.startswith("focus_"):
                return self.focus(db, name[6:], args, actor, now)
            if name == "study_session_log":
                start, end = instant(args["start"]), instant(args["end"])
                if end <= start or end > now or (end - start).total_seconds() > 86400:
                    raise PluginError("Geçmiş oturum başlangıç < bitiş ≤ şimdi olmalı ve 24 saati aşmamalı.")
                self.check_relations(db, "session", args)
                return self.store.save(db, "session", {**args, "seconds": (end - start).total_seconds(),
                    "intervals": [[stamp(start), stamp(end)]], "completed": args.get("completed", True)}, actor, name, now)
            if name in ("study_stats", "study_session_list"):
                self.settle(db, now)
                if name == "study_session_list":
                    return self.generic(db, "session", "list", args, actor)
                return self.stats(db, args, now)
            kind, action = name.rsplit("_", 1)
            if action == "create":
                defaults = {"course": {"description": "", "tags": []},
                            "exam": {"priority": "normal", "status": "upcoming"},
                            "topic": {"progress": 0, "difficulty": 3},
                            "study_plan": {"status": "planned"}}
                args = {**defaults.get(kind, {}), **args}
            result = self.generic(db, kind, action, args, actor)
            if kind == "exam":
                rows = result.get("items", []) if action == "list" else [result]
                for row in rows:
                    row["remaining_seconds"] = (instant(row["at"]) - now).total_seconds()
            return result

    @staticmethod
    def timer(item, now):
        intervals = list(item.get("intervals", []))
        if item["status"] == "active":
            start = instant(item["running_since"])
            intervals.append([stamp(start), stamp(max(now, start))])
        active = sum((instant(b) - instant(a)).total_seconds() for a, b in intervals)
        work, rest, rounds = item["work_minutes"] * 60, item["break_minutes"] * 60, item["rounds"]
        total = work * rounds + rest * (rounds - 1)
        effective = min(active, total) if item["mode"] == "pomodoro" else active
        segments = []
        # Map active-time work windows back to wall-clock intervals. Pauses and breaks disappear.
        cursor = 0.0
        for a, b in intervals:
            start, end = instant(a), instant(b)
            length = (end - start).total_seconds()
            windows = [(0, effective)] if item["mode"] == "free" else [(i * (work + rest), i * (work + rest) + work) for i in range(rounds)]
            for left, right in windows:
                lo, hi = max(cursor, left), min(cursor + length, right, effective)
                if hi > lo:
                    segments.append([stamp(start + timedelta(seconds=lo - cursor)), stamp(start + timedelta(seconds=hi - cursor))])
            cursor += length
        done = item["mode"] == "pomodoro" and active >= total
        position = effective % (work + rest)
        phase = "work" if item["mode"] == "free" or position < work else "break"
        remaining = None if item["mode"] == "free" else (work - position if phase == "work" else work + rest - position)
        return {**item, "status": "completed" if done else item["status"], "phase": "completed" if done or item["status"] == "completed" else phase,
                "round": min(int(effective // (work + rest)) + 1, rounds), "remaining_seconds": 0 if done else remaining,
                "elapsed_seconds": effective, "work_seconds": sum((instant(b) - instant(a)).total_seconds() for a, b in segments),
                "work_intervals": segments, "automatic_end": done, "server_time": stamp(now)}

    def complete(self, db, item, view, actor, now):
        if item["status"] == "completed":
            return
        item["status"] = "completed"
        item["finished_at"] = view["work_intervals"][-1][1] if view["automatic_end"] and view["work_intervals"] else stamp(now)
        item.pop("running_since", None)
        item["work_seconds"] = view["work_seconds"]
        item["work_intervals"] = view["work_intervals"]
        self.store.save(db, "focus", item, actor, "focus_finish", now)
        session = {k: item[k] for k in ("course_id", "topic_id", "references") if k in item}
        session.update(focus_id=item["id"], start=item["created_at"], end=item["finished_at"], type=item["mode"],
                       seconds=view["work_seconds"], completed=True, intervals=view["work_intervals"])
        self.store.save(db, "session", session, actor, "focus_session_log", now)

    def settle(self, db, now):
        for item in self.store.items(db, "focus"):
            if item["status"] == "active":
                view = self.timer(item, now)
                if view["automatic_end"]:
                    self.complete(db, item, view, "timer", now)

    def focus(self, db, action, args, actor, now):
        self.settle(db, now)
        if action == "start":
            if any(x["status"] != "completed" for x in self.store.items(db, "focus")):
                raise PluginError("Önce mevcut odak oturumunu bitirin.")
            self.check_relations(db, "focus", args)
            item = {"mode": "pomodoro", "work_minutes": 25, "break_minutes": 5, "rounds": 4, **args,
                    "status": "active", "intervals": [], "running_since": stamp(now)}
            item = self.store.save(db, "focus", item, actor, "focus_start", now)
        elif args.get("id"):
            item = self.store.get(db, "focus", args["id"])
        else:
            rows = self.store.items(db, "focus")
            if not rows:
                return {"status": "idle"}
            item = next((x for x in rows if x["status"] != "completed"), rows[0])
        if item["status"] == "completed":
            if action in ("pause", "resume"):
                raise PluginError("Tamamlanmış oturum değiştirilemez.")
            return {**item, "phase": "completed", "remaining_seconds": 0, "server_time": stamp(now)}
        if action in ("pause", "finish") and item["status"] == "active":
            item["intervals"].append([item["running_since"], stamp(max(now, instant(item["running_since"])))])
            item.pop("running_since")
            item["status"] = "paused"
        elif action == "resume" and item["status"] == "paused":
            item["status"], item["running_since"] = "active", stamp(now)
        view = self.timer(item, now)
        if action == "finish":
            self.complete(db, item, view, actor, now)
            return self.store.get(db, "focus", item["id"])
        if action in ("pause", "resume"):
            item = self.store.save(db, "focus", item, actor, "focus_" + action, now)
            return self.timer(item, now)
        return view

    def stats(self, db, args, now):
        tz = timezone(timedelta(minutes=args.get("offset_minutes", 0)))
        day = datetime.strptime(args.get("date", now.astimezone(tz).date().isoformat()), "%Y-%m-%d").replace(tzinfo=tz)
        week = day - timedelta(days=day.weekday())
        sessions = self.store.items(db, "session")
        def duration(start, end):
            seconds = 0
            for session in sessions:
                for a, b in session["intervals"]:
                    seconds += max(0, (min(instant(b), end) - max(instant(a), start)).total_seconds())
            return round(seconds, 2)
        return {"date": day.date().isoformat(), "daily_seconds": duration(day, day + timedelta(days=1)),
                "weekly_seconds": duration(week, week + timedelta(days=7)), "sessions": len(sessions)}
