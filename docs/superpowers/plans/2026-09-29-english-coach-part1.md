# English Coach Part 1 Implementation Plan

> **For agentic workers:** execute task-by-task with superpowers:executing-plans. No git in this project (user choice) — no commit steps.

**Goal:** Local site that generates adaptive lessons via `claude -p`, checks answers instantly, keeps history and mistakes in `data/`.

**Architecture:** Python stdlib `http.server` serves `web/` and a JSON API under `/api/*`; `coach/` holds storage, the Claude wrapper, prompt/context building and local answer checking. Frontend is no-build ES modules with a hash router and one file per screen.

**Tech Stack:** Python 3.9+ stdlib, `claude` CLI 2.1+, vanilla JS/CSS. Tests: `python3 -m unittest`.

**Verified 2026-09-29:** `claude -p --output-format json --json-schema <s> --system-prompt <p> --tools "" --setting-sources "" --no-session-persistence --model sonnet` returns `structured_output`, does not see `~/.claude/CLAUDE.md`, ~12 s per call.

---

## File map

| File | Responsibility |
|---|---|
| `coach/storage.py` | `Store(root)`: `read(name, default)`, `write(name, obj)` atomic; `lessons()`, `lesson(id)`, `save_lesson(obj)`, `next_lesson_id(date)` |
| `coach/claude.py` | `ask(prompt_name, payload, schema_name, model) -> dict`; `available() -> (bool, str)`; raises `ClaudeError` |
| `coach/checker.py` | `normalise(text)`, `check(item, answer) -> "correct" | "mismatch" | "wrong"` |
| `coach/context.py` | `build(store, focus_skill=None) -> dict` compact memory slice; `item_count(minutes)` |
| `coach/skills.py` | `apply_patch(skills, patch, lesson_id) -> list` |
| `coach/service.py` | `generate`, `check_answer`, `save_response`, `finish`, `import_vault` — orchestration used by the server |
| `coach/schemas/*.json` | `lesson`, `check`, `review`, `import` |
| `coach/prompts/*.md` | `generate_lesson`, `check_answer`, `review`, `import` — pedagogy from the skill |
| `server.py` | routing, JSON I/O, static files |
| `start.sh` | dependency checks, starts server, opens browser |
| `web/*` | `index.html`, `app.js`, `api.js`, `ui.js`, `soft.css`, `views/{home,lesson,history,mistakes,settings}.js` |

## Tasks

### Task 1: storage
Tests (`tests/test_storage.py`): write→read round-trip; `read` returns default when missing; no `.tmp` left after write; `next_lesson_id("2026-09-29")` → `2026-09-29-01`, then `-02` after a save; `lessons()` sorted newest first.

### Task 2: checker
Tests (`tests/test_checker.py`): case/whitespace/trailing punctuation/curly quotes ignored; `I've` ≡ `I have`, `don't` ≡ `do not`; `choice` wrong option → `wrong`; `gap`/`fix` non-match → `mismatch` (never `wrong`); `write`/`explain`/`confidence` → `None` (not locally checkable).

### Task 3: skills patch + context
Tests (`tests/test_skills.py`, `tests/test_context.py`): patch updates existing skill fields, bumps `count` by `countDelta`, appends examples with lesson id (max 5 kept), adds new skills, keeps untouched ones; `item_count(10/15/20/30)` = 8/12/16/24; `build` orders skills (mistake count ≥3 → understanding none/partial → weak → overdue), caps at 8, includes last 3 `nextFocus`, puts `focus_skill` first.

### Task 4: claude wrapper
Tests (`tests/test_claude.py`, subprocess mocked): builds the verified argument list; parses `structured_output`; non-zero exit / `is_error` / missing output → `ClaudeError` after one retry; timeout → `ClaudeError`.

### Task 5: service + server
Tests (`tests/test_server.py`, `claude.ask` mocked, server on a random port): `GET /api/state` returns profile, skills, lesson summaries, `claude` availability; `POST /api/lessons` creates a lesson; `POST /api/lessons/<id>/responses` stores and returns local result; `POST /api/lessons/<id>/finish` stores review and patches skills; `POST /api/settings` merges settings; unknown route → 404 JSON; static `/` serves `index.html`.

### Task 6: prompts + schemas
Port the skill's rules into the four prompts. Verify with one real `generate` call against imported data (manual).

### Task 7: frontend
Soft UI CSS (light/dark/auto), router, 5 screens. Manual check in the browser via Chrome DevTools MCP, both themes.

### Task 8: import + start.sh
Real one-time import of `~/Documents/Obsidian/English/IT English Coach`; `start.sh` checks `python3` and `claude`, starts server on 8765 (or next free), opens browser.

## Verification
`python3 -m unittest discover -s tests` green; end-to-end: import → generate 10-min lesson → answer all items → finish → review visible in History and Mistakes.
