"""
Authentication routes for patient, doctor, and admin accounts.
"""
from fastapi import APIRouter, HTTPException, status
from backend.schemas import (
    UserRegisterRequest, UserLoginRequest, LoginOrRegisterRequest,
    UserResponse, LoginOrRegisterResponse
)
from backend import services

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegisterRequest):
    try:
        user = services.register_patient(req.name, req.email, req.password)
        return user
    except services.AppError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=UserResponse)
def login(req: UserLoginRequest):
    user = services.login(req.email, req.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    return user


@router.post("/login-or-register", response_model=LoginOrRegisterResponse)
def login_or_register(req: LoginOrRegisterRequest):
    try:
        user, created, overridden = services.login_or_register(
            email=req.email,
            password=req.password,
            role=req.role,
            name=req.name
        )
        return {
            "user": user,
            "created": created,
            "role_overridden": overridden
        }
    except services.AppError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
