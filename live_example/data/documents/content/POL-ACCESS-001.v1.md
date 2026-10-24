---
{
  "access_scope": "general",
  "category": "policies",
  "document_id": "POL-ACCESS-001",
  "effective_from": "2011-01-01",
  "effective_until": null,
  "facts": {},
  "owner_employee_id": "EMP-003",
  "record_links": {
    "department_id": "DEP-SALES"
  },
  "status": "current",
  "version": 1
}
---
# Identity, ownership and business access

An authenticated account links to an employee. Application code supplies the immutable
acting user ID and current permissions; the model must not choose them through tool
arguments. A name mentioned in a prompt is not an authenticated identity.

## Private work

Every conversation, checkpoint, pending approval, trace, report and download belongs
to its owner. Check that ownership for reads, listing, streaming, resume and export.
Knowing an identifier or guessing a download URL grants no access. Reject a cross-owner
request before loading private content or invoking the model. No business role has an
automatic exception for another employee's private conversation.

## Company records

General commercial facts are available to the defined business roles. Finance detail,
operations detail, support cases and planning records require their respective scopes.
Apply document scopes before ranking and excerpting search results, not after exposing
restricted snippets. The employee directory excludes compensation, bank details and
private HR material. The baseline intentionally contains no such private HR dataset.

Approval permits a specific action only when the actor already has the required role.
It cannot elevate a sales account to finance. Revalidate access after interruption or
restart. An absent record should produce a bounded not-found response; do not substitute
another customer's record or invent order status. Account definitions in the company
contract are training identities, not evidence that authentication is already deployed.

Business reference: 2011-12-09. Dataset: acme-company-v8.
