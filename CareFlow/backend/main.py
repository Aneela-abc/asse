"""
CareFlow Backend REST API Server.
Built with FastAPI, featuring interactive Swagger documentation and relational SQLite database.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from database.db import init_database
from backend.services import BookingConflict, AppError, run_background_jobs_if_due
from backend.routes import auth, doctors, appointments, notifications, dashboard, calendar


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize relational database tables from schema.sql and seed sample data
    init_database()
    # Run initial check for background jobs
    run_background_jobs_if_due()
    yield


app = FastAPI(
    title="CareFlow Healthcare API",
    description="Dedicated Backend REST API for CareFlow Appointment & Follow-up Manager with double-booking safety, AI summaries, and notification queue.",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
@app.exception_handler(BookingConflict)
async def booking_conflict_handler(request: Request, exc: BookingConflict):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc), "error_type": "BookingConflict"}
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc), "error_type": "AppError"}
    )


# Register Route Modules
app.include_router(auth.router)
app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(notifications.router)
app.include_router(dashboard.router)
app.include_router(calendar.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "CareFlow Backend API"}


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "CareFlow Healthcare API",
        "version": "2.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }
