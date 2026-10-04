from __future__ import annotations

from datetime import date

from coach.storage import Store

MAX_SKILLS = 8
MAX_WORDS = 3
WORD_LESSONS = 3
MAX_LEARNED = 6


def item_count(minutes: int) -> int:
    return round(minutes * 0.8)


def _rank(skill: dict, today: str) -> int:
    if skill.get("kind") == "mistake" and skill.get("count", 0) >= 3:
        return 0
    if skill.get("understanding") in ("none", "partial"):
        return 1
    if skill.get("status") == "weak":
        return 2
    if skill.get("due", "9999") <= today:
        return 3
    return 4


def build(store: Store, focus_skill: str | None = None, today: str | None = None) -> dict:
    today = today or date.today().isoformat()
    profile = {k: v for k, v in store.read("profile", {}).items() if k != "settings"}
    skills = [s for s in store.read("skills", []) if s.get("status") != "mastered"]
    skills.sort(key=lambda s: (s["id"] != focus_skill, _rank(s, today)))
    done = [l for l in store.lessons() if l.get("status") == "done"]
    return {
        "today": today,
        "profile": profile,
        "skills": skills[:MAX_SKILLS],
        "focusSkill": focus_skill,
        "recentFocus": [l["review"]["nextFocus"] for l in done if l.get("review", {}).get("nextFocus")][:3],
        "recentTopics": [l.get("topic") for l in done[:5]],
        "placementPlan": _plan(store, done),
        "learnedChunks": [{"chunk": w["word"], "meaning": w.get("meaning", "")} for w in sorted(
            (w for w in store.read("words", []) if w.get("status", "learning") == "learning" and w.get("srs")),
            key=lambda w: w["srs"]["due"])[:MAX_LEARNED]],
        "drills": [{"skillId": k, "level": v["level"], "sessions": len(v["sessions"])} for k, v in store.read("drills", {}).items()],
        "savedWords": [{k: w[k] for k in ("word", "meaning", "context")} for w in sorted(
            (w for w in store.read("words", []) if w.get("source") != "lesson" and w.get("status", "learning") == "learning" and len(w["lessons"]) < WORD_LESSONS),
            key=lambda w: (len(w["lessons"]), w["addedAt"]))[:MAX_WORDS]],
    }


def _plan(store: Store, done: list[dict]) -> list | None:
    placement = next((a for a in reversed(store.read("assessments", [])) if a.get("plan")), None)
    if not placement:
        return None
    regular = sum(l.get("kind") != "placement" for l in done)
    return placement["plan"][regular:] or None
