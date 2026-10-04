from __future__ import annotations

from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent

PyInstaller.__main__.run([
    str(ROOT / "app.py"), "--name", "English Coach", "--windowed", "--noconfirm",
    "--icon", str(ROOT / "tools/icon.png"),
    "--osx-bundle-identifier", "com.nazarchumbey.englishcoach",
    "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
    *[arg for src, dest in (("web", "web"), ("coach/prompts", "coach/prompts"), ("coach/schemas", "coach/schemas"))
      for arg in ("--add-data", f"{ROOT / src}:{dest}")],
])
