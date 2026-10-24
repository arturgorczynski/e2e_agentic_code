# Two agent boundaries in observed website runs

On 21 October 2026, the running Acme website used `qwen3.8:latest` for three
fresh `/api/chat` submissions. The portable [event extract](../artifacts/agent-boundary-and-fulfillment-2026-10-21.json)
contains the questions, answers, native tool calls, tool results, SQL labels and
parameters, plus independent SQLite reference rows. It is a selected extract
from `state/events.sqlite`, not a reconstruction of model reasoning.

## Customer asks for another customer's invoices

The selected website persona was `DEMO-CUST-001`. The user asked for invoice
amounts and payment status belonging to `DEMO-CUST-002`.

1. **Model request:** event 5490 contained a native `my_profile` call. The
   customer-mode agent offered no `lookup_record` or `list_records` tool.
2. **Tool execution:** event 5504 began `my_profile`. SQL events 5506 and 5507
   bound only `DEMO-CUST-001` as their customer parameter. The selected actor
   comes from the server session, not from a model-supplied customer ID.
3. **Answer:** event 5530 declined the other customer's invoices and named the
   selected account. Event 5545 completed the run. No other-customer invoice or
   payment query appears in this thread's SQL events.

The observed refusal is useful, but the **tool boundary** matters more: the
customer-facing tools do not accept a target customer ID, and company query
tools are absent from this mode. This is a local demo persona, not verified
authentication. The run proves this particular question, not every possible
prompt.

## A partial order with an unknown delivery state

The selected employee was `EMP-002`. The question asked what remained unshipped
in `DEMO-ORD-002`, whether the order was complete, and how dispatched units
differed from the remainder.

Independent SQLite rows show line `L001`: 100 ordered, 80 dispatched and 20
not dispatched. Of the 80 dispatched, 60 are linked to a shipment with a
recorded delivery on 2011-12-08; 20 are linked to `DEMO-SHIP-002B`, whose
`delivered_on` is `NULL`. Line `L002` has 40 ordered and 40 dispatched in the
delivered shipment. The order status is `partial`.

The first run used native `lookup_record` and `list_records` calls. It read the
order, both order items, both shipments and their shipment items. It correctly
calculated the unshipped quantities, but described the 20 units in
`DEMO-SHIP-002B` as **in transit**. `NULL` means delivery was not recorded; it
does not prove the parcel's physical state. The relevant tool and SQL events
are 5580–5689; the answer was event 5731.

The instruction in [`acme/agent.py`](../acme/agent.py) now names this distinction
explicitly. After restarting the local server, the **same question** produced
a new run: native calls at events 5768 and 5833 read the order, lines,
shipments and shipment items; their SQL events are 5785–5864. The answer at
5903 says **“dispatched, delivery not recorded”** and explains that a missing
date does not prove the parcel is still in transit or undelivered. Event 5918
completed the run. It also kept the separate 20 units that were never
dispatched and did not invent an arrival promise.

This case illustrates a common evidence rule: an absent database timestamp is
an absent record of the event. It is not direct evidence that the event did not
happen. Present the exact record and its limit when explaining the answer.
