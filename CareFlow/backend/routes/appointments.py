"""
Appointment lifecycle routes: booking, listing, cancellation, and clinical completion.
"""
from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Dict, Any
from backend.schemas import (
    BookAppointmentRequest, BookAppointmentResponse,
    CompleteAppointmentRequest, CancelAppointmentRequest
)
from backend import services

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


@router.get("")
def list_appointments(
    user_id: str = Query(..., description="User ID requesting appointments"),
    role: str = Query(..., pattern="^(patient|doctor|admin)$", description="User role")
):
    user = {"id": user_id, "role": role}
    return services.list_appointments(user)


@router.post("/book", response_model=BookAppointmentResponse, status_code=status.HTTP_201_CREATED)
def book_appointment(req: BookAppointmentRequest):
    try:
        result = services.book_appointment(
            patient_id=req.patient_id,
            doctor_id=req.doctor_id,
            start_at=req.start_at,
            symptoms=req.symptoms
        )
        return result
    except services.BookingConflict as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except services.AppError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{appointment_id}/cancel")
def cancel_appointment(appointment_id: str, req: CancelAppointmentRequest):
    try:
        user = {"id": req.user_id, "role": req.role}
        services.cancel_appointment(appointment_id, user)
        return {"appointment_id": appointment_id, "status": "CANCELLED", "message": "Appointment cancelled successfully."}
    except services.AppError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{appointment_id}/complete")
def complete_appointment(appointment_id: str, req: CompleteAppointmentRequest):
    try:
        summary = services.complete_appointment(
            appointment_id=appointment_id,
            doctor_id=req.doctor_id,
            doctor_notes=req.doctor_notes,
            prescription=req.prescription
        )
        return {
            "appointment_id": appointment_id,
            "status": "COMPLETED",
            "postvisit_summary": summary
        }
    except services.AppError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
