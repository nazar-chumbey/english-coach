import tempfile
import unittest
from pathlib import Path

from coach.context import build, item_count
from coach.storage import Store


class ItemCountTest(unittest.TestCase):
    def test_scales_with_minutes(self):
        self.assertEqual([item_count(m) for m in (10, 15, 20, 30)], [8, 12, 16, 24])


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.store = Store(Path(tempfile.mkdtemp()))
        self.store.write("profile", {"role": "Full-stack", "levels": {"grammar": "A1+"}, "settings": {"x": 1}})
        self.store.write("skills", [
            {"id": "due", "kind": "vocab", "status": "improving", "due": "2026-09-01"},
            {"id": "weak", "kind": "grammar", "status": "weak", "understanding": "solid"},
            {"id": "fuzzy", "kind": "grammar", "status": "improving", "understanding": "partial"},
            {"id": "recurring", "kind": "mistake", "status": "weak", "count": 5},
            {"id": "done", "kind": "grammar", "status": "mastered"},
            *[{"id": f"later{i}", "kind": "vocab", "status": "stable", "due": "2027-01-01"} for i in range(6)],
        ])
        for n, focus in enumerate(["a", "b", "c", "d"], 1):
            self.store.save_lesson({"id": f"2026-09-0{n}-01", "topic": focus, "status": "done",
                                    "review": {"nextFocus": focus}})

    def test_priority_order_and_cap(self):
        ctx = build(self.store, today="2026-09-29")
        ids = [s["id"] for s in ctx["skills"]]
        self.assertEqual(ids[:4], ["recurring", "fuzzy", "weak", "due"])
        self.assertNotIn("done", ids)
        self.assertEqual(len(ids), 8)

    def test_focus_skill_first(self):
        ctx = build(self.store, focus_skill="later3", today="2026-09-29")
        self.assertEqual(ctx["skills"][0]["id"], "later3")
        self.assertEqual(ctx["focusSkill"], "later3")

    def test_recent_focus_and_profile_without_settings(self):
        ctx = build(self.store, today="2026-09-29")
        self.assertEqual(ctx["recentFocus"], ["d", "c", "b"])
        self.assertNotIn("settings", ctx["profile"])


class BaselineTest(unittest.TestCase):
    def test_maps_placement_levels(self):
        from coach.service import baseline
        b = baseline({"levels": {"general": "A2", "grammar": "A1+", "listening": "self-reported 3/5 (not assessed)",
                                 "reading": "B1+ (inferred, not directly tested)"}}, "2026-08-27")
        self.assertEqual(b["overall"], "A2")
        dims = {d["name"]: d for d in b["dimensions"]}
        self.assertEqual((dims["Граматика"]["level"], dims["Граматика"]["measured"]), ("A1+", True))
        self.assertFalse(dims["Слухання"]["measured"])
        self.assertEqual(dims["Читання"]["note"], "inferred, not directly tested")


if __name__ == "__main__":
    unittest.main()
