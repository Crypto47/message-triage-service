# Triage report: `data/final_messages.json`

Model: `deepseek/deepseek-v4.1-flash`  |  prompt version: `v2`  |  run at 2026-10-16 01:33

**10 messages: 2 automated, 8 to a person.**

## Scores against expected answers

9 messages have expected answers; each line counts only the answers that give that field.

- **Unsafe automations (must be 0): 0** 
- Missed automations (cost, not risk): 1 FN-001
- Route correct: 8/9
- Intents correct: 2/5
- Queue correct: not labelled
- Priority correct: not labelled
- Required warning flags raised: 4/4

**Does confidence predict mistakes?** (intent accuracy per band, AI-labelled messages only)

- high: 2/3 correct
- medium: no messages
- low: 0/2 correct

## Cost (measured)

- Cost of these answers: $0.00265 (cached answers count at their original price)
- **Per 1,000 messages: $0.265**  (includes second opinions)
- Average tokens per message: 1784 in, 187 out
- Fresh API calls made by this run: 0 (the rest came from the cache)
- Second opinions asked: 2: agreed 2, disagreed 0, failed 0

## Every message

| ID | Route | Queue | Priority | Confidence | Intents | Flags |
|---|---|---|---|---|---|---|
| FN-001 | human | support | P3 | low | order_status, service_or_price_question | code_mixed |
| FN-002 | human | bookings | P2 | low | reschedule_appointment, service_or_price_question | code_mixed |
| FN-003 | human | specialist | P2 | high | health_or_safety_question | health_risk |
| FN-004 | human | emergency_desk | P1 | high | unclear | urgent |
| FN-005 | human | billing | P2 | high | billing_dispute, refund_request, complaint | chargeback_or_legal_threat, repeat_contact |
| FN-006 | human | billing | P2 | low | cancel_appointment, refund_request | code_mixed |
| FN-007 | auto | marketing | P3 | high | press_inquiry |  |
| FN-008 | human | trust_safety | P2 | medium | refund_request, order_status | code_mixed, suspected_injection |
| FN-009 | human | consultants | P3 | high | quote_followup_payment | needs_context |
| FN-010 | auto | support | P3 | high | positive_feedback |  |

## Disagreements with expected answers

**FN-001** (wrong: route, intents)
- route: got `human`, expected `auto`
- intents: got `['order_status', 'service_or_price_question']`, expected `['order_status']`

**FN-002** (wrong: intents)
- intents: got `['reschedule_appointment', 'service_or_price_question']`, expected `['reschedule_appointment']`

**FN-007** (wrong: intents)
- intents: got `['press_inquiry']`, expected `['business_info']`

