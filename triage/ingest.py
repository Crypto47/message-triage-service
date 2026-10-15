"""
Step 1 of the pipeline: read the messages file and make every record safe.

Rule: a bad record never crashes anything. It becomes a normal message with
flags explaining what was wrong, and those flags send it to a human later.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from triage import config


@dataclass
class Message:
    id: str
    brand: str
    channel: str
    received_at: datetime | None   # None if missing or unreadable
    text: str                      # always a string, possibly empty
    flags: set[str] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)   # plain-English problems


# Invisible characters people use to hide text (zero-width spaces, direction marks)
_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")


def clean_text(value) -> tuple[str, list[str]]:
    """Return (clean text, notes). Never raises."""
    notes = []
    if value is None:
        return "", ["text is missing"]
    if not isinstance(value, str):
        return "", [f"text is a {type(value).__name__}, not a string"]

    text = unicodedata.normalize("NFC", value)
    if _INVISIBLE.search(text):
        notes.append("invisible characters removed")
        text = _INVISIBLE.sub("", text)
    # Drop control characters, but keep normal line breaks and tabs
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    text = text.strip()

    if len(text) > config.MAX_TEXT_CHARS:
        notes.append(f"text truncated from {len(text)} to {config.MAX_TEXT_CHARS} characters")
        text = text[: config.MAX_TEXT_CHARS]
    return text, notes


def parse_time(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def normalise(raw, index: int, seen_ids: set[str]) -> Message:
    """Turn one raw record (of any shape) into a safe Message."""
    flags, notes = set(), []

    if not isinstance(raw, dict):
        notes.append(f"record is a {type(raw).__name__}, not an object")
        flags.add("damaged_record")
        raw = {}

    # ID: must exist and be unique
    msg_id = raw.get("id")
    if not isinstance(msg_id, str) or not msg_id.strip():
        msg_id = f"ROW-{index + 1}"
        notes.append("missing or invalid id; generated one")
        flags.add("damaged_record")
    msg_id = msg_id.strip()
    if msg_id in seen_ids:
        n = 2
        while f"{msg_id}#{n}" in seen_ids:
            n += 1
        notes.append(f"duplicate id {msg_id}; renamed")
        msg_id = f"{msg_id}#{n}"
        flags.add("damaged_record")
    seen_ids.add(msg_id)

    # Brand: unknown brand means we can't know the policy, so a human looks
    brand = raw.get("brand") if isinstance(raw.get("brand"), str) else ""
    brand = brand.strip().lower()
    if brand not in config.ALL_BRANDS:
        notes.append(f"unknown brand {brand!r}")
        flags.add("damaged_record")

    # Channel: unknown is noted but doesn't block anything
    channel = raw.get("channel") if isinstance(raw.get("channel"), str) else ""
    channel = channel.strip().lower()
    if channel not in config.KNOWN_CHANNELS:
        notes.append(f"unknown channel {channel!r}")

    # Time: needed to resolve "tomorrow", "kal", "next Friday"
    received_at = parse_time(raw.get("received_at"))
    if received_at is None:
        notes.append("no readable timestamp; relative dates cannot be resolved")

    # Text
    text, text_notes = clean_text(raw.get("text"))
    notes += text_notes
    if any("truncated" in n for n in text_notes):
        flags.add("damaged_record")
    if not text:
        flags.add("empty_or_non_text")
    elif not any(ch.isalpha() for ch in text):
        notes.append("no words, only numbers or symbols (e.g. just a phone number)")
        flags.add("empty_or_non_text")

    return Message(msg_id, brand, channel, received_at, text, flags, notes)


def load(path: str) -> list[Message]:
    """
    Load a messages file. Accepts a JSON list, or an object holding a list
    under "messages". Only an unreadable FILE stops the run (with a clear
    error); a bad RECORD never does.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise SystemExit(f"Cannot read {path}: {e}")

    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        data = data["messages"]
    if not isinstance(data, list):
        data = [data]   # a single record: treat it as a list of one

    seen: set[str] = set()
    return [normalise(raw, i, seen) for i, raw in enumerate(data)]


if __name__ == "__main__":
    # Quick check: python -m triage.ingest data/messages.json
    path = sys.argv[1] if len(sys.argv) > 1 else "data/messages.json"
    messages = load(path)
    for m in messages:
        problems = (", ".join(sorted(m.flags)) or "ok")
        print(f"{m.id:12} {m.brand:17} {problems:35} {'; '.join(m.notes)}")
    print(f"\n{len(messages)} records loaded, {sum(1 for m in messages if m.flags)} flagged.")
