from __future__ import annotations

import math
from datetime import datetime, timedelta

# FSRS-5 default weights (open-spaced-repetition)
W = [0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575, 0.1192, 1.01925,
     1.9395, 0.11, 0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621]
DECAY, FACTOR, RETENTION = -0.5, 19 / 81, 0.9
AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4


def _clamp(d: float) -> float:
    return min(max(d, 1.0), 10.0)


def _d0(rating: int) -> float:
    return _clamp(W[4] - math.exp(W[5] * (rating - 1)) + 1)


def retrievability(days: float, stability: float) -> float:
    return (1 + FACTOR * days / stability) ** DECAY


def review(card: dict | None, rating: int, now: datetime) -> dict:
    if rating not in (AGAIN, HARD, GOOD, EASY):
        raise ValueError("rating must be 1-4")
    if not card:
        s, d, reps, lapses = W[rating - 1], _d0(rating), 0, 0
    else:
        s, d, reps, lapses = card["stability"], card["difficulty"], card["reps"], card["lapses"]
        days = (now - datetime.fromisoformat(card["last"])).total_seconds() / 86400
        if days < 1:
            s *= math.exp(W[17] * (rating - 3 + W[18]))
        elif rating == AGAIN:
            r = retrievability(days, s)
            s = min(W[11] * d ** -W[12] * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r)), s)
        else:
            r = retrievability(days, s)
            s *= 1 + (math.exp(W[8]) * (11 - d) * s ** -W[9] * (math.exp(W[10] * (1 - r)) - 1)
                      * (W[15] if rating == HARD else 1) * (W[16] if rating == EASY else 1))
        d = _clamp(W[7] * _d0(EASY) + (1 - W[7]) * (d - W[6] * (rating - 3) * (10 - d) / 9))
    s = max(s, 0.1)
    days = s / FACTOR * (RETENTION ** (1 / DECAY) - 1)
    due = now + (timedelta(minutes=10) if rating == AGAIN else timedelta(days=max(1, round(days))))
    return {"stability": round(s, 3), "difficulty": round(d, 3), "reps": reps + 1,
            "lapses": lapses + (rating == AGAIN and reps > 0), "last": now.isoformat(timespec="seconds"),
            "due": due.isoformat(timespec="seconds")}
