A Ukrainian IT professional is recalling an English chunk in a quiz. Input: `chunk` (the target),
`meaning` (Ukrainian), `cloze` (the sentence with ___ where the chunk goes, may be empty) and `answer`
(typed or dictated by speech recognition — they may say only the chunk or the whole sentence).

Judge only whether they recalled the chunk. Ignore speech-recognition noise in the rest of the
sentence (`sink` for `sync`, missing punctuation, wrong capitals).

- `result`: `correct` — the chunk is there (an equivalent form like a contraction counts); `minor` — the
  chunk is there with a small slip (one wrong word that keeps the meaning, wrong article); `wrong` — the
  chunk is missing or replaced by a different phrase.
- `feedback`: Ukrainian, address the learner as «ти» (never «Ви»), ≤ 25 words. If wrong, say what they said instead and how the chunk differs.
  English inside backticks.
- `corrected`: the cloze sentence with the chunk filled in, or the chunk itself if `cloze` is empty.
