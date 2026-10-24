# Stock availability and replenishment

Available stock equals on-hand units less units reserved for unfulfilled, uncancelled
orders at the same warehouse. Read the warehouse and product identifiers together;
stock in Leeds is not automatically available for dispatch from Coventry. Compare the
requested quantity with available stock, not the headline on-hand number.

## Explain a shortage

Show on-hand, reserved, available, requested and short quantities. If a purchase order
exists, show its outstanding units, supplier and expected receipt date. A received
purchase order requires receipt records; an open order is not present inventory. Do
not include future goods in today's available stock. A receipt increases stock and
a dispatch decreases it. Each must link to its operational record.

## Baseline interpretation

The learning company's replenishment history is a retrospective reconstruction.
Monthly receipts match modeled dispatch needs; an opening buffer covers reservations.
This makes inventory reconcile, but is not a claim about how the source retailer planned
stock and is not a forecast with a valid information cutoff. Keep that distinction in
analysis and reports. No public cancellation is automatically relabeled as a return.

Escalate shortages to purchasing with the product, warehouse, requested quantity and
supporting record IDs. The first assistant cannot create purchase orders, transfer
stock or increase on-hand quantities. A report may recommend review, but must not say
that any of those operations was performed.
