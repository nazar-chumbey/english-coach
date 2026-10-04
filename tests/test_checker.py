import unittest

from coach.checker import check, normalise


class NormaliseTest(unittest.TestCase):
    def test_case_space_punctuation(self):
        self.assertEqual(normalise("  I Deployed   it yesterday. "), "i deployed it yesterday")

    def test_curly_quotes_and_contractions(self):
        self.assertEqual(normalise("I’ve pushed it"), normalise("I have pushed it"))
        self.assertEqual(normalise("It doesn't work!"), normalise("it does not work"))
        self.assertEqual(normalise("I won't"), normalise("I will not"))
        self.assertEqual(normalise("I can't"), normalise("I can not"))


class CheckTest(unittest.TestCase):
    def test_choice(self):
        item = {"type": "choice", "options": ["did", "have", "was"], "accept": ["did"]}
        self.assertEqual(check(item, "did"), "correct")
        self.assertEqual(check(item, "have"), "wrong")

    def test_gap_and_fix_never_hard_wrong(self):
        for kind in ("gap", "fix"):
            item = {"type": kind, "accept": ["I deployed it yesterday."]}
            self.assertEqual(check(item, "i deployed it yesterday"), "correct")
            self.assertEqual(check(item, "I shipped it yesterday"), "mismatch")

    def test_gap_accepts_whole_sentence(self):
        cases = [
            ("I ___ (move) the ticket to Code Review, so you can take a look now.", ["have moved", "'ve moved"],
             "I've moved the ticket to Code Review, so you can take a look now."),
            ("«Has the client replied?» — «No, I ___ back from them yet.»", ["haven't heard"],
             "No, I haven't heard back from them yet."),
            ("Встав пропущені слова:\n___ you ever ___ (work) with the FHIR standard?", ["Have, worked"],
             "Have you ever worked with the FHIR standard?"),
            ("We need ___ new endpoint. ___ endpoint returns ___ data.", ["a, The, —"],
             "We need a new endpoint. The endpoint returns data."),
        ]
        for prompt, accept, answer in cases:
            item = {"type": "gap", "prompt": prompt, "accept": accept}
            self.assertEqual(check(item, answer), "correct", prompt)
            self.assertEqual(check(item, accept[0]), "correct")
        item = {"type": "gap", "prompt": "I opened ___ PR.", "accept": ["a"]}
        self.assertEqual(check(item, "I opened the PR."), "mismatch")

    def test_open_items_not_checked_locally(self):
        for kind in ("write", "explain", "confidence"):
            self.assertIsNone(check({"type": kind}, "anything"))


if __name__ == "__main__":
    unittest.main()
