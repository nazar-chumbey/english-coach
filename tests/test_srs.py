import unittest
from datetime import datetime, timedelta

from coach import srs

NOW = datetime(2026, 9, 30, 12)


class SrsTest(unittest.TestCase):
    def test_first_rating_sets_initial_stability(self):
        self.assertEqual([srs.review(None, g, NOW)["stability"] for g in (1, 2, 3, 4)], [0.403, 1.184, 3.173, 15.691])
        self.assertEqual(srs.review(None, 1, NOW)["due"], (NOW + timedelta(minutes=10)).isoformat())
        self.assertEqual(srs.review(None, 3, NOW)["due"], (NOW + timedelta(days=3)).isoformat())

    def test_successful_review_grows_and_lapse_shrinks(self):
        card = srs.review(None, 3, NOW)
        later = NOW + timedelta(days=3)
        good, again = srs.review(card, 3, later), srs.review(card, 1, later)
        self.assertGreater(good["stability"], card["stability"] * 2)
        self.assertLess(again["stability"], card["stability"])
        self.assertEqual((again["lapses"], good["lapses"], good["reps"]), (1, 0, 2))
        self.assertGreater(again["difficulty"], good["difficulty"])

    def test_bad_rating(self):
        with self.assertRaises(ValueError):
            srs.review(None, 5, NOW)
