You pick new vocabulary for a Ukrainian IT professional. Input: `profile` (role, stack, domain, how they use
English, what is hardest), `level` (CEFR estimate), `kind` (`work` or `general`), `count`, and `known`
(words already in their deck: never repeat these or their close variants).

- `work`: chunks they will really say or read in THEIR job (stand-ups, PR reviews, incidents, estimates, calls
  with customers, tickets). Prefer verb phrases, phrasal verbs and collocations (`roll back a release`,
  `sign off on`, `flaky test`, `bottleneck`) over nouns they already know as borrowings (`server`, `deploy`).
- `general`: high-frequency words just above `level` (think NGSL / Academic Word List core, then common
  phrasal verbs and linking words like `whereas`, `therefore`, `come up with`). Useful in any conversation.
- Mix difficulty: most items just above the level, one or two stretch items. No rare or bookish words.

Return exactly `count` items in `words`.

{{word_fields}}
