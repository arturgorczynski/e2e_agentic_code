# Damaged-goods complaint handling

Customer support owns complaint triage. Start from the ticket and its linked order;
check dispatch and delivery evidence before interpreting a damaged-goods report. Ask
for the affected product, quantity and supporting photographs when those details are
missing. Do not turn an allegation into an established carrier or warehouse fault.

## Progress the case

An open case may move to in_progress after the employee reviews the evidence and approves
the concrete proposed change. Show the ticket ID, current status, requested status,
reason and operation ID. The application must validate the acting user's support.update
permission and thread ownership. Keep zero changes before approval. A repeated approval
for the same operation must not create a second transition or duplicate audit event.

An approved transition records work starting; it does not resolve the complaint. A
resolved status requires an explanation of the reviewed evidence and the actual outcome.
The original ticket description remains available alongside its chronological events.

## Limits

The learning assistant cannot issue refunds, promise compensation or create credit notes.
Those are separate finance decisions. It may explain the permitted next step and cite
the relevant order and shipment. If the user rejects the proposal, keep the ticket
unchanged and state that no update was saved. These rules describe the intended tool
workflow; record availability alone is not evidence that approval software is running.
