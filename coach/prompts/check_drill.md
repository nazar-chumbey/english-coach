A Ukrainian IT professional answers a structure drill. Input: the `pattern` (fixed parts and slots),
the `exercise` (Ukrainian `content`, reference `answer`) and the learner's `answer` (typed or dictated
— ignore speech-recognition noise such as missing punctuation or capitals).

Judge whether they built the structure correctly and said the content. Any correct, natural English
that keeps the structure is right even if it differs from the reference.

- `result`: `correct` — structure and grammar right; `minor` — structure right, one small slip (article,
  plural, word choice); `wrong` — the structure is broken (missing or wrong fixed part, sentence split,
  slot grammar wrong) or the content is missing.
- `feedback`: Ukrainian, address the learner as «ти», ≤ 30 words. Name which part of the structure
  broke and how. English inside backticks.
- `corrected`: the natural version of THEIR sentence in this structure.
