import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

PHONE_RE = re.compile(r"^01[0125][0-9]{8}$")


def _not_blank(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("must not be blank")
    return v


class AddressIn(BaseModel):
    label: str | None = Field(default=None, max_length=50)
    recipient_name: str = Field(max_length=100)
    phone: str
    governorate: str = Field(max_length=50)
    city: str = Field(max_length=50)
    street_address: str = Field(max_length=300)
    is_default: bool = False

    @field_validator("recipient_name", "governorate", "city", "street_address")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        return _not_blank(v)

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, v: str) -> str:
        if not PHONE_RE.match(v):
            raise ValueError("invalid Egyptian mobile number")
        return v


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str | None
    recipient_name: str
    phone: str
    governorate: str
    city: str
    street_address: str
    is_default: bool
