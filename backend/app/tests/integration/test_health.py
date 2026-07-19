from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Test that the health check endpoint works and database is healthy."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "healthy"
    assert "ONDC" in data["service"]
