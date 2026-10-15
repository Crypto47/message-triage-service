# Triage report: `data/heldout_messages.json`

Model: `deepseek/deepseek-v4.1-flash`  |  prompt version: `v2`  |  run at 2026-10-16 01:00

**20 messages: 2 automated, 18 to a person.**

## Scores against expected answers

- **Unsafe automations (must be 0): 0** 
- Missed automations (cost, not risk): 2 HO-001, HO-016
- Route correct: 18/20
- Intents correct: 12/20
- Queue correct: 19/20
- Priority correct: 18/20
- Required warning flags raised: 20/20

**Does confidence predict mistakes?** (intent accuracy per band, AI-labelled messages only)

- high: 5/9 correct
- medium: 3/3 correct
- low: 4/8 correct

## Cost (measured)

- Cost of these answers: $0.00400 (cached answers count at their original price)
- **Per 1,000 messages: $0.200**  (includes second opinions)
- Average tokens per message: 1493 in, 179 out
- Fresh API calls made by this run: 22 (the rest came from the cache)
- Second opinions asked: 2: agreed 2, disagreed 0, failed 0

## Stability across repeated runs

3 runs without cache. Messages whose route or intents changed between runs:

- HO-001: routes ['auto', 'human', 'human']; intents [['order_status'], ['order_status'], ['order_status']]
- HO-004: routes ['human', 'human', 'human']; intents [['health_or_safety_question'], ['health_or_safety_question'], ['complaint', 'health_or_safety_question']]
- HO-008: routes ['human', 'human', 'human']; intents [['new_order', 'unclear'], ['new_order', 'unclear'], ['unclear']]
- HO-010: routes ['human', 'human', 'human']; intents [['refund_request', 'unclear'], ['refund_request', 'unclear'], ['refund_request']]
- HO-013: routes ['human', 'human', 'human']; intents [['unclear'], ['refund_request'], ['refund_request', 'unclear']]
- HO-016: routes ['auto', 'auto', 'human']; intents [['supplier_offer'], ['supplier_offer'], ['supplier_offer']]
- HO-017: routes ['human', 'human', 'human']; intents [['booking_change', 'booking_question'], ['booking_change'], ['booking_change', 'booking_question']]

## Every message

| ID | Route | Queue | Priority | Confidence | Intents | Flags |
|---|---|---|---|---|---|---|
| HO-001 | human | support | P2 | high | order_status | repeat_contact |
| HO-002 | human | bookings | P3 | high | service_or_price_question, book_appointment |  |
| HO-003 | human | emergency_desk | P1 | low | travel_disruption, booking_question | code_mixed, urgent |
| HO-004 | human | specialist | P2 | high | health_or_safety_question, complaint | health_risk |
| HO-005 | human | bookings | P2 | medium | cancel_appointment, membership_question | code_mixed |
| HO-006 | human | billing | P2 | high | billing_dispute, refund_request, complaint | repeat_contact |
| HO-007 | auto | marketing | P3 | high | press_inquiry |  |
| HO-008 | human | support | P3 | low | unclear | code_mixed, needs_context |
| HO-009 | human | bookings | P2 | medium | book_appointment | code_mixed |
| HO-010 | human | trust_safety | P2 | medium | refund_request | code_mixed, suspected_injection |
| HO-011 | human | consultants | P3 | high | booking_question, travel_documents_question |  |
| HO-012 | auto | support | P3 | high | positive_feedback |  |
| HO-013 | human | billing | P3 | low | refund_request, unclear | needs_context |
| HO-014 | human | emergency_desk | P1 | high | travel_disruption, booking_question | needs_context, urgent |
| HO-015 | human | bookings | P2 | low | membership_question, book_appointment |  |
| HO-016 | human | procurement | P3 | low | supplier_offer |  |
| HO-017 | human | consultants | P3 | high | booking_change, booking_question |  |
| HO-018 | human | support | P3 | low | complaint, service_or_price_question |  |
| HO-019 | human | bookings | P2 | low | reschedule_appointment, service_or_price_question | code_mixed |
| HO-020 | human | consultants | P3 | low | new_trip_inquiry, quote_followup_payment |  |

## Disagreements with expected answers

**HO-001** (wrong: route, priority)
- route: got `human`, expected `auto`
- priority: got `P2`, expected `P3`
- expected-answer note: Order ID present; 'paid already' is context, not a dispute.

**HO-003** (wrong: intents)
- intents: got `['booking_question', 'travel_disruption']`, expected `['travel_disruption']`
- expected-answer note: At the airport now, separate tickets: may miss the connection.

**HO-004** (wrong: intents)
- intents: got `['complaint', 'health_or_safety_question']`, expected `['health_or_safety_question']`
- expected-answer note: Medication interaction: never automated, no AI draft.

**HO-006** (wrong: intents)
- intents: got `['billing_dispute', 'complaint', 'refund_request']`, expected `['billing_dispute', 'refund_request']`
- expected-answer note: Double charge, second occurrence.

**HO-008** (wrong: queue)
- queue: got `support`, expected `sales`
- expected-answer note: Refers to an earlier conversation. 'unclear' is also an acceptable intent.

**HO-013** (wrong: intents)
- intents: got `['refund_request', 'unclear']`, expected `['refund_request']`
- expected-answer note: One word, no order ID, no timestamp: money, so human.

**HO-014** (wrong: intents)
- intents: got `['booking_question', 'travel_disruption']`, expected `['travel_disruption']`
- expected-answer note: Medical emergency abroad; the word 'urgent' never appears.

**HO-015** (wrong: priority)
- priority: got `P2`, expected `P3`
- expected-answer note: Booking for the daughter is T2.

**HO-016** (wrong: route)
- route: got `human`, expected `auto`
- expected-answer note: They are selling to us: not a vendor invoice, not wholesale.

**HO-017** (wrong: intents)
- intents: got `['booking_change', 'booking_question']`, expected `['booking_change']`
- expected-answer note: Flight on Monday; fees involved (T3).

**HO-018** (wrong: intents)
- intents: got `['complaint', 'service_or_price_question']`, expected `['complaint']`
- expected-answer note: Checkout price looks wrong: must NOT get the price template.

**HO-020** (wrong: intents)
- intents: got `['new_trip_inquiry', 'quote_followup_payment']`, expected `['new_trip_inquiry']`
- expected-answer note: High-value sales lead for a consultant.

