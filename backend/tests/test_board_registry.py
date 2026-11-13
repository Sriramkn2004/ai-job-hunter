from fastapi.testclient import TestClient

from app.main import app


def test_board_registry_create_list_and_delete():
    client = TestClient(app)
    payload = {
        "provider": "greenhouse",
        "slug": "ai-job-hunter-registry-test",
        "company_name": "Registry Test Company",
    }

    with client:
        created = client.post("/api/v1/sources/boards", json=payload)
        assert created.status_code == 200
        body = created.json()
        assert body["saved"] is True
        assert body["created"] is True
        board_id = body["id"]

        duplicate = client.post("/api/v1/sources/boards", json=payload)
        assert duplicate.status_code == 200
        assert duplicate.json()["created"] is False
        assert duplicate.json()["id"] == board_id

        listed = client.get("/api/v1/sources/boards")
        assert listed.status_code == 200
        assert any(row["id"] == board_id for row in listed.json())

        deleted = client.delete(f"/api/v1/sources/boards/{board_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"deleted": True, "id": board_id}

        missing = client.delete(f"/api/v1/sources/boards/{board_id}")
        assert missing.status_code == 404
