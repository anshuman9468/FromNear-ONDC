from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.repositories.user import user_repo


def test_register_user(client: TestClient) -> None:
    """Test registering a new user."""
    payload = {
        "email": "testuser@example.com",
        "password": "testpassword",
        "full_name": "Test User",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert data["email"] == "testuser@example.com"
    assert data["full_name"] == "Test User"
    assert "id" in data


def test_register_duplicate_user(client: TestClient) -> None:
    """Test registering a user that already exists."""
    payload = {
        "email": "duplicate@example.com",
        "password": "testpassword",
        "full_name": "Duplicate User",
    }
    response1 = client.post("/api/v1/auth/register", json=payload)
    assert response1.status_code == 201
    
    response2 = client.post("/api/v1/auth/register", json=payload)
    assert response2.status_code == 400
    assert "exists" in response2.json()["detail"]


def test_login_user(client: TestClient) -> None:
    """Test logging in with correct and incorrect credentials."""
    # Register the user first
    payload = {
        "email": "loginuser@example.com",
        "password": "correctpassword",
        "full_name": "Login User",
    }
    client.post("/api/v1/auth/register", json=payload)
    
    # Login - Incorrect credentials
    login_data_wrong = {"username": "loginuser@example.com", "password": "wrongpassword"}
    response_wrong = client.post("/api/v1/auth/login", data=login_data_wrong)
    assert response_wrong.status_code == 400
    
    # Login - Correct credentials
    login_data_correct = {"username": "loginuser@example.com", "password": "correctpassword"}
    response_correct = client.post("/api/v1/auth/login", data=login_data_correct)
    assert response_correct.status_code == 200
    
    token_data = response_correct.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


def test_get_me(client: TestClient) -> None:
    """Test getting current user profile."""
    # Register and login
    email = "meuser@example.com"
    password = "mepassword"
    payload = {
        "email": email,
        "password": password,
        "full_name": "Me User",
    }
    client.post("/api/v1/auth/register", json=payload)
    
    login_data = {"username": email, "password": password}
    login_response = client.post("/api/v1/auth/login", data=login_data)
    token = login_response.json()["access_token"]
    
    # Fetch profile with auth header
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["email"] == email
    assert data["full_name"] == "Me User"
    
    # Fetch profile with invalid auth header
    headers_invalid = {"Authorization": "Bearer invalidtoken"}
    response_invalid = client.get("/api/v1/auth/me", headers=headers_invalid)
    assert response_invalid.status_code == 401
