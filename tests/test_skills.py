import unittest

from coach.skills import apply_patch


class ApplyPatchTest(unittest.TestCase):
    def setUp(self):
        self.skills = [
            {"id": "articles", "kind": "mistake", "title": "Articles", "status": "weak", "count": 12,
             "examples": [{"wrong": f"w{i}", "right": f"r{i}", "lesson": "old"} for i in range(5)],
             "analogiesTried": []},
            {"id": "questions", "kind": "grammar", "title": "Questions", "status": "improving", "count": 3},
        ]

    def test_updates_existing_and_bumps_count(self):
        patch = [{"id": "articles", "status": "improving", "countDelta": 2, "analogy": "pointer vs value",
                  "examples": [{"wrong": "open PR", "right": "open a PR"}]}]
        result = {s["id"]: s for s in apply_patch(self.skills, patch, "2026-09-29-01")}
        art = result["articles"]
        self.assertEqual((art["status"], art["count"]), ("improving", 14))
        self.assertEqual(len(art["examples"]), 5)
        self.assertEqual(art["examples"][-1], {"wrong": "open PR", "right": "open a PR", "lesson": "2026-09-29-01"})
        self.assertEqual(art["analogiesTried"], ["pointer vs value"])
        self.assertEqual(result["questions"]["count"], 3)

    def test_adds_new_skill_with_defaults(self):
        patch = [{"id": "prepositions", "kind": "mistake", "title": "Prepositions", "countDelta": 1}]
        new = apply_patch(self.skills, patch, "2026-09-29-01")[-1]
        self.assertEqual((new["id"], new["count"], new["status"]), ("prepositions", 1, "weak"))

    def test_does_not_mutate_input(self):
        apply_patch(self.skills, [{"id": "articles", "countDelta": 1}], "x")
        self.assertEqual(self.skills[0]["count"], 12)


if __name__ == "__main__":
    unittest.main()
