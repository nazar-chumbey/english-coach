from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from coach import service
from coach.claude import ClaudeError
from coach.storage import Store

ROOT = Path(__file__).parent
WEB = ROOT / "web"
DEFAULT_VAULT = Path.home() / "Documents/Obsidian/English/IT English Coach"
LESSON = r"/api/lessons/([\w-]+)"


def make_handler(store: Store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if not self.path.startswith("/api/state"):
                sys.stderr.write(f"{self.command} {self.path} {args[1] if len(args) > 1 else ''}\n")

        def _send(self, code: int, body: bytes, kind: str):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _body(self) -> dict:
            size = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(size) or b"{}")

        def _route(self, routes):
            path = self.path.split("?")[0]
            for pattern, fn in routes:
                match = re.fullmatch(pattern, path)
                if match:
                    try:
                        return self._json(200, fn(*match.groups()))
                    except KeyError as e:
                        return self._json(404, {"error": str(e).strip("'")})
                    except ValueError as e:
                        return self._json(400, {"error": str(e)})
                    except ClaudeError as e:
                        return self._json(502, {"error": str(e)})
                    except Exception as e:
                        self.log_error("%r", e)
                        return self._json(500, {"error": f"{type(e).__name__}: {e}"})
            if path.startswith("/api/"):
                return self._json(404, {"error": "not found"})
            self._static(path)

        def _static(self, path: str):
            target = (WEB / path.lstrip("/")).resolve()
            if target.is_dir():
                target = target / "index.html"
            if WEB.resolve() not in target.parents or not target.is_file():
                return self._send(404, b"not found", "text/plain")
            kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self._send(200, target.read_bytes(), f"{kind}; charset=utf-8" if kind.startswith("text") or kind.endswith("javascript") else kind)

        def do_GET(self):
            self._route([
                (r"/api/state", lambda: service.state(store)),
                (LESSON, lambda i: service.get_lesson(store, i)),
            ])

        def do_POST(self):
            body = self._body()
            self._route([
                (r"/api/lessons", lambda: service.generate(store, int(body.get("minutes", 15)), body.get("focusSkill"))),
                (LESSON + "/responses", lambda i: service.respond(store, i, body["itemId"], body.get("text", ""))),
                (LESSON + "/finish", lambda i: service.finish(store, i)),
                (LESSON + "/quiz", lambda i: service.pass_quiz(store, i, body.get("results", []))),
                (LESSON + "/homework", lambda i: service.set_homework(store, i, body.get("status"), body.get("notes", ""))),
                (r"/api/words", lambda: service.save_word(store, body.get("word", ""), body.get("context", ""), body.get("lessonId"))),
                (r"/api/words/(w\d+)/delete", lambda i: service.delete_word(store, i)),
                (r"/api/words/(w\d+)", lambda i: service.set_word(store, i, body)),
                (r"/api/words/(w\d+)/review", lambda i: service.review_word(store, i, int(body.get("rating", 0)))),
                (r"/api/words/(w\d+)/recall", lambda i: service.check_recall(store, i, body.get("text", ""))),
                (r"/api/words/(w\d+)/sentence", lambda i: service.check_sentence(store, i, body.get("text", ""))),
                (r"/api/words/enrich", lambda: service.enrich_words(store)),
                (r"/api/words/suggest", lambda: service.suggest_words(store, body.get("kind", ""))),
                (r"/api/drills", lambda: service.generate_drill(store, body.get("skillId", ""))),
                (r"/api/drills/([\w-]+)/check", lambda i: service.check_drill(store, i, body.get("exercise", {}), body.get("pattern", {}), body.get("text", ""))),
                (r"/api/drills/([\w-]+)/finish", lambda i: service.finish_drill(store, i, body)),
                (r"/api/settings", lambda: service.update_settings(store, body)),
                (r"/api/assessment", lambda: service.assess(store)),
                (r"/api/onboarding", lambda: service.onboard(store, body)),
                (r"/api/placement", lambda: service.generate_placement(store)),
                (r"/api/import", lambda: service.import_vault(store, Path(body.get("vaultPath") or DEFAULT_VAULT).expanduser())),
            ])

    return Handler


def serve(port: int, data: Path) -> ThreadingHTTPServer:
    store = Store(data)
    service.backfill_chunks(store)
    service.assign_drill(store)
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(store))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = serve(port, Path(os.environ.get("EC_DATA", ROOT / "data")))
    print(f"English Coach: http://localhost:{port}")
    server.serve_forever()
