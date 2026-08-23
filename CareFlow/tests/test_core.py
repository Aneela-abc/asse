"""
Run with: python -m pytest tests/ -q
Uses a temporary SQLite DB (via DB_PATH env var) so it never touches data/healthcare.db.
"""
import os
import tempfile
from datetime import date, timedelta

import pytest

TMP_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
os.environ['DB_PATH'] = TMP_DB.name

import core  # noqa: E402  (import after DB_PATH is set)


@pytest.fixture(autouse=True, scope='session')
def setup_db():
    core.init_db()
    yield


def next_weekday(target):
    d = date.today()
    while d.weekday() != target:
        d += timedelta(days=1)
    return d


def get_seeded_doctor():
    """The DB is seeded with a few doctors on first init_db(); grab one."""
    docs = core.list_doctors('')
    assert docs, 'expected seeded doctors'
    return docs[0]


def new_patient(tag):
    user, created, overridden = core.login_or_register(f'patient.{tag}@test.dev', 'anything', 'patient')
    assert created is True
    return user


def test_any_password_accepted_and_reused_on_second_login():
    user1, created1, _ = core.login_or_register('open.access@test.dev', 'firstpassword', 'patient')
    assert created1 is True
    user2, created2, overridden2 = core.login_or_register('open.access@test.dev', 'totally-different-password', 'patient')
    assert created2 is False
    assert overridden2 is False
    assert user1['id'] == user2['id']


def test_role_is_sticky_to_existing_account():
    user1, created1, _ = core.login_or_register('sticky.role@test.dev', 'pw', 'doctor')
    assert created1 is True and user1['role'] == 'doctor'
    user2, created2, overridden2 = core.login_or_register('sticky.role@test.dev', 'pw2', 'patient')
    assert created2 is False
    assert overridden2 is True  # requested patient but existing account is doctor
    assert user2['role'] == 'doctor'


def test_new_doctor_gets_default_bookable_profile():
    doc, created, _ = core.login_or_register('fresh.doctor@test.dev', 'pw', 'doctor')
    assert created is True
    d = next_weekday(0)
    slots, _ = core.get_slots(doc['id'], d.isoformat())
    assert slots, 'new doctor should have a default working schedule and open slots'


def test_booking_and_double_booking_prevention():
    patient = new_patient('a')
    doctor = get_seeded_doctor()
    d = next_weekday(0)  # Monday
    slots, _ = core.get_slots(doctor['user_id'], d.isoformat())
    assert slots, 'expected open slots on a working Monday'
    result = core.book_appointment(patient['id'], doctor['user_id'], slots[0], 'severe headache and nausea')
    assert result['status'] == 'CONFIRMED'
    assert result['previsit_summary']['urgency_level'] in ('Low', 'Medium', 'High')

    with pytest.raises(core.BookingConflict):
        core.book_appointment(patient['id'], doctor['user_id'], slots[0], 'trying to double book')


def test_symptoms_required():
    patient = new_patient('b')
    doctor = get_seeded_doctor()
    d = next_weekday(2)  # Wednesday
    slots, _ = core.get_slots(doctor['user_id'], d.isoformat())
    with pytest.raises(core.AppError):
        core.book_appointment(patient['id'], doctor['user_id'], slots[0], '   ')


def test_leave_conflict_cancels_and_notifies():
    patient = new_patient('c')
    doctor = get_seeded_doctor()
    d = next_weekday(3)  # Thursday
    slots, _ = core.get_slots(doctor['user_id'], d.isoformat())
    result = core.book_appointment(patient['id'], doctor['user_id'], slots[1], 'follow-up checkup')
    aid = result['appointment_id']

    affected = core.admin_update_doctor(doctor['user_id'], leave_days=[d.isoformat()])
    assert aid in affected

    appts = {a['id']: a for a in core.list_appointments(patient)}
    assert appts[aid]['status'] == 'CANCELLED'

    notifs = core.list_notifications(patient['id'])
    assert any(n['type'] == 'LEAVE_CONFLICT' for n in notifs)


def test_complete_appointment_generates_summary_and_reminders():
    patient = new_patient('d')
    doctor = get_seeded_doctor()
    d = next_weekday(4)  # Friday
    slots, _ = core.get_slots(doctor['user_id'], d.isoformat())
    result = core.book_appointment(patient['id'], doctor['user_id'], slots[2], 'sore throat and cough')
    summary = core.complete_appointment(result['appointment_id'], doctor['user_id'], 'Viral pharyngitis, rest advised', 'Paracetamol 500mg twice a day')
    assert 'summary' in summary
    assert summary['medication_schedule']


def test_notification_queue_processes():
    processed = core.process_notifications()
    assert processed >= 0  # demo mode always "succeeds"; just ensure it runs without error
