# Lesson Gate Implementation Plan

> **For agentic workers:** execute task-by-task with superpowers:executing-plans. No git in this project (user choice) — no commit steps.

**Goal:** Lesson chunks land in the FSRS dictionary, and a new lesson is generated only after a chunk quiz, due chunk reviews and the homework step.

**Architecture:** `coach/service.py` gains `add_chunks`, `backfill_chunks`, `gate`, `pass_quiz`, `set_homework`; `generate()` refuses when the gate is not ready. Frontend gets `web/answer.js` (shared matching + 🎤 via Web Speech API), a `#/quiz/<id>` view and a checklist card on home.

**Tech Stack:** Python stdlib, vanilla JS. Tests: `python3 -m unittest` from the project root.

Spec: `docs/superpowers/specs/2026-10-02-lesson-gate-design.md`. Deviation: a chunk missed then fixed in the quiz is rated Hard (2), not Again — Again sets due +10 min and would re-block the gate instantly.

---

### Task 1: Backend — chunks into words, gate, quiz, homework

**Files:** Modify `coach/service.py`, `coach/context.py`, `server.py`, `tests/test_server.py`

- [ ] **Step 1: Failing tests** in `tests/test_server.py`. Keep the data dir: in `setUp` replace `server.serve(0, Path(tempfile.mkdtemp()))` with `self.data = Path(tempfile.mkdtemp())` + `server.serve(0, self.data)`. Add:

```python
CHUNKS = [{"chunk": "walk you through", "meaning": "пояснити", "example": "Let me walk you through the flow."},
          {"chunk": "as for ...", "meaning": "щодо", "example": "As for the UI, it works."}]

    def test_lesson_gate(self):
        self.ask.side_effect = lambda p, *a: {**fake_ask(p, *a), "chunks": CHUNKS} if p == "generate_lesson" else fake_ask(p, *a)
        lid = self.call("/api/lessons", {"minutes": 10})[1]["id"]
        self.call(f"/api/lessons/{lid}/finish", {})
        state = self.call("/api/state")[1]
        self.assertEqual([(w["word"], w["source"], w["cloze"]) for w in state["words"]],
                         [("walk you through", "lesson", "Let me ___ the flow."), ("as for", "lesson", "___ the UI, it works.")])
        self.assertEqual((state["gate"]["quiz"], state["gate"]["ready"], state["gate"]["words"]), (False, False, ["w1", "w2"]))
        self.assertEqual(self.call("/api/lessons", {"minutes": 10})[0], 400)
        gate = self.call(f"/api/lessons/{lid}/quiz", {"results": [{"wordId": "w1", "firstTry": True}, {"wordId": "w2", "firstTry": False}]})[1]
        self.assertEqual((gate["quiz"], gate["dueChunks"], gate["ready"]), (True, 0, False))
        self.assertEqual([w["srs"]["stability"] for w in self.call("/api/state")[1]["words"]], [3.173, 1.184])
        self.assertEqual(self.call(f"/api/lessons/{lid}/homework", {"status": "done", "notes": " "})[0], 400)
        self.assertTrue(self.call(f"/api/lessons/{lid}/homework", {"status": "done", "notes": "3 examples"})[1]["ready"])
        self.call("/api/lessons", {"minutes": 10})
        payload = self.ask.call_args.args[1]
        self.assertEqual((payload["previousHomework"]["notes"], payload["savedWords"]), ("3 examples", []))
        words = json.loads((self.data / "words.json").read_text("utf-8"))
        words[0]["srs"]["due"] = "2026-01-01T00:00:00"
        (self.data / "words.json").write_text(json.dumps(words), "utf-8")
        self.assertEqual(self.call("/api/state")[1]["gate"]["dueChunks"], 1)

    def test_backfill_chunks_on_start(self):
        data = Path(tempfile.mkdtemp())
        Store(data).save_lesson({"id": "2026-09-30-01", "status": "done", "items": [],
                                 "chunks": [{"chunk": "Does that make sense?", "meaning": "m", "example": "Ok. Does that make sense?"}]})
        for _ in range(2):
            server.serve(0, data).server_close()
        self.assertEqual([(w["word"], w["cloze"]) for w in Store(data).read("words", [])], [("Does that make sense", "Ok. ___?")])
```

Add `from coach.storage import Store` to imports. In `test_onboarding_and_placement`, after `self.call(f"/api/lessons/{lesson['id']}/finish", {})` add
`self.call(f"/api/lessons/{lesson['id']}/homework", {"status": "skipped", "notes": "busy"})` (REVIEW has a recommendation, so the gate needs it).

- [ ] **Step 2:** `python3 -m unittest tests.test_server -v` → the two new tests FAIL (KeyError `gate` / 404).

- [ ] **Step 3: `coach/service.py`.** Add after `delete_word`:

```python
def _chunk_word(chunk: str) -> str:
    return " ".join(chunk.split()).strip(" .,;:!?«»\"'…")


def _cloze(word: str, example: str) -> str:
    i = example.lower().find(word.lower())
    return example[:i] + "___" + example[i + len(word):] if i >= 0 else ""


def add_chunks(store: Store, lesson: dict) -> None:
    words = store.read("words", [])
    for c in lesson.get("chunks", []):
        word = _chunk_word(c["chunk"])
        if word and not any(w["word"].lower() == word.lower() for w in words):
            words.append(_new_word(words, word, source="lesson", lessonId=lesson["id"], context=c["example"][:300],
                                   meaning=c["meaning"], example=c["example"], cloze=_cloze(word, c["example"]), clozeAnswer=word))
    store.write("words", words)


def backfill_chunks(store: Store) -> None:
    with LOCK:
        for lesson in store.lessons():
            if lesson.get("status") == "done" and lesson.get("kind") != "placement":
                add_chunks(store, lesson)


def _gate_lesson(store: Store) -> dict:
    return next((l for l in store.lessons() if l.get("status") == "done" and l.get("kind") != "placement"
                 and not l.get("imported")), {})


def gate(store: Store) -> dict:
    lesson, now = _gate_lesson(store), datetime.now()
    words = store.read("words", [])
    chunks = {_chunk_word(c["chunk"]).lower() for c in lesson.get("chunks", [])}
    quiz = [w["id"] for w in words if w["word"].lower() in chunks]
    due = sum(w.get("source") == "lesson" and w.get("status", "learning") == "learning" and bool(w.get("srs"))
              and datetime.fromisoformat(w["srs"]["due"]) <= now for w in words)
    result = {"lessonId": lesson.get("id"), "words": quiz, "quiz": not quiz or bool(lesson.get("chunkQuiz")),
              "dueChunks": due, "recommendation": lesson.get("review", {}).get("recommendation", ""),
              "homework": lesson.get("homework")}
    return {**result, "ready": result["quiz"] and not due and bool(result["homework"] or not result["recommendation"])}


def pass_quiz(store: Store, lesson_id: str, results: list[dict]) -> dict:
    get_lesson(store, lesson_id)
    for r in results:
        review_word(store, r["wordId"], srs.GOOD if r.get("firstTry") else srs.HARD)
    with LOCK:
        lesson = get_lesson(store, lesson_id)
        lesson["chunkQuiz"] = {"passedAt": datetime.now().isoformat(timespec="seconds")}
        store.save_lesson(lesson)
    return gate(store)


def set_homework(store: Store, lesson_id: str, status: str, notes: str) -> dict:
    notes = str(notes).strip()
    if status not in ("done", "skipped") or not notes:
        raise ValueError("status must be done or skipped, notes are required")
    with LOCK:
        lesson = get_lesson(store, lesson_id)
        lesson["homework"] = {"status": status, "notes": notes[:1000], "at": datetime.now().isoformat(timespec="seconds")}
        store.save_lesson(lesson)
    return gate(store)
```

In `state()` add `"gate": gate(store),` to the returned dict.

In `generate()` after the minutes check:

```python
    passed = gate(store)
    if not passed["ready"]:
        missing = [n for n, ok in (("chunk quiz", passed["quiz"]), ("due chunks", not passed["dueChunks"]),
                                   ("homework", passed["homework"] or not passed["recommendation"])) if not ok]
        raise ValueError(f"finish the checklist first: {', '.join(missing)}")
    homework = passed["homework"] and {**passed["homework"], "recommendation": passed["recommendation"]}
```

and change the payload line to `payload = {**build(store, focus_skill), "minutes": minutes, "itemCount": item_count(minutes), "previousHomework": homework}`, plus `previousHomework=homework` in `lesson.update(...)` (so `finish()` sends it to the review prompt as part of the lesson).

In `finish()`, inside `with LOCK:` after `store.save_lesson(lesson)` add `add_chunks(store, lesson)`.

- [ ] **Step 4: `coach/context.py`.** `MAX_WORDS = 3`; in the `savedWords` filter add `w.get("source") != "lesson" and` before `w.get("status", "learning") == "learning"`.

- [ ] **Step 5: `server.py`.** In `do_POST` routes, after the `/finish` line:

```python
                (LESSON + "/quiz", lambda i: service.pass_quiz(store, i, body.get("results", []))),
                (LESSON + "/homework", lambda i: service.set_homework(store, i, body.get("status"), body.get("notes", ""))),
```

`serve()` becomes:

```python
def serve(port: int, data: Path) -> ThreadingHTTPServer:
    store = Store(data)
    service.backfill_chunks(store)
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(store))
```

- [ ] **Step 6:** `python3 -m unittest -v` → all PASS (if `test_context` pins `MAX_WORDS` 5, update the expectation to 3).

### Task 2: Prompts

**Files:** Modify `coach/prompts/generate_lesson.md`, `coach/prompts/review.md`

- [ ] In `generate_lesson.md`: replace `(up to 8 chunks then)` with `(still at most 5 chunks in total)`; replace `` `chunks`: 4–6 items`` with `` `chunks`: 3–5 items, saved words included — never more than 5, the learner must memorise each``. Append:

```
# Previous homework
`previousHomework` (may be null): the last review's `recommendation`, `status` done|skipped and the
learner's `notes`. Done → build one practice item around what they noticed. Skipped → do not repeat
that kind of task in `rationale`.
```

- [ ] In `review.md`, after the `recommendation` bullet add:
`` `lesson.previousHomework`: what happened to the last recommendation. Skipped → recommend a different format (shorter, reading instead of video, own PR threads). Done → mention their notes where relevant.``

### Task 3: Shared answer matching + 🎤

**Files:** Create `web/answer.js`; modify `web/views/words.js`, `web/soft.css`

- [ ] Create `web/answer.js`:

```js
import { h } from "./ui.js";

const CONTRACTIONS = [[/won't/g, "will not"], [/can't/g, "cannot"], [/n't/g, " not"], [/'re/g, " are"],
  [/'ve/g, " have"], [/'ll/g, " will"], [/'m/g, " am"], [/'d/g, " would"]];

export const norm = (s) => CONTRACTIONS.reduce((t, [re, full]) => t.replace(re, full), String(s).toLowerCase().replace(/[’`]/g, "'"))
  .replace(/[^\p{L}\p{N}' ]/gu, " ").split(/\s+/).filter(Boolean).join(" ");

export function typos(a, b) {
  const row = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    let prev = row[0]++;
    for (let j = 1; j <= b.length; j++) [prev, row[j]] = [row[j], Math.min(row[j] + 1, row[j - 1] + 1, prev + (a[i - 1] !== b[j - 1]))];
  }
  return row[b.length];
}

export const close = (given, target) => typos(norm(given), norm(target)) <= Math.floor(norm(target).length / 6);

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

export function micButton(input, onResult) {
  if (!Recognition) return null;
  const button = h("button.dictateAnswerButton", { title: "Сказати голосом", onclick: () => {
    const rec = Object.assign(new Recognition(), { lang: "en-US", maxAlternatives: 3 });
    rec.onresult = (e) => {
      const heard = [...e.results[0]].map((a) => a.transcript);
      input.value = heard[0];
      onResult(heard);
    };
    rec.onend = () => button.classList.remove("listening");
    button.classList.add("listening");
    rec.start();
  } }, "🎤");
  return button;
}
```

- [ ] In `web/views/words.js`: delete the local `norm` and `typos`, add `import { micButton, norm, typos } from "../answer.js";`, add `lesson: "з уроку"` to `SOURCE`. In `recall`, wrap the input: replace `input, hintLine, controls` in the final `put(...)` with `h("div.quizAnswerRow", {}, input, micButton(input, () => check())), hintLine, controls`.

- [ ] Append to `web/soft.css` (colors only via existing vars; reuse `.speakWordButton` look):

```css
.quizAnswerRow { display: flex; gap: 10px; align-items: center; }
.quizAnswerRow .answerInput { flex: 1; }
.dictateAnswerButton { border: 0; background: var(--track); border-radius: 50%; width: 44px; height: 44px; cursor: pointer; font-size: 18px; }
.dictateAnswerButton.listening { background: var(--g1); animation: dictatePulse 1s infinite; }
@keyframes dictatePulse { 50% { opacity: .5; } }
.gateChecklistRow { display: flex; gap: 12px; align-items: center; padding: 10px 0; }
```

(Before writing, check `soft.css` for the real button/track variable names and adjust.)

### Task 4: Quiz view + home checklist

**Files:** Create `web/views/quiz.js`; modify `web/app.js`, `web/api.js`, `web/views/home.js`

- [ ] `web/api.js` add:

```js
  passQuiz: (id, results) => call("POST", `/api/lessons/${id}/quiz`, { results }),
  homework: (id, status, notes) => call("POST", `/api/lessons/${id}/homework`, { status, notes }),
```

- [ ] `web/app.js`: `import quiz from "./views/quiz.js";` and route `[/^#\/quiz\/([\w-]+)$/, quiz, null],`.

- [ ] Create `web/views/quiz.js`:

```js
import { api } from "../api.js";
import { h, loading } from "../ui.js";
import { close, micButton } from "../answer.js";

export default function quiz(app, lessonId) {
  const { gate, words } = app.state;
  const cards = gate.lessonId === lessonId ? gate.words.map((id) => words.find((w) => w.id === id)) : [];
  if (!cards.length) return h("div.noticeBanner", {}, "Для цього уроку квізу немає.");
  const queue = [...cards].sort(() => Math.random() - 0.5);
  const missed = new Set();
  const bar = h("i");
  const slot = h("div.softCard");

  async function finish() {
    slot.replaceChildren(loading("Зберігаю результат"));
    try {
      await api.passQuiz(lessonId, cards.map((w) => ({ wordId: w.id, firstTry: !missed.has(w.id) })));
      app.go("#/");
    } catch (err) {
      slot.replaceChildren(h("div.noticeBanner", {}, `Не вдалося зберегти: ${err.message}`));
    }
  }

  function draw() {
    if (!queue.length) return finish();
    const left = new Set(queue).size;
    bar.style.width = `${((cards.length - left) / cards.length) * 100}%`;
    const w = queue[0];
    const input = h("input.answerInput", { placeholder: "Англійською…", autocomplete: "off",
      onkeydown: (e) => e.key === "Enter" && (e.preventDefault(), check()) });
    const button = h("button.primaryButton", { onclick: () => check() }, "Перевірити ↵");
    function check(heard = [input.value]) {
      if (!input.value.trim() || input.disabled) return;
      input.disabled = true;
      const ok = heard.some((t) => close(t, w.word));
      queue.shift();
      if (!ok) { missed.add(w.id); queue.push(w); }
      const next = h("button.primaryButton", { onclick: draw }, "Далі →");
      button.parentElement.replaceWith(h("div", {},
        h("div.feedbackBox", { class: ok ? "correct" : "wrong" }, h("p", {}, h("b", {}, ok ? "✓ Правильно" : `✗ Правильно: ${w.word}`)),
          w.example ? h("p", {}, h("i", {}, w.example)) : null),
        h("div.buttonRow", {}, next)));
      setTimeout(() => next.focus());
    }
    slot.replaceChildren(h("div.sectionLabel", {}, `Залишилось: ${left}`), h("p.itemPrompt", {}, h("b", {}, w.meaning)),
      w.cloze ? h("p.itemPrompt", {}, w.cloze) : null,
      h("div.quizAnswerRow", {}, input, micButton(input, check)), h("div.buttonRow", {}, h("div.spacer"), button));
    setTimeout(() => input.focus());
  }

  draw();
  return h("section", {}, h("h1.pageTitle", {}, "Квіз словосполучень"),
    h("p.pageSubtitle", {}, "Надрукуй або скажи фразу англійською. Помилка повертає картку в кінець черги."),
    h("div.drillProgress", {}, bar), slot);
}
```

- [ ] `web/views/home.js`: `import { rerender } from "../app.js";`. Add:

```js
function gateCard(app) {
  const { gate } = app.state;
  if (gate.ready) return null;
  const row = (ok, label, action) => h("div.gateChecklistRow", {},
    h("span.verdictIcon", { class: ok ? "good" : "weak" }, ok ? "✓" : "○"), h("div", {}, label), h("div.spacer"), ok ? null : action);
  const notes = h("textarea.answerInput", { placeholder: "Зроблено: що помітив (2–3 приклади). Пропуск: чому." });
  const send = (status) => notes.value.trim() && api.homework(gate.lessonId, status, notes.value).then(rerender);
  const homeworkDone = Boolean(gate.homework);
  return h("div.softCard", {},
    h("div.sectionLabel", {}, "Пропуск до уроку"),
    row(gate.quiz, `Квіз: ${gate.words.length} словосполучень з минулого уроку`,
      h("button.primaryButton", { onclick: () => app.go(`#/quiz/${gate.lessonId}`) }, "Пройти →")),
    row(!gate.dueChunks, gate.dueChunks ? `Повторити словосполучення: ${gate.dueChunks}` : "Повторення словосполучень",
      h("button.softButton", { onclick: () => app.go("#/words") }, "До словника →")),
    gate.recommendation ? [row(homeworkDone, rich("div", gate.recommendation), null),
      homeworkDone ? null : h("div", {}, notes, h("div.buttonRow", {},
        h("button.softButton", { onclick: () => send("skipped") }, "Пропустити"), h("div.spacer"),
        h("button.primaryButton", { onclick: () => send("done") }, "Зроблено")))] : null);
}
```

Add `import { api } from "../api.js";`. In `nextLessonCard`, the generate button: `disabled: !app.state.claude.ok || !app.state.gate.ready,` and `title: !app.state.gate.ready ? "Спершу пройди чекліст вище" : app.state.claude.ok ? null : app.state.claude.message,`. In `home()` render `gateCard(app)` right before `nextLessonCard(app, lessons)`.

(Check `.verdictIcon` tone class names in `soft.css` / `findingRow` usages — review uses `good|mixed|weak`.)

### Task 5: Verify

- [ ] `python3 -m unittest -v` → all PASS.
- [ ] E2E on a copy, never on real `data/`: `cp -r data /tmp/ec-gate && EC_DATA=/tmp/ec-gate python3 server.py 8790`, open `http://localhost:8790`:
  home shows the checklist only if the latest done lesson has chunks/recommendation; `#/words` lists chunks as «з уроку»;
  quiz: one wrong answer → card comes back, 🎤 fills the input in Chrome; after the quiz the row turns ✓;
  homework done → generate button enables.
- [ ] Stop the e2e server, report +/- LOC.
