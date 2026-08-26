# Pramaan Progress

## Current Iteration

- Role: BAP / Buyer NP
- Domain: `ONDC:RET10`
- API version: `1.2.0`
- Subscriber: `ondc.fromnear.com`
- Deployment: Cloud Run `fromnear-ondc-backend`
- Revision: `fromnear-ondc-backend-ret10strict`
- Health: `healthy` with database `healthy`

## Verification

- BAP key ID in deployed revision matches the subscribed portal profile.
- BAP signing public key in deployed revision matches the subscribed portal profile.
- `backend/test_full_ret10_lifecycle_dryrun.py`: 12/12 callbacks passed, 0 errors.
- `backend/test_cancel_flow_dryrun.py`: passed.
- `backend/test_unsolicited_on_update.py`: passed.
- `PYTHONPATH=backend python3 -m pytest -q backend/app/tests/unit backend/app/tests/integration`: 35 passed.
- Same-session Workbench run: Buyer Initiated Return reached 100%.
- Same-session Workbench run: Buyer Side Order Cancellation reached 100%.
- Same-session Workbench run: Discovery Flow incremental catalog refresh pull reached 100%.
- Incremental catalog refresh runner corrected so its second search sends `catalog_inc.mode=end`.
- Same-session Workbench run: Merchant Side RTO and Part Order Cancellation reached 100%.
- Same-session Workbench run: Order to confirm to fulfillment (Prepaid) reached 100%.
- Same-session Workbench run: Order to confirm to fulfillment Prepaid with IGM 1.0.0 reached 100%.
- Same-session Workbench run: Out of Stock reached 100%.
- Same-session Workbench run: Search and Custom Menu (Full Catalog City) reached 100%.
- Same-session Workbench run: Search and Custom Menu (Incremental Push) reached 100%.

## Latest Result

- All nine BAP scenarios in session `S-92ZeXqjELGywIP6TUpXVTAiwX597sR` reached 100% in Workbench.
