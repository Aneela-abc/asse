"""
Pydantic Schemas for Request / Response validation across API endpoints.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any


# --- Auth Schemas ---
class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Full Name")
    email: EmailStr = Field(..., description="User Email")
    password: str = Field(..., min_length=1, description="Password")


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User Email")
    password: str = Field(..., description="Password")


class LoginOrRegisterRequest(BaseModel):
    email: str = Field(..., description="User Email")
    password: str = Field(..., description="Password")
    role: str = Field(..., pattern="^(patient|doctor|admin)$", description="Role requested")
    name: Optional[str] = Field(None, description="Display Name (optional)")


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str


class LoginOrRegisterResponse(BaseModel):
    user: UserResponse
    created: bool
    role_overridden: bool


# --- Doctor & Slot Schemas ---
class DoctorResponse(BaseModel):
    user_id: str
    name: str
    email: str
    specialization: str
    working_days: str
    start_time: str
    end_time: str
    slot_minutes: int
    leave_days: str


class DoctorCreateRequest(BaseModel):
    name: str
    email: EmailStr
    password: Optional[str] = "doctor123"
    specialization: str
    working_days: str = "Mon,Tue,Wed,Thu,Fri"
    start_time: str = "09:00"
    end_time: str = "17:00"
    slot_minutes: int = 30


class DoctorUpdateRequest(BaseModel):
    specialization: Optional[str] = None
    working_days: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    slot_minutes: Optional[int] = None
    leave_days: Optional[List[str]] = None


class SlotsResponse(BaseModel):
    slots: List[str]
    is_on_leave: bool


# --- Appointment Schemas ---
class BookAppointmentRequest(BaseModel):
    patient_id: str
    doctor_id: str
    start_at: str
    symptoms: str


class PreVisitSummary(BaseModel):
    urgency_level: str
    chief_complaint: str
    suggested_questions: List[str]
    disclaimer: str


class PostVisitSummary(BaseModel):
    summary: str
    medication_schedule: List[str]
    follow_up_steps: List[str]
    disclaimer: str


class BookAppointmentResponse(BaseModel):
    appointment_id: str
    status: str
    previsit_summary: PreVisitSummary
    calendar: str


class CompleteAppointmentRequest(BaseModel):
    doctor_id: str
    doctor_notes: str
    prescription: str


class CancelAppointmentRequest(BaseModel):
    user_id: str
    role: str


# --- Notification Schemas ---
class NotificationItem(BaseModel):
    id: str
    appointment_id: Optional[str] = None
    user_id: str
    type: str
    channel: str
    status: str
    attempts: int
    last_error: Optional[str] = None
    payload: str
    next_attempt_at: Optional[str] = None
    created_at: str


class ProcessNotificationsResponse(BaseModel):
    processed_notifications: int
    processed_medication_reminders: int


# --- Dashboard Stats Schema ---
class DashboardStatsResponse(BaseModel):
    confirmed: int
    completed: int
    cancelled: int
    doctors: int
    patients: int
    notifications_queued: int
    notifications_sent: int
