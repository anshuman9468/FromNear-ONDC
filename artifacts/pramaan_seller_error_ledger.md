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

## Fresh-session evidence: `k4kD53-rIYTq0zTeyC7AtY_OF9WLDg5y`

| Root Cause | Flow/API | Old Count | New Count | Status | Code Owner | Fix |
|---|---|---:|---:|---|---|---|
| Workbench mock update request omits `subscriberID` before delivery | Buyer Return / `update` and Merchant RTO / `update` | Not previously isolated | 2 blocked mock steps | External Workbench blocker | Workbench mock generator | No Seller-side patch is valid because Cloud Run received no `/update`; rerun after Workbench emits a valid request. |
| Seller callback payloads fail to reach downstream validations | Catalog, cancellation, prepaid, OOS, incremental, RTO callbacks | Repeated historically | 0 in fresh green flows | Fixed and live-verified | Shared Seller builders and callback boundary | Current revision returned HTTP 200/ACK for all executed Seller callbacks; seven independent flows reached 100%. |
| Stale out-of-sequence records remain in a reused flow card | Merchant RTO | 5 stale records | 5 retained UI records | Session-history artifact | Workbench session UI | Do not count retained prior-attempt cards as new BPP callbacks; certify with a clean new session after the mock blocker is resolved. |

Current session outcome: seven flows completed at 100%; Return and RTO are externally blocked at malformed Workbench mock `update` requests. No new Seller-owned schema failure was observed in this run.

## Final deployment verification

- Commit `8e29a26` is pushed to `origin/main`.
- Cloud Run revision `fromnear-ondc-backend-00355-qn5` serves 100% traffic.
- Health endpoint is green and the live diagnostics report Seller signature and payload preflight PASS.
- The current Workbench session predates this revision, but the deployed source is the same verified implementation. A clean final Workbench report cannot be claimed while Workbench itself rejects Return/RTO mock updates with `subscriberID not set` before BPP delivery.

## Contract audit and diagnostics correction

The active contract source is `ONDC - API Contract for Retail - 1.2.0`. Relevant conclusions:

- `subscriber_id` and `ukId` are participant registry identity fields used in `keyId` and `/lookup`; they are not populated by payment or settlement fields.
- `@ondc/org/settlement_details` is conditional payment data. When `settlement_type` is `upi`, `upi_address` is required; this is independent of the HTTP/request `subscriberID` that Workbench reported missing.
- `/update` is the buyer-side part return/cancel request and `/on_update` is the Seller response or Seller-initiated part cancellation callback.

The repository diagnostics had a role consistency bug: lookup used the active BPP credentials, but registry cross-validation and the gateway probe used the base Buyer credentials. This was corrected and covered by the diagnostics test. It does not alter live protocol signing or disable production verification.

## Iteration 8 evidence

| Root Cause | Flow/API | Old Count | New Count | Status | Code Owner | Fix |
|---|---|---:|---:|---|---|---|
| Diagnostics compared BPP registry records with BAP key ID/public key | Pre-production registry diagnostics | 1 misleading result | 0 in local regression | Fixed and live-verified | Diagnostics utility | Compare `ukId`, signing key, and encryption key against the active BPP credential set. |
| Diagnostics gateway probe signed with BAP credentials while BPP mode was active | Gateway diagnostics | 1 misleading probe | 0 in local regression | Fixed and live-verified | Diagnostics utility | Sign with the same active credential set selected for registry lookup. |
| Verification script displayed obsolete Buyer/`.app` fallback values | `verify_preprod_registration.py` | 1 misleading operator instruction | 0 in source | Fixed | Verification tooling | Report active BPP credentials and `ONDC_SUBSCRIBER_URI`. |

No new Seller payload or callback schema failure was introduced. The Workbench `subscriberID not set` blocker remains external and occurs before the Seller endpoint.

## Iteration 9 evidence

The live diagnostics probe after revision `00356-kwx` exposed two contract-shape errors in the diagnostics utility itself:

| Root Cause | Flow/API | Old Count | New Count | Status | Code Owner | Fix |
|---|---|---:|---:|---|---|---|
| Registry lookup used `unique_key_id` instead of contract `ukId` and omitted country/city selectors | Registry diagnostics | 1 | 0 in source tests | Fixed and live-verified | Diagnostics utility | Send `subscriber_id`, `domain`, `ukId`, `country`, `city`, and `type`. |
| Gateway diagnostic search intent omitted payment | Gateway diagnostics | 1 | 0 in source tests | Fixed and live-verified | Diagnostics utility | Include buyer-app finder-fee payment fields required by the active search contract. |

These were diagnostic probe defects, not Seller callback payload defects. The correction makes live diagnostics useful for distinguishing registry onboarding failures from malformed local probes.

## Iteration 9 deployment evidence

- Cloud Run revision `fromnear-ondc-backend-00357-tsd` is ready and serves 100% traffic.
- Health endpoint is green.
- Live diagnostics: `configuration=PASS`, `registry=PASS`, `gateway=PASS`, `signature=PASS`, `subscriber=PASS`, `callback=PASS`, `payload=PASS`.
- The registry returned `SUBSCRIBED` for `ondc.fromnear.com` with Seller key ID `490ba361-51d0-49b7-8c00-182892758de9`, the configured Seller signing/encryption keys, and callback `https://ondc.fromnear.com/api/v1/ondc`.

This closes the registry and diagnostics-tooling blockers observed in earlier iterations. It does not replace final Workbench evidence: a new Seller Workbench session must still execute the Return/RTO update branches with a valid mock request before a zero-failure Pramaan result can be declared.

## Iteration 5: Contract-aligned breakup tag boundary

- Contract source reviewed: [ONDC API contract](https://docs.google.com/document/d/1brvcltG_DagZ3kGr1ZZQk4hG4tze3zvcxmGV4NMTzr8/edit), including the RET10 1.2.0 examples.
- Root cause: product breakup lines were normalized as fulfillment-level `quote` tags. RET10 validates product lines with the item taxonomy (`type`, `parent`, `child`, `origin`, `veg_nonveg`, `custom_group`), while fulfillment fee lines use `quote` metadata.
- Fix: both the canonical BPP quote builder and final outbound network canonicalizer now select tags from `@ondc/org/title_type`; the validator applies the matching vocabulary. The legacy default constant was corrected as a defensive guard.
- Verification: `51 passed`; all 12 local lifecycle callbacks passed the RET10 dry-run validator.
- Remote certification: pending a fresh Workbench Seller session. Existing sessions are not valid final evidence because they contain stale branch state and the seller key registry blocker.

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

## Iteration 10: live Workbench evidence

| Root Cause | Flow/API | Old Count | New Count | Status | Code Owner | Fix |
|---|---|---:|---:|---|---|---|
| Workbench persisted a stalled second mock `select` as the active flow | Out of Stock | N/A | 1 blocked step | External Workbench blocker | Workbench scenario runner | No Seller request was received after the first ACK; reset with a fresh session before final certification. |
| Workbench mock generator references undefined `defaultPayload` | Buyer Return `/update` | N/A | 1 generation failure | External Workbench blocker | Workbench mock generator | No Seller `/update` request reached the service; do not patch Seller payload code for this error. |
| RTO scenario has no marker distinguishing it from normal prepaid confirm | Merchant RTO `/on_update` | Persistent in earlier sessions | 1 blocked branch | Requires scenario input | Workbench scenario + Seller flow mode | Keep `auto` mode; do not globally force RTO because the same deployment must pass normal prepaid. |
| HTTP gzip content was parsed as JSON bytes | BAP callback ingress | Repeated in earlier live logs | 0 after deployment | Fixed and live-verified | `backend/app/api/endpoints/ondc.py` | Decode gzip/deflate before signature validation and JSON parsing; add integration regression test. |

Current session `Ed2abHsNVZSDuPHlLc898KPCWTxCEblX`: cancellation, discovery pull, IGM prepaid, and standard prepaid completed at 100% with ACKs. Return and RTO were blocked by Workbench/mock sequencing; Out of Stock blocked before its second mock request; catalog flows were not executed because the session remained active on that step.

## Iteration 12: supplied `seller(1).html`

| Root Cause | Flow/API | Old Count | New Count | Status | Code Owner | Fix |
|---|---|---:|---:|---|---|---|
| Product breakup lines used the fulfillment `quote` tag vocabulary | confirm/on_confirm and downstream order callbacks | Repeated | Repeated in 636-failure report | Fixed in source and deployed | Shared quote builder/network canonicalizer | Emit `type`/`item` for product lines; keep `quote`/`fulfillment` only for delivery lines. |
| BPP identity compared against Workbench BAP identity | select and callback context checks | Repeated | Repeated | Not a Seller defect | Workbench/BAP fixture | Keep registered Seller `bpp_id=ondc.fromnear.com`; do not replace it with `workbench.ondc.tech`. |
| Missing callback structures in stale/incomplete RTO and return branches | RTO/return on_update/on_status | Repeated | Clustered in report | Requires fresh execution evidence | Workbench state/mock sequencing | Re-test from a clean session after valid mock requests reach the Seller endpoint. |

Current supplied report totals: 15,809 validations; 15,173 passed; 636 failed; 30 optional failures. It predates revision `fromnear-ondc-backend-00362-8s5`; it is not evidence of the deployed tag fix.

## Iteration 13: offer tag shape

| Root Cause | Flow/API | Old Count | New Count | Status | Code Owner | Fix |
|---|---|---:|---:|---|---|---|
| Offer `O1` was defined without the `tags` array used by Workbench when it builds the RTO `select` request | RTO and Part Cancellation / `select` request verification | Persistent across supplied reports | 1 normalized failure pattern | Fixed in source and deployed in `fromnear-ondc-backend-00368-qgp`; requires a fresh Workbench session for remote confirmation | Catalog fixture and shared catalog normalizer | Add `tags: []` to the source offer and assert the normalizer always emits an array for every offer. |

Local verification: full backend test suite `58 passed`. The current supplied report remains historical evidence; it must not be edited or treated as proof of the new deployment.

## Iteration 14: empty update fulfillment array

| Root Cause | Flow/API | Old Count | New Count | Status | Code Owner | Fix |
|---|---|---:|---:|---|---|---|
| Sparse BAP update orders could preserve `fulfillments: []`; the update builder also skipped its fallback for `update_target=fulfillment` | Update Settlement Trail / BAP `/update` request verification | 1 visible normalized failure (repeated across report runs) | 0 in local regression | Fixed in source; deployment and fresh Workbench confirmation pending | `UpdateService` and `UpdateRequestBuilder` | Always synthesize one normalized fulfillment (`F1`) when the source order has no fulfillments; use `Return` for fulfillment-targeted updates and preserve valid tags. |

Verification: full backend suite `60 passed`; targeted update/protocol and BPP callback suite `32 passed`. This fixes the application-generated BAP update path. If the same failure appears in a Seller Workbench report before any `/update` request reaches this service, the malformed mock payload is Workbench-side and requires a fresh flow/input reset rather than another BPP response change.

## Iteration 15: canonical select item identity

| Root Cause | Flow/API | Old Count | New Count | Status | Code Owner | Fix |
|---|---|---:|---:|---|---|---|
| The search-result/cache path dropped catalog `location_id`, `parent_item_id`, and `fulfillment_id`; the shared request builder then received only `{id, location}` or `{id, quantity}` and could not serialize canonical RET10 item references | `/on_search` -> `/select` -> `/init`, all selected items | Repeated for item 0 and item 1 in supplied Workbench reports | 0 in local regression | Fixed in source; fresh Workbench confirmation pending | Search cache mapping, select service, shared item serializer | Carry canonical identity from the raw `on_search` catalog, enrich every selected item generically, serialize `location_id` only, and reject unknown/missing catalog identity instead of inventing a parent ID. |
| `on_select` callback persistence replaced the original select request, erasing identity when the callback omitted item reference fields | `/on_select` -> `/init` | Newly exposed by strict resolver | 0 in local regression | Fixed in source; fresh Workbench confirmation pending | Select lifecycle state persistence | Merge callback item fields over the original selected items by item ID, preserving canonical references for subsequent lifecycle requests. |

Local verification for this iteration: `63 passed` in `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest app/tests -q`; focused select/lifecycle verification: `40 passed`.

No Workbench report was generated in this code-only iteration, so a zero-error remote certification result is not claimed here. The final proof still requires a new Seller RET10 Grocery session against the deployed revision.

## Iteration 16: deployment verification

- Commit: `e7c79e8` (`fix(ondc): correct select item location and parent identifiers`).
- Deployment: Cloud Run revision `fromnear-ondc-backend-00371-wsd`, serving 100% traffic for `fromnear-ondc-backend` in `us-central1`.
- Runtime checks: `/api/v1/health` returned healthy; non-secret ONDC diagnostics reported `configuration`, `registry`, `gateway`, `signature`, `subscriber`, `callback`, and `payload` as `PASS`.
- Environment safety: deployment supplied no environment override flags; existing BAP/BPP environment variables and secrets were retained.
- Certification status: no new Workbench report was generated in this iteration. A fresh Seller RET10 Grocery session must still validate the wire payload and all applicable flows.

## Iteration 17: select item tag retention

| Root Cause | Flow/API | Old Count | New Count | Status | Code Owner | Fix |
|---|---|---:|---:|---|---|---|
| The shared BAP item serializer normalized catalog identity but discarded the catalog item's explicit `tags` array and substituted a synthetic `type` tag. | `/select`, and reused `/init`, `/confirm`, and `/update` request item serialization | Repeated `items[*].tags should be an array` failures in historical Workbench reports | 0 in local regression; remote count pending | Fixed in source and deployed; fresh Workbench confirmation pending | `backend/app/ondc/protocol/builders.py` | Preserve the authoritative `catalog_item.tags` array, including an explicit empty array; otherwise preserve caller tags or emit an honest empty array. Keep all prior catalog-derived identity fields. |
| The BPP catalog normalizer reused one mutable fallback tag list for items without source tags. | BPP `/on_search` catalog normalization | Not separately counted | 0 in local regression | Fixed | `backend/app/ondc/bpp/services/search.py` | Deep-copy the existing `np_fees` fallback per item so item metadata cannot leak across catalog records. |

Evidence:
- Checked-in catalog items `I1` and `I2` declare `tags: []`; the existing BPP normalizer intentionally supplies the valid RET10 `np_fees` tag before `on_search` is sent.
- The representative select preflight now emits both items with `location_id=L1`, `parent_item_id=V1`, `fulfillment_id=F1`, and the normalized `np_fees` tag array. No item emits the legacy `location` field.
- Focused suite: `36 passed`. Full backend suite: `64 passed`.
- Cloud Run revision `fromnear-ondc-backend-00372-vqj` is ready and serves 100% traffic. Health and ONDC diagnostics pass.
- No fresh Workbench report was generated by this iteration; the remote Seller RET10 result remains pending and must be verified with a new session.

## Iteration 18: final-egress forensic fix

| Root Cause | Flow/API | Old Count | New Count | Status | Code Owner | Fix |
|---|---|---:|---:|---|---|---|
| Final network canonicalizer unconditionally rewrote every quote-breakup item tag to outer code `quote`, regardless of callback action or breakup line type | Buyer cancellation and RTO/part cancellation / `on_cancel` | Present in fresh Workbench evidence for both product lines | 0 in final-wire regression tests | Fixed in source; fresh Workbench confirmation pending | `backend/app/ondc/bpp/client.py`, `backend/app/ondc/bpp/order_builder.py` | Removed the unconditional overwrite and made the shared quote builder action-aware: post-order product lines use `type`/`item`; delivery lines use an empty tag array. Pre-order quote vocabulary remains unchanged. |
| Delayed unsolicited lifecycle callbacks used the sparse callback/request context and `store_order` replaced the originating context | `on_status`, `on_update`, `on_cancel` after confirm/update | Present in fresh Workbench evidence | 0 in wire/context regression tests | Fixed in source; fresh Workbench confirmation pending | `backend/app/ondc/bpp/state_machine.py`, `backend/app/ondc/bpp/lifecycle.py` | Merge non-empty context fields into durable state and recover the originating context before rebuilding, validating, signing, and sending delayed callbacks. |
| Production egress was not observable with revision provenance or final tag shape | All post-order callback egress | Not independently countable | Diagnostic logging added | Fixed in source; deployment verification pending | `backend/app/ondc/bpp/client.py`, `backend/app/api/endpoints/ondc_bpp.py` | Log non-secret service/revision/build identity and final breakup item tags immediately before `httpx.AsyncClient.post`; never log Authorization or keys. |

For the full machine-readable evidence and source trace, see `artifacts/pramaan_seller_forensic_2026-09-02.json`.
