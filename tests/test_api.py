import sys
import os
import uuid
import pytest
from fastapi.testclient import TestClient

# Add backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from main import app

client = TestClient(app)

@pytest.fixture
def auth_headers():
    """Helper fixture to register a temporary user and get auth headers."""
    email = f"test_{uuid.uuid4().hex}@example.com"
    password = "testpassword123"
    full_name = "Test Runner"

    # Register user
    reg_resp = client.post(
        "/auth/register",
        params={"email": email, "password": password, "full_name": full_name}
    )
    assert reg_resp.status_code == 200

    # Log in
    login_resp = client.post(
        "/auth/login",
        data={"username": email, "password": password}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_bulk_scan(auth_headers):
    """Test that scan-bulk works correctly and processes concurrent requests without session sharing issues."""
    # Find test receipt path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    image_path = os.path.join(project_root, "test_receipt.jpg")
    
    if not os.path.exists(image_path):
        pytest.skip("test_receipt.jpg not found in project root")

    with open(image_path, "rb") as f:
        file_bytes = f.read()

    # Upload two copies of the receipt concurrently in a bulk scan request
    files = [
        ("files", ("receipt_1.jpg", file_bytes, "image/jpeg")),
        ("files", ("receipt_2.jpg", file_bytes, "image/jpeg")),
    ]

    response = client.post(
        "/expenses/scan-bulk",
        headers=auth_headers,
        files=files
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total_files"] == 2
    assert "results" in data
    assert len(data["results"]) == 2
