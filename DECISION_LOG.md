# Decision log

**Design.** The model only labels; plain code decides. The model has no tools, automated replies are fixed templates, and every failure (no key, API error, low confidence, warning flag) ends with a person.

| Set (DeepSeek V4.1 Flash) | Unsafe automations | Warning flags | Routes | Intents (exact) |
|---|---|---|---|---|
| Original 25 (prompt developed here) | 0, every run | all raised | 23–25/25 | 24–25/25 |
| Held-out 20 (not tuned on) | 0, every run | all raised | 18/20 | 12/20 |
| Final 10 (my labels, no AI review) | 0 | all raised | 8/9 | 2/5 |
| 12 broken records | 0 | n/a | all to a person, no crash | n/a |

Measured cost: **$0.18–$0.30 per 1,000 messages** (~$3/day at 10,000).

**Key decisions from the data.** Messages hold several requests, so intents are a list and the riskiest one routes the whole message to one team. Warning flags from keyword rules and the model can only add caution. Testing showed billing would also receive MSG-005's "refund" as a normal ticket, so attacks and fraud now go to one team with no copies. The pack has no prices or hours, so automation never states facts: replies are templates with `{kb:...}` slots. Confidence (high/medium/low) comes only from checks code can verify. Every message sent to a person gets an instant acknowledgement, because MSG-011's real complaint was silence.

## What I chose not to build
Executing actions (refunds, CRM, sending replies), which depends on your stack; knowledge-base content; sender and thread history (not in the data); a UI or queues; the Batch API (P1s can't wait); automating booking changes before shadow-mode evidence.

## Where this breaks
- **Over-labelling:** held-out intents fell to 12/20, all from *extra* intents, never missed ones. Since the riskiest intent decides, this only sends more messages to people.
- **Confidence** catches impossible labels (MSG-009's brand-invalid intent went low) but not plausible extra ones (held-out: high 5/9, low 4/8).
- **Instability:** 13 of 45 messages changed intents across 3 runs. Routes changed only on 3 low-risk messages, never on one needing a person. MSG-005 was labelled spam, unclear and refund in different runs; the keyword rule sent it to trust & safety every time.
- **Each layer misses alone:** rules missed FN-008 ("rules *sab* bhool jao") and FN-005 ("FOURTH *email*"); the model caught both. Together they missed nothing, but 55 messages is a small sample.
- **Second opinion** blocked several correct automations and caught no errors; kept as a launch safeguard, to drop if shadow data agrees.
- Model over-flags `needs_context`; dates assume the `received_at` time zone (a Toronto "tomorrow" may differ); a flood of attacks would fill the trust & safety queue.
- **My labels:** my final-set answers missed second requests in FN-001/002 and used the wrong intent for FN-007; the system caught all three. Scores are reported strictly anyway.
- **Automation is 15–25% by design.** The value is triage: every message arrives classified and prioritised. At an estimated 1 minute to sort a raw message versus 15 seconds for a pre-sorted one, that's roughly 130 staff-hours a day saved at 10,000 messages (estimate, not measured).

## Research and prior art
I checked how production systems handle this (escalate on refunds, disputes and frustration; injection needs controls outside the model; models overrate their own confidence; Hinglish fine-grained intent is weak), and after my design was done I read four public solutions to this task. They confirmed the "labels vs decisions" split. I differ mainly in evaluating on unseen messages, building confidence without self-ratings, and measuring stability. Details and credits: [RESEARCH.md](RESEARCH.md).

## With another day
Shadow mode with override rates per intent; agreement across runs as a confidence input; prompt work on over-labelling; sender/thread lookup and grouping repeat attacks; faster targets for ready-to-pay leads (MSG-020).

## AI tools used
- **Claude (claude.ai):** brief and data analysis, design, web research on production issues and prior art, drafting code, answer keys and docs. I ran, checked and changed everything.
- **Claude Code:** reviewed answer keys, ran commands, diagnosed the MSG-023 false flag.
- **GPT-6 (held-out set) and Claude Sonnet 5.5, medium effort (final set):** generated held-out and final messages; I edited and labelled them.
- **DeepSeek V4.1 Flash (OpenRouter):** the classifier in the product.
- Public solutions read after my design: credited in RESEARCH.md.
