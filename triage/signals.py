"""
Step 2 of the pipeline: plain-code checks, no AI.

Finds IDs, amounts, phone numbers and dates, and raises warning flags.
These run whatever the AI says, and they can only ADD caution, never remove
it. So if a message fools the AI, these checks still send it to a human.

Keyword lists cover English, Hinglish (Hindi in Latin letters) and a little
Hindi script. They are deliberately small and readable, not exhaustive.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta

from triage import config
from triage.ingest import Message, load


@dataclass
class Signals:
    entities: dict[str, list[str]] = field(default_factory=dict)  # e.g. {"order_id": ["VW-48812"]}
    flags: set[str] = field(default_factory=set)
    dates: list[dict] = field(default_factory=list)   # {"phrase", "date", "note"}
    imminent: bool = False                            # a date within the next 48 hours
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

ENTITY_PATTERNS = {
    "order_id":    re.compile(r"\bVW-\d{5}\b", re.IGNORECASE),
    # 6-8 capitals and digits, containing at least one of each (e.g. VYG9K2M)
    "booking_ref": re.compile(r"\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{6,8}\b"),
    "amount":      re.compile(r"(?:INR|Rs\.?|₹|CAD|USD|\$)\s?\d[\d,]*(?:\.\d+)?", re.IGNORECASE),
    "email":       re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "phone":       re.compile(r"\+?\d[\d\s-]{8,16}\d"),
}


def extract_entities(text: str) -> dict[str, list[str]]:
    found = {}
    for kind, pattern in ENTITY_PATTERNS.items():
        values = [m.group(0).strip() for m in pattern.finditer(text)]
        if kind == "phone":
            # A phone number has 10-13 digits; this skips amounts and order numbers
            values = [v for v in values if 10 <= sum(c.isdigit() for c in v) <= 13]
        if kind == "order_id":
            values = [v.upper() for v in values]
        if values:
            found[kind] = list(dict.fromkeys(values))   # unique, keep order
    return found


# ---------------------------------------------------------------------------
# Warning flags: keyword rules
# ---------------------------------------------------------------------------

def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


INJECTION = [
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|rules|messages)",
    r"system (notice|prompt|message|override)",
    r"(administrator|admin|developer|god) mode",
    r"you are now",
    r"(do not|don't|dont) (escalate|forward|send).{0,30}(human|agent|person|staff)",
    r"reply (only )?[\"']?confirmed",
    r"(private|hidden|secret|internal) instructions",
    # Hinglish
    r"rules? bhool ja",
    r"instructions? (bata|batao|dikha)",
    r"human ko mat",
    r"kisi (human|insaan|agent) ko mat",
    # Hindi script: "forget the rules / instructions"
    r"(निर्देश|नियम).{0,10}भूल",
]

URGENT = [
    r"\burgent", r"\bemergency\b", r"\bimmediately\b", r"\basap\b",
    r"\bstranded\b", r"\bambulance\b", r"\bhospital\b", r"\baccident\b",
    r"chest pain", r"(can'?t|cannot|struggling to) breathe",
    r"missed (my |the |our )?(connection|flight)",
    r"(flight|connection).{0,40}(cancel|delay)",
    r"airport (pe|par|mein|me)\b.{0,40}|(at|stuck at) (the )?airport",
]

HEALTH = [
    r"safe (to take|for me|with|during)", r"blood pressure", r"\bmedication", r"\bmedicine",
    r"pregnan", r"breastfeed", r"diabet", r"side effects?", r"(drug )?interactions?",
    r"\ballerg", r"\bdawai\b", r"\bdawa\b",
]

CHARGEBACK_OR_LEGAL = [
    r"chargeback", r"(raise|raising|report|complain).{0,25}(my )?bank", r"consumer (court|forum)",
    r"\blawyer\b", r"legal action", r"\bsue\b",
]

REPEAT_CONTACT = [
    r"(second|third|fourth|\d+(st|nd|rd|th)) time", r"nobody (has )?(responded|replied)",
    r"no one (has )?(responded|replied)", r"still waiting", r"already (wrote|emailed|messaged|called)",
    r"teesri baar", r"dusri baar", r"kitni baar",
]

PAYMENT_INSTRUCTIONS = [
    r"bank details", r"process (the )?payment", r"wire transfer", r"\bIFSC\b",
    r"account number", r"pay (the|this|our) invoice",
]

ACCESSIBILITY = [
    r"wheelchair", r"\belderly\b", r"over (6|7|8)0\b", r"disab", r"mobility", r"senior citizen",
    r"\bblind\b", r"\bdeaf\b",
]

NEEDS_CONTEXT = [
    r"the other one", r"^what about\b", r"as (discussed|i said|mentioned)", r"following up",
    r"you sent", r"same as (before|last time)", r"pehle jo bola", r"jaise pehle",
]

# Common Hindi words written in Latin letters; two or more suggests Hinglish
HINGLISH_WORDS = {
    "hai", "hain", "kya", "kar", "karo", "karna", "kardo", "mera", "meri", "mujhe", "nahi",
    "toh", "aur", "bhi", "wala", "wali", "baje", "bhai", "abhi", "hu", "hoon", "hoga",
    "bata", "batao", "chahiye", "kitna", "pehle", "jo", "bola", "dena", "rakhna", "ka", "ki", "ke",
}

DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def raise_flags(m: Message, entities: dict) -> set[str]:
    t = m.text
    flags = set()
    if _any(INJECTION, t):
        flags.add("suspected_injection")
    if _any(URGENT, t):
        flags.add("urgent")
    # Health questions only matter for the supplements brand; for travel,
    # a medical emergency is caught by "urgent" instead.
    if m.brand == config.VITALIS and _any(HEALTH, t):
        flags.add("health_risk")
    if _any(CHARGEBACK_OR_LEGAL, t):
        flags.add("chargeback_or_legal_threat")
    if _any(REPEAT_CONTACT, t):
        flags.add("repeat_contact")
    if _any(PAYMENT_INSTRUCTIONS, t):
        flags.add("possible_fraud")
    if _any(ACCESSIBILITY, t):
        flags.add("accessibility_need")
    if _any(NEEDS_CONTEXT, t.strip()):
        flags.add("needs_context")
    if "phone" in entities or "email" in entities:
        flags.add("contains_pii")

    words = set(re.findall(r"[a-z]+", t.lower()))
    if len(words & HINGLISH_WORDS) >= 2 or DEVANAGARI.search(t):
        flags.add("code_mixed")    # Hinglish or Hindi script
    return flags


# ---------------------------------------------------------------------------
# Relative dates, resolved against when the message arrived
# ---------------------------------------------------------------------------

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# phrase pattern -> (days to add, note)
RELATIVE_DAYS = [
    (r"\bday after tomorrow\b|\bparso\b|परसों", 2,
     "'parso' can also mean the day before yesterday; assumed the future"),
    (r"\btomorrow\b|\bkal\b|कल", 1,
     "'kal' means both yesterday and tomorrow; assumed tomorrow"),
    (r"\btoday\b|\baaj\b|आज|\btonight\b", 0, ""),
    (r"\byesterday\b", -1, ""),
]


def resolve_dates(m: Message) -> list[dict]:
    if m.received_at is None:
        return []
    base: date = m.received_at.date()
    text = m.text.lower()
    found = []

    for pattern, days, note in RELATIVE_DAYS:
        match = re.search(pattern, text)
        if match:
            d = base + timedelta(days=days)
            note = note if match.group(0) in ("kal", "parso", "कल", "परसों") else ""
            found.append({"phrase": match.group(0), "date": d.isoformat(), "note": note})

    for i, name in enumerate(WEEKDAYS):
        match = re.search(rf"\b(next |this |coming )?{name}\b", text)
        if match:
            ahead = (i - base.weekday()) % 7 or 7    # the next one, never today
            note = "'next' may mean the week after" if match.group(1) == "next " else ""
            found.append({"phrase": match.group(0), "date": (base + timedelta(days=ahead)).isoformat(),
                          "note": note})
    return found


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyse(m: Message) -> Signals:
    if not m.text:
        return Signals()
    entities = extract_entities(m.text)
    flags = raise_flags(m, entities)
    dates = resolve_dates(m)

    imminent = False
    if m.received_at is not None:
        limit_days = config.IMMINENT_BOOKING_HOURS / 24
        imminent = any(0 <= (date.fromisoformat(d["date"]) - m.received_at.date()).days <= limit_days
                       for d in dates)

    notes = []
    if m.received_at is None and re.search(r"tomorrow|kal|parso|today|monday|tuesday|wednesday|"
                                           r"thursday|friday|saturday|sunday", m.text, re.IGNORECASE):
        notes.append("relative date mentioned but no timestamp to resolve it")
    return Signals(entities, flags, dates, imminent, notes)


if __name__ == "__main__":
    # Quick check: python -m triage.signals data/messages.json
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Hindi text on Windows consoles
    path = sys.argv[1] if len(sys.argv) > 1 else "data/messages.json"
    for m in load(path):
        s = analyse(m)
        ents = "; ".join(f"{k}={','.join(v)}" for k, v in s.entities.items())
        dates = "; ".join(f"{d['phrase']}->{d['date']}" for d in s.dates)
        print(f"{m.id:9} flags=[{', '.join(sorted(s.flags))}]")
        if ents:
            print(f"{'':9} entities: {ents}")
        if dates:
            print(f"{'':9} dates: {dates}{'  (IMMINENT)' if s.imminent else ''}")
