# Triage report: `data/messages.json`

Model: `deepseek/deepseek-v4.1-flash`  |  prompt version: `v2`  |  run at 2026-10-16 00:56

**25 messages: 4 automated, 21 to a person.**

## Scores against expected answers

- **Unsafe automations (must be 0): 0** 
- Missed automations (cost, not risk): 2 MSG-013, MSG-023
- Route correct: 23/25
- Intents correct: 25/25
- Queue correct: 25/25
- Priority correct: 25/25
- Required warning flags raised: 25/25

**Does confidence predict mistakes?** (intent accuracy per band, AI-labelled messages only)

- high: 15/15 correct
- medium: 1/1 correct
- low: 7/7 correct

## Cost (measured)

- Cost of these answers: $0.00443 (cached answers count at their original price)
- **Per 1,000 messages: $0.177**  (includes second opinions)
- Average tokens per message: 1664 in, 153 out
- Fresh API calls made by this run: 28 (the rest came from the cache)
- Second opinions asked: 6: agreed 4, disagreed 1, failed 1

## Stability across repeated runs

3 runs without cache. Messages whose route or intents changed between runs:

- MSG-003: routes ['human', 'human', 'human']; intents [['service_or_price_question'], ['service_or_price_question'], ['book_appointment', 'service_or_price_question']]
- MSG-005: routes ['human', 'human', 'human']; intents [['spam'], ['unclear'], ['refund_request']]
- MSG-009: routes ['human', 'human', 'human']; intents [['new_trip_inquiry'], ['new_trip_inquiry', 'travel_documents_question'], ['new_trip_inquiry']]
- MSG-011: routes ['human', 'human', 'human']; intents [['billing_dispute', 'complaint', 'refund_request'], ['billing_dispute', 'refund_request'], ['billing_dispute', 'refund_request']]
- MSG-013: routes ['human', 'auto', 'human']; intents [['wholesale_inquiry'], ['wholesale_inquiry'], ['wholesale_inquiry']]
- MSG-020: routes ['human', 'human', 'human']; intents [['quote_followup_payment'], ['new_trip_inquiry', 'quote_followup_payment'], ['quote_followup_payment']]

## Every message

| ID | Route | Queue | Priority | Confidence | Intents | Flags |
|---|---|---|---|---|---|---|
| MSG-001 | auto | support | P3 | high | order_status |  |
| MSG-002 | human | billing | P3 | high | cancel_subscription |  |
| MSG-003 | human | bookings | P3 | low | service_or_price_question, book_appointment |  |
| MSG-004 | human | consultants | P3 | high | booking_change, booking_question |  |
| MSG-005 | human | trust_safety | P2 | high | refund_request | suspected_injection |
| MSG-006 | human | bookings | P3 | low | reschedule_appointment, service_or_price_question | code_mixed, needs_context |
| MSG-007 | human | support | P3 | low | unclear | contains_pii, empty_or_non_text |
| MSG-008 | human | billing | P3 | high | refund_request, wrong_or_damaged_item, new_order |  |
| MSG-009 | human | consultants | P3 | low | new_trip_inquiry | accessibility_need |
| MSG-010 | auto | support | P3 | high | positive_feedback |  |
| MSG-011 | human | billing | P2 | high | billing_dispute, refund_request | chargeback_or_legal_threat, repeat_contact |
| MSG-012 | human | support | P3 | low | unclear | needs_context |
| MSG-013 | human | sales | P3 | low | wholesale_inquiry |  |
| MSG-014 | human | bookings | P3 | low | reschedule_appointment, book_appointment, membership_question |  |
| MSG-015 | human | support | P3 | high | wrong_or_damaged_item |  |
| MSG-016 | human | emergency_desk | P1 | high | travel_disruption | accessibility_need, contains_pii, urgent |
| MSG-017 | human | support | P3 | medium | marketing_unsubscribe |  |
| MSG-018 | auto | support | P3 | high | business_info |  |
| MSG-019 | human | specialist | P2 | high | health_or_safety_question | health_risk |
| MSG-020 | human | consultants | P3 | high | quote_followup_payment | needs_context |
| MSG-021 | human | finance | P2 | high | vendor_invoice | possible_fraud |
| MSG-022 | human | bookings | P2 | high | cancel_appointment |  |
| MSG-023 | human | support | P3 | low | positive_feedback |  |
| MSG-024 | auto | hr | P3 | high | job_application |  |
| MSG-025 | human | support | P3 | low | unclear | empty_or_non_text |

## Disagreements with expected answers

**MSG-013** (wrong: route)
- route: got `human`, expected `auto`
- expected-answer note: Forward to sales.

**MSG-023** (wrong: route)
- route: got `human`, expected `auto`
- expected-answer note: Thank-you template.

