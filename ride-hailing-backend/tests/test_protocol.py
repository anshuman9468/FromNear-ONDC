from app.protocol import action_payload, search_payload


def test_search_is_trv10_and_has_route_stops():
    payload = search_payload(start_gps="12.9716,77.5946", end_gps="12.9352,77.6245")
    assert payload["context"]["domain"] == "ONDC:TRV10"
    assert [s["type"] for s in payload["message"]["intent"]["fulfillment"]["stops"]] == ["START", "END"]


def test_confirm_preserves_bpp_routing_context():
    payload = action_payload("confirm", transaction_id="txn", bpp_id="bpp.example", bpp_uri="https://bpp.example", message={"order": {"id": "o1"}})
    assert payload["context"]["bpp_id"] == "bpp.example"
    assert payload["message"]["order"]["id"] == "o1"
