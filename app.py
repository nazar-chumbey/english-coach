from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import server

NAME = "English Coach"
PORTS = range(8765, 8785)
IDLE = 180
HOME = Path.home()
DATA = HOME / "Library/Application Support" / NAME
BROWSERS = (Path("/Applications/Google Chrome.app"), Path("/Applications/Microsoft Edge.app"))


def load_shell_env() -> None:
    marker = "__EC_ENV__"
    try:
        out = subprocess.run([os.environ.get("SHELL", "/bin/zsh"), "-ilc", f"printf {marker}; env -0"],
                             capture_output=True, timeout=15, stdin=subprocess.DEVNULL).stdout
        pairs = out.split(marker.encode(), 1)[-1].decode(errors="ignore").split("\0")
        os.environ.update(p.split("=", 1) for p in pairs if "=" in p)
    except (OSError, subprocess.TimeoutExpired):
        pass
    extra = [HOME / ".local/bin", Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    os.environ["PATH"] = os.pathsep.join([os.environ.get("PATH", ""), *map(str, extra)])


def running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as r:
            return json.loads(r.read()).get("app") == "english-coach"
    except OSError:
        return False


def open_window(url: str) -> None:
    for app in BROWSERS:
        if app.is_dir():
            subprocess.run(["open", "-na", str(app), "--args", f"--app={url}"], check=False)
            return
    webbrowser.open(url)


def main() -> None:
    port = next((p for p in PORTS if running(p)), None)
    if port:
        return open_window(f"http://localhost:{port}")
    frozen = getattr(sys, "frozen", False)
    subprocess.Popen([sys.executable, *([] if frozen else [__file__]), "--serve"], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def serve() -> None:
    load_shell_env()
    data = Path(os.environ.get("EC_DATA") or DATA)
    for port in PORTS:
        try:
            httpd = server.serve(port, data)
            break
        except OSError:
            continue
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    open_window(f"http://localhost:{port}")
    started = time.time()
    while time.time() - (server.ACTIVITY["ping"] or started) < IDLE:
        time.sleep(5)
    httpd.shutdown()


if __name__ == "__main__":
    serve() if "--serve" in sys.argv else main()
