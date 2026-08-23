# ============================================================
# services.py
# ============================================================

"""
Core Business Logic and Service Layer for CareFlow Backend.
Encapsulates transactions, concurrency safeguards, AI processing,
notifications, reminders and Google Calendar integration.
"""

import json
import sqlite3
import hashlib
import time
import uuid
import smtplib
import re
import urllib.request
import urllib.parse

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional, List, Dict, Tuple, Any

from database.db import get_db
from backend.config import (
    APP_SECRET,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
)


# ============================================================
# CUSTOM EXCEPTIONS
# ============================================================

class BookingConflict(Exception):
    pass


class AppError(Exception):
    pass


# ============================================================
# AI PROMPTS
# ============================================================

PRE_PROMPT = """You are a clinical administrative assistant, not a diagnostician.
Analyse the patient's symptoms and return JSON with exactly these keys:
urgency_level (Low/Medium/High),
chief_complaint (string),
suggested_questions (array of exactly 3 strings),
disclaimer (string).

Do not diagnose.

Symptoms: {symptoms}
"""

POST_PROMPT = """You are a healthcare communication assistant.
Convert the doctor's clinical notes into a patient-friendly summary.

Return JSON with exactly:
summary,
medication_schedule (array),
follow_up_steps (array),
disclaimer.

Preserve the prescription exactly.
Do not invent medicine names, doses, or diagnoses.

Notes: {notes}

Prescription: {prescription}
"""


# ============================================================
# GENERAL HELPERS
# ============================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def uid() -> str:
    return str(uuid.uuid4())


def hash_pw(p: str) -> str:
    return hashlib.sha256(
        (APP_SECRET + "|" + p).encode()
    ).hexdigest()


def iso_parse(x: str) -> datetime:
    return datetime.fromisoformat(
        x.replace("Z", "+00:00")
    )


# ============================================================
# SQLITE SAFETY / RUNTIME TABLE INITIALIZATION
# ============================================================

def ensure_runtime_tables(c: sqlite3.Connection):
    """
    Makes sure tables/columns required by background jobs exist.

    This is important for Streamlit Cloud because the SQLite database
    can sometimes be created from an older schema.
    """

    # --------------------------------------------------------
    # job_state
    # --------------------------------------------------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS job_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # notifications
    # --------------------------------------------------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            appointment_id TEXT,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            channel TEXT DEFAULT 'email',
            status TEXT DEFAULT 'QUEUED',
            attempts INTEGER DEFAULT 0,
            payload TEXT DEFAULT '{}',
            next_attempt_at TEXT,
            created_at TEXT NOT NULL,
            last_error TEXT
        )
        """
    )

    # --------------------------------------------------------
    # Add missing columns if an old notifications table exists
    # --------------------------------------------------------
    notification_columns = {
        "appointment_id": "TEXT",
        "user_id": "TEXT",
        "type": "TEXT",
        "channel": "TEXT",
        "status": "TEXT",
        "attempts": "INTEGER",
        "payload": "TEXT",
        "next_attempt_at": "TEXT",
        "created_at": "TEXT",
        "last_error": "TEXT",
    }

    existing = {
        row["name"]
        for row in c.execute(
            "PRAGMA table_info(notifications)"
        ).fetchall()
    }

    for column, definition in notification_columns.items():
        if column not in existing:
            try:
                c.execute(
                    f"ALTER TABLE notifications "
                    f"ADD COLUMN {column} {definition}"
                )
            except sqlite3.Error:
                pass

    # --------------------------------------------------------
    # medication_reminders
    # --------------------------------------------------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS medication_reminders (
            id TEXT PRIMARY KEY,
            appointment_id TEXT,
            patient_id TEXT,
            medication_text TEXT,
            frequency_hours INTEGER,
            created_at TEXT,
            active INTEGER DEFAULT 1,
            next_run_at TEXT
        )
        """
    )

    # --------------------------------------------------------
    # calendar_events
    # --------------------------------------------------------
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY,
            appointment_id TEXT,
            provider TEXT,
            external_event_id TEXT,
            status TEXT,
            metadata TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    c.commit()


# ============================================================
# LLM SERVICES
# ============================================================

def request_json(
    url: str,
    method: str = "POST",
    data: Any = None,
    headers: Optional[Dict[str, str]] = None,
) -> Any:

    req = urllib.request.Request(
        url,
        method=method,
        headers=headers or {},
    )

    if data is not None:
        req.data = json.dumps(data).encode()
        req.add_header(
            "Content-Type",
            "application/json",
        )

    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(
            r.read().decode()
        )


def llm(prompt: str) -> Optional[Dict[str, Any]]:

    if not LLM_API_KEY:
        return None

    try:
        out = request_json(
            LLM_BASE_URL + "/chat/completions",
            data={
                "model": LLM_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "Return valid JSON only.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "temperature": 0.1,
            },
            headers={
                "Authorization": "Bearer " + LLM_API_KEY
            },
        )

        txt = (
            out["choices"][0]["message"]["content"]
            .strip()
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        return json.loads(txt)

    except Exception:
        return None


def previsit(symptoms: str) -> Dict[str, Any]:

    result = llm(
        PRE_PROMPT.format(symptoms=symptoms)
    )

    if result:
        return result

    s = symptoms.lower()

    high = [
        "chest pain",
        "difficulty breathing",
        "severe bleeding",
        "unconscious",
        "stroke",
        "seizure",
    ]

    med = [
        "high fever",
        "persistent vomiting",
        "severe pain",
    ]

    urgency = (
        "High"
        if any(x in s for x in high)
        else "Medium"
        if any(x in s for x in med)
        else "Low"
    )

    return {
        "urgency_level": urgency,
        "chief_complaint": symptoms[:160],
        "suggested_questions": [
            "When did the symptoms start?",
            "What makes the symptoms better or worse?",
            "Are there any other symptoms or medicines to mention?",
        ],
        "disclaimer": (
            "AI-generated administrative summary; "
            "not a diagnosis."
        ),
    }


def postvisit(
    notes: str,
    prescription: str,
) -> Dict[str, Any]:

    result = llm(
        POST_PROMPT.format(
            notes=notes,
            prescription=prescription,
        )
    )

    if result:
        return result

    return {
        "summary": (
            notes.strip()
            or "Your doctor has completed the visit notes."
        ),
        "medication_schedule": (
            [prescription]
            if prescription.strip()
            else []
        ),
        "follow_up_steps": [
            "Follow the doctor's instructions and attend any scheduled follow-up."
        ],
        "disclaimer": (
            "Patient-friendly AI summary; follow your doctor's "
            "prescription and seek clarification for any uncertainty."
        ),
    }


# ============================================================
# EMAIL & NOTIFICATIONS
# ============================================================

def send_email(
    to: str,
    subject: str,
    body: str,
) -> Tuple[bool, str]:

    if not SMTP_HOST:
        return True, "DEMO_MODE"

    try:
        msg = EmailMessage()

        msg["From"] = SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject

        msg.set_content(body)

        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT,
            timeout=20,
        ) as s:

            s.starttls()

            s.login(
                SMTP_USER,
                SMTP_PASSWORD,
            )

            s.send_message(msg)

        return True, ""

    except Exception as e:
        return False, str(e)


def notify(
    c: sqlite3.Connection,
    appointment_id: Optional[str],
    user_id: str,
    typ: str,
    subject: str,
    body: str,
):

    ensure_runtime_tables(c)

    n = uid()
    created = now_iso()

    c.execute(
        """
        INSERT INTO notifications(
            id,
            appointment_id,
            user_id,
            type,
            channel,
            status,
            attempts,
            payload,
            next_attempt_at,
            created_at,
            last_error
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            n,
            appointment_id,
            user_id,
            typ,
            "email",
            "QUEUED",
            0,
            json.dumps({
                "subject": subject,
                "body": body,
            }),
            created,
            created,
            None,
        ),
    )


def process_notifications(
    c: Optional[sqlite3.Connection] = None,
    limit: int = 50,
) -> int:

    close = False

    if c is None:
        c = get_db()
        close = True

    try:

        # IMPORTANT:
        # Fixes "no such table: notifications" and old-schema
        # problems on Streamlit Cloud.
        ensure_runtime_tables(c)

        rows = c.execute(
            """
            SELECT
                n.*,
                u.email,
                u.name
            FROM notifications n
            JOIN users u
                ON u.id = n.user_id
            WHERE n.status = 'QUEUED'
              AND (
                  n.next_attempt_at IS NULL
                  OR n.next_attempt_at <= ?
              )
            ORDER BY n.created_at
            LIMIT ?
            """,
            (
                now_iso(),
                limit,
            ),
        ).fetchall()

        done = 0

        for r in rows:

            try:
                p = json.loads(
                    r["payload"] or "{}"
                )
            except Exception:
                p = {}

            subject = p.get(
                "subject",
                "CareFlow Notification",
            )

            body = p.get(
                "body",
                "You have a notification from CareFlow.",
            )

            ok, err = send_email(
                r["email"],
                subject,
                body,
            )

            attempts = (
                int(r["attempts"] or 0) + 1
            )

            if ok:

                c.execute(
                    """
                    UPDATE notifications
                    SET status='SENT',
                        attempts=?,
                        last_error=?
                    WHERE id=?
                    """,
                    (
                        attempts,
                        err,
                        r["id"],
                    ),
                )

                done += 1

            else:

                next_time = (
                    datetime.now(timezone.utc)
                    + timedelta(
                        minutes=min(
                            60,
                            2 ** attempts,
                        )
                    )
                ).isoformat()

                c.execute(
                    """
                    UPDATE notifications
                    SET attempts=?,
                        last_error=?,
                        next_attempt_at=?
                    WHERE id=?
                    """,
                    (
                        attempts,
                        err,
                        next_time,
                        r["id"],
                    ),
                )

        c.commit()

        return done

    except sqlite3.Error:
        c.rollback()
        raise

    finally:

        if close:
            c.close()


# ============================================================
# USERS & AUTH
# ============================================================

def user_by_id(
    c: sqlite3.Connection,
    id: str,
) -> Optional[Dict[str, Any]]:

    row = c.execute(
        """
        SELECT id, name, email, role
        FROM users
        WHERE id=?
        """,
        (id,),
    ).fetchone()

    return dict(row) if row else None


def doctor_profile(
    c: sqlite3.Connection,
    id: str,
) -> Optional[Dict[str, Any]]:

    row = c.execute(
        """
        SELECT
            d.*,
            u.name,
            u.email
        FROM doctors d
        JOIN users u
            ON u.id = d.user_id
        WHERE d.user_id=?
        """,
        (id,),
    ).fetchone()

    return dict(row) if row else None


def add_user(
    c: sqlite3.Connection,
    id: str,
    name: str,
    email: str,
    password: str,
    role: str,
):

    c.execute(
        "INSERT INTO users VALUES(?,?,?,?,?,?)",
        (
            id,
            name,
            email.lower(),
            hash_pw(password),
            role,
            now_iso(),
        ),
    )


def register_patient(
    name: str,
    email: str,
    password: str,
) -> Dict[str, Any]:

    c = get_db()

    try:

        if c.execute(
            "SELECT 1 FROM users WHERE email=?",
            (email.lower(),),
        ).fetchone():

            raise AppError(
                "An account with this email already exists."
            )

        id = uid()

        c.execute("BEGIN IMMEDIATE")

        add_user(
            c,
            id,
            name,
            email,
            password,
            "patient",
        )

        c.commit()

        return dict(
            user_by_id(c, id)
        )

    finally:
        c.close()


def login(
    email: str,
    password: str,
) -> Optional[Dict[str, Any]]:

    c = get_db()

    try:

        r = c.execute(
            "SELECT * FROM users WHERE email=?",
            (email.lower(),),
        ).fetchone()

        if (
            not r
            or r["password_hash"]
            != hash_pw(password)
        ):
            return None

        return {
            "id": r["id"],
            "name": r["name"],
            "email": r["email"],
            "role": r["role"],
        }

    finally:
        c.close()


def login_or_register(
    email: str,
    password: str,
    role: str,
    name: Optional[str] = None,
) -> Tuple[Dict[str, Any], bool, bool]:

    email = email.strip().lower()

    if not email or "@" not in email:
        raise AppError(
            "Please enter a valid email address."
        )

    c = get_db()

    try:

        c.execute("BEGIN IMMEDIATE")

        row = c.execute(
            "SELECT * FROM users WHERE email=?",
            (email,),
        ).fetchone()

        if row:

            c.commit()

            user = {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "role": row["role"],
            }

            return (
                user,
                False,
                row["role"] != role,
            )

        id = uid()

        display_name = (
            (name or "").strip()
            or email.split("@")[0]
            .replace(".", " ")
            .replace("_", " ")
            .title()
        )

        add_user(
            c,
            id,
            display_name,
            email,
            password or "x",
            role,
        )

        if role == "doctor":

            c.execute(
                """
                INSERT INTO doctors(
                    user_id,
                    specialization,
                    working_days,
                    start_time,
                    end_time,
                    slot_minutes,
                    leave_days
                )
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    id,
                    "General Medicine",
                    "Mon,Tue,Wed,Thu,Fri",
                    "09:00",
                    "17:00",
                    30,
                    "[]",
                ),
            )

        c.commit()

        return (
            {
                "id": id,
                "name": display_name,
                "email": email,
                "role": role,
            },
            True,
            False,
        )

    finally:
        c.close()


# ============================================================
# DOCTORS & SLOTS
# ============================================================

def list_doctors(
    specialization_query: str = "",
) -> List[Dict[str, Any]]:

    c = get_db()

    try:

        rows = c.execute(
            """
            SELECT
                d.user_id,
                u.name,
                u.email,
                d.specialization,
                d.working_days,
                d.start_time,
                d.end_time,
                d.slot_minutes,
                d.leave_days
            FROM doctors d
            JOIN users u
                ON u.id = d.user_id
            WHERE lower(d.specialization)
                LIKE lower(?)
            ORDER BY u.name
            """,
            ("%" + specialization_query + "%",),
        ).fetchall()

        return [dict(r) for r in rows]

    finally:
        c.close()


def slot_ok(
    profile: Dict[str, Any],
    start: str,
) -> Tuple[bool, str]:

    dt = iso_parse(start)

    days = [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun",
    ]

    if (
        days[dt.weekday()]
        not in profile["working_days"].split(",")
    ):
        return (
            False,
            "Doctor is not working on this day.",
        )

    if start[:10] in json.loads(
        profile["leave_days"]
    ):
        return (
            False,
            "Doctor is on leave for this date.",
        )

    t = dt.strftime("%H:%M")

    if not (
        profile["start_time"]
        <= t
        < profile["end_time"]
    ):
        return (
            False,
            "Slot is outside working hours.",
        )

    if (
        dt.minute
        % int(profile["slot_minutes"])
        != 0
    ):
        return (
            False,
            "Slot does not align with slot duration.",
        )

    return True, ""


def get_slots(
    doctor_id: str,
    date_str: str,
) -> Tuple[List[str], bool]:

    c = get_db()

    try:

        p = doctor_profile(
            c,
            doctor_id,
        )

        if not p:
            raise AppError(
                "Doctor not found."
            )

        slots = []

        dt = datetime.fromisoformat(
            date_str + "T" + p["start_time"]
        )

        end = datetime.fromisoformat(
            date_str + "T" + p["end_time"]
        )

        while dt < end:

            s = dt.isoformat()

            ok, _ = slot_ok(
                dict(p),
                s,
            )

            busy = c.execute(
                """
                SELECT 1
                FROM appointments
                WHERE doctor_id=?
                  AND start_at=?
                  AND status IN(
                      'HELD',
                      'CONFIRMED',
                      'COMPLETED'
                  )
                """,
                (
                    doctor_id,
                    s,
                ),
            ).fetchone()

            if ok and not busy:
                slots.append(s)

            dt += timedelta(
                minutes=p["slot_minutes"]
            )

        return (
            slots,
            date_str in json.loads(
                p["leave_days"]
            ),
        )

    finally:
        c.close()


# ============================================================
# APPOINTMENTS
# ============================================================

def book_appointment(
    patient_id: str,
    doctor_id: str,
    start_at: str,
    symptoms: str,
) -> Dict[str, Any]:

    c = get_db()

    try:

        ensure_runtime_tables(c)

        p = doctor_profile(
            c,
            doctor_id,
        )

        if not p:
            raise AppError(
                "Doctor not found."
            )

        ok, msg = slot_ok(
            dict(p),
            start_at,
        )

        if not ok:
            raise AppError(msg)

        symptoms = symptoms.strip()

        if not symptoms:
            raise AppError(
                "Symptoms are required before confirming the appointment."
            )

        dt = iso_parse(start_at)

        end = (
            dt
            + timedelta(
                minutes=p["slot_minutes"]
            )
        ).isoformat()

        c.execute("BEGIN IMMEDIATE")

        busy = c.execute(
            """
            SELECT 1
            FROM appointments
            WHERE doctor_id=?
              AND start_at=?
              AND status IN(
                  'HELD',
                  'CONFIRMED',
                  'COMPLETED'
              )
            """,
            (
                doctor_id,
                start_at,
            ),
        ).fetchone()

        if busy:

            c.rollback()

            raise BookingConflict(
                "This slot was just booked by another patient. "
                "Please select another slot."
            )

        aid = uid()

        summary = previsit(symptoms)

        try:

            c.execute(
                """
                INSERT INTO appointments
                VALUES(
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )
                """,
                (
                    aid,
                    patient_id,
                    doctor_id,
                    start_at,
                    end,
                    "CONFIRMED",
                    None,
                    symptoms,
                    json.dumps(summary),
                    None,
                    None,
                    None,
                    now_iso(),
                    now_iso(),
                ),
            )

        except sqlite3.IntegrityError:

            c.rollback()

            raise BookingConflict(
                "This slot was just booked by another patient. "
                "Please select another slot."
            )

        pu = user_by_id(
            c,
            patient_id,
        )

        du = user_by_id(
            c,
            doctor_id,
        )

        notify(
            c,
            aid,
            patient_id,
            "BOOKING_CONFIRMATION",
            "Appointment confirmed",
            (
                f"Your appointment with "
                f"{du['name']} is confirmed for "
                f"{start_at}."
            ),
        )

        notify(
            c,
            aid,
            doctor_id,
            "BOOKING_CONFIRMATION",
            "New appointment",
            (
                f"{pu['name']} booked {start_at}. "
                f"Pre-visit summary: "
                f"{summary['chief_complaint']} "
                f"(Urgency: "
                f"{summary['urgency_level']})."
            ),
        )

        c.commit()

        cal = sync_calendar_booking(
            c,
            aid,
        )

        return {
            "appointment_id": aid,
            "status": "CONFIRMED",
            "previsit_summary": summary,
            "calendar": cal,
        }

    finally:
        c.close()


def list_appointments(
    user: Dict[str, Any],
) -> List[Dict[str, Any]]:

    c = get_db()

    try:

        if user["role"] == "patient":

            rows = c.execute(
                """
                SELECT
                    a.*,
                    u.name AS doctor_name,
                    d.specialization
                FROM appointments a
                JOIN users u
                    ON u.id = a.doctor_id
                JOIN doctors d
                    ON d.user_id = a.doctor_id
                WHERE a.patient_id=?
                ORDER BY a.start_at DESC
                """,
                (user["id"],),
            ).fetchall()

        elif user["role"] == "doctor":

            rows = c.execute(
                """
                SELECT
                    a.*,
                    u.name AS patient_name
                FROM appointments a
                JOIN users u
                    ON u.id = a.patient_id
                WHERE a.doctor_id=?
                ORDER BY a.start_at DESC
                """,
                (user["id"],),
            ).fetchall()

        else:

            rows = c.execute(
                """
                SELECT
                    a.*,
                    p.name AS patient_name,
                    dr.name AS doctor_name
                FROM appointments a
                JOIN users p
                    ON p.id = a.patient_id
                JOIN users dr
                    ON dr.id = a.doctor_id
                ORDER BY a.start_at DESC
                """
            ).fetchall()

        return [dict(r) for r in rows]

    finally:
        c.close()


def cancel_appointment(
    appointment_id: str,
    user: Dict[str, Any],
):

    c = get_db()

    try:

        ensure_runtime_tables(c)

        a = c.execute(
            "SELECT * FROM appointments WHERE id=?",
            (appointment_id,),
        ).fetchone()

        if not a:
            raise AppError(
                "Appointment not found."
            )

        if (
            user["role"] != "admin"
            and user["id"]
            not in (
                a["patient_id"],
                a["doctor_id"],
            )
        ):
            raise AppError(
                "Not allowed."
            )

        c.execute(
            """
            UPDATE appointments
            SET status='CANCELLED',
                updated_at=?
            WHERE id=?
            """,
            (
                now_iso(),
                appointment_id,
            ),
        )

        c.execute(
            """
            UPDATE calendar_events
            SET status='DELETE_PENDING',
                updated_at=?
            WHERE appointment_id=?
            """,
            (
                now_iso(),
                appointment_id,
            ),
        )

        other = (
            a["doctor_id"]
            if user["id"] == a["patient_id"]
            else a["patient_id"]
        )

        notify(
            c,
            appointment_id,
            other,
            "CANCELLATION",
            "Appointment cancelled",
            (
                f"Appointment "
                f"{a['start_at']} was cancelled."
            ),
        )

        c.commit()

    finally:
        c.close()


def complete_appointment(
    appointment_id: str,
    doctor_id: str,
    doctor_notes: str,
    prescription: str,
) -> Dict[str, Any]:

    c = get_db()

    try:

        ensure_runtime_tables(c)

        a = c.execute(
            "SELECT * FROM appointments WHERE id=?",
            (appointment_id,),
        ).fetchone()

        if not a:
            raise AppError(
                "Appointment not found."
            )

        if a["doctor_id"] != doctor_id:
            raise AppError(
                "Doctor access required."
            )

        summary = postvisit(
            doctor_notes.strip(),
            prescription.strip(),
        )

        c.execute(
            """
            UPDATE appointments
            SET status='COMPLETED',
                doctor_notes=?,
                prescription=?,
                postvisit_summary=?,
                updated_at=?
            WHERE id=?
            """,
            (
                doctor_notes.strip(),
                prescription.strip(),
                json.dumps(summary),
                now_iso(),
                appointment_id,
            ),
        )

        create_medication_reminders(
            c,
            appointment_id,
            a["patient_id"],
            prescription,
        )

        notify(
            c,
            appointment_id,
            a["patient_id"],
            "POST_VISIT_SUMMARY",
            "Visit summary",
            summary["summary"],
        )

        c.commit()

        return summary

    finally:
        c.close()


# ============================================================
# ADMIN & DOCTOR UPDATES
# ============================================================

def admin_create_doctor(
    name: str,
    email: str,
    password: str,
    specialization: str,
    working_days: str,
    start_time: str,
    end_time: str,
    slot_minutes: int,
) -> str:

    c = get_db()

    try:

        if c.execute(
            "SELECT 1 FROM users WHERE email=?",
            (email.lower(),),
        ).fetchone():

            raise AppError(
                "An account with this email already exists."
            )

        id = uid()

        c.execute("BEGIN IMMEDIATE")

        add_user(
            c,
            id,
            name,
            email,
            password or "doctor123",
            "doctor",
        )

        c.execute(
            "INSERT INTO doctors VALUES(?,?,?,?,?,?,?)",
            (
                id,
                specialization,
                working_days,
                start_time,
                end_time,
                int(slot_minutes),
                "[]",
            ),
        )

        c.commit()

        return id

    finally:
        c.close()


def admin_update_doctor(
    doctor_id: str,
    specialization: Optional[str] = None,
    working_days: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    slot_minutes: Optional[int] = None,
    leave_days: Optional[List[str]] = None,
) -> List[str]:

    c = get_db()

    try:

        p = doctor_profile(
            c,
            doctor_id,
        )

        if not p:
            raise AppError(
                "Doctor not found."
            )

        leaves = (
            leave_days
            if leave_days is not None
            else json.loads(p["leave_days"])
        )

        c.execute(
            """
            UPDATE doctors
            SET specialization=?,
                working_days=?,
                start_time=?,
                end_time=?,
                slot_minutes=?,
                leave_days=?
            WHERE user_id=?
            """,
            (
                specialization or p["specialization"],
                working_days or p["working_days"],
                start_time or p["start_time"],
                end_time or p["end_time"],
                (
                    int(slot_minutes)
                    if slot_minutes
                    else p["slot_minutes"]
                ),
                json.dumps(leaves),
                doctor_id,
            ),
        )

        affected = []

        for day in leaves:

            rows = c.execute(
                """
                SELECT
                    a.id,
                    a.patient_id,
                    a.start_at
                FROM appointments a
                WHERE a.doctor_id=?
                  AND substr(a.start_at,1,10)=?
                  AND a.status='CONFIRMED'
                """,
                (
                    doctor_id,
                    day,
                ),
            ).fetchall()

            for a in rows:

                c.execute(
                    """
                    UPDATE appointments
                    SET status='CANCELLED',
                        updated_at=?
                    WHERE id=?
                    """,
                    (
                        now_iso(),
                        a["id"],
                    ),
                )

                notify(
                    c,
                    a["id"],
                    a["patient_id"],
                    "LEAVE_CONFLICT",
                    "Doctor leave notification",
                    (
                        f"Your appointment on "
                        f"{a['start_at']} was cancelled "
                        f"because the doctor is on leave."
                    ),
                )

                affected.append(a["id"])

        c.commit()

        return affected

    finally:
        c.close()


# ============================================================
# NOTIFICATIONS & MEDICATION REMINDERS
# ============================================================

def list_notifications(
    user_id: str,
) -> List[Dict[str, Any]]:

    c = get_db()

    try:

        ensure_runtime_tables(c)

        rows = c.execute(
            """
            SELECT *
            FROM notifications
            WHERE user_id=?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()

        return [dict(r) for r in rows]

    finally:
        c.close()


def create_medication_reminders(
    c: sqlite3.Connection,
    aid: str,
    patient_id: str,
    prescription: str,
):

    ensure_runtime_tables(c)

    text = prescription.strip()

    if not text:
        return

    patterns = [
        (
            r"(?:twice|2)\s+(?:a\s+)?day",
            12,
        ),
        (
            r"(?:three times|3\s+times)\s+(?:a\s+)?day",
            8,
        ),
        (
            r"(?:four times|4\s+times)\s+(?:a\s+)?day",
            6,
        ),
        (
            r"(?:once|1)\s+(?:a\s+)?day",
            24,
        ),
        (
            r"every\s+(\d+)\s+hours?",
            None,
        ),
    ]

    hours = 24

    for pat, h in patterns:

        m = re.search(
            pat,
            text,
            re.I,
        )

        if m:

            hours = (
                int(m.group(1))
                if h is None
                else h
            )

            break

    current = now_iso()

    c.execute(
        """
        INSERT INTO medication_reminders
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            uid(),
            aid,
            patient_id,
            text,
            hours,
            current,
            1,
            current,
        ),
    )


def process_medication_reminders(
    c: Optional[sqlite3.Connection] = None,
    limit: int = 50,
) -> int:

    close = False

    if c is None:
        c = get_db()
        close = True

    try:

        ensure_runtime_tables(c)

        rows = c.execute(
            """
            SELECT *
            FROM medication_reminders
            WHERE active=1
              AND next_run_at<=?
            LIMIT ?
            """,
            (
                now_iso(),
                limit,
            ),
        ).fetchall()

        n = 0

        for r in rows:

            notify(
                c,
                r["appointment_id"],
                r["patient_id"],
                "MEDICATION_REMINDER",
                "Medication reminder",
                (
                    "Reminder: follow your prescription schedule. "
                    f"Prescription: {r['medication_text']}"
                ),
            )

            next_run = (
                datetime.now(timezone.utc)
                + timedelta(
                    hours=r["frequency_hours"]
                )
            ).isoformat()

            c.execute(
                """
                UPDATE medication_reminders
                SET next_run_at=?
                WHERE id=?
                """,
                (
                    next_run,
                    r["id"],
                ),
            )

            n += 1

        c.commit()

        return n

    finally:

        if close:
            c.close()


# ============================================================
# BACKGROUND JOBS
# ============================================================

def run_background_jobs_if_due(
    min_interval_seconds: int = 20,
) -> Dict[str, int]:

    c = get_db()

    try:

        # THIS IS THE IMPORTANT FIX.
        # Make all background-job tables available before
        # process_notifications() executes its SELECT.
        ensure_runtime_tables(c)

        row = c.execute(
            """
            SELECT value
            FROM job_state
            WHERE key='last_run'
            """
        ).fetchone()

        last = (
            float(row["value"])
            if row and row["value"]
            else 0
        )

        current_time = time.time()

        if (
            current_time - last
            < min_interval_seconds
        ):
            return {
                "notifications": 0,
                "reminders": 0,
            }

        c.execute(
            """
            INSERT OR REPLACE INTO job_state(
                key,
                value
            )
            VALUES('last_run',?)
            """,
            (str(current_time),),
        )

        c.commit()

        notifications = process_notifications(c)

        reminders = process_medication_reminders(c)

        return {
            "notifications": notifications,
            "reminders": reminders,
        }

    except sqlite3.Error:

        c.rollback()

        # Do not crash the Streamlit application because
        # a background notification job failed.
        return {
            "notifications": 0,
            "reminders": 0,
        }

    except Exception:

        c.rollback()

        return {
            "notifications": 0,
            "reminders": 0,
        }

    finally:
        c.close()


# ============================================================
# GOOGLE CALENDAR SERVICES
# ============================================================

def google_configured() -> bool:
    return bool(
        GOOGLE_CLIENT_ID
        and GOOGLE_CLIENT_SECRET
    )


def google_auth_url(
    user_id: str,
    redirect_uri: str,
    state_extra: str = "",
) -> str:

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": (
            "https://www.googleapis.com/auth/"
            "calendar.events"
        ),
        "access_type": "offline",
        "prompt": "consent",
        "state": user_id + state_extra,
    }

    return (
        "https://accounts.google.com/"
        "o/oauth2/v2/auth?"
        + urllib.parse.urlencode(params)
    )


def google_token_exchange(
    code: str,
    redirect_uri: str,
) -> Dict[str, Any]:

    data = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        },
    )

    with urllib.request.urlopen(
        req,
        timeout=20,
    ) as r:

        return json.loads(
            r.read().decode()
        )


def google_api(
    access_token: str,
    url: str,
    method: str = "POST",
    payload: Any = None,
) -> Dict[str, Any]:

    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "Authorization":
                "Bearer " + access_token,
            "Content-Type":
                "application/json",
        },
    )

    if payload is not None:
        req.data = json.dumps(
            payload
        ).encode()

    with urllib.request.urlopen(
        req,
        timeout=20,
    ) as r:

        raw = r.read()

        return (
            json.loads(raw.decode())
            if raw
            else {}
        )


def save_google_token(
    user_id: str,
    tok: Dict[str, Any],
):

    c = get_db()

    try:

        c.execute(
            """
            INSERT OR REPLACE INTO google_tokens(
                user_id,
                access_token,
                refresh_token,
                expires_at,
                scope,
                updated_at
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                user_id,
                tok["access_token"],
                tok.get("refresh_token"),
                int(time.time())
                + int(
                    tok.get(
                        "expires_in",
                        3600,
                    )
                ),
                tok.get("scope", ""),
                now_iso(),
            ),
        )

        c.commit()

    finally:
        c.close()


def calendar_create_for_user(
    c: sqlite3.Connection,
    user_id: str,
    a: sqlite3.Row,
) -> Optional[str]:

    tok = c.execute(
        """
        SELECT *
        FROM google_tokens
        WHERE user_id=?
        """,
        (user_id,),
    ).fetchone()

    if not tok:
        return None

    try:

        start = iso_parse(
            a["start_at"]
        )

        end = iso_parse(
            a["end_at"]
        )

        payload = {
            "summary":
                "Healthcare Appointment",
            "description":
                "CareFlow appointment",
            "start": {
                "dateTime":
                    start.isoformat(),
                "timeZone":
                    "UTC",
            },
            "end": {
                "dateTime":
                    end.isoformat(),
                "timeZone":
                    "UTC",
            },
        }

        out = google_api(
            tok["access_token"],
            "https://www.googleapis.com/calendar/v3/"
            "calendars/primary/events",
            "POST",
            payload,
        )

        return out.get("id")

    except Exception:
        return None


def sync_calendar_booking(
    c: sqlite3.Connection,
    aid: str,
) -> str:

    ensure_runtime_tables(c)

    a = c.execute(
        """
        SELECT *
        FROM appointments
        WHERE id=?
        """,
        (aid,),
    ).fetchone()

    if not a:
        return "NOT_FOUND"

    ids = {}

    for u in [
        a["patient_id"],
        a["doctor_id"],
    ]:

        eid = calendar_create_for_user(
            c,
            u,
            a,
        )

        if eid:
            ids[u] = eid

    if len(ids) == 2:

        status = "SYNCED"

    elif not google_configured():

        status = "DEMO_PENDING"

    else:

        status = "SYNC_PENDING"

    row = c.execute(
        """
        SELECT id
        FROM calendar_events
        WHERE appointment_id=?
        """,
        (aid,),
    ).fetchone()

    if row:

        c.execute(
            """
            UPDATE calendar_events
            SET status=?,
                metadata=?,
                updated_at=?
            WHERE appointment_id=?
            """,
            (
                status,
                json.dumps(ids),
                now_iso(),
                aid,
            ),
        )

    else:

        c.execute(
            """
            INSERT INTO calendar_events
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                uid(),
                aid,
                "google",
                None,
                status,
                json.dumps(ids),
                now_iso(),
                now_iso(),
            ),
        )

    c.commit()

    return status


def ics_for_appointment(
    a: Dict[str, Any],
    doctor_name: str,
    patient_name: str,
) -> str:

    start = iso_parse(
        a["start_at"]
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    end = iso_parse(
        a["end_at"]
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    timestamp = (
        now_iso()
        .replace("-", "")
        .replace(":", "")
        .split("+")[0]
        + "Z"
    )

    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//CareFlow//Appointment//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{a['id']}@careflow\r\n"
        f"DTSTAMP:{timestamp}\r\n"
        f"DTSTART:{start}\r\n"
        f"DTEND:{end}\r\n"
        f"SUMMARY:Healthcare Appointment with {doctor_name}\r\n"
        f"DESCRIPTION:Appointment between "
        f"{patient_name} and {doctor_name}.\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


# ============================================================
# DASHBOARD STATISTICS
# ============================================================

def dashboard_stats() -> Dict[str, int]:

    c = get_db()

    try:

        ensure_runtime_tables(c)

        stats = {}

        for status in [
            "CONFIRMED",
            "COMPLETED",
            "CANCELLED",
        ]:

            stats[
                status.lower()
            ] = c.execute(
                """
                SELECT COUNT(*) n
                FROM appointments
                WHERE status=?
                """,
                (status,),
            ).fetchone()["n"]

        stats["doctors"] = c.execute(
            """
            SELECT COUNT(*) n
            FROM doctors
            """
        ).fetchone()["n"]

        stats["patients"] = c.execute(
            """
            SELECT COUNT(*) n
            FROM users
            WHERE role='patient'
            """
        ).fetchone()["n"]

        stats["notifications_queued"] = c.execute(
            """
            SELECT COUNT(*) n
            FROM notifications
            WHERE status='QUEUED'
            """
        ).fetchone()["n"]

        stats["notifications_sent"] = c.execute(
            """
            SELECT COUNT(*) n
            FROM notifications
            WHERE status='SENT'
            """
        ).fetchone()["n"]

        return stats

    finally:
        c.close()