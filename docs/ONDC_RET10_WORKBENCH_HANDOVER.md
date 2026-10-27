# ONDC RET10 Seller/BPP Workbench Handover

Last verified: 2026-10-27
Environment: ONDC pre-production, RET10 Grocery, BPP/Seller, core version 1.2.0
Callback identity: `ondc.fromnear.com` at `https://ondc.fromnear.com/api/v1/ondc`

## Verified result

The fresh Brave Workbench session completed all 14 visible RET10 flows at 100%. The generated Pramaan report showed **16,008 checks passed and 0 failed**. The preview's failed-check filter showed 0. The HTML report is saved locally at:

Newest `Report_*.html` in local `artifacts/` (the filename embeds the Workbench session identifier and is intentionally not published).

The flow request/response logs are retained locally under `artifacts/` and `artifacts/workbench_runs/20261027/`. They are intentionally not included in this public repository because exchanges can contain session identifiers, catalog and order payloads, and participant details.

## Flow inventory

Use a new Workbench session after a deployment or when a clean report is required. Keep the participant set to BPP, `ONDC:RET10`, Grocery, version `1.2.0`, PRE-PRODUCTION, and the registered `ondc.fromnear.com` callback. Run the flows sequentially and save each flow's JSON exchange log before continuing.

The verified session completed these 14 flows:

1. Buyer Delivery
2. Buyer Initiated Return (Full Order and Partial Order)
3. Buyer Side Order Cancellation
4. Catalog Rejection Flow
5. Discovery Flow Incremental Catalog Refresh Pull
6. Merchant Side RTO and Part Order Cancellation Flow
7. Order to Confirm to Fulfillment (Prepaid)
8. Order to Confirm to Fulfillment Prepaid with IGM No Action v-2.0.0
9. Order to Confirm to Fulfillment Prepaid with IGM Rejection v-2.0.0
10. Order to Confirm to Fulfillment Prepaid with IGM v-2.0.0
11. Order to Confirm to Fulfillment Prepaid with IGM 1.0.0
12. Out of Stock (Error Code)
13. Search and Custom Menu (Full Catalog City)
14. Search and Custom Menu (Incremental Push)

For catalog-dependent flows, run Full Catalog City first and retain its valid `on_search` request. If a Workbench restore/paste form requests `on_search`, use the raw request object (`context` and `message.catalog`), not the enclosing exchange-log array (`req`/`res`/`signature`). Check that the provider, items, locations, fulfillment and offers populate before submitting.

For out-of-stock, use the current catalog stock when choosing the first (shortage) quantity, then submit a quantity within stock for the recovery selection. Do not hard-code a quantity that is actually in stock and expect an out-of-stock response. For offer scenarios, select only an offer present in the catalog and include its tags; omit an optional offer when none is selected.

## What fixed the reported errors

The earlier 237-failure report grouped failures into 230 RTO status-selector mismatches, six out-of-stock checks, and one incomplete offer on the incoming Buyer `select`. The repair was based on the official Pramaan RET10 selectors and the captured Workbench exchanges:

- **RTO:** Pramaan selects status events using fulfillment type and status, not the UI step label. The Seller now emits an initial `Delivery`/`Pending` status before the partial cancellation sequence and a final `RTO`/`RTO-Delivered` fulfillment. The final ONDC order state is `Cancelled`, as required by the official RTO assertion. Changes are in `backend/app/ondc/bpp/lifecycle.py` and `backend/app/ondc/bpp/order_builder.py`.
- **Return status vocabulary:** final callback canonicalization preserves the RET10 wire values `Return_Initiated`, `Return_Approved`, `Return_Picked`, and `Return_Delivered` (underscores). The builder and validator must agree on these values.
- **Out-of-stock:** the negative selection is determined from requested quantity versus catalog availability, not from repeated selection by itself. A rejected item is encoded with selected count `0` and the expected item error; a corrected in-stock selection can then succeed. Zero must survive canonicalization.
- **Prepaid/RTO classification:** `bpp_terms` is not a reliable RTO discriminator. Ordinary prepaid orders must not be misclassified as merchant cancellations or race through RTO/delivery callbacks. The normal auto mode waits for the relevant tracking step before final delivery behavior.
- **Incoming Buyer offer:** a Seller cannot repair an invalid `select` request after Workbench has recorded it. The test input must reference the actual catalog offer and its tags, or leave an unselected optional offer out.

The relevant deployed source files are `backend/app/ondc/bpp/lifecycle.py` and `backend/app/ondc/bpp/order_builder.py`. Focused regression coverage is in `backend/app/tests/unit/test_bpp_rto_final_callback.py` and `backend/app/tests/unit/test_report_zun_regressions.py`. The recorded focused local run reported 71 passing tests before the fresh Workbench pass; this handover does not claim that the entire repository test suite was rerun as part of the final report generation.

## Deployment and verification loop

1. Confirm the active Cloud Run service is the pre-production Seller/BPP backend and its configured subscriber identity, callback URL and signing key ID match the active ONDC registration. Keep private keys in Secret Manager; never paste or commit them.
2. Review the exact source diff and focused tests. Prepare the source package from the reviewed code; do not deploy local bytecode, virtual environments, downloaded reports, flow logs, or key files.
3. Deploy to the pre-production service. Wait for the new revision to become ready and confirm it receives the intended traffic. Keep the previous serving revision available for rollback.
4. Open a fresh Workbench BPP/RET10 Grocery pre-production session using `ondc.fromnear.com`. Complete flows sequentially, save exchange logs, and confirm each reaches 100% with the expected ACK/callback sequence.
5. Generate the report only after the flows are complete. Open the preview, read the total/passed/failed counts, and open the failed-check filter. Download and keep the HTML report locally.
6. For any failure, classify it from the exact assertion and exchange: Seller callback/schema, invalid Buyer test input, or Workbench/mock behavior. Change Seller code only for a failure attributable to the Seller. After a code deployment, start a fresh session and repeat the affected checks plus the full applicable flow set before claiming a clean report.

The Oct 27 Cloud Build used the reviewed `lifecycle.py` and `order_builder.py` overlay on the pre-production Seller image. The recorded build completed successfully; the deployed revision was `fromnear-ondc-ret10-seller-preprod-bzz237`, with traffic restored to auto mode. The final fresh report then verified all 14 flows with 16,008/16,008 checks passing. Recheck the live service and registration before any future run; deployment identifiers and registry state can change.

## Source and evidence map

| Purpose | Location |
|---|---|
| RTO/prepaid lifecycle sequence | `backend/app/ondc/bpp/lifecycle.py` |
| RET10 order, fulfillment, quantity and return wire shape | `backend/app/ondc/bpp/order_builder.py` |
| RTO wire status regression | `backend/app/tests/unit/test_bpp_rto_final_callback.py` |
| RTO, prepaid, return and stock regressions | `backend/app/tests/unit/test_report_zun_regressions.py` |
| Fresh final HTML report (local only) | Newest `artifacts/Report_*.html` (filename embeds the private session identifier) |
| Per-flow run exchanges (local only) | `artifacts/workbench_runs/20261027/` and `artifacts/` |
