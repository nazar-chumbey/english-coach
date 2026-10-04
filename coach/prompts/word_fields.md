Fields for every word card (the learner is a Ukrainian IT professional; the card drives spaced-repetition drills):

- `word`: dictionary form, keeping the whole chunk (`ran into` → `run into`). Keep casing for names and acronyms.
- `meaning`: Ukrainian, ≤ 12 words, the sense the learner needs (the one from `context` if given), not every dictionary sense.
- `ipa`: British or American IPA in slashes, e.g. `/ɪnˈʃʊərəns/`.
- `example`: one short natural English sentence from IT work (or everyday life for general words).
- `collocations`: 2–3 frequent English chunks with the word (`file an insurance claim`), no translations.
- `association`: Ukrainian, ≤ 25 words, the single strongest memory hook. Pick in this order:
  (a) transparent word parts or etymology (`un-predict-able`); (b) a cognate or a false-friend warning
  (`actual` ≠ «актуальний»); (c) otherwise the keyword method: a Ukrainian word that SOUNDS like the English
  one, joined to the meaning in one vivid, concrete, slightly absurd image. Never just restate the meaning.
- `cloze`: a NEW sentence (not `example`) where the target appears once, contiguous, replaced by `___`.
  The sentence must make only the target fit.
- `clozeAnswer`: the exact text removed from `cloze` (may be inflected: `ran into`).
- `distractors`: 3 wrong Ukrainian meanings in the same style and length as `meaning`. Take them from
  look-alike or easily confused English words (`insurance` → «наполегливість» from insistence, «запевнення»
  from assurance), so they catch a guess. Someone who knows the word must find each one clearly wrong: never
  a synonym, a part, a consequence or a broader/narrower sense of the right meaning.
