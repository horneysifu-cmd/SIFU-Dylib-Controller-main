import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.sqlite3")
    monkeypatch.setattr(main, "ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setattr(main, "_rate_buckets", {})
    with TestClient(main.app) as test_client:
        yield test_client


def admin_headers():
    return {"Authorization": "Bearer test-admin-token"}


def create_license(client, **overrides):
    payload = {"prefix": "SIFU", "duration_days": 30, "device_limit": 1}
    payload.update(overrides)
    response = client.post(
        "/api/admin/licenses", json=payload, headers=admin_headers()
    )
    assert response.status_code == 200
    return response.json()


def test_health_is_available(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_admin_routes_require_token(client):
    response = client.get("/api/admin/licenses")
    assert response.status_code == 401


def test_license_can_activate_and_validate(client):
    license_data = create_license(client)
    activation = client.post(
        "/api/license/activate",
        json={
            "license_key": license_data["license_key"],
            "device_ref": "test-device-reference-001",
        },
    )
    assert activation.status_code == 200
    assert activation.json()["valid"] is True

    validation = client.post(
        "/api/license/validate",
        json={
            "license_key": license_data["license_key"],
            "device_ref": "test-device-reference-001",
        },
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is True


def test_device_limit_is_enforced(client):
    license_data = create_license(client, device_limit=1)
    first = client.post(
        "/api/license/activate",
        json={
            "license_key": license_data["license_key"],
            "device_ref": "test-device-reference-001",
        },
    )
    second = client.post(
        "/api/license/activate",
        json={
            "license_key": license_data["license_key"],
            "device_ref": "test-device-reference-002",
        },
    )
    assert first.status_code == 200
    assert second.status_code == 403
    assert second.json()["detail"] == "Device limit reached."


def test_blocked_device_cannot_validate(client):
    license_data = create_license(client)
    activation = client.post(
        "/api/license/activate",
        json={
            "license_key": license_data["license_key"],
            "device_ref": "test-device-reference-001",
        },
    )
    device_id = activation.json()["device_id"]

    blocked = client.patch(
        f"/api/admin/devices/{device_id}",
        json={"status": "blocked"},
        headers=admin_headers(),
    )
    assert blocked.status_code == 200

    validation = client.post(
        "/api/license/validate",
        json={
            "license_key": license_data["license_key"],
            "device_ref": "test-device-reference-001",
        },
    )
    assert validation.status_code == 403


def test_banned_license_cannot_activate(client):
    license_data = create_license(client)
    banned = client.patch(
        f"/api/admin/licenses/{license_data['license_id']}",
        json={"status": "banned"},
        headers=admin_headers(),
    )
    assert banned.status_code == 200

    activation = client.post(
        "/api/license/activate",
        json={
            "license_key": license_data["license_key"],
            "device_ref": "test-device-reference-001",
        },
    )
    assert activation.status_code == 403
