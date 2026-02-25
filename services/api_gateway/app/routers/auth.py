"""API Gateway — Auth routes (login / register stubs)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth import (
    STUB_USERS,
    create_access_token,
    create_driver,
    get_current_user,
    list_drivers,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    name: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "client"
    name: str = ""


class RegisterResponse(BaseModel):
    message: str
    username: str


class DriverCreateRequest(BaseModel):
    username: str
    password: str
    name: str = ""


class DriverResponse(BaseModel):
    username: str
    name: str
    role: str = "driver"


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    """Authenticate and return a JWT access token."""
    user = STUB_USERS.get(payload.username)
    if not user or user["password"] != payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(
        data={
            "sub": payload.username,
            "role": user["role"],
            "name": user["name"],
        }
    )

    return LoginResponse(
        access_token=token,
        username=payload.username,
        role=user["role"],
        name=user["name"],
    )


@router.post("/register", response_model=RegisterResponse)
async def register(payload: RegisterRequest) -> RegisterResponse:
    """Stub user registration (adds to in-memory store for prototype)."""
    if payload.username in STUB_USERS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{payload.username}' already exists",
        )

    STUB_USERS[payload.username] = {
        "password": payload.password,
        "role": payload.role,
        "name": payload.name or payload.username,
    }

    return RegisterResponse(
        message="User registered successfully",
        username=payload.username,
    )


@router.get("/drivers", response_model=list[DriverResponse])
async def get_drivers(user: dict = Depends(get_current_user)) -> list[DriverResponse]:
    """List all drivers (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can list drivers",
        )
    return [DriverResponse(**driver) for driver in list_drivers()]


@router.post("/drivers", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
async def post_driver(
    payload: DriverCreateRequest,
    user: dict = Depends(get_current_user),
) -> DriverResponse:
    """Create a new driver account (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can create drivers",
        )

    try:
        driver = create_driver(
            username=payload.username,
            password=payload.password,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return DriverResponse(**driver)
