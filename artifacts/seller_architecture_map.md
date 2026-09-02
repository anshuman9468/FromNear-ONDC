# Seller RET10 Architecture Map

## Runtime Path

```text
ONDC BAP/Workbench request
  -> backend/app/api/endpoints/ondc_bpp.py route
  -> synchronous ACK response
  -> async Seller service handler
  -> shared state_machine.py transaction store
  -> shared item_identity.py + order_builder.py/catalog normalizer
  -> bpp/client.py canonicalization + signature
  -> BAP callback URL (/on_search, /on_select, /on_init, ...)
```

## Action Mapping

| Workbench action | Route/controller | Service | Shared builders/state | Outbound callback |
|---|---|---|---|---|
| `search` | `ondc_bpp.py` search handler | `services/search.py` | catalog normalizer, search counters | `on_search` |
| `select` | `ondc_bpp.py` select handler / `order.py` BAP route | `bpp/services/select.py` / `services/select.py` | canonical item identity resolver, order builder, OOS/RTO tracker | `on_select` or domain error callback |
| `init` | `ondc_bpp.py` init handler | `services/init.py` | order/quote/payment builder, tracker | `on_init` |
| `confirm` | `ondc_bpp.py` confirm handler | `services/confirm.py` | order/quote/payment builder, lifecycle scheduler | `on_confirm` |
| `status` | `ondc_bpp.py` status handler | `services/status.py` | status state machine, canonical order | `on_status` |
| `track` | `ondc_bpp.py` track handler | `services/track.py` | tracking payload, tracker | `on_track` |
| `update` | `ondc_bpp.py` update handler | `services/update.py` | return/RTO state machine, canonical order | `on_update` |
| `cancel` | `ondc_bpp.py` cancel handler | `services/cancel.py` | cancellation state, canonical order | `on_cancel` |
| `issue` | `ondc_bpp.py` issue handler | `services/issue.py` | issue/resolution payload builder | `on_issue` |
| `support`/`rating` | protocol/service handlers where enabled | support/rating services | request parsers | corresponding callback if enabled |

## Cross-Cutting Invariants

- `order_builder.py` is the final source for BPP order callbacks and supplies IDs, items, quote breakup, fulfillment locations, billing, payment settlements, tags, and timestamps.
- `protocol/item_identity.py` is the shared identity boundary. It accepts only catalog-backed `id`, `location_id`, `parent_item_id`, and `fulfillment_id` references and never invents a parent ID.
- `services/search.py` retains raw `on_search` catalog data and enriches every `/select` item from that transaction/provider catalog before `SelectRequestBuilder` serializes it.
- `services/select.py` merges sparse `on_select` callbacks over the original select request so later `/init` and `/confirm` requests cannot lose catalog references.
- `client.py` is the final network boundary. It canonicalizes payloads before signing and posting, and sets the registered Seller context (`ondc.fromnear.com`).
- `state_machine.py` owns per-transaction selection counts, lifecycle state, callback deduplication, and persistent RTO classification.
- BAP request builders under `backend/app/ondc/protocol/builders.py` are separate from BPP callback builders. A BAP fixture failure must not be “fixed” by weakening Seller callback logic.
- The callback sender must preserve direct callback message correlation and serialize unsolicited lifecycle callbacks in protocol order.
