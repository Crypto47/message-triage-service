# Research and prior art

Before and during the build I checked how this problem is solved in production and what is known to break. After my own design was done, I also read public solutions to this same task.

## How production systems do it
- **The standard pattern:** an LLM classifies intent and handles routine volume, and escalates to people on frustration, churn, refunds, disputes and cancellations ([industry overview](https://learn.engineering.vips.edu/applications/customer-support-ticket-triage); Anthropic's [ticket-routing guide](https://docs.anthropic.com/en/docs/about-claude/use-case-guides/ticket-routing)). Classification itself is a solved problem; the hard part is the guardrails around it.
- **Prompt injection can't be prompted away.** OWASP's Top 10 for LLM Applications (LLM01) recommends layered defences with controls outside the model. → The model has no tools; code decides; keyword flags run independently of the model.
- **Models are overconfident when asked to rate themselves** ([Xiong et al., "Can LLMs Express Their Uncertainty?"](https://arxiv.org/pdf/2306.13063)). → Confidence uses only checks code can verify.
- **LLMs get broad intent right on Hinglish but miss fine-grained intent** ([JMIR 2026, Hinglish intent study](https://www.jmir.org/2026/1/e86545)). → Hinglish lowers confidence. My held-out results matched this: main intents right, extra or missing secondary intents wrong.
- **Free tiers and provider data policies** (OpenRouter docs). → Built and tested on a cheap paid model; production would pin a provider that doesn't store or train on customer messages.

## Public solutions to this task
I read four public repositories after my design was settled. They confirmed the core split (the model labels, code decides), which is now the common baseline rather than a differentiator.

**Credited:**
- [aashuBX/ai-message-assistant](https://github.com/aashuBX/ai-message-assistant): "unsafe automations must be zero" as the release gate, and a second classification before automating. Theirs re-asks at a higher temperature; mine uses different wording.
- [coder-irwin/gajan-message-triage](https://github.com/coder-irwin/gajan-message-triage): their observation that MSG-022 was read correctly in only one of four runs is why I measured stability across repeated runs. Their "with another day" date rule is one I built (bookings within 48 hours get higher priority).
- [bored-apes/message-triage](https://github.com/bored-apes/message-triage): offline keyword mode doubling as the API-failure fallback, which my design shares.

**What I did differently:**
1. **A held-out set and a final set labelled by me alone.** The public solutions I read evaluate on the same 25 messages their prompts were written against. My scores drop on unseen messages (intents 12/20), and I report that gap.
2. **Confidence without any self-rating.** Others start from the model's own certainty; one reports the model rated 30 of 31 intents "high." Mine is built only from verifiable checks.
3. **Stability measured, not assumed:** 13 of 45 messages changed intents across 3 runs, but no message needing a person was ever automated.
4. **An acknowledgement for every message sent to a person**, since silence was MSG-011's actual complaint.
5. **Attacks and fraud go to one team with no copies**, found by reading real output.
6. **Scope kept to the 3-hour brief:** no UI or deployment extras; the effort went into evaluation.
