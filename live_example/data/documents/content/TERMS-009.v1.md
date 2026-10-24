---
{
  "access_scope": "general",
  "category": "customer_terms",
  "document_id": "TERMS-009",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "country": "United Kingdom",
    "first_order": "2010-12-01",
    "id": "UCI-CUST-18102",
    "last_order": "2011-12-08",
    "name": "Cotswold Trading Living",
    "orders": 60,
    "payment_terms_days": 30,
    "segment": "Online reseller"
  },
  "owner_employee_id": "EMP-003",
  "record_links": {
    "customer_id": "UCI-CUST-18102"
  },
  "status": "current",
  "version": 1
}
---
# Account terms: Cotswold Trading Living

## Account identity

Use `UCI-CUST-18102` as the stable account reference. The first selected source country is United Kingdom; the account name and online reseller segment are fictional. The training contact uses a reserved example-domain address. It is not a contact discovered about the real retailer's customer.

## Terms and purchasing context

The modeled payment term is 30 calendar days after invoice posting. These terms are assigned by the Acme rule, not extracted from UCI. There are 60 selected orders between 2010-12-01 and 2011-12-08. Compare orders within that coverage before assuming an account is inactive or growing.

## Service handoff

Sales owns commercial coordination. For a delivery question, obtain the specific order and its shipment lines. A source country label is insufficient to infer a postal address, route or guaranteed lead time. For settlement detail, refer the case to finance rather than exposing allocations through a general account summary.

## Exceptions

Cancelled orders remain in history, partial consignments retain outstanding lines, and a credit note requires its own evidence. Quotation changes, refunds and order edits are outside the first assistant's write tools. A report can identify the required human review without claiming it has taken place.

Business reference: 2011-12-09. Dataset: acme-company-v8.
