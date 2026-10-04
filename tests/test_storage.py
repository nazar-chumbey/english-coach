import tempfile
import unittest
from pathlib import Path

from coach.storage import Store


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.store = Store(self.root)

    def test_round_trip(self):
        self.store.write("profile", {"name": "Nazar", "levels": {"grammar": "A1+"}})
        self.assertEqual(self.store.read("profile", {})["levels"]["grammar"], "A1+")

    def test_read_default_when_missing(self):
        self.assertEqual(self.store.read("skills", []), [])

    def test_write_leaves_no_temp_files(self):
        self.store.write("skills", [{"id": "articles"}])
        self.assertEqual([p.name for p in self.root.rglob("*.tmp")], [])

    def test_next_lesson_id_increments_per_day(self):
        self.assertEqual(self.store.next_lesson_id("2026-09-29"), "2026-09-29-01")
        self.store.save_lesson({"id": "2026-09-29-01", "createdAt": "2026-09-29T10:00:00"})
        self.assertEqual(self.store.next_lesson_id("2026-09-29"), "2026-09-29-02")

    def test_lessons_sorted_newest_first(self):
        self.store.save_lesson({"id": "2026-09-01-01", "createdAt": "2026-09-01T10:00:00"})
        self.store.save_lesson({"id": "2026-09-29-01", "createdAt": "2026-09-29T10:00:00"})
        self.assertEqual([l["id"] for l in self.store.lessons()], ["2026-09-29-01", "2026-09-01-01"])

    def test_write_recreates_missing_root(self):
        import shutil
        shutil.rmtree(self.root)
        self.store.save_lesson({"id": "2026-09-29-01"})
        self.assertEqual(self.store.lesson("2026-09-29-01"), {"id": "2026-09-29-01"})

    def test_lesson_missing_returns_none(self):
        self.assertIsNone(self.store.lesson("nope"))

    def test_lesson_id_cannot_escape_root(self):
        self.assertIsNone(self.store.lesson("../profile"))


if __name__ == "__main__":
    unittest.main()
