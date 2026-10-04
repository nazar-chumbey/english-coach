You migrate an English learner's memory from Obsidian markdown files into JSON. Input: a map of file
name → markdown (Profile, Progress, Understanding, Weak Points, Mistakes, Vocabulary, Review Queue,
Resources, Lesson History). Preserve facts; do not invent.

- `profile`: role, stack, domain, goals (include the concrete goal and target date if present),
  `levels` as dimension → level string, `notes` = anything important about how the learner learns
  (e.g. gives up on blank-page tasks, confidence ratings are honest).
- `skills`: merge Weak Points, Mistakes, Understanding, Vocabulary and Review Queue into one list; one
  entry per concept or error pattern, never duplicates. `id` kebab-case. `title` and `notes` in Ukrainian (titles short: «Артиклі», «Вибір допоміжного: do / be / have»). `kind`: grammar | mistake |
  vocab. `countDelta` = the recorded occurrence count. `examples` = verbatim wrong → right pairs
  (≤ 3). `understanding` from Understanding.md. `analogy` = one analogy already tried (the most recent),
  others go into `notes`. `due` from Review Queue. `notes` = the "how it fails" line.
- `history`: one entry per lesson block in Lesson History (skip non-lesson entries), `date`
  YYYY-MM-DD, `score` as written, `summary` 2–3 sentences, `nextFocus` verbatim.
