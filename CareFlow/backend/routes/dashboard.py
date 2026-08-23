"""
Admin dashboard statistics route.
"""
from fastapi import APIRouter
from backend.schemas import DashboardStatsResponse
from backend import services

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
def get_stats():
    return services.dashboard_stats()
