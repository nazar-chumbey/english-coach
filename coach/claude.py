from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
TIMEOUT = 480


class ClaudeError(RuntimeError):
    pass


class ClaudeTimeout(ClaudeError):
    pass


def available() -> tuple[bool, str]:
    if not shutil.which("claude"):
        return False, "Claude Code not found. Install it: https://claude.com/claude-code"
    return True, ""


def _once(args: list[str], payload: str) -> dict:
    try:
        proc = subprocess.run(args, input=payload, capture_output=True, text=True,
                              timeout=TIMEOUT, cwd=tempfile.gettempdir())
    except subprocess.TimeoutExpired:
        raise ClaudeTimeout("Claude did not answer in time")
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise ClaudeError((proc.stderr or proc.stdout).strip()[:300] or "Empty response from Claude")
    if proc.returncode or out.get("is_error") or out.get("structured_output") is None:
        raise ClaudeError(str(out.get("result") or proc.stderr)[:300])
    return out["structured_output"]


def _prompt(name: str) -> str:
    text = (HERE / "prompts" / f"{name}.md").read_text("utf-8")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: _prompt(m[1]), text)


def ask(prompt: str, payload: dict, schema: str, model: str) -> dict:
    args = [
        "claude", "-p", "--output-format", "json", "--no-session-persistence",
        "--tools", "", "--setting-sources", "", "--model", model,
        "--system-prompt", _prompt(prompt),
        "--json-schema", (HERE / "schemas" / f"{schema}.json").read_text("utf-8"),
    ]
    body = json.dumps(payload, ensure_ascii=False)
    try:
        return _once(args, body)
    except ClaudeTimeout:
        raise
    except ClaudeError:
        return _once(args, body)
