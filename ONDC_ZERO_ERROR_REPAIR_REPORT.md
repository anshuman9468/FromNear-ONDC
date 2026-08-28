# ONDC RET10 Zero-Error Repair Audit

## Initial State

The supplied `seller.html` report was generated on 2026-08-28 and contains:

- Total tests: 14,905
- Passed: 13,595
- Failed: 1,310
- Pending: 0
- Skipped: 0
- Unique failure signatures: 58

The Workbench flow cards reaching 100% did not mean that all report assertions
passed. The report combines BPP callback checks with Workbench-generated BAP
input checks, so those two categories must be separated.

## Root-Cause Findings

### 1. BAP input fixture shape

The repeated `retail_bap_select` failures inspect Workbench/BAP request data
containing `location` and missing `location_id`, `parent_item_id`, and `tags`.
The shared BAP request builder now normalizes these fields through
`_complete_bap_item`, without modifying the test assertions or report data.

### 2. Quote-breakup item tags

The report's BPP verification expects the standard item-tag vocabulary under
`quote.breakup[].item.tags[]` and rejects `code: "quote"`. Both shared builders
now emit `code: "type"` with a valid nested type value.

### 3. RTO update ordering

The RTO update handler previously started unsolicited status pushes without
first sending the paired direct `on_update` callback. This produced repeated
empty-context/order failures and out-of-sequence records. The handler now
validates, stores, and sends direct `on_update` before the RTO status sequence.

### 4. BPP identity

The BPP response context correctly uses the registered subscriber ID
`ondc.fromnear.com`. It must not be changed to the Workbench BAP fixture ID
`workbench.ondc.tech`; doing so would make the signed BPP response identify the
wrong party.

## Changes Applied

- `backend/app/ondc/bpp/order_builder.py`
- `backend/app/ondc/bpp/services/update.py`
- `backend/app/ondc/protocol/builders.py`
- `backend/app/tests/unit/test_bpp_callback_guards.py`

## Local Validation

- Python compilation: passed
- Formatting/error check: passed
- Application tests: 42 passed
- No tests were disabled or assertions weakened.

## Deployment

The repaired image is deployed to Cloud Run service `fromnear-ondc-backend`
with revision `fromnear-ondc-backend-00268-xc2`, serving 100% traffic.

Health and BPP key lookup smoke checks passed after deployment.

## Required Fresh Validation

The supplied HTML report is historical and cannot be updated by code changes.
Create a fresh BPP Workbench session after deployment, run the affected flows,
then generate a new report. Only that new report can establish the final
failure count. This audit intentionally does not claim zero failures without
that fresh report.
