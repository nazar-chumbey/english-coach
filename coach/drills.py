from __future__ import annotations

import random
from datetime import datetime

from coach import claude
from coach.storage import Store

SEEN = 40
RUNS = 2
LEVELS = range(1, 6)


def _skill(store: Store, skill_id: str) -> dict:
    skill = next((s for s in store.read("skills", []) if s["id"] == skill_id), None)
    if skill is None:
        raise KeyError(f"skill {skill_id} not found")
    return skill


def generate(store: Store, skill_id: str, model: str) -> dict:
    skill = _skill(store, skill_id)
    entry = store.read("drills", {}).get(skill_id, {})
    profile = store.read("profile", {})
    start = 3 if entry.get("level", 0) >= 3 else 1
    payload = {"skill": {k: skill.get(k) for k in ("id", "title", "notes", "examples")},
               "profile": {k: profile.get(k) for k in ("role", "stack", "domain")},
               "start": start, "seen": entry.get("seen", [])}
    return {**claude.ask("generate_drill", payload, "drill", model), "skillId": skill_id, "start": start}


def check(store: Store, skill_id: str, exercise: dict, pattern: dict, text: str, model: str) -> dict:
    _skill(store, skill_id)
    if not text.strip():
        raise ValueError("answer is empty")
    return claude.ask("check_drill", {"pattern": pattern, "exercise": exercise, "answer": text}, "sentence", model)


def record(store: Store, skill_id: str, result: dict) -> dict:
    skill = _skill(store, skill_id)
    drills = store.read("drills", {})
    entry = drills.setdefault(skill_id, {"level": 0, "seen": [], "sessions": []})
    levels = sorted({int(l) for l in result.get("levels", []) if int(l) in LEVELS})
    passed, clean = bool(result.get("passed")) and 5 in levels, bool(result.get("clean"))
    entry["level"] = max([entry["level"], *levels])
    entry["seen"] = (entry["seen"] + [str(a) for a in result.get("answers", [])])[-SEEN:]
    entry["sessions"].append({"at": datetime.now().isoformat(timespec="seconds"), "start": result.get("start", 1),
                              "passed": passed, "levels": levels, "clean": clean})
    store.write("drills", drills)
    if passed and clean and skill.get("status") == "weak":
        store.write("skills", [{**s, "status": "improving"} if s["id"] == skill_id else s for s in store.read("skills", [])])
    return entry


def pick(skills: list[dict], exclude: str | None = None) -> str | None:
    pool = [s for s in skills if s.get("status") in ("weak", "improving")]
    focus = [s for s in pool if s.get("kind") in ("grammar", "mistake")] or pool
    choices = [s for s in focus if s["id"] != exclude] or focus
    return random.choice(choices)["id"] if choices else None


def runs_since(store: Store, skill_id: str, since: str) -> int:
    return sum(s["passed"] and s["at"] >= since for s in store.read("drills", {}).get(skill_id, {}).get("sessions", []))
