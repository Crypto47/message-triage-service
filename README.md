# Message triage service

Reads inbound customer messages for Vitalis Wellness, Hair Studio and Voyage Travel, and for each one decides **what the customer wants, what details are in the message, and what happens next, handled by whom**. Every result carries a confidence band and plain-English reasons.

**Read [DECISION_LOG.md](DECISION_LOG.md) first.** Research and prior art: [RESEARCH.md](RESEARCH.md).

## Run it

Needs Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
# put your OpenRouter key in .env:  OPENAI_COMPAT_API_KEY=sk-or-...
python run.py data/messages.json
```

**What you need to supply:** one [OpenRouter API key](https://openrouter.ai/keys) with a little credit (a full run of the 25 messages costs under 1 cent). The model is set in `.env` (`TRIAGE_MODEL`, default `deepseek/deepseek-v4.1-flash`).

**No key?** It still runs. Every message goes to a person, with priority and queue set by keyword rules, so emergencies are still P1 and the injection attempt still goes to trust & safety.

Each run writes to `output/<file name>/`:
- `report.md`: summary, scores against expected answers, measured cost, every message, every disagreement
- `results.json`: the full result for every message

Other runs:

```bash
python run.py data/heldout_messages.json            # 20 messages the prompt was not tuned on
python run.py data/final_messages.json --expected eval/expected_final.json
python run.py data/broken_messages.json             # 12 deliberately broken records
python run.py data/messages.json --runs 3           # re-ask 3 times without cache: stability
python -m triage.decide data/messages.json MSG-005  # one message, full result
```

Saved reports from our runs are in `sample_output/`.

## How it decides

```
ingest -> signals -> AI labels -> checks + decision -> result
```

1. **Ingest** (`triage/ingest.py`): every record becomes a safe message. Null text, wrong types, missing or duplicate IDs, unknown brands, hidden characters and very long text are flagged, never crash.
2. **Signals** (`triage/signals.py`, no AI): regex finds order IDs, booking refs, amounts and phone numbers; resolves "tomorrow", "kal", "parso", weekdays against `received_at`; raises warning flags (injection, urgency, health, fraud, chargeback, repeat contact, needs history) in English, Hinglish and some Hindi script.
3. **AI labels** (`triage/llm.py`): one call per message returns intents (each with an exact quote as evidence), details, flags and an "ambiguous" marker, in a strict JSON schema. The message is sent as data; the model has no tools. Answers are cached; failures fall back to a person.
4. **Checks + decision** (`triage/decide.py`, plain code): verifies the labels, sets the confidence band, then decides the route, queue, priority, template and acknowledgement.

The whole policy (intents, risk tiers, flags, queues, templates) is plain data in `triage/config.py`.

## When a person sees the message

Automation acts only if **all** of these hold; otherwise a person handles it:

1. The AI labelled it successfully.
2. No warning flag that always needs a person (injection, fraud, urgent, health, chargeback or legal threat, repeat contact, needs earlier context, empty or damaged record).
3. Every intent is low-risk: **T0** (thank-you, info template) or **T1** (read-only lookup, forward to a team). Anything that changes a booking (T2) or involves money, health, safety or expert judgement (T3) always goes to a person.
4. Confidence is good enough for the tier: medium or better for T0, high for T1.
5. A second, differently worded classification agrees.

**Confidence** is built only from checks code can verify, never from the model rating itself:
- **high** = no problems
- **medium** = one minor problem (very short message, or Hinglish/Hindi)
- **low** = any major problem (a quote or ID not found in the message, wrong ID format, intent not valid for the brand, required detail missing, model says ambiguous, second opinion disagrees, AI unavailable)

Automated replies are **fixed templates**. Facts such as prices or opening hours come from the brand's own content (`{kb:...}` slots), never from the model.

## Cost per 1,000 messages

**Measured: $0.18–$0.30 per 1,000 messages** across our runs, including second opinions. That's about **$1.80–$3.00 a day at 10,000 messages**.

How it is built (from `report.md` of each run):
- Average per message: about 1,600 input and 170 output tokens, including second opinions (asked for about 1 in 5 messages).
- The input is mostly the fixed prompt and schema (~1,000 tokens), so longer messages barely change the cost.
- Prices: DeepSeek V4.1 Flash list price $0.15 input / $0.60 output per million tokens (October 2026). The report uses OpenRouter's own billed figure when it returns one, which varies with the provider serving the request; that's why runs range from $0.18 to $0.30.
- Reasoning is switched off: labelling doesn't need it, and it would multiply output tokens.

**Assumptions:** real messages are about as long as the sample; the second-opinion rate stays near 20%; infrastructure cost is ignored (one small container).

## Scaling to 10,000 a day

10,000 a day is about 7 messages a minute on average. `run.py` processes one message at a time, which keeps up with the average. For peaks (assume 5×, about 35 a minute), run several workers in parallel: messages are independent, so this is a deployment change, not a code change. Rate limits and server errors are retried with backoff; after that the message goes to a person, never dropped. A rejected key or empty credit stops further calls at once, so 10,000 messages don't make 10,000 failing calls.

## Assumptions

- No sender identity or conversation history (the data has none), so messages that depend on earlier context go to a person.
- "Unsubscribe" is ambiguous (mailing list or paid subscription?), so a person checks it.
- Relative dates use the time zone of `received_at`.
- Response targets: P1 15 minutes, P2 2 hours, P3 24 hours (to confirm with the business).
- This service makes decisions; it doesn't execute them or send replies.

## Layout

```
triage/config.py    the policy: intents, tiers, flags, queues, templates, settings
triage/ingest.py    safe loading
triage/signals.py   regex details, keyword flags, dates (no AI)
triage/llm.py       AI labels: prompt, schema, cache, retries, fallback
triage/decide.py    checks, confidence, routing
run.py              run a file, score it, report cost and stability
data/               original 25, held-out 20, final 10, broken 12
eval/               expected answers, format checker
sample_output/      reports from our runs
```
