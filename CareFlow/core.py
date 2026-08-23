"""
CareFlow Core compatibility wrapper.
Delegates to the database and backend services layer while preserving all existing function signatures.
"""
from database.db import get_db, init_database
from backend.services import (
    BookingConflict, AppError,
    now_iso as now, uid, hash_pw, add_user, user_by_id, doctor_profile,
    register_patient, login, login_or_register,
    list_doctors, get_slots, slot_ok, iso_parse,
    book_appointment, list_appointments, cancel_appointment, complete_appointment,
    admin_create_doctor, admin_update_doctor,
    list_notifications, process_notifications,
    create_medication_reminders, process_medication_reminders, run_background_jobs_if_due,
    google_configured, google_auth_url, google_token_exchange, google_api,
    save_google_token, calendar_create_for_user, sync_calendar_booking, ics_for_appointment,
    dashboard_stats, previsit, postvisit, llm
)

# Alias for backwards compatibility
init_db = init_database
db = get_db
