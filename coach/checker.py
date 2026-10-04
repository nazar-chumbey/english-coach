from __future__ import annotations

import re

CONTRACTIONS = {
    "won't": "will not", "can't": "cannot", "n't": " not", "'ve": " have", "'re": " are",
    "'ll": " will", "'m": " am", "'d": " would", "can not": "cannot",
}
GAP = re.compile(r"_{3,}")
QUOTES = re.compile(r"[«»“”\"]")
PARTS = re.compile(r"\s*(?:[,;/]|\.\.\.|…)\s*")


def normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'")
    for short, full in CONTRACTIONS.items():
        text = text.replace(short, full)
    text = re.sub(r"[^\w\s']", " ", text)
    return " ".join(text.split())


def _fill(template: str, accept: list[str]):
    pieces = GAP.split(re.sub(r"\([^)]*\)", " ", template))
    for answer in accept:
        words = [answer] if len(pieces) == 2 else PARTS.split(answer)
        if len(words) == len(pieces) - 1:
            yield "".join(p + ("" if w.strip() in "—-" else w) for p, w in zip(pieces, words)) + pieces[-1]


def sentences(item: dict) -> set[str]:
    lines = " ".join(l for l in item.get("prompt", "").splitlines() if GAP.search(l))
    if not lines:
        return set()
    quoted = " ".join(s for s in QUOTES.split(lines) if GAP.search(s))
    return {*_fill(lines, item.get("accept", [])), *_fill(quoted, item.get("accept", []))}


def check(item: dict, answer: str) -> str | None:
    if item["type"] not in ("choice", "gap", "fix"):
        return None
    if normalise(answer) in {normalise(a) for a in [*item.get("accept", []), *sentences(item)]}:
        return "correct"
    return "wrong" if item["type"] == "choice" else "mismatch"
