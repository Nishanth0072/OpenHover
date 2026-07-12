from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class RegisterInitiateRequest(BaseModel):
    """Payload to initiate registration with email and password."""

    email: EmailStr = Field(
        ...,
        description="User's email address.",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 characters, must contain uppercase, lowercase, and digit).",
        examples=["SecurePass123"],
    )


class RegisterInitiateResponse(BaseModel):
    """Response returned upon initiating registration."""

    registration_token: str = Field(
        ...,
        description="Unique registration session token.",
    )
    message: str = Field(
        ...,
        description="Success message.",
    )



class RegisterRequest(BaseModel):
    """Initiate registration with email, password, and verified OTP."""

    email: EmailStr = Field(
        ...,
        description="User's email address.",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 characters, must contain uppercase, lowercase, and digit).",
        examples=["SecurePass123"],
    )
    otp: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit OTP code received via email.",
        examples=["482915"],
    )


class RegisterVerifyRequest(BaseModel):
    """Step 2: Verify registration OTP to create the account."""

    registration_token: str = Field(
        ...,
        description="Unique registration session token returned from step 1.",
    )
    email: EmailStr = Field(
        ...,
        description="Email address used during registration initiation.",
        examples=["user@example.com"],
    )
    otp: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit OTP code received via email.",
        examples=["482915"],
    )


class LoginRequest(BaseModel):
    """User login payload (step 1 — password validation)."""

    email: EmailStr = Field(
        ...,
        description="User's email address.",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="User's password.",
        examples=["SecurePass123"],
    )


class VerifyLoginOTPRequest(BaseModel):
    """Step 2 of MFA login — verify the OTP with the temporary MFA token."""

    mfa_token: str = Field(
        ...,
        description="Short-lived MFA challenge token received from POST /auth/login.",
    )
    otp: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit OTP code received via email.",
        examples=["482915"],
    )


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str = Field(
        ...,
        description="Short-lived JWT access token.",
    )
    refresh_token: str = Field(
        ...,
        description="Long-lived JWT refresh token.",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer').",
    )


class LoginMFAChallengeResponse(BaseModel):
    """Response from POST /auth/login when MFA OTP is required (step 1)."""

    otp_required: bool = Field(
        default=True,
        description="Always True — indicates the client must complete OTP verification.",
    )
    mfa_token: str = Field(
        ...,
        description="Short-lived MFA challenge JWT. Send this to POST /auth/login/verify.",
    )
    email: str = Field(
        ...,
        description="The email address the OTP was sent to.",
    )


class UserProfileResponse(BaseModel):
    """User profile information."""

    id: str
    email: str
    is_verified: bool
    plan: str
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None
    phone_number: str | None = None
    bio: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileUpdateRequest(BaseModel):
    """Payload to update user profile information."""

    username: str | None = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    first_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, max_length=50)
    avatar_url: str | None = Field(None, max_length=500)
    phone_number: str | None = Field(None, max_length=20)
    bio: str | None = Field(None, max_length=1000)


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str


class LogoutRequest(BaseModel):
    """Optional payload for single-session logout."""

    refresh_token: str | None = Field(
        default=None,
        description="The refresh token for the current session. "
                    "If provided, it will be revoked alongside the access token.",
    )
