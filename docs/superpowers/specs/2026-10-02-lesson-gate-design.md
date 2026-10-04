# Lesson gate: chunks into the dictionary + checklist before the next lesson

## Problem
Lesson chunks (`lesson.chunks`) are shown once and lost — they never reach `words.json`, so nothing
schedules them for review. The review `recommendation` is shown and forgotten. Lessons can be generated
back to back without consolidating anything.

## Changes

### 1. Fewer chunks
- `generate_lesson.md`: at most 5 chunks per lesson, saved words included (was 4–6, up to 8 with saved words).
- `context.MAX_WORDS` 5 → 3, so at least 2 slots stay for new chunks.

### 2. Chunks become words
- On `finish()` of a regular lesson, every chunk is added to `words.json` via `_new_word` with
  `source: "lesson"`, `lessonId`, `meaning`, `example`, `cloze` = example with the chunk replaced by `___`
  (case-insensitive; if the chunk is not literally in the example, `cloze` = `___ — <meaning>`),
  `clozeAnswer` = chunk. Existing word (case-insensitive) → skipped.
- One-time backfill: on server start, done lessons whose chunks are not yet in `words.json` are added
  the same way (idempotent, so no flag needed).
- They live in the existing FSRS trainer (`#/words`); `SOURCE` gets `lesson: "з уроку"`.

### 3. Gate
State lives on the latest done regular lesson (`gate lesson`):
- `chunkQuiz: {passedAt}`
- `homework: {status: "done" | "skipped", notes, at}` — `notes` required for done (what they noticed),
  reason required for skipped.

`service.gate(store)` returns `{lessonId, quiz: bool, dueChunks: int, homework: bool, chunks: [...]}`;
`ready` = quiz passed AND `dueChunks == 0` AND homework set. No gate lesson (first lesson after
placement, or it has no chunks) → quiz counts as passed. No `review.recommendation` → homework counts as set.
`dueChunks` = words with `source == "lesson"`, status learning, `srs.due <= now`.
`generate()` raises `ValueError` with the list of what is missing when not ready. `state()` includes `gate`.

Endpoints: `POST /api/lessons/<id>/quiz` (marks passed, body = per-chunk results `{wordId, firstTry}`
→ FSRS rating 3 for first try, 1 otherwise, via `review_word`), `POST /api/lessons/<id>/homework`.

### 4. Quiz page `#/quiz/<lessonId>`
- Card: Ukrainian meaning + cloze sentence; input + 🎤 button.
- Local check: normalise like `norm` in words.js + contractions; correct if Levenshtein ≤ ⌊len/6⌋.
- Wrong → show the correct chunk, card goes to the end of the queue. Pass when every chunk answered
  correctly after its last miss; then POST results and return home.
- 🎤: `webkitSpeechRecognition || SpeechRecognition`, `lang: "en-US"`, transcript fills the input and
  is checked the same way. Button hidden when the API is missing (Firefox).

### 5. Home
"Пропуск до уроку" card above the next-lesson card: three rows with ✓/○, each linking to quiz,
`#/words`, or an inline homework form (done + notes / skip + reason). "Згенерувати урок" disabled with
a title listing what is left.

### 6. Prompts
`generate_lesson` and `review` payloads get `homework` from the gate lesson so the agent can refer to
what the learner noticed or why they skipped.

## Tests
- `generate()` raises when gate not ready, passes when ready; first lesson has no gate.
- `finish()` adds chunks to words, no duplicates; backfill idempotent.
- quiz endpoint applies FSRS ratings and sets `passedAt`; homework validation (notes/reason required).
