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

## Iteration 5

Session ID: Not created; source-level contract fix only
Deployment revision: Not deployed in this iteration
Protocol version: 1.2.0 behavior from the active Workbench contract examples
Header validation: OFF for Workbench sessions only

Passed validations:
- `51 passed` in `PYTHONPATH=. pytest -q app/tests`.
- All 12 callback payloads passed `test_full_ret10_lifecycle_dryrun.py` with zero local RET10 validation errors.

Failed validations:
- No new Workbench report in this iteration.

Flows passed: Local lifecycle coverage only
Flows failed: Remote flows not executed in this iteration
Flows newly reached: None

Fixed since prior run:
- Product quote-breakup lines now emit RET10 item taxonomy tags.
- Fulfillment-level quote lines retain `quote` / `fulfillment` metadata.
- Final network canonicalization applies the same boundary to legacy stored orders.

Persistent:
- Seller key ID `490ba361-51d0-49b7-8c00-182892758de9` still requires successful pre-production registry propagation before signed Workbench callbacks can be certified.

Regressions: none observed locally.

Next iteration objective:
- Commit and deploy the verified source change, confirm the live revision, then use a new Workbench Seller RET10 Grocery session and analyze a fresh report.

## Deployment Correction: Seller Unique Key ID

Deployment revision: `fromnear-ondc-backend-00338-bk5` (100% traffic)
Seller key ID configured: `490ba361-51d0-49b7-8c00-182892758de9`
Buyer key ID unchanged: `8c5c6504-113b-4150-acb0-6e2577c972ca`

The previous deployment used `490ba36f...` with a letter `f`; it was corrected to the user-confirmed `490ba361...` with the digit `1`. Health, signature derivation, callback routes, and payload preflight remain PASS. The official registry still returns `15040 Subscriber not found`, so the corrected seller key must be registered/subscribed before rerunning Workbench.

## Iteration 3: Quote quantity root-cause fix

Session ID: `JFxl8BFnlg05sii2VhU8yLMgbCe-f6Ts` (existing session; not a fresh certification run)
Deployment revision: `fromnear-ondc-backend-00344-m2f`
Protocol version: `1.2.0`
Header validation: Workbench-only setting; production signature verification unchanged

Passed validations:
- Cloud Run revision `00344-m2f` is ready, receives traffic, and `/api/v1/health` reports a healthy database.
- Full local test suite: `50 passed`.
- Full lifecycle dry run: all 12 callback payloads passed RET10 validation.
- Existing session showed 100% completion for full catalog, incremental pull, incremental push, buyer cancellation, buyer return, and prepaid fulfillment flows.

Failed or incomplete remote flows:
- RTO remains incomplete at 86% in the existing session because its terminal unsolicited `on_cancel` was not recorded.
- Out-of-stock remains incomplete at step 3 in the existing session; the BPP logs showed the earlier callback was HTTP 200/ACK, but Workbench did not advance the second select step.
- IGM flow remains incomplete at the optional issue branch in the existing session.

Fixed since prior run:
- Prevented catalog quantity metadata from overwriting the numeric requested quantity while building `quote.breakup[*].item.quantity.selected.count`.
- Added a regression assertion that every quote breakup selected count is an integer.

Regressions: none in local tests or dry run.

Remaining requirement:
- A fresh Workbench Seller session and fresh report are required to verify the deployed fix. The current browser automation connection had no user tab, so the existing session was opened in a new controlled tab only for state inspection; no zero-error claim is made from it.

## Iteration 4: RTO detection and Seller helper identity

Session ID: `JFxl8BFnlg05sii2VhU8yLMgbCe-f6Ts` (existing session; not replayed)
Deployment revision: `fromnear-ondc-backend-00345-d5v` (100% traffic)
Protocol version: `1.2.0`
Header validation: Workbench-only setting; production signature verification unchanged

Passed validations:
- Cloud Run revision `00345-d5v` is ready, receives 100% traffic, and `/api/v1/health` reports healthy.
- Full local test suite: `51 passed`.
- Full lifecycle dry run: all 12 callback payloads passed RET10 validation.

Failed or incomplete remote flows:
- Existing RTO flow remains at 86% because it began before revision `00345-d5v`; its old transaction already followed the non-RTO branch and cannot be repaired by replaying cards.
- Existing Out-of-Stock flow remains at step 3 waiting for Workbench's second mock `/select`; no callback was received for that request.
- Existing IGM flow stops at the scenario's mock issue branch; this is not evidence of a Seller callback failure.

Fixed since prior run:
- RTO detection now scans order-level tags as well as item and fulfillment tags.
- Added regression coverage for order-level `rto_action` markers.
- Seller helper scripts now send `ondc.fromnear.com` as `bpp_id` and use `https://ondc.fromnear.com/api/v1/ondc` as `bpp_uri`; they no longer send the Workbench Buyer identity as the Seller.

Regressions: none in local tests or dry run.

Next iteration objective:
- Create a fresh Workbench Seller RET10 Grocery session against revision `00345-d5v`, disable Header Validation in Workbench, run every applicable flow once, and generate a fresh report. Do not reuse the old session for certification.

## Iteration 6: Local contract audit cleanup

Session ID: Not applicable
Deployment revision: Not deployed in this iteration
Protocol version: `1.2.0`
Header validation: Workbench-only setting; production signature verification unchanged

Passed validations:
- Focused Seller application suite: `51 passed`.
- Full local lifecycle dry run: all 12 callback payloads passed RET10 validation.
- Buyer cancellation dry run passed.
- Catalog audit confirms MSN `bpp_terms` is under `bpp/descriptor.tags`, provider tags use the restricted provider vocabulary, item tags are arrays, item locations use `location_id`, and item categories use the RET10 grocery enum.

Failed or incomplete remote flows:
- No new Workbench run in this iteration.
- Seller registry propagation remains an external prerequisite for signed callback certification.

Fixed since prior run:
- Corrected two contradictory repository audits that treated `bpp_terms` as both required and forbidden under provider tags.
- Corrected the item category audit to validate the RET10 grocery category enum; the alphanumeric constraint remains applied to provider category object IDs only.

Regressions: none observed in the focused local suite.

Next iteration objective:
- Commit the audit corrections, deploy only after the live deployment credentials and registry state are confirmed, then run a fresh Workbench Seller session and parse the resulting report.
