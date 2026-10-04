# Structure drill + drill in the lesson gate

## Problem
A new sentence structure (`what → because → why → so → action → check`) is hard to produce inside a
free-writing task: the learner juggles the structure, articles and verb forms at once and falls back
to two short sentences. The "Помилки" page only lists skills and offers a full 10-minute lesson.

## Changes

### 1. Tab rename
Nav "Помилки" → "Тренажер", page title "Тренажер", subtitle "Твої слабкі місця і тренажер на кожне".
Route stays `#/mistakes`.

### 2. Drill session (`#/drill/<skillId>`, button "Тренажер" on every skill card)
One Claude call (`generate_drill`, model = settings `generate`) returns:
- `pattern.parts`: ordered list of `{kind: "slot", label, hint}` (Ukrainian label/hint, e.g.
  «що сталося» / «підмет + дієслово») and `{kind: "fixed", text}` (`because`, `, so we need to`).
- `explanation`: ≤ 2 Ukrainian sentences on when to use the structure.
- `exercises`: 3 per level for levels `start..5`; each `{level, content (Ukrainian facts), slots
  (English, one per slot part), answer (full English sentence)}`.

Payload: skill (title, notes, examples), profile (role/stack/domain), `start`, `seen` (up to 40 earlier
answers for this skill — never repeat them), topics must rotate (bug, deploy, PR, call, stand-up).

Levels:
1. **Розбери** — pieces (slot texts + fixed texts) shuffled; learner clicks them in order. Local check.
2. **По частинах** — one input per slot with label + hint above, fixed parts shown between. Local check
   per slot (`recalled` from answer.js); any miss → Claude check of the assembled sentence.
3. **Разом** — one input, the pattern shown faded above.
4. **Складніше** — one input, only `content`; pattern hidden.
5. **Скажи** — like 4, with 🎤 emphasised (typing still works).

Levels 3–5: local `close(answer)` → correct; else Claude `check_drill` (`sentence` schema:
result/feedback/corrected; correct|minor pass). A miss shows feedback and serves the next exercise of
the same level; 3 misses on one level end the session as not passed.
Start level: 1, or 3 if the skill's best level ≥ 3.

### 3. Storage `data/drills.json`
`{skillId: {"level": best passed level, "seen": [answers ≤ 40], "sessions": [{"at", "start", "passed": bool, "levels": [passed levels], "clean": bool}]}}`
`POST /api/drills` `{skillId}` → generated session (not stored). `POST /api/drills/<skillId>/check`
`{exercise, pattern, text}` → verdict. `POST /api/drills/<skillId>/finish` `{start, levels, passed, clean, answers}`.
`clean` = levels 4 and 5 passed on the first exercise. Passed + clean + skill status `weak` → `improving`
(never higher).

### 4. Gate
On `finish()` of a regular lesson: `lesson.drillSkill` = random pick among skills with status weak or
improving (kind grammar or mistake first, else any), different from the previous gate lesson's pick.
Server start assigns it to the current gate lesson if missing.
Gate adds `drill: {skillId, title, required: 2, done}` — `done` = passed sessions of that skill with
`at` ≥ the gate lesson's `finishedAt`. `ready` also needs `done >= required`. No weak/improving skills
→ no drill row.

### 5. Lesson context
`build()` adds `drills`: `[{skillId, level, sessions}]` so the generator knows what was drilled.

## Tests
- gate needs 2 passed drill sessions after the lesson; failed sessions do not count.
- finish promotes weak → improving only when passed and clean; never beyond improving.
- `seen` is capped at 40 and sent to `generate_drill`.
- drillSkill differs from the previous pick when another candidate exists.
