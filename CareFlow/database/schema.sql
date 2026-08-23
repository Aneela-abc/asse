-- ============================================================================
-- CareFlow Relational Database Schema
-- Database: SQLite (Compatible with PostgreSQL / MySQL table structures)
-- ============================================================================

-- 1. Users Table (Patient, Doctor, Admin identity)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('patient', 'doctor', 'admin')),
    created_at TEXT NOT NULL
);

-- 2. Doctors Table (Doctor profiles, working hours, and leave schedules)
CREATE TABLE IF NOT EXISTS doctors (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    specialization TEXT NOT NULL,
    working_days TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    slot_minutes INTEGER NOT NULL DEFAULT 30,
    leave_days TEXT NOT NULL DEFAULT '[]'
);

-- 3. Appointments Table (State machine: HELD -> CONFIRMED -> COMPLETED / CANCELLED / NO_SHOW)
CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES users(id),
    doctor_id TEXT NOT NULL REFERENCES users(id),
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('HELD', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW')),
    hold_expires_at TEXT,
    symptoms TEXT NOT NULL DEFAULT '',
    previsit_summary TEXT,
    postvisit_summary TEXT,
    doctor_notes TEXT,
    prescription TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Double-booking prevention index: Ensures no overlapping active bookings for the same doctor and slot
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_slot 
ON appointments(doctor_id, start_at) 
WHERE status IN ('HELD', 'CONFIRMED', 'COMPLETED');

-- 4. Notifications Table (Durable email/message queue with retry logic)
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    appointment_id TEXT,
    user_id TEXT NOT NULL REFERENCES users(id),
    type TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('QUEUED', 'SENT', 'FAILED')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    payload TEXT NOT NULL,
    next_attempt_at TEXT,
    created_at TEXT NOT NULL
);

-- 5. Calendar Events Table (External sync mapping: Google Calendar, .ics)
CREATE TABLE IF NOT EXISTS calendar_events (
    id TEXT PRIMARY KEY,
    appointment_id TEXT NOT NULL UNIQUE REFERENCES appointments(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    external_event_id TEXT,
    status TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 6. Google Tokens Table (OAuth 2.0 per-user access and refresh tokens)
CREATE TABLE IF NOT EXISTS google_tokens (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at INTEGER NOT NULL,
    scope TEXT,
    updated_at TEXT NOT NULL
);

-- 7. Medication Reminders Table (Derived from prescription text)
CREATE TABLE IF NOT EXISTS medication_reminders (
    id TEXT PRIMARY KEY,
    appointment_id TEXT NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES users(id),
    medication_text TEXT NOT NULL,
    frequency_hours INTEGER NOT NULL,
    next_run_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- 8. Job State Table (Coordination of scheduled queue jobs)
CREATE TABLE IF NOT EXISTS job_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
