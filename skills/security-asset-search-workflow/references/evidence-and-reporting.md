# Evidence and Reporting

Use this reference when turning search results into findings.

## Evidence quality

### Strong

- direct owner-approved verification
- current response from an in-scope asset
- owner-side inventory, DNS, certificate, or cloud record
- matching evidence from multiple independent data sources

### Medium

- recent asset-search result with clear matching fields
- certificate or DNS evidence that matches the scope
- repeated results across time

### Weak

- old indexed result
- title or banner match without ownership confirmation
- organization-name match only
- result from shared hosting, CDN, or parked domains
- screenshot without timestamp or source

## Confidence labels

Use simple labels:

- **confirmed**: enough evidence to act
- **likely**: probably real, needs owner-side check
- **possible**: useful lead, not a finding yet
- **false positive**: explain why
- **stale**: was visible in an index, not confirmed current

## Report notes

Each finding should state:

- what was searched
- why the asset is in scope or not
- what matched
- how fresh the evidence is
- what remains unverified
- what the next check should be

Avoid dramatic wording. A search result is a lead until verified.

## Example wording

Good:

- "This host is likely in scope because the certificate subject matches the approved domain. The indexed title suggests an admin dashboard. Current exposure needs owner-side verification."
- "The result appears stale. The search index last saw it on the recorded date, but no current verification has been performed."

Weak:

- "Critical exposure found" with only a search-engine row.
- "The organization is vulnerable" without confirming ownership and current reachability.

## Handling sensitive output

For public reports:

- redact secrets if accidentally present
- avoid full secret values, private keys, or session values
- use partial hostnames only if disclosure would create risk
- keep raw exports in private storage when they contain sensitive infrastructure details
