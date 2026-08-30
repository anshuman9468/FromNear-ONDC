# Seller RET10 Error Ledger

This ledger compares the two historical Workbench reports supplied for the Seller NP. Counts are report assertion counts, not unique protocol defects. The newer report reached deeper Return/RTO lifecycle suites, so a larger total is not by itself a regression.

| Root Cause | Flow/API | Old Count | New Count | Status | Code Owner | Fix |
|---|---|---:|---:|---|---|---|
| BAP input items use legacy `location` and omit `location_id`, `parent_item_id`, and `tags` | RTO, Return, Prepaid, Buyer Cancel / select-init-confirm | Repeated | Repeated | External fixture / not BPP-owned | Workbench BAP input | Do not patch Seller responses; use canonical Workbench input or the repository BAP request builders. |
| Workbench request context uses `workbench.ondc.tech` as `bpp_id` instead of registered Seller `ondc.fromnear.com` | RTO and other request/callback context checks | Present | Present | External session configuration | Workbench/BAP | Keep outgoing BPP context registered as `ondc.fromnear.com`; record as non-actionable until the session input is corrected. |
| Nested `quote.breakup[*].item.tags` uses forbidden tag group/value | Prepaid, Buyer Cancel, Return, RTO / on_select-on_init-on_confirm-on_status-on_cancel | 27+ | 30+ | Fixed in source; fresh live run passed this validator before auth rejection | Shared BPP quote builder/network canonicalizer | Emit outer `code: quote`; nested `type` value is `item` for product lines and `fulfillment` for delivery lines, matching the active Workbench RET10 assertion. |
| Nested delivery quote tag uses forbidden `fulfillment` value | Prepaid, Buyer Cancel, Return, RTO | 14+ | 10+ | Fixed in source; covered by the corrected quote vocabulary | Shared BPP quote builder/network canonicalizer | Use `fulfillment` only as the nested `quote.type` value, not as the outer tag code. |
| Empty callback records after RTO lifecycle sequencing failure | RTO / on_update and on_status | 862 | 863 | Root cause isolated; requires fresh-session confirmation | Lifecycle scheduler and Workbench sequencing | Persist RTO classification from initial select and serialize callbacks through the canonical network boundary. |
| RTO/return callback shape appears undefined after an out-of-sequence or missing callback | RTO / Return | 500+ | 600+ | Likely downstream symptom, not independent missing fields | Callback delivery/state sequencing | Treat empty response cascades as callback delivery/order failures; do not add arbitrary fields to an absent payload. |
| Catalog time range format was incompatible with the active Workbench assertion | Incremental/full catalog | 2 | 2 | Fixed in source; full-catalog live flow reached 100% | Shared catalog normalizer | Emit the active RET10 `HHMM` operating-hours strings `0900` and `2100`. |
| Out-of-stock callback lacks root `error` envelope in the observed run | Out of Stock / on_select | 0 | 6 | Needs fresh live reproduction | Select service OOS detector | Ensure the second/invalid selection is classified as OOS and sends `error.type=DOMAIN-ERROR`, `error.code=40002`, and message. |
| Return fulfillment tags empty or wrong action vocabulary | Return / update settlement trail | 0 | 2 | Source contains action-specific normalization; pending fresh report | Fulfillment tag normalizer | Keep at least one valid action-specific tag and preserve `cancel_request` for cancellation fulfillment. |
| Seller callback key is not present in the pre-production registry | All direct/unsolicited callbacks, currently on_select | Not reported | Live blocker | External registration blocker confirmed by signed v2 lookup (`15040 Subscriber not found`) | ONDC pre-production registry / participant onboarding | Register/subscribe `ondc.fromnear.com` with seller key ID `490ba36f-51d0-49b7-8c00-182892758de9`; do not switch callbacks to the buyer key. |
| Workbench reports registry response unmarshal failure while validating callback Authorization | All callback flows, currently on_select | Not reported | Live blocker symptom | Downstream symptom of missing/unavailable seller registry record | Workbench/registry | Re-run only after seller key registration propagates; live `/lookup` already returns the required array shape. |

## Report Totals

| Report | Tests | Passes | Failures | Suites | Interpretation |
|---|---:|---:|---:|---:|---|
| `seller.html` | 11,284 | 10,241 | 1,043 | 13 | Earlier run; fewer deep lifecycle suites were reached. |
| `seller(1).html` | 14,936 | 13,595 | 1,341 | 14 | More failures, but also more executed/deeper Return coverage; compare normalized ownership before calling it a regression. |

## Ownership Rule

Failures named `retail_bap_*` validate inbound BAP/Workbench request fixtures. They are not fields emitted by this Seller BPP and cannot be corrected by changing BPP callbacks. Failures named `retail_bpp_*` or callback delivery/state failures are Seller-owned unless live evidence shows the Workbench or gateway rejected the request before it reached the service.

Header Validation: OFF is a Workbench session setting only. Production signature verification remains enabled.

## Live Iteration 1 Evidence

- Deployment: Cloud Run revision `fromnear-ondc-backend-00336-ncq` (v15), health endpoint passed.
- Fresh Workbench Seller session: `JFxl8BFnlg05sii2VhU8yLMgbCe-f6Ts`.
- Full catalog flow reached 100% on the immediately preceding fresh session after the catalog-range fix.
- The current cancellation flow passed the previous quote-tag rejection point, then failed at callback authentication with Workbench's registry lookup error.
- Direct signed pre-production registry lookup for both configured key IDs returned `15040 Subscriber not found`; this is not fixable in application code.
- Live `https://ondc.fromnear.com/lookup`, `/api/v1/lookup`, and `/api/v1/ondc/lookup` each return a JSON array with the seller public keys.

## Deployment Verification After Diagnostics Fix

- Cloud Run revision `fromnear-ondc-backend-00337-5j5` is ready and serving 100% traffic.
- `/api/v1/health` returned `healthy` with a healthy database.
- `/api/v1/diagnostics/ondc` confirms the configured BPP private key derives the configured BPP signing public key and payload preflight passes.
- The official pre-production registry still returns HTTP 401 with error `15040 Subscriber not found` for the seller key. This remains an onboarding/registry state blocker and is not resolved by changing JSON payloads or callback code.

## Seller Key ID Correction

- The deployed BPP key ID was corrected from the mistyped `490ba36f...` to `490ba361-51d0-49b7-8c00-182892758de9` in Cloud Run revision `fromnear-ondc-backend-00338-bk5`.
- The buyer key ID remains unchanged.
- Diagnostics still report signature and payload preflight PASS, but the official registry returns `15040 Subscriber not found` for the corrected seller ID. Registration/subscription is still required.
