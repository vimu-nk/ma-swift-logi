"""API Gateway — JWT authentication utilities."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

security = HTTPBearer()

ALGORITHM = "HS256"

# Stub users for prototype (in production, use a user DB)
STUB_USERS = {
    # 5 Clients
    "client1": {"password": "password123", "role": "client", "name": "Client A"},
    "client2": {"password": "password123", "role": "client", "name": "Client B"},
    "client3": {"password": "password123", "role": "client", "name": "Client C"},
    "client4": {"password": "password123", "role": "client", "name": "Client D"},
    "client5": {"password": "password123", "role": "client", "name": "Client E"},
    # 3 Drivers
    "driver1": {"password": "password123", "role": "driver", "name": "Driver Kamal"},
    "driver2": {"password": "password123", "role": "driver", "name": "Driver Nimal"},
    "driver3": {"password": "password123", "role": "driver", "name": "Driver Sunimal"},
    # 1 Admin
    "admin": {"password": "admin123", "role": "admin", "name": "System Admin"},
}


def list_drivers() -> list[dict[str, str]]:
    """Return all driver users from the in-memory stub store."""
    drivers: list[dict[str, str]] = []
    for username, data in STUB_USERS.items():
        if data.get("role") == "driver":
            drivers.append(
                {
                    "username": username,
                    "name": data.get("name", username),
                    "role": "driver",
                }
            )
    drivers.sort(key=lambda d: d["username"])
    return drivers


def create_driver(*, username: str, password: str, name: str) -> dict[str, str]:
    """Create a driver user in the in-memory stub store."""
    if username in STUB_USERS:
        raise ValueError(f"User '{username}' already exists")

    STUB_USERS[username] = {
        "password": password,
        "role": "driver",
        "name": name or username,
    }

    return {
        "username": username,
        "name": STUB_USERS[username]["name"],
        "role": "driver",
    }


def create_access_token(data: dict[str, Any], expires_minutes: int = 60) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """FastAPI dependency — extract and validate the current user from JWT."""
    payload = verify_token(credentials.credentials)
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return {
        "username": username,
        "role": payload.get("role", "client"),
        "name": payload.get("name", ""),
    }
