from __future__ import annotations

import os
import subprocess
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"

tag = os.environ.get("GITHUB_REF_NAME", "")
version = tag if tag.startswith("v") else subprocess.run(
    ["git", "describe", "--tags", "--abbrev=0"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "dev"
BUILD.mkdir(exist_ok=True)
(BUILD / "version.txt").write_text(version, "utf-8")

PyInstaller.__main__.run([
    str(ROOT / "app.py"), "--name", "English Coach", "--windowed", "--noconfirm",
    "--icon", str(ROOT / "tools/icon.png"), "--hidden-import", "certifi",
    "--osx-bundle-identifier", "com.nazarchumbey.englishcoach",
    "--distpath", str(ROOT / "dist"), "--workpath", str(BUILD), "--specpath", str(BUILD),
    *[arg for src, dest in ((ROOT / "web", "web"), (ROOT / "coach/prompts", "coach/prompts"),
                            (ROOT / "coach/schemas", "coach/schemas"), (BUILD / "version.txt", "."))
      for arg in ("--add-data", f"{src}:{dest}")],
])
