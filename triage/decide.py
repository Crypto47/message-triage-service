"""
Step 4 of the pipeline: plain code checks the AI's labels and DECIDES.

1. Combine warning flags from ingest, keyword rules and the model.
   (Flags only add caution. The model can raise a flag but never remove one.)
2. Check the labels: is each quoted value really in the message, is each ID
   in the right format, does each intent exist for this brand, is anything
   needed missing? Each failed check is a MAJOR or MINOR problem.
3. Confidence band: high (no problems), medium (one minor), low (otherwise).
4. Route: automation only if every intent is low-risk (T0/T1), no warning flag
   forces a human, the band is good enough for the tier, AND a second,
   differently worded classification agrees. Everything else goes to a human.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime

from triage import config
from triage.config import FLAGS, INTENTS, TIER_RANK, Tier
from triage.ingest import Message, load
from triage.llm import LLMResult, classify
from triage.signals import Signals, analyse

# When several flags want a queue, the most serious wins (first in this list)
FLAG_QUEUE_ORDER = ["suspected_injection", "urgent", "possible_fraud", "health_risk"]

# Intents where a date in the next 48 hours makes the message time-critical
IMMINENT_INTENTS = {"book_appointment", "reschedule_appointment", "cancel_appointment",
                    "booking_change", "booking_question", "travel_disruption", "membership_question"}

FORMATS = {
    "order_id": re.compile(r"^VW-\d{5}$"),
    "booking_ref": re.compile(r"^(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{6,8}$"),
}
DATE_TYPES = {"date", "current_slot", "new_slot"}


@dataclass
class Problem:
    key: str        # a key from config.MAJOR_PROBLEMS or config.MINOR_PROBLEMS
    detail: str     # plain-English explanation for this message


@dataclass
class Decision:
    record: dict                        # the full JSON-ready result
    wants_second_opinion: bool = False  # True if only the second check stands before automation


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _in_text(value: str, text: str) -> bool:
    return bool(value.strip()) and _squash(value) in _squash(text)


def _valid_date(value: str) -> bool:
    try:
        datetime.fromisoformat(value[:10])
        return True
    except (ValueError, TypeError):
        return False


def check_labels(m: Message, labels: dict, signals: Signals) -> tuple[list[dict], dict, list[Problem]]:
    """Return (intents, grounded entities, problems)."""
    problems: list[Problem] = []

    # Intents: unique, and each one's evidence must be a real quote from the message
    intents, seen = [], set()
    for item in labels.get("intents", []):
        name = item.get("intent")
        if name in seen or name not in INTENTS:
            continue
        seen.add(name)
        evidence = item.get("evidence", "")
        if not _in_text(evidence, m.text):
            problems.append(Problem("value_not_in_text", f"evidence for '{name}' is not a quote from the message"))
        if m.brand and m.brand not in INTENTS[name].brands:
            problems.append(Problem("intent_not_valid_for_brand", f"'{name}' does not exist for {m.brand or 'an unknown brand'}"))
        intents.append({"intent": name, "tier": INTENTS[name].tier.value,
                        "queue": INTENTS[name].queue, "evidence": evidence})

    # Entities: keep only values that really appear in the message (drop invented ones)
    entities: dict[str, list[str]] = {k: list(v) for k, v in signals.entities.items()}
    for e in labels.get("entities", []):
        kind, text, normal = e.get("type"), e.get("text", ""), (e.get("normalized") or "").strip()
        if not _in_text(text, m.text):
            problems.append(Problem("value_not_in_text", f"{kind} '{text}' does not appear in the message; ignored"))
            continue
        if kind in FORMATS and not FORMATS[kind].match(normal.upper()):
            problems.append(Problem("invalid_format", f"{kind} '{normal}' has the wrong format"))
            continue
        if kind in DATE_TYPES and normal and not _valid_date(normal):
            problems.append(Problem("invalid_format", f"{kind} '{normal}' is not a valid date"))
        value = normal or text
        entities.setdefault(kind, [])
        if value not in entities[kind]:
            entities[kind].append(value)

    # Required details for each intent
    for item in intents:
        for needed in INTENTS[item["intent"]].required:
            if not entities.get(needed):
                problems.append(Problem("missing_required_detail", f"'{item['intent']}' needs a {needed}, none found"))

    if labels.get("ambiguous"):
        problems.append(Problem("model_marked_ambiguous", "the model judged the message ambiguous"))
    return intents, entities, problems


def band_for(problems: list[Problem]) -> str:
    major = sum(p.key in config.MAJOR_PROBLEMS for p in problems)
    minor = sum(p.key in config.MINOR_PROBLEMS for p in problems)
    if major == 0 and minor == 0:
        return "high"
    if major == 0 and minor == 1:
        return "medium"
    return "low"


BAND_RANK = {"low": 0, "medium": 1, "high": 2}


def _second_opinion_agrees(primary: dict, second: dict, m: Message, signals: Signals) -> bool:
    """Same set of intents and the same IDs, and no new warning flags."""
    p_intents = {i["intent"] for i in primary.get("intents", [])}
    s_intents = {i["intent"] for i in second.get("intents", [])}
    if p_intents != s_intents:
        return False
    def ids(lbl):
        return {e.get("normalized", "").upper() for e in lbl.get("entities", [])
                if e.get("type") in ("order_id", "booking_ref")}
    if ids(primary) != ids(second):
        return False
    return set(second.get("flags", [])) <= set(primary.get("flags", []))


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

def _fill(template: str, **values) -> str:
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", value)
    return out    # {kb:...} placeholders stay: the brand's own content fills them


def decide(m: Message, signals: Signals, primary: LLMResult, second: LLMResult | None = None) -> Decision:
    problems: list[Problem] = []
    why: list[str] = []

    # 1. Flags from every source (caution only ever adds up)
    flags = set(m.flags) | set(signals.flags)
    model_ok = primary.ok and primary.labels is not None
    if model_ok:
        flags |= set(primary.labels.get("flags", []))
    if config.VITALIS != m.brand:
        flags.discard("health_risk")   # supplement-safety questions only exist for Vitalis

    # 2. Labels and checks
    if model_ok:
        intents, entities, label_problems = check_labels(m, primary.labels, signals)
        problems += label_problems
    else:
        intents, entities = [], dict(signals.entities)
        problems.append(Problem("classifier_unavailable", f"AI labels unavailable: {primary.error}"))
    if not intents:
        intents = [{"intent": "unclear", "tier": Tier.T3.value, "queue": INTENTS["unclear"].queue, "evidence": ""}]

    words = len(m.text.split())
    if 0 < words < config.SHORT_MESSAGE_WORDS:
        problems.append(Problem("very_short_message", f"only {words} word(s)"))
    if "code_mixed" in flags:
        problems.append(Problem("code_mixed_language", "Hinglish or Hindi script"))

    # 3. Risk: the riskiest intent decides
    top = max(intents, key=lambda i: TIER_RANK[Tier(i["tier"])])
    tier = Tier(top["tier"])
    hard_flags = sorted(f for f in flags if FLAGS.get(f) and FLAGS[f].forces_human)

    # 4. Route
    wants_second = False
    if not model_ok:
        route = "human"; why.append(f"AI labels unavailable ({primary.error}), so a person decides")
    elif hard_flags:
        route = "human"; why.append(f"warning flag(s) that always need a person: {', '.join(hard_flags)}")
    elif tier in (Tier.T2, Tier.T3):
        route = "human"
        why.append(f"'{top['intent']}' is {tier.value}: "
                   + ("money, health, safety or expert judgement" if tier == Tier.T3 else "changes a booking or account"))
    else:
        needed = config.AUTO_MIN_BAND[tier]
        band_now = band_for(problems)
        if BAND_RANK[band_now] < BAND_RANK[needed]:
            route = "human"; why.append(f"confidence {band_now} is below the {needed} needed for {tier.value}")
        elif second is None:
            route = "human"; wants_second = True
            why.append("waiting for a second opinion before automating")
        elif not second.ok or not _second_opinion_agrees(primary.labels, second.labels or {}, m, signals):
            problems.append(Problem("second_opinion_disagrees",
                                    "second opinion " + ("could not be obtained" if not second.ok else "disagreed")))
            route = "human"; why.append("the second, differently worded classification did not agree")
        else:
            route = "auto"; why.append(f"all intents are {tier.value} or lower, confidence {band_now}, second opinion agrees")

    band = band_for(problems)

    # 5. Queue and priority
    queue = top["queue"]
    for f in FLAG_QUEUE_ORDER:
        if f in flags and FLAGS[f].queue:
            queue = FLAGS[f].queue
            break
    secondary = sorted({i["queue"] for i in intents} - {queue})
    if {"suspected_injection", "possible_fraud"} & flags:
        # The owning team handles it alone: copying an attacker's "refund request"
        # to billing as a normal ticket is exactly what the attack wants.
        secondary = []
        why.append("no copies to other teams: suspected attack or fraud")

    priority = config.DEFAULT_PRIORITY
    for f in flags:
        p = FLAGS.get(f).priority if FLAGS.get(f) else None
        if p and config.PRIORITY_RANK[p] < config.PRIORITY_RANK[priority]:
            priority = p
    if signals.imminent and any(i["intent"] in IMMINENT_INTENTS for i in intents):
        if config.PRIORITY_RANK[config.IMMINENT_BOOKING_PRIORITY] < config.PRIORITY_RANK[priority]:
            priority = config.IMMINENT_BOOKING_PRIORITY
            why.append("booking within 48 hours, so priority raised")

    # 6. What gets sent: fixed templates only, never model text
    brand_name = config.BRAND_NAMES.get(m.brand, "us")
    actions, auto_reply, ack = [], None, None
    if route == "auto":
        for i in intents:
            action = INTENTS[i["intent"]].action
            actions.append(action)
            if action and action.startswith("reply_template:"):
                topic = (entities.get("topic") or entities.get("service") or entities.get("product") or ["your question"])[0]
                auto_reply = _fill(config.REPLY_TEMPLATES[action.split(":", 1)[1]],
                                   brand_name=brand_name, topic=topic)
    else:
        no_ack = any(not FLAGS[f].send_ack for f in flags if f in FLAGS) or \
                 any(i["intent"] in config.NO_ACK_INTENTS for i in intents)
        if not no_ack:
            ack = _fill(config.ACKNOWLEDGEMENT_TEMPLATE, brand_name=brand_name,
                        response_target=config.PRIORITY_TARGET[priority])

    summary = primary.labels.get("summary", "") if model_ok else ""
    if "suspected_injection" in flags:
        summary = "Withheld: this message contains instructions aimed at the AI. Read the original text."

    record = {
        "id": m.id,
        "brand": m.brand,
        "channel": m.channel,
        "received_at": m.received_at.isoformat() if m.received_at else None,
        "text": m.text,
        "intents": intents,
        "entities": entities,
        "dates": signals.dates,
        "flags": sorted(flags),
        "confidence": {"band": band,
                       "reasons": [f"{'MAJOR' if p.key in config.MAJOR_PROBLEMS else 'minor'}: {p.detail}"
                                   for p in problems]},
        "route": route,
        "queue": queue,
        "secondary_queues": secondary,
        "priority": priority,
        "response_target": config.PRIORITY_TARGET[priority],
        "why": why,
        "actions": actions,
        "auto_reply": auto_reply,
        "acknowledgement": ack,
        "summary": summary,
        "notes": m.notes + signals.notes,
        "model": {"name": primary.model, "ok": primary.ok, "error": primary.error, "cached": primary.cached,
                  "input_tokens": primary.input_tokens + (second.input_tokens if second else 0),
                  "output_tokens": primary.output_tokens + (second.output_tokens if second else 0),
                  "cost_usd": round(primary.cost_usd + (second.cost_usd if second else 0), 6),
                  "fresh_api_calls": int(primary.ok and not primary.cached) + int(bool(second) and second.ok and not second.cached),
                  "second_opinion": None if second is None else (
                      f"failed ({second.error})" if not second.ok else ("agreed" if route == "auto" else "disagreed")),
                  "second_opinion_said": None if second is None or not second.ok else {
                      "intents": sorted({i["intent"] for i in second.labels.get("intents", [])}),
                      "flags": sorted(second.labels.get("flags", [])),
                      "ids": sorted({e.get("normalized", "") for e in second.labels.get("entities", [])
                                     if e.get("type") in ("order_id", "booking_ref")}),
                  }},
    }
    return Decision(record, wants_second)


def triage_one(m: Message) -> dict:
    """Run the whole chain for one message, with the second opinion when needed."""
    s = analyse(m)
    if "empty_or_non_text" in m.flags:
        # Nothing to read (null text, only a phone number or emoji): don't pay for an AI call
        primary = LLMResult(ok=False, error="no words to classify")
    else:
        primary = classify(m)
    d = decide(m, s, primary)
    if d.wants_second_opinion:
        d = decide(m, s, primary, classify(m, variant="second"))
    return d.record


if __name__ == "__main__":
    # Check one message end to end: python -m triage.decide data/messages.json MSG-001
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    path = sys.argv[1] if len(sys.argv) > 1 else "data/messages.json"
    wanted = sys.argv[2] if len(sys.argv) > 2 else None
    messages = [m for m in load(path) if wanted is None or m.id == wanted][:1]
    if not messages:
        sys.exit(f"No message with id {wanted} in {path}")
    print(json.dumps(triage_one(messages[0]), ensure_ascii=False, indent=2))
