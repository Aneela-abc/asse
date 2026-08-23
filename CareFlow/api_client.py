# ============================================================
# api_client.py
# ============================================================

"""
CareFlow API Client.
Provides a clean interface for Streamlit or any other frontend
client to interact with the FastAPI backend REST API.

Includes transparent fallback to direct services if the backend
server is not reachable.
"""

import os
import requests

from typing import Optional, List, Dict, Any, Tuple

from database.db import get_db, init_database
from backend import services
from backend.services import (
    AppError,
    BookingConflict,
    doctor_profile,
    user_by_id,
)


# ============================================================
# CONFIGURATION
# ============================================================

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

USE_API = os.getenv(
    "USE_BACKEND_API",
    "true"
).lower() in (
    "true",
    "1",
    "yes",
)


db = get_db
init_db = init_database


# ============================================================
# HELPERS
# ============================================================

def env(k, default=""):
    return os.getenv(k, default)


def is_backend_online() -> bool:

    if not USE_API:
        return False

    try:

        r = requests.get(
            f"{BACKEND_URL}/health",
            timeout=1.0,
        )

        return r.status_code == 200

    except Exception:
        return False


# ============================================================
# AUTH
# ============================================================

def login_or_register(
    email: str,
    password: str,
    role: str,
    name: Optional[str] = None,
) -> Tuple[Dict[str, Any], bool, bool]:

    if is_backend_online():

        try:

            r = requests.post(
                f"{BACKEND_URL}/api/auth/login-or-register",
                json={
                    "email": email,
                    "password": password,
                    "role": role,
                    "name": name,
                },
                timeout=5.0,
            )

            if r.status_code == 200:

                data = r.json()

                return (
                    data["user"],
                    data["created"],
                    data["role_overridden"],
                )

            else:

                try:
                    detail = r.json().get(
                        "detail",
                        "Authentication failed",
                    )
                except Exception:
                    detail = "Authentication failed"

                raise services.AppError(detail)

        except (
            requests.RequestException,
            KeyError,
            ValueError,
        ):

            pass

    return services.login_or_register(
        email,
        password,
        role,
        name,
    )


# ============================================================
# DOCTORS
# ============================================================

def list_doctors(
    specialization: str = "",
) -> List[Dict[str, Any]]:

    if is_backend_online():

        try:

            r = requests.get(
                f"{BACKEND_URL}/api/doctors",
                params={
                    "specialization": specialization
                },
                timeout=5.0,
            )

            if r.status_code == 200:
                return r.json()

        except requests.RequestException:
            pass

    return services.list_doctors(
        specialization
    )


def get_slots(
    doctor_id: str,
    date_str: str,
) -> Tuple[List[str], bool]:

    if is_backend_online():

        try:

            r = requests.get(
                f"{BACKEND_URL}/api/doctors/"
                f"{doctor_id}/slots",
                params={
                    "date": date_str
                },
                timeout=5.0,
            )

            if r.status_code == 200:

                data = r.json()

                return (
                    data["slots"],
                    data["is_on_leave"],
                )

            else:

                try:
                    detail = r.json().get(
                        "detail",
                        "Error fetching slots",
                    )
                except Exception:
                    detail = "Error fetching slots"

                raise services.AppError(detail)

        except (
            requests.RequestException,
            KeyError,
            ValueError,
        ):

            pass

    return services.get_slots(
        doctor_id,
        date_str,
    )


# ============================================================
# APPOINTMENTS
# ============================================================

def book_appointment(
    patient_id: str,
    doctor_id: str,
    start_at: str,
    symptoms: str,
) -> Dict[str, Any]:

    if is_backend_online():

        try:

            r = requests.post(
                f"{BACKEND_URL}/api/appointments/book",
                json={
                    "patient_id": patient_id,
                    "doctor_id": doctor_id,
                    "start_at": start_at,
                    "symptoms": symptoms,
                },
                timeout=15.0,
            )

            if r.status_code in (
                200,
                201,
            ):

                return r.json()

            elif r.status_code == 409:

                try:
                    detail = r.json().get(
                        "detail",
                        "Slot already booked",
                    )
                except Exception:
                    detail = "Slot already booked"

                raise services.BookingConflict(
                    detail
                )

            else:

                try:
                    detail = r.json().get(
                        "detail",
                        "Booking failed",
                    )
                except Exception:
                    detail = "Booking failed"

                raise services.AppError(detail)

        except (
            services.BookingConflict,
            services.AppError,
        ):

            raise

        except requests.RequestException:

            pass

    return services.book_appointment(
        patient_id,
        doctor_id,
        start_at,
        symptoms,
    )


def list_appointments(
    user: Dict[str, Any],
) -> List[Dict[str, Any]]:

    if is_backend_online():

        try:

            r = requests.get(
                f"{BACKEND_URL}/api/appointments",
                params={
                    "user_id": user["id"],
                    "role": user["role"],
                },
                timeout=5.0,
            )

            if r.status_code == 200:
                return r.json()

        except requests.RequestException:
            pass

    return services.list_appointments(
        user
    )


def cancel_appointment(
    appointment_id: str,
    user: Dict[str, Any],
):

    if is_backend_online():

        try:

            r = requests.post(
                f"{BACKEND_URL}/api/appointments/"
                f"{appointment_id}/cancel",
                json={
                    "user_id": user["id"],
                    "role": user["role"],
                },
                timeout=5.0,
            )

            if r.status_code == 200:
                return

            try:
                detail = r.json().get(
                    "detail",
                    "Cancellation failed",
                )
            except Exception:
                detail = "Cancellation failed"

            raise services.AppError(detail)

        except services.AppError:
            raise

        except requests.RequestException:
            pass

    return services.cancel_appointment(
        appointment_id,
        user,
    )


def complete_appointment(
    appointment_id: str,
    doctor_id: str,
    doctor_notes: str,
    prescription: str,
) -> Dict[str, Any]:

    if is_backend_online():

        try:

            r = requests.post(
                f"{BACKEND_URL}/api/appointments/"
                f"{appointment_id}/complete",
                json={
                    "doctor_id": doctor_id,
                    "doctor_notes": doctor_notes,
                    "prescription": prescription,
                },
                timeout=15.0,
            )

            if r.status_code == 200:

                return r.json()[
                    "postvisit_summary"
                ]

            try:
                detail = r.json().get(
                    "detail",
                    "Completion failed",
                )
            except Exception:
                detail = "Completion failed"

            raise services.AppError(detail)

        except services.AppError:
            raise

        except requests.RequestException:
            pass

    return services.complete_appointment(
        appointment_id,
        doctor_id,
        doctor_notes,
        prescription,
    )


# ============================================================
# ADMIN
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

    if is_backend_online():

        try:

            r = requests.post(
                f"{BACKEND_URL}/api/doctors",
                json={
                    "name": name,
                    "email": email,
                    "password": password,
                    "specialization": specialization,
                    "working_days": working_days,
                    "start_time": start_time,
                    "end_time": end_time,
                    "slot_minutes": slot_minutes,
                },
                timeout=5.0,
            )

            if r.status_code in (
                200,
                201,
            ):

                return r.json()["doctor_id"]

            try:
                detail = r.json().get(
                    "detail",
                    "Doctor creation failed",
                )
            except Exception:
                detail = "Doctor creation failed"

            raise services.AppError(detail)

        except services.AppError:
            raise

        except requests.RequestException:
            pass

    return services.admin_create_doctor(
        name,
        email,
        password,
        specialization,
        working_days,
        start_time,
        end_time,
        slot_minutes,
    )


def admin_update_doctor(
    doctor_id: str,
    specialization: Optional[str] = None,
    working_days: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    slot_minutes: Optional[int] = None,
    leave_days: Optional[List[str]] = None,
) -> List[str]:

    if is_backend_online():

        try:

            r = requests.patch(
                f"{BACKEND_URL}/api/doctors/"
                f"{doctor_id}",
                json={
                    "specialization": specialization,
                    "working_days": working_days,
                    "start_time": start_time,
                    "end_time": end_time,
                    "slot_minutes": slot_minutes,
                    "leave_days": leave_days,
                },
                timeout=5.0,
            )

            if r.status_code == 200:

                return r.json()[
                    "affected_cancelled_appointments"
                ]

            try:
                detail = r.json().get(
                    "detail",
                    "Doctor update failed",
                )
            except Exception:
                detail = "Doctor update failed"

            raise services.AppError(detail)

        except services.AppError:
            raise

        except requests.RequestException:
            pass

    return services.admin_update_doctor(
        doctor_id,
        specialization,
        working_days,
        start_time,
        end_time,
        slot_minutes,
        leave_days,
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

def list_notifications(
    user_id: str,
) -> List[Dict[str, Any]]:

    if is_backend_online():

        try:

            r = requests.get(
                f"{BACKEND_URL}/api/notifications",
                params={
                    "user_id": user_id
                },
                timeout=5.0,
            )

            if r.status_code == 200:
                return r.json()

        except requests.RequestException:
            pass

    return services.list_notifications(
        user_id
    )


def process_notifications() -> int:

    if is_backend_online():

        try:

            r = requests.post(
                f"{BACKEND_URL}/api/notifications/process",
                timeout=10.0,
            )

            if r.status_code == 200:

                return r.json().get(
                    "processed_notifications",
                    0,
                )

        except requests.RequestException:
            pass

    return services.process_notifications()


# ============================================================
# DASHBOARD
# ============================================================

def dashboard_stats() -> Dict[str, int]:

    if is_backend_online():

        try:

            r = requests.get(
                f"{BACKEND_URL}/api/dashboard/stats",
                timeout=5.0,
            )

            if r.status_code == 200:
                return r.json()

        except requests.RequestException:
            pass

    return services.dashboard_stats()


# ============================================================
# GOOGLE CALENDAR
# ============================================================

def google_configured() -> bool:
    return services.google_configured()


def google_auth_url(
    user_id: str,
    redirect_uri: str,
) -> str:

    return services.google_auth_url(
        user_id,
        redirect_uri,
    )


def google_token_exchange(
    code: str,
    redirect_uri: str,
) -> Dict[str, Any]:

    return services.google_token_exchange(
        code,
        redirect_uri,
    )


def save_google_token(
    user_id: str,
    tok: Dict[str, Any],
):

    return services.save_google_token(
        user_id,
        tok,
    )


def ics_for_appointment(
    a: Dict[str, Any],
    doctor_name: str,
    patient_name: str,
) -> str:

    return services.ics_for_appointment(
        a,
        doctor_name,
        patient_name,
    )


# ============================================================
# BACKGROUND JOBS
# ============================================================

def run_background_jobs_if_due():

    try:

        return services.run_background_jobs_if_due()

    except sqlite3.Error:
        return {
            "notifications": 0,
            "reminders": 0,
        }

    except Exception:
        return {
            "notifications": 0,
            "reminders": 0,
        }