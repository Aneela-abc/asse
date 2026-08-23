"""
Notifications and queue processing routes.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List
from backend.schemas import NotificationItem, ProcessNotificationsResponse
from backend import services

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationItem])
def list_notifications(user_id: str = Query(..., description="User ID to fetch notifications for")):
    return services.list_notifications(user_id)


@router.post("/process", response_model=ProcessNotificationsResponse)
def trigger_process_queue():
    notifs = services.process_notifications()
    reminders = services.process_medication_reminders()
    return {
        "processed_notifications": notifs,
        "processed_medication_reminders": reminders
    }
