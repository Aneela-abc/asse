"""
Doctor listing, profile management, and available slot discovery routes.
"""
from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional
from backend.schemas import (
    DoctorResponse, DoctorCreateRequest, DoctorUpdateRequest, SlotsResponse
)
from backend import services

router = APIRouter(prefix="/api/doctors", tags=["Doctors & Schedules"])


@router.get("", response_model=List[DoctorResponse])
def list_doctors(specialization: str = Query("", description="Filter doctors by specialization")):
    return services.list_doctors(specialization_query=specialization)


@router.get("/{doctor_id}/slots", response_model=SlotsResponse)
def get_slots(doctor_id: str, date: str = Query(..., description="Date in YYYY-MM-DD format")):
    try:
        slots, is_on_leave = services.get_slots(doctor_id, date)
        return {"slots": slots, "is_on_leave": is_on_leave}
    except services.AppError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", status_code=status.HTTP_201_CREATED)
def admin_create_doctor(req: DoctorCreateRequest):
    try:
        doc_id = services.admin_create_doctor(
            name=req.name,
            email=req.email,
            password=req.password or 'doctor123',
            specialization=req.specialization,
            working_days=req.working_days,
            start_time=req.start_time,
            end_time=req.end_time,
            slot_minutes=req.slot_minutes
        )
        return {"doctor_id": doc_id, "message": "Doctor created successfully."}
    except services.AppError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{doctor_id}")
def admin_update_doctor(doctor_id: str, req: DoctorUpdateRequest):
    try:
        affected = services.admin_update_doctor(
            doctor_id=doctor_id,
            specialization=req.specialization,
            working_days=req.working_days,
            start_time=req.start_time,
            end_time=req.end_time,
            slot_minutes=req.slot_minutes,
            leave_days=req.leave_days
        )
        return {
            "doctor_id": doctor_id,
            "affected_cancelled_appointments": affected,
            "message": f"Profile updated. {len(affected)} conflicting appointments cancelled and notified."
        }
    except services.AppError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
