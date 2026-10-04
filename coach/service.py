from __future__ import annotations

import random
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

from coach import claude, drills, srs
from coach.checker import check, normalise
from coach.context import build, item_count
from coach.skills import apply_patch
from coach.storage import Store

DEFAULT_SETTINGS = {"defaultMinutes": 15,
                    "models": {"generate": "sonnet", "check": "sonnet", "review": "sonnet", "assess": "sonnet"}}
VAULT_FILES = ("Profile", "Progress", "Understanding", "Weak Points", "Mistakes", "Vocabulary",
               "Review Queue", "Resources", "Lesson History")
LOCK = threading.Lock()


def settings(store: Store) -> dict:
    saved = store.read("profile", {}).get("settings", {})
    return {**DEFAULT_SETTINGS, **saved, "models": {**DEFAULT_SETTINGS["models"], **saved.get("models", {})}}


def _model(store: Store, task: str) -> str:
    return settings(store)["models"][task]


def _score(lesson: dict) -> str:
    checked = [r for r in lesson.get("responses", {}).values() if r["result"] in ("correct", "minor", "mismatch", "wrong")]
    good = sum(r["result"] in ("correct", "minor") for r in checked)
    return f"{good}/{len(checked)}" if checked else lesson.get("score", "")


def summary(lesson: dict) -> dict:
    keys = ("id", "createdAt", "topic", "minutes", "status", "imported", "kind")
    return {**{k: lesson.get(k) for k in keys}, "score": _score(lesson),
            "answered": len(lesson.get("responses", {})), "total": len(lesson.get("items", [])),
            "nextLesson": lesson.get("review", {}).get("nextLesson")}


def state(store: Store) -> dict:
    ok, message = claude.available()
    lessons = store.lessons()
    assessments = store.read("assessments", [])
    done = sum(l.get("status") == "done" for l in lessons)
    return {"profile": {**store.read("profile", {}), "settings": settings(store)},
            "skills": store.read("skills", []),
            "words": store.read("words", []),
            "lessons": [summary(l) for l in lessons],
            "assessments": assessments,
            "gate": gate(store),
            "drills": store.read("drills", {}),
            "newLessonsSinceAssessment": done - assessments[-1]["lessonsDone"] if assessments else done,
            "claude": {"ok": ok, "message": message}}


DIMENSIONS = {"grammar": "Граматика", "vocabulary": "Словник", "writing": "Письмо", "reading": "Читання",
              "professional_it_communication": "Професійна комунікація", "sentence_production": "Побудова речень",
              "listening": "Слухання", "speaking": "Говоріння"}


def baseline(profile: dict, date_: str) -> dict:
    levels = profile.get("levels", {})
    dims = [{"name": DIMENSIONS.get(k, k), "level": v.split(" (")[0], "measured": "not assessed" not in v,
             "note": v.partition(" (")[2].rstrip(")")} for k, v in levels.items() if k != "general"]
    return {"source": "placement", "assessedAt": date_, "lessonsDone": 0, "overall": levels.get("general", ""),
            "summary": "Стартова точка: результат placement-тесту.", "dimensions": dims}


def assess(store: Store) -> dict:
    lessons = [l for l in store.lessons() if l.get("status") == "done"]
    assessments = store.read("assessments", [])
    recent = [{k: l.get(k) for k in ("id", "topic", "score", "review")} |
              {"answers": [{"prompt": i["prompt"], "type": i["type"], **l["responses"][i["id"]]}
                           for i in l.get("items", []) if i["id"] in l.get("responses", {})]}
              for l in lessons[:8]]
    payload = {"today": date.today().isoformat(), "profile": store.read("profile", {}),
               "skills": store.read("skills", []), "recentLessons": recent,
               "previous": assessments[-1] if assessments else None}
    result = claude.ask("assess", payload, "assessment", _model(store, "assess"))
    result.update(source="agent", assessedAt=datetime.now().isoformat(timespec="seconds"), lessonsDone=len(lessons))
    with LOCK:
        store.write("assessments", store.read("assessments", []) + [result])
    return result


def update_settings(store: Store, changes: dict) -> dict:
    with LOCK:
        profile = store.read("profile", {})
        if "name" in changes:
            profile["name"] = str(changes.pop("name")).strip()
        if "goal" in changes:
            profile["goal"] = {**profile.get("goal", {}), **changes.pop("goal")}
        current = profile.get("settings", {})
        models = {**current.get("models", {}), **changes.pop("models", {})}
        profile["settings"] = {**current, **changes, "models": models}
        store.write("profile", profile)
    return settings(store)


def _shuffle_options(lesson: dict) -> dict:
    for item in lesson.get("items", []):
        if item.get("options"):
            random.shuffle(item["options"])
    return lesson


def generate(store: Store, minutes: int, focus_skill: str | None = None) -> dict:
    if minutes not in (10, 15, 20, 30):
        raise ValueError("minutes must be 10, 15, 20 or 30")
    passed = gate(store)
    if not passed["ready"]:
        missing = [n for n, ok in (("chunk quiz", passed["quiz"]), ("due chunks", not passed["dueChunks"]),
                                   ("drill", not passed["drill"] or passed["drill"]["done"] >= passed["drill"]["required"]),
                                   ("homework", passed["homework"] or not passed["recommendation"])) if not ok]
        raise ValueError(f"finish the checklist first: {', '.join(missing)}")
    homework = passed["homework"] and {**passed["homework"], "recommendation": passed["recommendation"]}
    payload = {**build(store, focus_skill), "minutes": minutes, "itemCount": item_count(minutes), "previousHomework": homework}
    lesson = _shuffle_options(claude.ask("generate_lesson", payload, "lesson", _model(store, "generate")))
    with LOCK:
        today = date.today().isoformat()
        lesson.update(id=store.next_lesson_id(today), createdAt=datetime.now().isoformat(timespec="seconds"),
                      minutes=minutes, status="in_progress", responses={}, previousHomework=homework)
        store.save_lesson(lesson)
        taught = {w["word"] for w in payload["savedWords"]}
        store.write("words", [{**w, "lessons": w["lessons"] + [lesson["id"]]} if w["word"] in taught else w
                              for w in store.read("words", [])])
    return lesson


WORD_FIELDS = ("meaning", "ipa", "example", "association", "collocations", "cloze", "clozeAnswer", "distractors")
WORD_STATUSES = ("suggested", "learning", "known")


def _new_word(words: list[dict], word: str, **extra) -> dict:
    return {"id": f"w{max((int(w['id'][1:]) for w in words), default=0) + 1}", "word": word, "context": "",
            "lessonId": None, "addedAt": datetime.now().isoformat(timespec="seconds"), "source": "saved",
            "status": "learning", "meaning": "", "example": "", "lessons": [], "srs": None, **extra}


def _update_word(store: Store, word_id: str, changes: dict) -> dict:
    with LOCK:
        words = store.read("words", [])
        entry = next((w for w in words if w["id"] == word_id), None)
        if entry is None:
            raise KeyError(f"word {word_id} not found")
        entry.update(changes)
        store.write("words", words)
    return entry


def save_word(store: Store, word: str, context: str = "", lesson_id: str | None = None) -> dict:
    word = " ".join(str(word).split()).strip(" .,;:!?«»\"'")
    if not 0 < len(word) <= 80:
        raise ValueError("word must be 1-80 characters")
    with LOCK:
        words = store.read("words", [])
        entry = next((w for w in words if w["word"].lower() == word.lower()), None)
        if entry:
            return entry
        entry = _new_word(words, word, context=context[:300], lessonId=lesson_id)
        store.write("words", words + [entry])
    if not claude.available()[0]:
        return entry
    explained = claude.ask("explain_word", {"word": word, "context": context}, "word", _model(store, "check"))
    return _update_word(store, entry["id"], explained)


def enrich_words(store: Store) -> list[dict]:
    missing = [w for w in store.read("words", []) if w.get("status", "learning") == "learning" and not w.get("cloze")]
    ask = lambda w: (w["id"], claude.ask("explain_word", {"word": w["word"], "context": w.get("context", "")},
                                         "word", _model(store, "check")))
    with ThreadPoolExecutor(4) as pool:
        for word_id, explained in pool.map(ask, missing):
            _update_word(store, word_id, {k: explained[k] for k in WORD_FIELDS})
    return store.read("words", [])


def suggest_words(store: Store, kind: str, count: int = 8) -> list[dict]:
    if kind not in ("work", "general"):
        raise ValueError("kind must be work or general")
    assessments = store.read("assessments", [])
    payload = {"profile": {k: v for k, v in store.read("profile", {}).items() if k != "settings"},
               "level": assessments[-1].get("overall", "") if assessments else "", "kind": kind, "count": count,
               "known": [w["word"] for w in store.read("words", [])]}
    found = claude.ask("suggest_words", payload, "word_batch", _model(store, "generate"))["words"]
    with LOCK:
        words = store.read("words", [])
        for item in found:
            if not any(w["word"].lower() == item["word"].lower() for w in words):
                words.append(_new_word(words, item.pop("word"), status="suggested", **item))
        store.write("words", words)
    return words


def set_word(store: Store, word_id: str, changes: dict) -> dict:
    allowed = {k: v for k, v in changes.items() if k in ("status", "association")}
    if allowed.get("status", "learning") not in WORD_STATUSES:
        raise ValueError(f"status must be one of {WORD_STATUSES}")
    return _update_word(store, word_id, allowed)


def review_word(store: Store, word_id: str, rating: int) -> dict:
    entry = next((w for w in store.read("words", []) if w["id"] == word_id), None)
    if entry is None:
        raise KeyError(f"word {word_id} not found")
    return _update_word(store, word_id, {"srs": srs.review(entry.get("srs"), rating, datetime.now()),
                                         **({} if entry.get("srs") else {"introducedAt": date.today().isoformat()})})


def check_sentence(store: Store, word_id: str, sentence: str) -> dict:
    entry = next((w for w in store.read("words", []) if w["id"] == word_id), None)
    if entry is None:
        raise KeyError(f"word {word_id} not found")
    if not sentence.strip():
        raise ValueError("sentence is empty")
    return claude.ask("check_sentence", {"word": entry["word"], "meaning": entry.get("meaning", ""), "sentence": sentence},
                      "sentence", _model(store, "check"))


def check_recall(store: Store, word_id: str, answer: str) -> dict:
    entry = next((w for w in store.read("words", []) if w["id"] == word_id), None)
    if entry is None:
        raise KeyError(f"word {word_id} not found")
    if not answer.strip():
        raise ValueError("answer is empty")
    payload = {"chunk": entry["word"], "meaning": entry.get("meaning", ""), "cloze": entry.get("cloze", ""), "answer": answer}
    return claude.ask("check_recall", payload, "sentence", _model(store, "check"))


def delete_word(store: Store, word_id: str) -> dict:
    with LOCK:
        words = store.read("words", [])
        if not any(w["id"] == word_id for w in words):
            raise KeyError(f"word {word_id} not found")
        store.write("words", [w for w in words if w["id"] != word_id])
    return {"ok": True}


def _chunk_word(chunk: str) -> str:
    return " ".join(chunk.split()).strip(" .,;:!?«»\"'…")


def _cloze(word: str, example: str) -> str:
    i = example.lower().find(word.lower())
    return example[:i] + "___" + example[i + len(word):] if i >= 0 else ""


def add_chunks(store: Store, lesson: dict) -> None:
    words = store.read("words", [])
    for c in lesson.get("chunks", []):
        word = _chunk_word(c["chunk"])
        if word and not any(w["word"].lower() == word.lower() for w in words):
            words.append(_new_word(words, word, source="lesson", lessonId=lesson["id"], context=c["example"][:300],
                                   meaning=c["meaning"], example=c["example"], cloze=_cloze(word, c["example"]), clozeAnswer=word))
    store.write("words", words)


def backfill_chunks(store: Store) -> None:
    with LOCK:
        for lesson in store.lessons():
            if lesson.get("status") == "done" and lesson.get("kind") != "placement":
                add_chunks(store, lesson)


def _gate_lesson(store: Store) -> dict:
    return next((l for l in store.lessons() if l.get("status") == "done" and l.get("kind") != "placement"
                 and not l.get("imported")), {})


def gate(store: Store) -> dict:
    lesson, now = _gate_lesson(store), datetime.now()
    words = store.read("words", [])
    chunks = {_chunk_word(c["chunk"]).lower() for c in lesson.get("chunks", [])}
    quiz = [w["id"] for w in words if w["word"].lower() in chunks]
    due = sum(w.get("source") == "lesson" and w.get("status", "learning") == "learning" and bool(w.get("srs"))
              and datetime.fromisoformat(w["srs"]["due"]) <= now for w in words)
    skill = next((s for s in store.read("skills", []) if s["id"] == lesson.get("drillSkill")), None)
    drill = skill and {"skillId": skill["id"], "title": skill.get("title") or skill["id"], "required": drills.RUNS,
                       "done": drills.runs_since(store, skill["id"], lesson.get("finishedAt", ""))}
    result = {"lessonId": lesson.get("id"), "words": quiz, "quiz": not quiz or bool(lesson.get("chunkQuiz")),
              "dueChunks": due, "recommendation": lesson.get("review", {}).get("recommendation", ""),
              "homework": lesson.get("homework"), "drill": drill}
    return {**result, "ready": result["quiz"] and not due and bool(result["homework"] or not result["recommendation"])
            and (not drill or drill["done"] >= drill["required"])}


def assign_drill(store: Store) -> None:
    with LOCK:
        lesson = _gate_lesson(store)
        if lesson and "drillSkill" not in lesson:
            lesson["drillSkill"] = drills.pick(store.read("skills", []))
            store.save_lesson(lesson)


def generate_drill(store: Store, skill_id: str) -> dict:
    return drills.generate(store, skill_id, _model(store, "generate"))


def check_drill(store: Store, skill_id: str, exercise: dict, pattern: dict, text: str) -> dict:
    return drills.check(store, skill_id, exercise, pattern, text, _model(store, "check"))


def finish_drill(store: Store, skill_id: str, result: dict) -> dict:
    with LOCK:
        drills.record(store, skill_id, result)
    return gate(store)


def pass_quiz(store: Store, lesson_id: str, results: list[dict]) -> dict:
    get_lesson(store, lesson_id)
    for r in results:
        review_word(store, r["wordId"], srs.GOOD if r.get("firstTry") else srs.HARD)
    with LOCK:
        lesson = get_lesson(store, lesson_id)
        lesson["chunkQuiz"] = {"passedAt": datetime.now().isoformat(timespec="seconds")}
        store.save_lesson(lesson)
    return gate(store)


def set_homework(store: Store, lesson_id: str, status: str, notes: str) -> dict:
    notes = str(notes).strip()
    if status not in ("done", "skipped") or not notes:
        raise ValueError("status must be done or skipped, notes are required")
    with LOCK:
        lesson = get_lesson(store, lesson_id)
        lesson["homework"] = {"status": status, "notes": notes[:1000], "at": datetime.now().isoformat(timespec="seconds")}
        store.save_lesson(lesson)
    return gate(store)


PROFILE_FIELDS = ("name", "role", "stack", "domain", "usage", "hardest", "selfLevel", "dreaded", "goal")


def onboard(store: Store, answers: dict) -> dict:
    with LOCK:
        profile = store.read("profile", {})
        profile.update({k: answers[k] for k in PROFILE_FIELDS if k in answers}, onboardedAt=date.today().isoformat())
        if answers.get("minutes") in (10, 15, 20, 30):
            profile["settings"] = {**profile.get("settings", {}), "defaultMinutes": answers["minutes"]}
        store.write("profile", profile)
    return state(store)


def generate_placement(store: Store) -> dict:
    profile = {k: v for k, v in store.read("profile", {}).items() if k != "settings"}
    if not profile.get("onboardedAt"):
        raise ValueError("onboarding first")
    test = _shuffle_options(claude.ask("generate_placement", {"profile": profile}, "placement", _model(store, "generate")))
    with LOCK:
        test.update(id=store.next_lesson_id(date.today().isoformat()), kind="placement", minutes=25,
                    createdAt=datetime.now().isoformat(timespec="seconds"), status="in_progress", responses={})
        store.save_lesson(test)
    return test


def _grade_placement(store: Store, lesson: dict) -> dict:
    items = [{**i, "answer": lesson["responses"].get(i["id"], {}).get("text", "")} for i in lesson["items"]]
    payload = {"today": date.today().isoformat(),
               "profile": {k: v for k, v in store.read("profile", {}).items() if k != "settings"}, "items": items}
    result = claude.ask("grade_placement", payload, "placement_result", _model(store, "assess"))
    with LOCK:
        store.write("skills", apply_patch(store.read("skills", []), result.pop("skills"), lesson["id"]))
        profile = store.read("profile", {})
        profile.update(notes=result.pop("notes"), levels={d["name"]: d["level"] for d in result["dimensions"]})
        store.write("profile", profile)
        for r in result.pop("itemResults"):
            if r["id"] in lesson["responses"]:
                lesson["responses"][r["id"]].update(result=r["result"], feedback=r["feedback"], ai=True)
        done = sum(l.get("status") == "done" for l in store.lessons())
        store.write("assessments", store.read("assessments", []) + [
            {**result, "source": "placement", "assessedAt": datetime.now().isoformat(timespec="seconds"), "lessonsDone": done + 1}])
        lesson.update(status="done", score=_score(lesson), finishedAt=datetime.now().isoformat(timespec="seconds"),
                      review={"summary": result["summary"], "nextLesson": " ".join(f"{i + 1}. {p['title']}." for i, p in enumerate(result["plan"]))})
        store.save_lesson(lesson)
    return lesson


def get_lesson(store: Store, lesson_id: str) -> dict:
    lesson = store.lesson(lesson_id)
    if lesson is None:
        raise KeyError(f"lesson {lesson_id} not found")
    return lesson


def respond(store: Store, lesson_id: str, item_id: str, text: str) -> dict:
    lesson = get_lesson(store, lesson_id)
    item = next((i for i in lesson["items"] if i["id"] == item_id), None)
    if item is None:
        raise KeyError(f"item {item_id} not found")
    placement = lesson.get("kind") == "placement"
    result = None if placement else check(item, text)
    response = {"text": text, "result": result or "noted"}
    if not placement and (item["type"] in ("write", "explain") or result == "mismatch" and claude.available()[0]):
        verdict = claude.ask("check_answer", {"item": item, "answer": text}, "check", _model(store, "check"))
        response.update(verdict, result=verdict["result"], ai=True)
    if item.get("useChunks") and response["result"] in ("correct", "minor"):
        response["usedChunks"] = _review_used(store, item["useChunks"], text)
    with LOCK:
        lesson = get_lesson(store, lesson_id)
        lesson["responses"][item_id] = response
        store.save_lesson(lesson)
    return response


def _review_used(store: Store, chunks: list[dict], text: str) -> list[str]:
    answer = f" {normalise(text)} "
    used = [c["chunk"] for c in chunks if f" {normalise(c['chunk'])} " in answer]
    for w in store.read("words", []):
        if w.get("srs") and w["word"].lower() in {_chunk_word(u).lower() for u in used}:
            review_word(store, w["id"], srs.GOOD)
    return used


def finish(store: Store, lesson_id: str) -> dict:
    lesson = get_lesson(store, lesson_id)
    if lesson.get("kind") == "placement":
        return _grade_placement(store, lesson)
    touched = {i["skill"] for i in lesson["items"]} | set(lesson.get("focus", []))
    payload = {"today": date.today().isoformat(), "lesson": lesson,
               "skills": [s for s in store.read("skills", []) if s["id"] in touched]}
    review = claude.ask("review", payload, "review", _model(store, "review"))
    with LOCK:
        previous = _gate_lesson(store).get("drillSkill")
        store.write("skills", apply_patch(store.read("skills", []), review.pop("skills"), lesson_id))
        lesson = get_lesson(store, lesson_id)
        lesson.update(review=review, status="done", score=_score(lesson), drillSkill=drills.pick(store.read("skills", []), previous),
                      finishedAt=datetime.now().isoformat(timespec="seconds"))
        store.save_lesson(lesson)
        add_chunks(store, lesson)
    return lesson


def import_vault(store: Store, vault: Path) -> dict:
    if store.read("skills", None) is not None:
        raise ValueError("data already exists, import runs only once")
    files = {n: (vault / f"{n}.md").read_text("utf-8") for n in VAULT_FILES if (vault / f"{n}.md").exists()}
    if "Profile" not in files:
        raise ValueError(f"no Profile.md in {vault}")
    data = claude.ask("import", files, "import", _model(store, "generate"))
    with LOCK:
        store.write("profile", {**data["profile"], "settings": store.read("profile", {}).get("settings", {})})
        store.write("skills", apply_patch([], data["skills"], "import"))
        first = min((h["date"] for h in data["history"]), default=date.today().isoformat())
        store.write("assessments", [baseline(data["profile"], first)])
        for past in sorted(data["history"], key=lambda h: h["date"]):
            store.save_lesson({"id": store.next_lesson_id(past["date"]), "createdAt": f"{past['date']}T00:00:00",
                               "topic": past["topic"], "status": "done", "imported": True, "score": past["score"],
                               "items": [], "responses": {},
                               "review": {"summary": past["summary"], "nextFocus": past["nextFocus"]}})
    return state(store)
