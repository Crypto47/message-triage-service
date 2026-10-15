"""
Format check for an expected-answers file. It checks NAMES only (intents,
routes, queues, priorities, flags), never whether an answer is right, so the
answers stay entirely the labeller's own judgement.

    python eval/check_answers.py eval/expected_final.json
"""
import json
import sys

sys.path.insert(0, ".")
from triage import config  # noqa: E402


def as_answer_dict(data) -> dict:
    """Accept answers as {"FN-001": {...}} OR as a list [{"id": "FN-001", ...}]. Format only."""
    if isinstance(data, list):
        return {item["id"]: item for item in data if isinstance(item, dict) and "id" in item}
    return {k: v for k, v in data.items() if not k.startswith("_")} if isinstance(data, dict) else {}

path = sys.argv[1] if len(sys.argv) > 1 else "eval/expected_final.json"
with open(path, encoding="utf-8") as f:
    answers = as_answer_dict(json.load(f))

queues = {s.queue for s in config.INTENTS.values()} | {f.queue for f in config.FLAGS.values() if f.queue}
problems = []
for mid, a in answers.items():
    if not any(k in a for k in ("intents", "route", "queue", "priority", "must_flags")):
        problems.append(f"{mid}: gives no answer to score (needs at least one of intents/route/queue/priority/must_flags)")
    for i in a.get("intents", []) + [x for alt in a.get("acceptable_intents", []) for x in alt]:
        if i not in config.INTENTS:
            problems.append(f"{mid}: unknown intent '{i}'")
    for r in ([a["route"]] if "route" in a else []) + a.get("acceptable_routes", []):
        if r not in ("auto", "human"):
            problems.append(f"{mid}: route must be 'auto' or 'human', got '{r}'")
    for q in ([a["queue"]] if "queue" in a else []) + a.get("acceptable_queues", []):
        if q not in queues:
            problems.append(f"{mid}: unknown queue '{q}'")
    for p in ([a["priority"]] if "priority" in a else []) + a.get("acceptable_priorities", []):
        if p not in config.PRIORITY_RANK:
            problems.append(f"{mid}: priority must be P1, P2 or P3, got '{p}'")
    for fl in a.get("must_flags", []):
        if fl not in config.FLAGS:
            problems.append(f"{mid}: unknown flag '{fl}'")

print("\n".join(problems) if problems else f"Format OK: {len(answers)} answers in {path}")
print("\nValid queues:", ", ".join(sorted(queues)))
