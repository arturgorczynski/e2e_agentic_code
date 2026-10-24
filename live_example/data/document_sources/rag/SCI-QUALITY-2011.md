# Research methods note: monitoring dispatch quality

## Purpose

This short scientific methods note describes how Acme could monitor a dispatch quality measure without confusing random fluctuation with a verified process change. It is authored for the fictional company and contains no claim of a completed quality trial. The statistical background is the NIST/SEMATECH Engineering Statistics Handbook, “What are Control Charts?”, https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm. We paraphrase the method and apply it only as a proposed design.

## Define a measurable event

Choose one event, such as a consignment dispatched after its documented target date. Define the denominator as all eligible consignments dispatched in a complete reporting week. Keep canceled orders, returns and split shipments under explicit rules. A split order can create multiple consignments, so a consignment rate and an order rate answer different questions. Record the location, carrier, product mix and target-date policy effective at the time. Without stable definitions, a change in the rate can be caused by a changed denominator.

## Establish a baseline

Use a run of complete historical periods whose process definition is stable. Plot the observed measure over time, estimate a center and suitable control limits under assumptions appropriate to the measure and sample sizes, then monitor later periods against the frozen baseline. A control signal is a prompt to investigate, not proof of a particular cause. The NIST handbook explains that a control chart places the statistic against time with a center line and control limits. The choice of chart and assumptions need review by someone who understands the data generation process.

Acme's dispatch events are modeled. A chart drawn from them can test the analytics pipeline but cannot establish real-world warehouse performance. If the exercise adds newer synthetic cases, label a new version of the input population. Never present a chart over a mixed 2011 and contemporary clock as one continuous observed process.

## Investigation protocol

When a signal appears, check missing rows, late data entry, duplicate consignments, a new carrier assignment and target-date changes before attributing it to staff or equipment. Then examine linked order and shipment IDs. Compare like with like: Coventry dispatches and Leeds return-hub dispatches may have different purposes. Preserve the original chart, query, source hashes and investigated explanation. If the explanation remains unknown, say so.

## RAG interpretation

This document can answer “What would a control signal mean?” and “Which event definition should be recorded?” It cannot answer “Did Acme's quality improve?” without a completed chart and underlying events. A retrieval system should distinguish this protocol from an incident report and should cite the exact version effective for the question's date.
