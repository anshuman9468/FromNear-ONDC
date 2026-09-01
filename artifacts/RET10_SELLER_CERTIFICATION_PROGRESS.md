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

## Iteration 13: Offer tag shape

Session ID: historical report only; fresh remote confirmation pending
Deployment revision: `fromnear-ondc-backend-00368-qgp` (100% traffic)
Protocol version: `1.2.0`
Header validation: Workbench-only setting; production signature verification unchanged

Passed validations:
- Full backend test suite: `58 passed`.
- Catalog normalizer now emits `offers[*].tags` as an array for sparse and real catalog fixtures.

Failed validations:
- Historical RTO `select` reports contain `message.order.offers[0].tags should be a array`.

Fixed since prior run:
- Added `tags: []` to the checked-in `O1` offer fixture.
- Added regression tests for normalized and source offer tag shape.

Next iteration objective:
- Rerun the RTO flow from a fresh Workbench session and confirm the historical offer-tag failure is absent from the live request.

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

## Iteration 7: Fresh Workbench execution on current Seller revision

Session ID: `k4kD53-rIYTq0zTeyC7AtY_OF9WLDg5y`
Deployment revision: `fromnear-ondc-backend-00353-lfc` (100% traffic; `ONDC_BPP_FLOW_MODE=auto`)
Protocol version: `1.2.0`
Header validation: OFF

Passed validations:
- Local Seller suite: `52 passed`.
- Full Catalog City: 100%, all expected steps ACK.
- Buyer Side Order Cancellation: 100%, all expected steps ACK.
- Discovery incremental catalog refresh pull: 100%, all expected steps ACK.
- Prepaid with IGM 1.0.0: 100%, all expected steps ACK.
- Prepaid fulfillment: 100%, all expected steps ACK.
- Out of Stock: 100%, all expected steps ACK.
- Incremental catalog push: 100%, all expected steps ACK.
- RTO seller callbacks through `on_update`: select, on_select, init, on_init, confirm, on_confirm, and on_update all returned HTTP 200/ACK.

Failed or incomplete remote flows:
- Buyer Initiated Return: Workbench mock `update` stopped at step 13 with `BAD Request: subscriberID not set`; no `/update` request reached the Seller BPP.
- Merchant Side RTO: Workbench mock `update` stopped at step 8 with `BAD Request: subscriberID not set`; no `/update` request reached the Seller BPP.
- The RTO card retains five out-of-sequence entries from an earlier attempt in this same session. The fresh execution before the mock failure had no new out-of-sequence callback.

Fixed since prior run:
- No speculative Seller code change was made for the two mock failures because live Cloud Run logs prove the failing request never reached this BPP.
- Current deployed callbacks continued to pass the previously failing quote-tag and catalog shape checks.

Persistent:
- Workbench's mock update request omits `subscriberID` in both Return and RTO scenarios. This is an external test-harness blocker, not a Seller response validation failure.

New deeper validations: none; the blocked mock requests prevented downstream update assertions.

Regressions: none observed in local tests or the seven independent green flows.

Root causes:
1. The shared Seller payload fixes are effective on the current live revision.
2. Return/RTO cannot advance past the Workbench mock update step because the mock request is malformed before BPP delivery.

Code changes in this iteration:
- None after the fresh-session evidence; prior uncommitted source changes remain covered by the local suite and current deployment.

Tests added: none in this iteration; existing quote-tag, area-code, RTO, and callback guard tests cover the deployed changes.

Next iteration objective:
- Commit and push the verified source and certification artifacts, deploy the committed revision, verify health and traffic, and generate the current session report. Re-run Return/RTO only if Workbench provides a valid update request containing `subscriberID`.

## Deployment verification after Iteration 7

Deployment revision: `fromnear-ondc-backend-00355-qn5`
Traffic: 100%
Health: `https://ondc.fromnear.com/api/v1/health` returned `status=healthy`, `database=healthy`.
Diagnostics: configuration, signature derivation, callback route, and payload preflight PASS; registry/gateway/subscriber lookup remain external pre-production checks.
Git commit: `8e29a26` pushed to `origin/main`.

The Workbench session `k4kD53-rIYTq0zTeyC7AtY_OF9WLDg5y` was executed before this final deployment and already verified seven independent green flows. The remaining Return/RTO failures are Workbench mock requests rejected with `subscriberID not set` before reaching the Seller endpoint; they require a fresh valid Workbench mock request for final certification.

## Iteration 8: Contract-aligned active BPP diagnostics

Session ID: `k4kD53-rIYTq0zTeyC7AtY_OF9WLDg5y` (existing evidence; no new Workbench report generated)
Deployment revision: `fromnear-ondc-backend-00357-tsd`
Protocol version: `1.2.0`
Header validation: Workbench-only setting; production signature verification unchanged

Contract review:
- The Retail 1.2.0 contract defines `keyId` as `subscriber_id|unique_key_id|algorithm`; registry lookup and signature verification therefore use participant identity and registered keys, not payment data.
- Settlement details are a separate payment structure. For `settlement_type: upi`, `upi_address` is required; this cannot repair a missing transport/request `subscriberID` in a Workbench mock update.
- The contract identifies `/update` as the buyer-initiated part return/cancel request and `/on_update` as the Seller response or Seller-initiated part cancellation.

Code changes:
- Diagnostics now compares registry `ukId`, signing key, and encryption key against the active BPP credential set when seller credentials are configured.
- Diagnostics now signs its gateway probe with the same active BPP credentials used for registry lookup.
- `verify_preprod_registration.py` now reports the active credential set and the configured callback URI instead of the Buyer key/obsolete `.app` URL.

Verification:
- Full application suite: `52 passed`.
- RET10 lifecycle dry run: 12 callback payloads passed.
- Buyer cancellation dry run: passed.
- Catalog audit: all six checks passed.

## Iteration 10: Live session Ed2abHsNVZSDuPHlLc898KPCWTxCEblX

Session ID: `Ed2abHsNVZSDuPHlLc898KPCWTxCEblX`
Deployment revision: `fromnear-ondc-backend-00358-j4c` (100% traffic)
Protocol version: `1.2.0`
Header validation: Workbench-only setting reported OFF by the operator; production signature verification remains enabled.

Flows observed:
- Buyer Initiated Return: 72%; Workbench mock `update` failed to generate (`defaultPayload is not defined`) before any Seller `/update` request.
- Buyer Side Order Cancellation: 100% with expected callbacks ACK.
- Discovery incremental catalog refresh pull: 100% with expected callbacks ACK.
- Merchant Side RTO and Part Order Cancellation: 43%; select/init/confirm ACK, but unsolicited `on_update` remained waiting. The request had no RTO/cancel marker, so `auto` mode could not safely classify it.
- Order to confirm to fulfillment Prepaid with IGM 1.0.0: 100% with expected callbacks ACK.
- Order to confirm to fulfillment (Prepaid): 100% with expected callbacks ACK.
- Out of Stock: 13%; first select/on_select ACK, then Workbench stayed at the second mock `select` in SENDING. Cloud Run logs show no second request reached the Seller.
- Full Catalog City and Incremental Push: not started because Workbench persisted Out of Stock as the active flow.

Certification status: not a clean final report. The active-flow lock disabled report generation. Do not claim zero failures from this session.

Verification:
- Full backend suite: `53 passed`.
- Live health: healthy database/service.
- Live revision: `fromnear-ondc-backend-00358-j4c`, 100% traffic.

Next iteration objective:
- Start a fresh Seller session after the Workbench active-flow lock is reset, run catalog flows first, then all order/exception flows, and generate a report.

Deployment verification:
- Cloud Run revision `fromnear-ondc-backend-00357-tsd` is ready and serves 100% traffic.
- `/api/v1/health` reports healthy database/service status.
- Live diagnostics reports `configuration=PASS`, `registry=PASS`, `gateway=PASS`, `signature=PASS`, `subscriber=PASS`, `callback=PASS`, and `payload=PASS`.
- Registry lookup returned the subscribed BPP record for `ondc.fromnear.com`, Seller key ID `490ba361-51d0-49b7-8c00-182892758de9`, and callback `https://ondc.fromnear.com/api/v1/ondc`.

Remote certification status:
- This confirms the deployed participant identity and diagnostics probes, but it is not a new clean Workbench/Pramaan report. The last Workbench evidence still had Return/RTO blocked by malformed mock `update` requests with `subscriberID not set` before BPP delivery.

Next iteration objective:
- Start a fresh Seller Workbench session against revision `00357-tsd`, keep Header Validation OFF, run all applicable flows, and generate a fresh report. Treat any remaining malformed mock update as a Workbench blocker, not a Seller payload failure.

Remote status:
- The prior fresh session had seven independent green flows.
- Return and RTO remain blocked at Workbench mock `update` with `subscriberID not set`; no `/update` request reached the Seller service, so payment fields cannot resolve that blocker.

Next iteration objective:
- Deploy this diagnostics correction, verify the active Cloud Run revision and health, then create a fresh Seller Workbench session with a valid update mock before final certification.

## Iteration 9: Contract-correct registry and gateway probes

Deployment revision: `fromnear-ondc-backend-00357-tsd`
Protocol version: `1.2.0`
Header validation: Workbench-only setting; production signature verification unchanged

Live probe findings:
- The registry returned `15050 JSON Request Invalid format` because the diagnostics request used `unique_key_id`; the contract requires `ukId` and the lookup selectors `country`, `city`, and `type`.
- The gateway returned `400 Payment is required in intent for search request` because the diagnostics search intent lacked the buyer-app finder-fee payment object.

Code changes:
- Registry diagnostics now sends the contract-shaped `ukId`, `country`, `city`, and `type` fields.
- Gateway diagnostics now includes `@ondc/org/buyer_app_finder_fee_type=percent` and `@ondc/org/buyer_app_finder_fee_amount=3` in `message.intent.payment`.
- Added assertions covering the active BPP registry request and payment-bearing gateway probe.

Verification before deployment:
- Full application suite: `52 passed`.
- RET10 lifecycle dry run: 12 callback payloads passed.
- Buyer cancellation dry run: passed.
- Catalog audit: all six checks passed.

## Iteration 11: Supplied JFxl session comparison

Session ID: `JFxl8BFnlg05sii2VhU8yLMgbCe-f6Ts`
Deployment revision: live diagnostics confirms the current Cloud Run service is healthy; the browser session contains historical executions and is not a clean new certification run.
Protocol version: `1.2.0`
Header validation: Workbench-only setting; production signature verification unchanged

Observed Workbench flow status:
- Buyer Initiated Return: 100%
- Buyer Side Order Cancellation: 100%
- Discovery incremental catalog refresh pull: 100%
- Merchant Side RTO and Part Order Cancellation: 86%, with retained out-of-sequence callback records
- Order to confirm to fulfillment (Prepaid): 100%
- Order to confirm to fulfillment Prepaid with IGM 1.0.0: 83%
- Out of Stock: 100%
- Search and Custom Menu (Full Catalog City): 100%
- Search and Custom Menu (Incremental Push): 100%

Certification status: not clean. The page does not show a single clean 100% session; RTO and IGM remain incomplete, and the RTO card retains 14 out-of-sequence records. Generate Report is disabled for this state.

Backend comparison:
- Live seller registry lookup: PASS; `ondc.fromnear.com` is `SUBSCRIBED` for Seller key ID `490ba361-51d0-49b7-8c00-182892758de9`.
- Signing key derivation: PASS.
- Callback route checks: PASS for all required Seller callbacks.
- Gateway, subscriber reachability, and payload preflight: PASS.
- No new backend payload defect is evidenced by this session; its remaining failures are incomplete/stale Workbench flow state and must be re-tested in a clean session before changing source.

Next iteration objective:
- Use a genuinely fresh Seller Workbench session, clear prior flow data, run catalog first, then run RTO and IGM from their first step, and generate the report. Do not use the 86%/83% page as final certification evidence.

## Iteration 12: `seller(1).html` forensic comparison and deployed tag fix

Report: `/home/anshumandutta/Downloads/seller(1).html`
Report totals: 15,809 validations; 15,173 passed; 636 failed; 30 optional failures.
Deployment revision: `fromnear-ondc-backend-00362-8s5` (100% traffic)
Protocol version: `1.2.0`
Header validation: Workbench-only setting; production signature verification unchanged.

Root-cause findings:
- The report was generated before the current quote-tag correction. Product breakup lines were emitted with `item.tags.code=quote`, but RET10 1.2.0 requires the item taxonomy vocabulary for product lines; only fulfillment charge lines use `quote` metadata.
- Repeated `bpp_id=workbench.ondc.tech` comparisons are Workbench/BAP input inconsistencies. The Seller callback identity must remain the registered `ondc.fromnear.com`; changing it would break registry consistency.
- Large RTO/return callback clusters include incomplete/stale Workbench branches and malformed mock inputs; they cannot be treated as proof of a live Seller payload defect without a fresh request reaching Cloud Run.

Code fix:
- The order builder and final outbound canonicalizer now emit `type/item` tags for product breakup lines and `quote/fulfillment` tags for delivery lines.
- The local RET10 validator and callback regression tests enforce the same line-specific vocabulary.

Verification:
- Full backend suite: `55 passed`.
- Targeted callback/lifecycle suite: `19 passed`.
- Live health: PASS.
- Live diagnostics: configuration, registry, gateway, signature, subscriber, callback, and payload all PASS.

Certification status: the supplied report is not a final post-fix report. A new Seller Workbench session must execute the applicable flows against revision `00362-8s5` before zero actionable BPP failures can be claimed.

## Iteration 14: BAP update fulfillment floor

Session ID: not created; source fix and local verification only
Deployment revision: `fromnear-ondc-backend-00369-88z` (100% traffic)
Protocol version: `1.2.0`
Header validation: Workbench-only setting; production signature verification unchanged

Observed failure:
- `retail_bap_update_message_05_minItems`: `message.order.fulfillments` was `[]` but must contain at least one item.

Root cause:
- The BAP `UpdateService` did not add its fallback fulfillment for `update_target="fulfillment"`.
- `UpdateRequestBuilder` then preserved an empty or missing fulfillment list instead of enforcing the RET10 minimum.

Code fix:
- `UpdateService` now creates a Return fulfillment whenever normalization produces none.
- `UpdateRequestBuilder` now guarantees one fully normalized `F1` fulfillment for both item and fulfillment update targets.
- Added parametrized regression coverage for both update targets.

Verification:
- Targeted protocol/BPP tests: `32 passed`.
- Full backend suite: `60 passed`.
- Only existing Pydantic deprecation warnings remain.

Certification status:
- The supplied screenshot is a request-verification failure. It is not proof that the BPP callback builder emitted an empty list.
- The change is deployed and health-checked; use a fresh Workbench session and rerun the Update Settlement Trail/RTO path. A fresh report is required to confirm the live result.

Next iteration objective:
- Deploy and verify the revision, then rerun the exact Workbench flow from a clean session. If the report still shows the same request-side failure without an application `/update` request, capture the Workbench mock payload as an external fixture issue.
