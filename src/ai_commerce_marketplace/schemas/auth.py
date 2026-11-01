import re

from pydantic import BaseModel, EmailStr, Field, field_validator

PHONE_RE = re.compile(r"^01[0125][0-9]{8}$")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str
    password: str = Field(min_length=8, max_length=128)
    # Only customer is allowed here; sellers are created separately (see service).
    role: str = "customer"

    @field_validator("full_name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("full_name must not be blank")
        return v.strip()

    @field_validator("phone")
    @classmethod
    def _valid_egyptian_phone(cls, v: str) -> str:
        if not PHONE_RE.match(v):
            raise ValueError("invalid Egyptian mobile number")
        return v

    @field_validator("password")
    @classmethod
    def _strong_enough(cls, v: str) -> str:
        if not (any(c.isalpha() for c in v) and any(c.isdigit() for c in v)):
            raise ValueError("password must contain letters and digits")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Public user view. Never includes password_hash."""

    id: int
    role: str
    full_name: str
    email: str
    phone: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
