"""
Integration tests for CareFlow FastAPI Backend REST API.
Uses TestClient with a temporary SQLite database.
"""
import os
import tempfile
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

TMP_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
os.environ['DB_PATH'] = TMP_DB.name

from database.db import init_database
from backend.main import app


@pytest.fixture(autouse=True, scope='session')
def setup_api_db():
    init_database()
    yield


client = TestClient(app)


def next_weekday(target):
    d = date.today()
    while d.weekday() != target:
        d += timedelta(days=1)
    return d


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_auth_login_or_register():
    # Register new patient
    res = client.post(
        "/api/auth/login-or-register",
        json={"email": "rest.patient@test.dev", "password": "pass", "role": "patient", "name": "REST Patient"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["created"] is True
    assert data["user"]["email"] == "rest.patient@test.dev"
    assert data["user"]["role"] == "patient"

    # Re-login with different password
    res2 = client.post(
        "/api/auth/login-or-register",
        json={"email": "rest.patient@test.dev", "password": "other-pass", "role": "patient"}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["created"] is False
    assert data2["user"]["id"] == data["user"]["id"]


def test_doctors_and_slots():
    res = client.get("/api/doctors")
    assert res.status_code == 200
    doctors = res.json()
    assert len(doctors) >= 3

    doc_id = doctors[0]["user_id"]
    mon = next_weekday(0).isoformat()
    res_slots = client.get(f"/api/doctors/{doc_id}/slots?date={mon}")
    assert res_slots.status_code == 200
    slots_data = res_slots.json()
    assert "slots" in slots_data
    assert len(slots_data["slots"]) > 0


def test_book_appointment_and_conflict_via_api():
    # Setup patient & doctor
    res_pat = client.post(
        "/api/auth/login-or-register",
        json={"email": "booking.patient@test.dev", "password": "pass", "role": "patient"}
    )
    pat_id = res_pat.json()["user"]["id"]

    doctors = client.get("/api/doctors").json()
    doc_id = doctors[0]["user_id"]
    mon = next_weekday(0).isoformat()
    slots = client.get(f"/api/doctors/{doc_id}/slots?date={mon}").json()["slots"]
    slot_to_book = slots[0]

    # Book slot
    res_book = client.post(
        "/api/appointments/book",
        json={
            "patient_id": pat_id,
            "doctor_id": doc_id,
            "start_at": slot_to_book,
            "symptoms": "Fever and sore throat"
        }
    )
    assert res_book.status_code == 201
    booking_data = res_book.json()
    assert booking_data["status"] == "CONFIRMED"
    assert "previsit_summary" in booking_data

    # Attempt duplicate booking on same slot -> Should return 409 Conflict
    res_conflict = client.post(
        "/api/appointments/book",
        json={
            "patient_id": pat_id,
            "doctor_id": doc_id,
            "start_at": slot_to_book,
            "symptoms": "Another patient booking same slot"
        }
    )
    assert res_conflict.status_code == 409
    assert "booked" in res_conflict.json()["detail"].lower()


def test_dashboard_and_notifications_via_api():
    res_stats = client.get("/api/dashboard/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert "confirmed" in stats
    assert "doctors" in stats

    res_proc = client.post("/api/notifications/process")
    assert res_proc.status_code == 200
    assert "processed_notifications" in res_proc.json()
