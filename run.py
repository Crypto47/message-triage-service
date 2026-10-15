"""
Run the triage service on a messages file, save the results, and score them.

    python run.py data/messages.json
    python run.py data/heldout_messages.json
    python run.py data/messages.json --runs 3      # re-ask the AI 3 times (no cache) to find unstable messages

Writes to output/<file name>/:
    results.json   one full result per message
    report.md      readable summary: routes, scores, cost, every disagreement

Expected answers are picked up automatically if they exist:
    data/messages.json          -> eval/expected.json
    data/heldout_messages.json  -> eval/expected_heldout.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

from triage import config
from triage.decide import triage_one
from triage.ingest import load

def as_answer_dict(data) -> dict:
    """Accept answers as {"FN-001": {...}} OR as a list [{"id": "FN-001", ...}]. Format only."""
    if isinstance(data, list):
        return {item["id"]: item for item in data if isinstance(item, dict) and "id" in item}
    return {k: v for k, v in data.items() if not k.startswith("_")} if isinstance(data, dict) else {}


EXPECTED_FOR = {
    "messages.json": "eval/expected.json",
    "heldout_messages.json": "eval/expected_heldout.json",
}


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

def run_file(path: str) -> list[dict]:
    results = []
    for m in load(path):
        try:
            results.append(triage_one(m))
        except Exception as e:
            # Last line of defence: one message failing never stops the others
            results.append({"id": m.id, "brand": m.brand, "text": m.text, "route": "human",
                            "queue": "support", "priority": "P2", "intents": [], "flags": sorted(m.flags),
                            "confidence": {"band": "low", "reasons": [f"MAJOR: internal error {e!r}"]},
                            "why": ["internal error while processing; a person must check it"],
                            "model": {"cost_usd": 0, "input_tokens": 0, "output_tokens": 0}})
        print(f"  {results[-1]['id']:10} -> {results[-1]['route']:5} {results[-1]['queue']}", flush=True)
    return results


# ---------------------------------------------------------------------------
# Scoring against expected answers
# ---------------------------------------------------------------------------

def score(results: list[dict], expected: dict) -> dict:
    """Score only the fields each expected answer actually gives (route, intents, queue, priority, flags)."""
    rows, unsafe, missed = [], [], []
    by_band = {"high": [0, 0], "medium": [0, 0], "low": [0, 0]}   # band -> [correct, total]

    for r in results:
        exp = expected.get(r["id"])
        if not exp:
            continue
        got_intents = sorted({i["intent"] for i in r.get("intents", [])})
        check = {}
        if "route" in exp:
            ok_routes = exp.get("acceptable_routes", [exp["route"]])
            check["route"] = r["route"] in ok_routes
            if r["route"] == "auto" and "auto" not in ok_routes:
                unsafe.append(r["id"])
            if r["route"] == "human" and "human" not in ok_routes:
                missed.append(r["id"])
        if "intents" in exp:
            ok_intents = [sorted(x) for x in exp.get("acceptable_intents", [])] + [sorted(exp["intents"])]
            check["intents"] = got_intents in ok_intents
            band = r.get("confidence", {}).get("band", "low")
            if r.get("model", {}).get("ok"):       # only messages the AI actually labelled
                by_band[band][0] += check["intents"]
                by_band[band][1] += 1
        if "queue" in exp:
            check["queue"] = r["queue"] in exp.get("acceptable_queues", [exp["queue"]])
        if "priority" in exp:
            check["priority"] = r["priority"] in exp.get("acceptable_priorities", [exp["priority"]])
        if "must_flags" in exp:
            check["flags"] = set(exp["must_flags"]) <= set(r.get("flags", []))

        rows.append({"id": r["id"], "check": check, "got_intents": got_intents,
                     "exp_intents": sorted(exp.get("intents", [])), "route": r["route"], "exp_route": exp.get("route"),
                     "queue": r["queue"], "exp_queue": exp.get("queue"), "priority": r["priority"],
                     "exp_priority": exp.get("priority"),
                     "missing_flags": sorted(set(exp.get("must_flags", [])) - set(r.get("flags", []))),
                     "note": exp.get("note", "")})

    totals = {}
    for k in ("route", "intents", "queue", "priority", "flags"):
        scored = [row["check"][k] for row in rows if k in row["check"]]
        totals[k] = (sum(scored), len(scored))
    return {"n": len(rows), "totals": totals, "unsafe": unsafe, "missed": missed, "rows": rows, "by_band": by_band}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def money_and_model_stats(results: list[dict]) -> dict:
    n = len(results) or 1
    cost = sum(r.get("model", {}).get("cost_usd", 0) for r in results)
    tin = sum(r.get("model", {}).get("input_tokens", 0) for r in results)
    tout = sum(r.get("model", {}).get("output_tokens", 0) for r in results)
    second = [r.get("model", {}).get("second_opinion") for r in results]
    second = [x for x in second if x]
    return {"cost": cost, "per_1000": cost / n * 1000, "avg_in": tin / n, "avg_out": tout / n,
            "fresh_calls": sum(r.get("model", {}).get("fresh_api_calls", 0) for r in results),
            "second_asked": len(second),
            "second_agreed": sum(x == "agreed" for x in second),
            "second_disagreed": sum(x == "disagreed" for x in second),
            "second_failed": sum(x.startswith("failed") for x in second)}


def write_report(path: str, results: list[dict], sc: dict | None, stability: dict | None, out_dir: str) -> str:
    st = money_and_model_stats(results)
    routes = Counter(r["route"] for r in results)
    lines = [f"# Triage report: `{path}`", "",
             f"Model: `{config.MODEL}`  |  prompt version: `{config.PROMPT_VERSION}`  |  "
             f"run at {time.strftime('%Y-%m-%d %H:%M')}", "",
             f"**{len(results)} messages: {routes['auto']} automated, {routes['human']} to a person.**", ""]

    if sc:
        t = sc["totals"]
        def frac(k):
            ok, n = t[k]
            return f"{ok}/{n}" if n else "not labelled"
        lines += ["## Scores against expected answers", "",
                  f"{sc['n']} messages have expected answers; each line counts only the answers that give that field.", "",
                  f"- **Unsafe automations (must be 0): {len(sc['unsafe'])}** {', '.join(sc['unsafe'])}",
                  f"- Missed automations (cost, not risk): {len(sc['missed'])} {', '.join(sc['missed'])}",
                  f"- Route correct: {frac('route')}",
                  f"- Intents correct: {frac('intents')}",
                  f"- Queue correct: {frac('queue')}",
                  f"- Priority correct: {frac('priority')}",
                  f"- Required warning flags raised: {frac('flags')}", "",
                  "**Does confidence predict mistakes?** (intent accuracy per band, AI-labelled messages only)", ""]
        for band, (ok, total) in sc["by_band"].items():
            lines.append(f"- {band}: {ok}/{total} correct" if total else f"- {band}: no messages")
        lines.append("")

    lines += ["## Cost (measured)", "",
              f"- Cost of these answers: ${st['cost']:.5f} (cached answers count at their original price)",
              f"- **Per 1,000 messages: ${st['per_1000']:.3f}**  (includes second opinions)",
              f"- Average tokens per message: {st['avg_in']:.0f} in, {st['avg_out']:.0f} out",
              f"- Fresh API calls made by this run: {st['fresh_calls']} (the rest came from the cache)",
              f"- Second opinions asked: {st['second_asked']}: agreed {st['second_agreed']}, "
              f"disagreed {st['second_disagreed']}, failed {st['second_failed']}", ""]

    if stability:
        lines += ["## Stability across repeated runs", "",
                  f"{stability['runs']} runs without cache. Messages whose route or intents changed between runs:", ""]
        lines += [f"- {mid}: {detail}" for mid, detail in stability["unstable"].items()] or ["- none"]
        lines.append("")

    lines += ["## Every message", "",
              "| ID | Route | Queue | Priority | Confidence | Intents | Flags |",
              "|---|---|---|---|---|---|---|"]
    for r in results:
        intents = ", ".join(i["intent"] for i in r.get("intents", []))
        lines.append(f"| {r['id']} | {r['route']} | {r['queue']} | {r['priority']} | "
                     f"{r.get('confidence', {}).get('band', '')} | {intents} | {', '.join(r.get('flags', []))} |")

    if sc:
        wrong = [row for row in sc["rows"] if not all(row["check"].values())]
        lines += ["", "## Disagreements with expected answers", ""]
        if not wrong:
            lines.append("None.")
        for row in wrong:
            bad = [k for k, v in row["check"].items() if not v]
            lines.append(f"**{row['id']}** (wrong: {', '.join(bad)})")
            if "route" in bad:
                lines.append(f"- route: got `{row['route']}`, expected `{row['exp_route']}`")
            if "intents" in bad:
                lines.append(f"- intents: got `{row['got_intents']}`, expected `{row['exp_intents']}`")
            if "queue" in bad:
                lines.append(f"- queue: got `{row['queue']}`, expected `{row['exp_queue']}`")
            if "priority" in bad:
                lines.append(f"- priority: got `{row['priority']}`, expected `{row['exp_priority']}`")
            if "flags" in bad:
                lines.append(f"- missing flags: `{row['missing_flags']}`")
            if row["note"]:
                lines.append(f"- expected-answer note: {row['note']}")
            lines.append("")

    report = "\n".join(lines) + "\n"
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Run message triage on a file and score it.")
    ap.add_argument("path", nargs="?", default="data/messages.json")
    ap.add_argument("--expected", help="expected-answers file (auto-detected if omitted)")
    ap.add_argument("--runs", type=int, default=1, help="repeat N times without the cache to measure stability")
    args = ap.parse_args()

    name = os.path.splitext(os.path.basename(args.path))[0]
    out_dir = os.path.join("output", name)
    os.makedirs(out_dir, exist_ok=True)

    if not config.API_KEY:
        print("No API key set: running on keyword rules only. Every message will go to a person.\n")

    stability = None
    if args.runs > 1:
        config.USE_CACHE = False
        all_runs = []
        for i in range(args.runs):
            print(f"Run {i + 1} of {args.runs} (no cache):")
            all_runs.append(run_file(args.path))
        results = all_runs[-1]
        unstable = {}
        for idx, r in enumerate(results):
            routes = [run[idx]["route"] for run in all_runs]
            intents = [tuple(sorted(i["intent"] for i in run[idx].get("intents", []))) for run in all_runs]
            if len(set(routes)) > 1 or len(set(intents)) > 1:
                unstable[r["id"]] = f"routes {routes}; intents {[list(x) for x in intents]}"
        stability = {"runs": args.runs, "unstable": unstable}
        # Cost of ONE run is what matters per 1,000 messages
    else:
        print(f"Triaging {args.path}:")
        results = run_file(args.path)

    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    expected_path = args.expected or EXPECTED_FOR.get(os.path.basename(args.path))
    sc = None
    if expected_path and os.path.exists(expected_path):
        with open(expected_path, encoding="utf-8") as f:
            sc = score(results, as_answer_dict(json.load(f)))

    report = write_report(args.path, results, sc, stability, out_dir)
    # Print the top of the report (summary, scores, cost)
    print("\n" + report.split("## Every message")[0].strip())
    print(f"\nFull report: {os.path.join(out_dir, 'report.md')}")


if __name__ == "__main__":
    main()
