from typing import Annotated

from pydantic import Field, StringConstraints, field_validator

from app.schemas.common import StrictSchema

PhoneNumber = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^(?:\+[1-9][0-9]{7,14}|[6-9][0-9]{9})$",
        min_length=10,
        max_length=16,
    ),
]


class OTPRequest(StrictSchema):
    phone: PhoneNumber

    @field_validator("phone")
    @classmethod
    def canonical_phone(cls, value: str) -> str:
        from app.core.phone import canonicalize_phone
        return canonicalize_phone(value)


class OTPVerify(StrictSchema):
    phone: PhoneNumber
    otp: str = Field(pattern=r"^[0-9]{4,10}$")

    @field_validator("phone")
    @classmethod
    def canonical_phone(cls, value: str) -> str:
        from app.core.phone import canonicalize_phone
        return canonicalize_phone(value)


class TokenResponse(StrictSchema):
    access_token: str = Field(min_length=1)
    token_type: str = "bearer"
    expires_in: int = Field(gt=0, description="Token lifetime in seconds")


class FirebaseTokenVerify(StrictSchema):
    id_token: str = Field(min_length=1, description="Firebase ID token from client SDK")


class EmailLoginRequest(StrictSchema):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=128)
