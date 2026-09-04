from app.protocol import action_payload, search_payload
from fastapi.testclient import TestClient
from app.main import app


def test_search_is_trv10_and_has_route_stops():
    payload = search_payload(start_gps="12.9716,77.5946", end_gps="12.9352,77.6245")
    assert payload["context"]["domain"] == "ONDC:TRV10"
    assert payload["context"]["version"] == "2.0.1"
    assert payload["context"]["location"]["city"]["code"] == "std:080"
    assert [s["type"] for s in payload["message"]["intent"]["fulfillment"]["stops"]] == ["START", "END"]
    assert payload["message"]["intent"]["payment"]["collected_by"] == "BAP"


def test_confirm_preserves_bpp_routing_context():
    payload = action_payload("confirm", transaction_id="txn", bpp_id="bpp.example", bpp_uri="https://bpp.example", message={"order": {"id": "o1"}})
    assert payload["context"]["bpp_id"] == "bpp.example"
    assert payload["message"]["order"]["id"] == "o1"


def test_callback_rejects_wrong_domain_and_acks_valid_callback():
    client = TestClient(app)
    invalid = client.post("/on_search", json={"context": {"domain": "ONDC:RET10", "action": "on_search"}})
    assert invalid.status_code == 400
    valid = client.post("/on_search", json={"context": {"domain": "ONDC:TRV10", "action": "on_search", "transaction_id": "t"}})
    assert valid.json() == {"message": {"ack": {"status": "ACK"}}}
