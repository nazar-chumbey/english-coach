from __future__ import annotations

import copy

MAX_EXAMPLES = 5
FIELDS = ("kind", "title", "status", "understanding", "due", "notes")


def apply_patch(skills: list[dict], patch: list[dict], lesson_id: str) -> list[dict]:
    result = copy.deepcopy(skills)
    by_id = {s["id"]: s for s in result}
    for change in patch:
        skill = by_id.get(change["id"])
        if skill is None:
            skill = {"id": change["id"], "kind": "grammar", "title": change["id"], "status": "weak",
                     "count": 0, "examples": [], "analogiesTried": []}
            result.append(skill)
            by_id[skill["id"]] = skill
        skill.update({k: change[k] for k in FIELDS if change.get(k) is not None})
        skill["count"] = skill.get("count", 0) + change.get("countDelta", 0)
        examples = skill.get("examples", []) + [{**e, "lesson": lesson_id} for e in change.get("examples", [])]
        skill["examples"] = examples[-MAX_EXAMPLES:]
        if change.get("analogy"):
            skill["analogiesTried"] = skill.get("analogiesTried", []) + [change["analogy"]]
    return result
