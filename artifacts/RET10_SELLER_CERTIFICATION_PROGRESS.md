# RET10 Seller Certification Progress

## Iteration 0: Historical baseline

Session ID: historical reports only
Deployment revision: `fromnear-ondc-backend-00332-wwk` (last verified before this iteration)
Protocol version: `1.2.0`
Header validation: OFF for Workbench testing only

Passed validations: `seller.html` 10,241; `seller(1).html` 13,595
Failed validations: `seller.html` 1,043; `seller(1).html` 1,341

Flows passed: not safely inferable as complete from historical reports
Flows failed: RTO/Return/Prepaid/Buyer Cancel/OOS/catalog suites contain failures
Flows newly reached: Return Flow and deeper RTO lifecycle checks in `seller(1).html`

Fixed since prior run:
- Persistent RTO classification added at the initial select/init/confirm boundary.
- Canonical BPP order/fulfillment/payment field completion exists at the network boundary.

Persistent:
- Historical reports contain malformed Workbench/BAP request fixtures.
- Historical BPP callback reports show nested quote-tag vocabulary mismatch.

New deeper validations:
- The newer report added substantial Return Flow assertions, explaining part of the increase from 1,043 to 1,341.

Regressions:
- No regression can be attributed from report counts alone; a fresh same-session comparison is required.

Root causes:
1. Nested quote breakup item tags are serialized with the wrong tag group/value.
2. Catalog location time ranges do not match the active Workbench validator.
3. Callback sequencing/empty-response cascades obscure the first lifecycle delivery failure.
4. Some OOS runs do not classify the Workbench negative selection as an error response.

Code changes in this iteration: pending implementation and verification.
Tests added: parser and targeted regression tests pending.

Next iteration objective:
- Apply shared builder fixes, run local tests, deploy, then execute a fresh Workbench Seller RET10 Grocery session and parse its report.

## Iteration 1: Live verification after v15

Session ID: `JFxl8BFnlg05sii2VhU8yLMgbCe-f6Ts`
Deployment revision: `fromnear-ondc-backend-00337-5j5`
Protocol version: `1.2.0`
Header validation: not visible in the fresh session controls; production signature code remains enabled

Passed validations: local wire preflight; targeted callback tests; full-catalog flow reached 100% on the immediately preceding fresh session
Failed validations: current Buyer Side Order Cancellation stops at `on_select` callback authentication before Workbench payload assertions

Flows passed: Full Catalog City on the preceding fresh session reached 100%; no clean post-v15 full suite
Flows failed: Buyer Side Order Cancellation blocked at `on_select`; remaining flows not executed in this fresh session
Flows newly reached: quote-tag schema rejection was cleared; registry authentication became the first blocker

Fixed since prior run:
- Shared quote breakup tags now use the active Workbench RET10 vocabulary at the network boundary.
- Catalog operating-hours range now uses the active Workbench format.
- BPP lifecycle state can persist across Cloud Run instances when enabled.
- Diagnostics now select seller/BPP credentials when configured and compare raw or DER public-key encodings correctly.

Persistent:
- Seller key ID `490ba36f-51d0-49b7-8c00-182892758de9` is not found in the official pre-production registry.
- The base/buyer key ID is also not found by direct pre-production lookup and must not be used for seller callbacks.

New deeper validations:
- None after the current auth rejection; Workbench did not reach callback schema validation in this attempt.

Regressions:
- None demonstrated. The live change from quote-tag rejection to registry authentication confirms the payload fix was reached.

Root causes:
1. Shared callback quote tags required final network canonicalization for stored legacy orders.
2. Catalog location time range required the active Workbench operating-hours format.
3. Cloud Run multi-instance lifecycle correlation required durable state.
4. Callback verification is blocked until the seller key is subscribed in pre-production.

Code changes in this iteration:
- Added BPP-specific diagnostic credential selection and correct raw/DER key matching.
- Added regression coverage for BPP diagnostic credential selection.

Tests added: `app/tests/unit/test_bpp_callback_guards.py`, `app/tests/unit/test_diagnostics.py`

Next iteration objective:
- Complete ONDC pre-production seller key subscription/propagation, then rerun a new Workbench Seller session against the latest revision and generate a fresh report.

## Iteration 2: Deployment and diagnostics verification

Session ID: no new Workbench session; blocked before callback authentication
Deployment revision: `fromnear-ondc-backend-00337-5j5` (100% traffic)
Protocol version: `1.2.0`
Header validation: Workbench-only setting; not changed in application code

Passed validations:
- Cloud Run revision became ready and serves 100% traffic.
- `/api/v1/health` reports healthy database and service.
- `/api/v1/diagnostics/ondc` reports seller/BPP signature derivation match and payload preflight PASS.
- Existing local targeted tests and the 12-callback lifecycle dry-run remain green.

Failed validations:
- No new Workbench validations executed. The prior fresh session remains blocked at callback authentication by the pre-production registry response `15040 Subscriber not found`.

Flows passed: no new Workbench flow execution in this iteration
Flows failed: no new flow execution; prior session blocked at `on_select`
Flows newly reached: none

Fixed since prior run:
- Diagnostics now report the seller-specific BPP credentials instead of the buyer/base credentials.
- Diagnostics compare compatible raw and DER public-key encodings.

Persistent:
- The official pre-production registry does not contain seller key ID `490ba36f-51d0-49b7-8c00-182892758de9` for `ondc.fromnear.com`.

Regressions: none observed

Next iteration objective:
- After registry subscription and propagation, create a fresh Seller RET10 Grocery session, disable Header Validation in Workbench, run all applicable flows, download the report, and parse every failure.
