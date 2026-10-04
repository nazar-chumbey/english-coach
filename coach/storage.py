from __future__ import annotations

import json
import os
import re
from pathlib import Path

LESSON_ID = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{2}$")


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        (self.root / "lessons").mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def read(self, name: str, default):
        path = self._path(name)
        return json.loads(path.read_text("utf-8")) if path.exists() else default

    def write(self, name: str, obj) -> None:
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), "utf-8")
        os.replace(tmp, path)

    def lesson(self, lesson_id: str) -> dict | None:
        if not LESSON_ID.match(lesson_id):
            return None
        return self.read(f"lessons/{lesson_id}", None)

    def save_lesson(self, lesson: dict) -> None:
        self.write(f"lessons/{lesson['id']}", lesson)

    def lessons(self) -> list[dict]:
        items = [json.loads(p.read_text("utf-8")) for p in (self.root / "lessons").glob("*.json")]
        return sorted(items, key=lambda l: l["id"], reverse=True)

    def next_lesson_id(self, date: str) -> str:
        taken = [p.stem for p in (self.root / "lessons").glob(f"{date}-*.json")]
        return f"{date}-{len(taken) + 1:02d}"
