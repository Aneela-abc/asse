## 🚀 Live Application

[Click here to open the Healthcare Appointment Manager](https://healthcare-appointment-manager-3-84ci.onrender.com/)

# CareFlow — Healthcare Appointment & Follow-up Manager

A modern, full-stack healthcare appointment platform featuring a **dedicated FastAPI REST API Backend**, a **standalone Table-Based Relational Database**, and an interactive **Streamlit Frontend UI**.

---

## 🌟 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                       │
│             (Interactive Web UI / Portals)                  │
│                 http://localhost:8501                       │
└──────────────────────────────┬──────────────────────────────┘
                               │  REST API Calls (HTTP/JSON)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI REST API Backend                    │
│      (Swagger Docs: http://127.0.0.1:8000/docs)             │
│   Auth • Doctors • Appointments • AI Summaries • Queue      │
└──────────────────────────────┬──────────────────────────────┘
                               │  SQL Transactions (WAL)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│            Table-Based Relational Database Layer            │
│         (database/schema.sql • data/healthcare.db)          │
│   users • doctors • appointments • notifications • tokens   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Options

#### Option A: Run Full Stack (Backend + Frontend together)
```bash
python run_all.py
```
- **Streamlit Frontend:** [http://localhost:8501](http://localhost:8501)
- **FastAPI Interactive Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc API Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

#### Option B: Run Services Individually
```bash
# Terminal 1: Start FastAPI Backend
python run_backend.py

# Terminal 2: Start Streamlit Frontend
python run_frontend.py
```

---

## 🗄️ Relational Database & Table Structure

The database layer is located in [`database/`](file:///c:/Users/Lenovo/Downloads/CareFlow_Streamlit_Healthcare_Appointment_Manager%20%281%29/careflow-streamlit/database) and defined explicitly via [`database/schema.sql`](file:///c:/Users/Lenovo/Downloads/CareFlow_Streamlit_Healthcare_Appointment_Manager%20%281%29/careflow-streamlit/database/schema.sql).

### Key Tables:
| Table Name | Description | Key Columns / Constraints |
|---|---|---|
| `users` | User credentials & roles | `id`, `name`, `email` (UNIQUE), `password_hash`, `role` (patient/doctor/admin), `created_at` |
| `doctors` | Doctor profiles, working hours & leave | `user_id` (FK `users.id`), `specialization`, `working_days`, `start_time`, `end_time`, `slot_minutes`, `leave_days` |
| `appointments` | Booking state machine | `id`, `patient_id` (FK), `doctor_id` (FK), `start_at`, `end_at`, `status`, `symptoms`, `previsit_summary`, `postvisit_summary`, `doctor_notes`, `prescription` |
| `ux_active_slot` | **Unique Index** preventing double-booking | `UNIQUE(doctor_id, start_at)` WHERE `status IN ('HELD', 'CONFIRMED', 'COMPLETED')` |
| `notifications` | Durable email queue & retry status | `id`, `appointment_id`, `user_id` (FK), `type`, `channel`, `status`, `attempts`, `payload`, `next_attempt_at` |
| `calendar_events`| Calendar event sync state | `id`, `appointment_id` (FK), `provider`, `external_event_id`, `status`, `metadata` |
| `google_tokens` | OAuth 2.0 access & refresh tokens | `user_id` (FK), `access_token`, `refresh_token`, `expires_at`, `scope` |
| `medication_reminders` | Automated prescription schedules | `id`, `appointment_id` (FK), `patient_id` (FK), `medication_text`, `frequency_hours`, `next_run_at`, `active` |
| `job_state` | Background worker tracking | `key`, `value` |

---

## 📡 Backend REST API Reference

All endpoints are documented with live interactive schemas at `http://127.0.0.1:8000/docs`:

### Authentication (`/api/auth`)
- `POST /api/auth/register` — Register a new patient account
- `POST /api/auth/login` — Authenticate existing credentials
- `POST /api/auth/login-or-register` — Frictionless open-access login/registration

### Doctors & Schedules (`/api/doctors`)
- `GET /api/doctors` — Search and list doctors (supports `?specialization=...`)
- `GET /api/doctors/{doctor_id}/slots?date=YYYY-MM-DD` — Retrieve available non-conflicting time slots
- `POST /api/doctors` — Admin endpoint to create new doctor profile
- `PATCH /api/doctors/{doctor_id}` — Update doctor schedule and leave days (automatically cancels conflicting appointments & notifies affected patients)

### Appointments (`/api/appointments`)
- `GET /api/appointments?user_id=...&role=...` — Retrieve scoped appointments for patient, doctor, or admin
- `POST /api/appointments/book` — Atomic slot booking + AI pre-visit summary + notification triggering
- `POST /api/appointments/{id}/cancel` — Cancel appointment and notify counterparty
- `POST /api/appointments/{id}/complete` — Doctor notes + AI post-visit patient summary + medication reminder scheduling

### Notifications & Queue (`/api/notifications`)
- `GET /api/notifications?user_id=...` — View user notification history
- `POST /api/notifications/process` — Trigger queued notification and reminder delivery

### Dashboard & Analytics (`/api/dashboard`)
- `GET /api/dashboard/stats` — Overall statistics for admin portal

### Calendar Sync (`/api/calendar`)
- `GET /api/calendar/google/configured` — Check Google OAuth configuration status
- `GET /api/calendar/google/auth-url` — Generate Google OAuth consent URL
- `POST /api/calendar/google/token` — Exchange Google OAuth authorization code
- `GET /api/calendar/ics/{appointment_id}` — Download universal `.ics` calendar invite

---

## 🧪 Ruanning Tests

Execute unit tests and API integration tests:
```bash
python -m pytest tests/ -v
```

---

## ⚙️ Configuration (`.env.example` → `.env`)

| Variable | Purpose | Default if Unset |
|---|---|---|
| `BACKEND_URL` | URL of the FastAPI Backend API | `http://127.0.0.1:8000` |
| `USE_BACKEND_API` | Whether frontend communicates over REST API | `true` |
| `DB_PATH` | Path to SQLite database file | `data/healthcare.db` |
| `APP_SECRET` | Secret key for hashing | Insecure default (must set for production) |
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | OpenAI-compatible LLM endpoint | Deterministic rule-based summaries |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | SMTP credentials for email delivery | Demo mode (notifications queued and marked sent) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Google Calendar OAuth credentials | Downloadable `.ics` invite fallback |
