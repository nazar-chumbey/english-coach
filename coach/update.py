from __future__ import annotations

import json
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = "nazar-chumbey/english-coach"
ASSET = "EnglishCoach-macOS.zip"
TTL = 6 * 3600
CACHE = {"at": 0.0, "release": None}


def current(root: Path) -> str:
    file = root / "version.txt"
    return file.read_text("utf-8").strip() if file.exists() else "dev"


def _parse(tag: str) -> tuple[int, ...]:
    return tuple(int(part) for part in tag.lstrip("v").split("."))


def _open(url: str):
    import certifi
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "english-coach"})
    return urllib.request.urlopen(request, timeout=15, context=ssl.create_default_context(cafile=certifi.where()))


def latest() -> dict:
    if time.time() - CACHE["at"] > TTL:
        with _open(f"https://api.github.com/repos/{REPO}/releases/latest") as response:
            CACHE.update(at=time.time(), release=json.load(response))
    return CACHE["release"]


def check(version: str) -> dict:
    if version == "dev":
        return {"current": version, "available": False}
    release = latest()
    return {"current": version, "latest": release["tag_name"], "notes": release.get("body") or "",
            "available": _parse(release["tag_name"]) > _parse(version)}


def install() -> dict:
    app = Path(sys.executable).resolve().parents[2]
    if app.suffix != ".app":
        raise ValueError("updates work only from the installed app")
    release = latest()
    asset = next(a for a in release["assets"] if a["name"] == ASSET)
    work = Path(tempfile.mkdtemp(dir=app.parent, prefix=".english-coach-update-"))
    with _open(asset["browser_download_url"]) as response, open(work / ASSET, "wb") as file:
        shutil.copyfileobj(response, file)
    subprocess.run(["ditto", "-x", "-k", str(work / ASSET), str(work)], check=True)
    app.rename(work / "old.app")
    (work / app.name).rename(app)
    subprocess.Popen(["/bin/sh", "-c", f'sleep 2; rm -rf "{work}"; open --env EC_NO_WINDOW=1 "{app}"'], start_new_session=True)
    return {"ok": True, "version": release["tag_name"]}
