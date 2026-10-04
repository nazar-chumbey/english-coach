import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import server
from coach.claude import ClaudeError
from coach.storage import Store

LESSON = {
    "topic": "Auxiliaries", "rationale": "r", "focus": ["aux"], "chunks": [],
    "explanation": {"title": "t", "body": "b", "analogy": "a", "wrong": [], "right": []},
    "items": [
        {"id": "q1", "type": "choice", "section": "review", "prompt": "p", "options": ["did", "have"],
         "accept": ["did"], "why": "w", "skill": "aux"},
        {"id": "q2", "type": "write", "section": "situation", "prompt": "p", "why": "w", "skill": "articles"},
        {"id": "q3", "type": "gap", "section": "practice", "prompt": "I ___ (fix) it.", "accept": ["fixed"], "why": "w", "skill": "past"},
    ],
}
CHECK = {"result": "minor", "feedback": "f", "corrected": "c", "corrections": []}
ASSESSMENT = {"overall": "A2+", "summary": "s", "confidence": "low", "dimensions": [], "strengths": [],
              "weaknesses": [], "toTarget": {"summary": "t", "eta": "e", "steps": []}}
PLACEMENT = {"topic": "Placement test", "rationale": "r", "items": [
    {"id": "p1", "type": "gap", "section": "grammar", "prompt": "I ___ (fix) it yesterday.", "skill": "past"},
    {"id": "p2", "type": "write", "section": "writing", "prompt": "Stand-up", "skill": "standup"}]}
GRADED = {**ASSESSMENT, "notes": "n", "plan": [{"title": "Questions", "why": "w"}, {"title": "Articles", "why": "w"}],
          "dimensions": [{"name": "Граматика", "level": "A2", "measured": True, "note": ""}],
          "itemResults": [{"id": "p1", "result": "wrong", "feedback": "fixed"}, {"id": "p2", "result": "minor", "feedback": "f"}],
          "skills": [{"id": "past", "kind": "grammar", "countDelta": 1}]}
REVIEW = {"summary": "s", "improved": [], "corrections": [], "understanding": "u", "nextFocus": "n",
          "recommendation": "r", "skills": [{"id": "articles", "kind": "mistake", "countDelta": 1}]}


CARD = {"meaning": "натрапити", "ipa": "/rʌn/", "example": "e", "association": "a", "collocations": ["c"],
        "cloze": "We ___ a bug.", "clozeAnswer": "ran into", "distractors": ["x", "y", "z"]}
CHUNKS = [{"chunk": "walk you through", "meaning": "пояснити", "example": "Let me walk you through the flow."},
          {"chunk": "as for ...", "meaning": "щодо", "example": "As for the UI, it works."}]
SUGGESTED = {"words": [{**CARD, "word": "roll back", "source": "work"}, {**CARD, "word": "Run into", "source": "work"}]}


def fake_ask(prompt, payload, schema, model):
    return json.loads(json.dumps({"generate_lesson": LESSON, "check_answer": CHECK, "review": REVIEW, "assess": ASSESSMENT,
                                 "generate_placement": PLACEMENT, "grade_placement": GRADED,
                                 "explain_word": {**CARD, "word": "run into"}, "suggest_words": SUGGESTED,
                                 "check_sentence": {"result": "minor", "feedback": "f", "corrected": "c"},
                                 "check_recall": {"result": "correct", "feedback": "f", "corrected": "c"},
                                 "check_drill": {"result": "minor", "feedback": "f", "corrected": "c"},
                                 "generate_drill": {"pattern": {"title": "t", "parts": []}, "explanation": "e", "exercises": []}}[prompt]))


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.data = Path(tempfile.mkdtemp())
        self.srv = server.serve(0, self.data)
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        patcher = mock.patch("coach.service.claude.ask", side_effect=fake_ask)
        self.ask = patcher.start()
        self.addCleanup(patcher.stop)
        available = mock.patch("coach.service.claude.available", return_value=(True, ""))
        available.start()
        self.addCleanup(available.stop)
        self.addCleanup(self.srv.shutdown)

    def pass_drill(self):
        drill = self.call("/api/state")[1]["gate"]["drill"]
        for _ in range(drill["required"]):
            gate = self.call(f"/api/drills/{drill['skillId']}/finish", {"levels": [1, 2, 3, 4, 5], "passed": True, "clean": False})[1]
        return gate

    def call(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_full_lesson_flow(self):
        code, lesson = self.call("/api/lessons", {"minutes": 10})
        self.assertEqual((code, lesson["status"], lesson["minutes"]), (200, "in_progress", 10))
        lid = lesson["id"]
        self.assertEqual(self.call(f"/api/lessons/{lid}/responses", {"itemId": "q1", "text": "did"})[1]["result"], "correct")
        self.assertEqual(self.call(f"/api/lessons/{lid}/responses", {"itemId": "q2", "text": "I open PR"})[1]["result"], "minor")
        code, done = self.call(f"/api/lessons/{lid}/finish", {})
        self.assertEqual((code, done["status"], done["score"], done["review"]["nextFocus"]), (200, "done", "2/2", "n"))
        state = self.call("/api/state")[1]
        self.assertEqual(state["skills"][0]["id"], "articles")
        self.assertEqual(state["lessons"][0]["id"], lid)

    def test_choice_does_not_call_ai(self):
        lid = self.call("/api/lessons", {"minutes": 10})[1]["id"]
        self.ask.reset_mock()
        self.call(f"/api/lessons/{lid}/responses", {"itemId": "q1", "text": "have"})
        self.ask.assert_not_called()

    def test_gap_sentence_local_and_mismatch_goes_to_ai(self):
        lid = self.call("/api/lessons", {"minutes": 10})[1]["id"]
        self.ask.reset_mock()
        self.assertEqual(self.call(f"/api/lessons/{lid}/responses", {"itemId": "q3", "text": "I fixed it."})[1]["result"], "correct")
        self.ask.assert_not_called()
        r = self.call(f"/api/lessons/{lid}/responses", {"itemId": "q3", "text": "I have fixed it."})[1]
        self.assertEqual((r["result"], r["ai"]), ("minor", True))

    def test_saved_words(self):
        w = self.call("/api/words", {"word": " ran into, ", "context": "I ran into an issue", "lessonId": "x"})[1]
        self.assertEqual((w["id"], w["word"], w["meaning"], w["lessons"]), ("w1", "run into", "натрапити", []))
        self.assertEqual(self.call("/api/words", {"word": "Run into"})[1]["id"], "w1")
        self.assertEqual(self.call("/api/words", {"word": " "})[0], 400)
        for _ in range(3):
            lid = self.call("/api/lessons", {"minutes": 10})[1]["id"]
            self.assertEqual(self.ask.call_args.args[1]["savedWords"][0]["word"], "run into")
        self.call("/api/lessons", {"minutes": 10})
        self.assertEqual(self.ask.call_args.args[1]["savedWords"], [])
        self.assertEqual(len(self.call("/api/state")[1]["words"][0]["lessons"]), 3)
        self.assertEqual(self.call("/api/words/w1/delete", {}), (200, {"ok": True}))
        self.assertEqual(self.call("/api/words/w1/delete", {})[0], 404)
        self.assertEqual(self.call("/api/state")[1]["words"], [])

    def test_word_training(self):
        self.call("/api/words", {"word": "run into"})
        words = self.call("/api/words/suggest", {"kind": "work"})[1]
        self.assertEqual([(w["word"], w["status"], w["source"]) for w in words],
                         [("run into", "learning", "saved"), ("roll back", "suggested", "work")])
        self.assertEqual(self.ask.call_args.args[1]["known"], ["run into"])
        self.assertEqual(self.call("/api/words/suggest", {"kind": "x"})[0], 400)
        self.assertEqual(self.call("/api/words/w2", {"status": "known", "word": "hack"})[1]["word"], "roll back")
        self.assertEqual(self.call("/api/words/w2", {"status": "nope"})[0], 400)
        w = self.call("/api/words/w1/review", {"rating": 3})[1]
        self.assertEqual((w["srs"]["reps"], w["srs"]["stability"]), (1, 3.173))
        self.assertEqual(self.call("/api/words/w1/review", {"rating": 9})[0], 400)
        self.assertEqual(self.call("/api/words/w1/sentence", {"text": "I ran into it"})[1]["result"], "minor")
        self.assertEqual(self.call("/api/words/w9/review", {"rating": 3})[0], 404)
        self.assertEqual(self.call("/api/words/w1/recall", {"text": "we ran into a sink issue"})[1]["result"], "correct")
        self.assertEqual(self.ask.call_args.args[1]["chunk"], "run into")
        self.assertEqual(self.call("/api/words/w1/recall", {"text": " "})[0], 400)
        self.call("/api/lessons", {"minutes": 10})
        self.assertEqual([w["word"] for w in self.ask.call_args.args[1]["savedWords"]], ["run into"])

    def test_enrich_fills_old_cards(self):
        with mock.patch("coach.service.claude.available", return_value=(False, "")):
            self.assertNotIn("cloze", self.call("/api/words", {"word": "Run  into"})[1])
        w = self.call("/api/words/enrich", {})[1][0]
        self.assertEqual((w["word"], w["cloze"]), ("Run into", "We ___ a bug."))

    def test_errors(self):
        self.assertEqual(self.call("/api/lessons", {"minutes": 7})[0], 400)
        self.assertEqual(self.call("/api/lessons/2026-01-01-01")[0], 404)
        self.assertEqual(self.call("/api/nope")[0], 404)
        self.ask.side_effect = ClaudeError("down")
        self.assertEqual(self.call("/api/lessons", {"minutes": 10}), (502, {"error": "down"}))

    def test_settings_merge(self):
        s = self.call("/api/settings", {"theme": "dark", "models": {"check": "haiku"}})[1]
        self.assertEqual((s["theme"], s["models"]["check"], s["models"]["generate"]), ("dark", "haiku", "sonnet"))
        self.call("/api/settings", {"name": " Назар "})
        profile = self.call("/api/state")[1]["profile"]
        self.assertEqual((profile["name"], "name" in profile["settings"]), ("Назар", False))

    def test_assessment_and_goal(self):
        self.assertEqual(self.call("/api/state")[1]["newLessonsSinceAssessment"], 0)
        lid = self.call("/api/lessons", {"minutes": 10})[1]["id"]
        self.call(f"/api/lessons/{lid}/finish", {})
        self.assertEqual(self.call("/api/state")[1]["newLessonsSinceAssessment"], 1)
        code, a = self.call("/api/assessment", {})
        self.assertEqual((code, a["overall"], a["source"], a["lessonsDone"]), (200, "A2+", "agent", 1))
        state = self.call("/api/state")[1]
        self.assertEqual((len(state["assessments"]), state["newLessonsSinceAssessment"]), (1, 0))
        self.call("/api/settings", {"goal": {"target": "B2", "purpose": "p"}})
        self.call("/api/settings", {"goal": {"deadline": "2026-12-31"}})
        goal = self.call("/api/state")[1]["profile"]["goal"]
        self.assertEqual(goal, {"target": "B2", "purpose": "p", "deadline": "2026-12-31"})

    def test_onboarding_and_placement(self):
        self.assertEqual(self.call("/api/placement", {})[0], 400)
        self.call("/api/onboarding", {"name": "Олег", "role": "QA", "minutes": 20, "goal": {"target": "B2", "purpose": "співбесіди"}})
        profile = self.call("/api/state")[1]["profile"]
        self.assertEqual((profile["name"], profile["settings"]["defaultMinutes"], profile["goal"]["purpose"]), ("Олег", 20, "співбесіди"))
        test = self.call("/api/placement", {})[1]
        self.assertEqual(test["kind"], "placement")
        self.ask.reset_mock()
        r = self.call(f"/api/lessons/{test['id']}/responses", {"itemId": "p2", "text": "I fix bug"})[1]
        self.assertEqual(r["result"], "noted")
        self.ask.assert_not_called()
        self.call(f"/api/lessons/{test['id']}/responses", {"itemId": "p1", "text": "fix"})
        done = self.call(f"/api/lessons/{test['id']}/finish", {})[1]
        self.assertEqual((done["status"], done["responses"]["p1"]["result"], done["score"]), ("done", "wrong", "1/2"))
        state = self.call("/api/state")[1]
        self.assertEqual((state["assessments"][-1]["source"], state["profile"]["levels"]), ("placement", {"Граматика": "A2"}))
        self.assertEqual(state["skills"][0]["id"], "past")
        lesson = self.call("/api/lessons", {"minutes": 10})[1]
        payload = self.ask.call_args.args[1]
        self.assertEqual(payload["placementPlan"][0]["title"], "Questions")
        self.call(f"/api/lessons/{lesson['id']}/finish", {})
        self.call(f"/api/lessons/{lesson['id']}/homework", {"status": "skipped", "notes": "busy"})
        self.pass_drill()
        self.call("/api/lessons", {"minutes": 10})
        self.assertEqual(self.ask.call_args.args[1]["placementPlan"][0]["title"], "Articles")

    def test_lesson_gate(self):
        self.ask.side_effect = lambda p, *a: {**fake_ask(p, *a), "chunks": CHUNKS} if p == "generate_lesson" else fake_ask(p, *a)
        lid = self.call("/api/lessons", {"minutes": 10})[1]["id"]
        self.call(f"/api/lessons/{lid}/finish", {})
        state = self.call("/api/state")[1]
        self.assertEqual([(w["word"], w["source"], w["cloze"]) for w in state["words"]],
                         [("walk you through", "lesson", "Let me ___ the flow."), ("as for", "lesson", "___ the UI, it works.")])
        self.assertEqual((state["gate"]["quiz"], state["gate"]["ready"], state["gate"]["words"]), (False, False, ["w1", "w2"]))
        self.assertEqual(self.call("/api/lessons", {"minutes": 10})[0], 400)
        gate = self.call(f"/api/lessons/{lid}/quiz", {"results": [{"wordId": "w1", "firstTry": True}, {"wordId": "w2", "firstTry": False}]})[1]
        self.assertEqual((gate["quiz"], gate["dueChunks"], gate["ready"]), (True, 0, False))
        self.assertEqual([w["srs"]["stability"] for w in self.call("/api/state")[1]["words"]], [3.173, 1.184])
        self.assertEqual(self.call(f"/api/lessons/{lid}/homework", {"status": "done", "notes": " "})[0], 400)
        self.assertFalse(self.call(f"/api/lessons/{lid}/homework", {"status": "done", "notes": "3 examples"})[1]["ready"])
        self.assertTrue(self.pass_drill()["ready"])
        self.call("/api/lessons", {"minutes": 10})
        payload = self.ask.call_args.args[1]
        self.assertEqual((payload["previousHomework"]["notes"], payload["savedWords"]), ("3 examples", []))
        words = json.loads((self.data / "words.json").read_text("utf-8"))
        words[0]["srs"]["due"] = "2026-01-01T00:00:00"
        (self.data / "words.json").write_text(json.dumps(words), "utf-8")
        self.assertEqual(self.call("/api/state")[1]["gate"]["dueChunks"], 1)

    def test_used_chunks_count_as_review(self):
        self.call("/api/words", {"word": "run into"})
        self.call("/api/words/w1/review", {"rating": 3})
        write = {"id": "q1", "type": "write", "section": "situation", "prompt": "p", "why": "w", "skill": "s",
                 "facts": "f", "model": "m", "useChunks": [{"chunk": "run into", "meaning": "натрапити"}, {"chunk": "so far", "meaning": "поки"}]}
        self.ask.side_effect = lambda p, *a: {**fake_ask(p, *a), "items": [write]} if p == "generate_lesson" else fake_ask(p, *a)
        lid = self.call("/api/lessons", {"minutes": 10})[1]["id"]
        self.assertEqual(self.ask.call_args.args[1]["learnedChunks"], [{"chunk": "run into", "meaning": "натрапити"}])
        r = self.call(f"/api/lessons/{lid}/responses", {"itemId": "q1", "text": "We run into a timeout."})[1]
        self.assertEqual(r["usedChunks"], ["run into"])
        self.assertEqual(self.call("/api/state")[1]["words"][0]["srs"]["reps"], 2)

    def test_drill(self):
        skills = [{"id": "a", "kind": "grammar", "status": "weak", "title": "A"}, {"id": "b", "kind": "mistake", "status": "improving"},
                  {"id": "c", "kind": "vocab", "status": "weak"}]
        (self.data / "skills.json").write_text(json.dumps(skills), "utf-8")
        session = self.call("/api/drills", {"skillId": "a"})[1]
        self.assertEqual((session["start"], self.ask.call_args.args[1]["seen"]), (1, []))
        self.assertEqual(self.call("/api/drills", {"skillId": "zz"})[0], 404)
        self.assertEqual(self.call("/api/drills/a/check", {"exercise": {}, "pattern": {}, "text": "x"})[1]["result"], "minor")
        self.call("/api/drills/a/finish", {"levels": [1, 2, 3], "passed": False, "answers": [f"s{i}" for i in range(30)]})
        self.assertEqual(self.call("/api/state")[1]["skills"][0]["status"], "weak")
        self.call("/api/drills/a/finish", {"levels": [3, 4, 5], "passed": True, "clean": True, "answers": [f"t{i}" for i in range(30)]})
        state = self.call("/api/state")[1]
        self.assertEqual((state["skills"][0]["status"], state["drills"]["a"]["level"], len(state["drills"]["a"]["seen"])), ("improving", 5, 40))
        self.assertEqual([s["passed"] for s in state["drills"]["a"]["sessions"]], [False, True])
        self.call("/api/drills", {"skillId": "a"})
        self.assertEqual((self.ask.call_args.args[1]["start"], self.ask.call_args.args[1]["seen"][-1]), (3, "t29"))
        self.call("/api/drills/a/finish", {"levels": [3, 4, 5], "passed": True, "clean": True})
        self.assertEqual(self.call("/api/state")[1]["skills"][0]["status"], "improving")
        from coach.drills import pick
        self.assertEqual({pick(skills, "a") for _ in range(20)}, {"b"})
        self.assertIsNone(pick([{"id": "x", "status": "stable"}]))

    def test_backfill_chunks_on_start(self):
        data = Path(tempfile.mkdtemp())
        Store(data).save_lesson({"id": "2026-09-30-01", "status": "done", "items": [],
                                 "chunks": [{"chunk": "Does that make sense?", "meaning": "m", "example": "Ok. Does that make sense?"}]})
        for _ in range(2):
            server.serve(0, data).server_close()
        self.assertEqual([(w["word"], w["cloze"]) for w in Store(data).read("words", [])], [("Does that make sense", "Ok. ___?")])

    def test_rejects_foreign_host_and_origin(self):
        port = self.srv.server_address[1]
        for headers in ({"Host": f"evil.example:{port}"}, {"Origin": "https://evil.example"}):
            req = urllib.request.Request(self.base + "/api/state", headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(req)
            self.assertEqual(caught.exception.code, 403)
        req = urllib.request.Request(self.base + "/api/state", headers={"Origin": f"http://localhost:{port}"})
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.status, 200)

    def test_update_check(self):
        release = {"tag_name": "v1.2.0", "html_url": "u", "assets": []}
        with mock.patch("coach.update.latest", return_value=release):
            self.assertEqual(self.call("/api/update")[1], {"current": "dev", "available": False})
            with mock.patch("server.VERSION", "v1.1.9"):
                self.assertEqual(self.call("/api/update")[1]["available"], True)
            with mock.patch("server.VERSION", "v1.10.0"):
                self.assertEqual(self.call("/api/update")[1]["available"], False)
        self.assertEqual(self.call("/api/update", {})[0], 400)

    def test_static_index_and_traversal(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertIn(b"<html", r.read())
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.base + "/../server.py")


if __name__ == "__main__":
    unittest.main()
