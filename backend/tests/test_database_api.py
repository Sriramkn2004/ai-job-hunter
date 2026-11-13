from fastapi.testclient import TestClient

from app.main import app


def test_job_is_persisted_between_requests():
    client = TestClient(app)
    source_job_id = "test:db-persistence-check"
    payload = {
        "source": "test",
        "source_job_id": source_job_id,
        "company": "Acme",
        "title": "Python Developer",
        "description": "Build Python backend services",
        "location": "Bangalore",
        "country": "India",
        "salary_min": 1800000,
        "salary_currency": "INR",
        "salary_period": "year",
    }

    with client:
        created = client.post("/api/v1/jobs", json=payload)
        assert created.status_code == 200
        assert created.json()["screening"]["status"] == "matched"

        # A second HTTP request reads the same record from persistent storage.
        listed = client.get("/api/v1/jobs?status=matched")
        assert listed.status_code == 200
        assert any(job["source_job_id"] == source_job_id for job in listed.json())
