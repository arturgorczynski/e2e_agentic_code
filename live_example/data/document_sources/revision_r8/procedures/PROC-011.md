# Ticket-history handoff

## Use and owner

Customer support (`DEP-SUPPORT`) owns the history of a service case. Event `DEMO-TKT-004:1` is an authored scenario event dated 2011-12-06, not a customer message supplied by the UCI source. Use the ticket ID from the case under review and keep the customer, order and assigned employee attached to it.

## Review steps

1. Read the ticket's original topic, description, opening date, current status and assigned employee. Confirm that its order belongs to the selected customer before sharing details.
2. Read every linked `ticket_events` entry in date and ID order. Record the last event's status and compare it with the ticket's current status; retain earlier notes as part of the audit trail.
3. Separate what the customer reported, what an employee recorded, and what shipment, invoice or payment records actually show. A case note is not proof that a parcel was delivered, a refund was paid or a message was sent.
4. Route a stock or carrier discrepancy to Logistics and a balance or credit question to Finance. Include the exact linked IDs and the evidence still needed.

## Decision and exception

A resolved status needs an event that records the evidence and outcome. Do not infer resolution from a drafted reply or from an assigned owner. If the ticket status differs from the latest event, leave the discrepancy visible and request an authorized correction; do not silently rewrite the history.

## Handoff record

Record reviewer, reference date, ticket, order and customer IDs, latest event ID, current status, unresolved evidence and the next owner. Distinguish archived 2011 cases from contemporary account history when reporting trends.
