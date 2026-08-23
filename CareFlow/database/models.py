"""
Data structures representing the relational database tables in CareFlow.
"""
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any


@dataclass
class User:
    id: str
    name: str
    email: str
    password_hash: str
    role: str  # patient, doctor, admin
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Doctor:
    user_id: str
    specialization: str
    working_days: str
    start_time: str
    end_time: str
    slot_minutes: int = 30
    leave_days: str = "[]"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Appointment:
    id: str
    patient_id: str
    doctor_id: str
    start_at: str
    end_at: str
    status: str  # HELD, CONFIRMED, CANCELLED, COMPLETED, NO_SHOW
    hold_expires_at: Optional[str]
    symptoms: str
    previsit_summary: Optional[str]
    postvisit_summary: Optional[str]
    doctor_notes: Optional[str]
    prescription: Optional[str]
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Notification:
    id: str
    appointment_id: Optional[str]
    user_id: str
    type: str
    channel: str
    status: str
    attempts: int
    last_error: Optional[str]
    payload: str
    next_attempt_at: Optional[str]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MedicationReminder:
    id: str
    appointment_id: str
    patient_id: str
    medication_text: str
    frequency_hours: int
    next_run_at: str
    active: int
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
