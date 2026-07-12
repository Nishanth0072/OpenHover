"""
Open-Brain Backend — Authentication Router

Endpoints: register/send-otp, register, login (MFA step 1),
           login/verify (MFA step 2), refresh, logout.
"""

import re
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from loguru import logger

from app.database import get_db
from app.redis import get_redis
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    RegisterInitiateRequest,
    RegisterInitiateResponse,
    RegisterVerifyRequest,
    LoginRequest,
    VerifyLoginOTPRequest,
    TokenResponse,
    LoginMFAChallengeResponse,
    MessageResponse,
    ErrorResponse,
    LogoutRequest,
)
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_mfa_token,
    decode_token,
    generate_otp,
    store_otp,
    verify_otp,
    store_refresh_token,
    revoke_refresh_token,
    is_refresh_token_valid,
    validate_token_version,
    check_login_rate_limit,
    increment_login_attempts,
    reset_login_attempts,
    revoke_all_user_tokens,
    revoke_current_session,
)
from app.services.email_service import send_otp_email

router = APIRouter()

# Password strength regex: at least 1 uppercase, 1 lowercase, 1 digit
PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")

# Dummy bcrypt hash used when user is not found, to prevent timing-based email enumeration
_DUMMY_HASH = "$2b$12$LJ3m4ys3Lg2V45JGv3eOGOaIyUCfRkWmB0aNGFq6xnPcGYdq9vKXi"


# ---------------------------------------------------------------------------
# Registration — Step 1: Send OTP
# ---------------------------------------------------------------------------

@router.post(
    "/register/send-otp",
    response_model=RegisterInitiateResponse,
    status_code=status.HTTP_200_OK,
    summary="Send registration OTP",
    description="Generates a 6-digit OTP and sends it to the provided email. "
                "The OTP is valid for 5 minutes.",
    responses={
        409: {"model": ErrorResponse, "description": "Email already registered"},
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
)
async def send_registration_otp(
    request: Request,
    payload: RegisterInitiateRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Generate and email an OTP for email verification during registration."""
    # Rate limit by client IP
    client_ip = request.client.host if request.client else "unknown"
    if not await check_login_rate_limit(redis_client, f"otp:register:{client_ip}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please try again later.",
        )

    # Validate password strength
    if not PASSWORD_PATTERN.match(payload.password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one uppercase letter, one lowercase letter, and one digit.",
        )

    # Check if the email is already registered
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Generate the OTP and registration token
    otp = generate_otp()
    registration_token = str(uuid.uuid4())

    try:
        await send_otp_email(payload.email, otp, purpose="verification")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    # Hash and store registration session data grouped in Redis for 5 minutes
    pwd_hash = hash_password(payload.password)
    session_data = {
        "email": payload.email,
        "password_hash": pwd_hash,
        "otp": otp,
    }
    await redis_client.setex(
        f"register:pending:{registration_token}",
        300,  # 5 minutes TTL
        json.dumps(session_data),
    )

    # Increment rate-limit counter (reuses login rate-limit infra)
    await increment_login_attempts(redis_client, f"otp:register:{client_ip}")

    return RegisterInitiateResponse(
        registration_token=registration_token,
        message="OTP sent to your email address.",
    )


# ---------------------------------------------------------------------------
# Registration — Step 2: Verify OTP & Create Account
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user account after verifying the email OTP. "
                "Returns JWT tokens on success.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or expired OTP"},
        409: {"model": ErrorResponse, "description": "Email already registered"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def register(
    request: Request,
    payload: RegisterVerifyRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Create a new user account after verifying the OTP."""
    # Rate limit registration by client IP
    client_ip = request.client.host if request.client else "unknown"
    if not await check_login_rate_limit(redis_client, f"register:{client_ip}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
        )

    # Fetch temporary registration data from Redis
    session_key = f"register:pending:{payload.registration_token}"
    session_data_bytes = await redis_client.get(session_key)
    if not session_data_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration session expired or invalid. Please request a new OTP.",
        )

    # Parse session data
    try:
        session_data = json.loads(session_data_bytes)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse registration session data.",
        )

    stored_email = session_data.get("email")
    stored_password_hash = session_data.get("password_hash")
    stored_otp = session_data.get("otp")

    # Validate that email matches what was initiated
    if payload.email != stored_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address does not match the registration session.",
        )

    # Verify the OTP
    if payload.otp != stored_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new one.",
        )

    # Check for duplicate email in database
    result = await db.execute(select(User).where(User.email == payload.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        # Clean up Redis since this account is already registered
        await redis_client.delete(session_key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Create user (verified because OTP was valid)
    user = User(
        email=payload.email,
        password_hash=stored_password_hash,
        is_verified=True,
    )
    db.add(user)
    await db.flush()

    # Clean up temporary registration data from Redis
    await redis_client.delete(session_key)

    # Generate tokens
    access_token = create_access_token(user.id, user.token_version)
    refresh_token_str, refresh_expires = create_refresh_token(user.id, user.token_version)

    # Store refresh token hash in DB
    await store_refresh_token(db, user.id, refresh_token_str, refresh_expires)

    await db.commit()

    logger.info(f"New user registered: {user.email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
    )


# ---------------------------------------------------------------------------
# Login — Step 1: Validate Password & Send OTP
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=LoginMFAChallengeResponse,
    summary="Login (MFA step 1)",
    description="Validates the user's password and sends a login OTP. "
                "Returns a short-lived MFA challenge token.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        429: {"model": ErrorResponse, "description": "Too many login attempts"},
    },
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Authenticate user password and send MFA OTP (step 1 of 2)."""
    # Check rate limit
    if not await check_login_rate_limit(redis_client, payload.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again in 15 minutes.",
        )

    # Find user
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Always run bcrypt verification to prevent timing-based email enumeration
    password_hash = user.password_hash if user else _DUMMY_HASH
    password_valid = verify_password(payload.password, password_hash)

    if not user or not password_valid:
        await increment_login_attempts(redis_client, payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Password is valid — generate & send OTP
    otp = generate_otp()
    await store_otp(redis_client, "login", payload.email, otp)
    try:
        await send_otp_email(payload.email, otp, purpose="login")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    # Create short-lived MFA challenge token
    mfa_token = create_mfa_token(user.id, user.email)

    logger.info(f"MFA challenge issued for user: {user.email}")

    return LoginMFAChallengeResponse(
        otp_required=True,
        mfa_token=mfa_token,
        email=user.email,
    )


# ---------------------------------------------------------------------------
# Login — Step 2: Verify OTP & Issue Tokens
# ---------------------------------------------------------------------------

@router.post(
    "/login/verify",
    response_model=TokenResponse,
    summary="Verify login OTP (MFA step 2)",
    description="Validates the OTP and MFA challenge token. Returns the "
                "final JWT access and refresh token pair.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or expired OTP"},
        401: {"model": ErrorResponse, "description": "Invalid MFA token"},
    },
)
async def verify_login_otp(
    payload: VerifyLoginOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Verify MFA OTP and issue final JWT tokens (step 2 of 2)."""
    # Decode the MFA challenge token
    mfa_payload = decode_token(payload.mfa_token)
    if mfa_payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA token is invalid or expired. Please log in again.",
        )

    if mfa_payload.get("type") != "mfa_challenge":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Expected MFA challenge token.",
        )

    user_id = mfa_payload.get("sub")
    email = mfa_payload.get("email")

    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed MFA token.",
        )

    # Verify the OTP
    otp_valid = await verify_otp(redis_client, "login", email, payload.otp)
    if not otp_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new one.",
        )

    # Fetch user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    # Reset login rate limit on successful MFA
    await reset_login_attempts(redis_client, email)

    # Generate final tokens
    access_token = create_access_token(user.id, user.token_version)
    refresh_token_str, refresh_expires = create_refresh_token(user.id, user.token_version)

    # Store refresh token
    await store_refresh_token(db, user.id, refresh_token_str, refresh_expires)

    await db.commit()

    logger.info(f"User logged in (MFA verified): {user.email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
    )


# ---------------------------------------------------------------------------
# Token Refresh
# ---------------------------------------------------------------------------

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh tokens",
    description="Exchange a valid refresh token for a new token pair. Send the refresh token in the Authorization: Bearer header.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"},
    },
)
async def refresh_tokens(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Token rotation: validates refresh token, issues new pair, revokes old."""
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token in Authorization header.",
        )

    old_token = auth_header.replace("Bearer ", "")

    # Decode refresh token
    payload = decode_token(old_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Expected refresh token.",
        )

    user_id = payload.get("sub")
    token_version = payload.get("token_version")

    # Validate token version
    is_valid = await validate_token_version(user_id, token_version, redis_client, db)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked. Please log in again.",
        )

    # Check if refresh token is still valid in DB
    if not await is_refresh_token_valid(db, old_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or is invalid.",
        )

    # Revoke old refresh token
    await revoke_refresh_token(db, old_token)

    # Fetch user for current token_version
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    # Generate new token pair
    new_access_token = create_access_token(user.id, user.token_version)
    new_refresh_token, new_refresh_expires = create_refresh_token(user.id, user.token_version)

    # Store new refresh token
    await store_refresh_token(db, user.id, new_refresh_token, new_refresh_expires)

    await db.commit()

    logger.info(f"Tokens refreshed for user {user.email}")

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


# ---------------------------------------------------------------------------
# Logout (Single Session)
# ---------------------------------------------------------------------------

@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (current session)",
    description=(
        "Logs out the current session only. Blacklists the current access token "
        "and optionally revokes the provided refresh token. Other devices remain logged in."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def logout(
    payload: LogoutRequest = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Log out the current session (single device)."""
    # Extract jti and exp from the decoded access token payload
    token_payload = getattr(current_user, "_token_payload", {})
    jti = token_payload.get("jti")
    exp = token_payload.get("exp")

    refresh_token_raw = payload.refresh_token if payload else None

    if jti and exp:
        await revoke_current_session(
            db, redis_client, jti, exp, refresh_token_raw
        )

    await db.commit()
    logger.info(f"User logged out (single session): {current_user.email}")
    return MessageResponse(message="Successfully logged out.")


# ---------------------------------------------------------------------------
# Logout All Devices
# ---------------------------------------------------------------------------

@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Logout all devices",
    description=(
        "Logs out the user from ALL devices by bumping the token version. "
        "All existing access and refresh tokens are instantly invalidated."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Log out the user from all devices."""
    await revoke_all_user_tokens(db, redis_client, current_user.id)
    await db.commit()
    logger.info(f"User logged out (all devices): {current_user.email}")
    return MessageResponse(message="Successfully logged out from all devices.")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="email is required.")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        # Avoid user enumeration: return success even if email not found
        return MessageResponse(message="Password reset OTP sent to your email.")

    otp = generate_otp()
    await store_otp(redis_client, "reset", email, otp)
    logger.info(f"[FORGOT PASSWORD] Generated reset OTP for {email}: {otp}")

    return MessageResponse(message="Password reset OTP sent to your email.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    email = payload.get("email")
    otp = payload.get("otp")
    new_password = payload.get("new_password")

    if not email or not otp or not new_password:
        raise HTTPException(status_code=400, detail="Missing required parameters.")

    # Verify the OTP
    is_valid = await verify_otp(redis_client, "reset", email, otp)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.password_hash = hash_password(new_password)
    user.token_version += 1  # Invalidate all current sessions
    await db.commit()

    return MessageResponse(message="Password reset successfully.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_password = payload.get("current_password")
    new_password = payload.get("new_password")

    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="current_password and new_password are required.")

    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect current password.")

    current_user.password_hash = hash_password(new_password)
    current_user.token_version += 1  # Invalidate other sessions
    await db.commit()

    return MessageResponse(message="Password changed successfully.")


@router.post("/resend-otp")
async def resend_otp(
    payload: dict,
    redis_client: aioredis.Redis = Depends(get_redis),
):
    email = payload.get("email")
    purpose = payload.get("purpose", "register")
    if not email:
        raise HTTPException(status_code=400, detail="email is required.")

    otp = generate_otp()
    if purpose == "register":
        reg_token = str(uuid.uuid4())
        session_key = f"register:pending:{reg_token}"
        # Store dummy session for registration OTP mock
        await redis_client.setex(
            session_key,
            300,
            json.dumps({"email": email, "password_hash": "dummy_hash", "otp": otp})
        )
        logger.info(f"[RESEND REGISTER OTP] Token: {reg_token}, OTP: {otp}")
        return {"registration_token": reg_token, "message": "OTP resent."}
    else:
        await store_otp(redis_client, "login", email, otp)
        logger.info(f"[RESEND LOGIN OTP] OTP: {otp}")
        return {"message": "OTP resent."}


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    email = payload.get("email")
    otp = payload.get("otp")
    if not email or not otp:
        raise HTTPException(status_code=400, detail="email and otp are required.")

    is_valid = await verify_otp(redis_client, "register", email, otp)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired email verification OTP.")

    # Find user and mark as verified
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        user.is_verified = True
        await db.commit()

    return MessageResponse(message="Email verified successfully.")


@router.get("/google/login")
async def google_login():
    return {
        "redirect_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=mock_client_id&response_type=code&redirect_uri=http://localhost:8000/auth/google/callback&scope=openid%20email"
    }


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(
    code: str = "mock_code",
    db: AsyncSession = Depends(get_db),
):
    # Mock OAuth handler: create or fetch user with mock email
    mock_email = "google_user@example.com"
    result = await db.execute(select(User).where(User.email == mock_email))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email=mock_email,
            password_hash=hash_password(str(uuid.uuid4())),
            is_verified=True,
            plan="free"
        )
        db.add(user)
        await db.flush()

    access_token = create_access_token(user.id, user.token_version)
    refresh_token, refresh_expires = create_refresh_token(user.id, user.token_version)
    await store_refresh_token(db, user.id, refresh_token, refresh_expires)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/2fa/enable")
async def enable_2fa(
    current_user: User = Depends(get_current_user),
):
    return {
        "secret": "JBSWY3DPEHPK3PXP",
        "qr_code_url": f"otpauth://totp/OpenBrain:{current_user.email}?secret=JBSWY3DPEHPK3PXP&issuer=OpenBrain"
    }


@router.post("/2fa/disable", response_model=MessageResponse)
async def disable_2fa(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    code = payload.get("code")
    if not code or len(code) != 6:
        raise HTTPException(status_code=400, detail="Invalid 2FA code.")
    return MessageResponse(message="2FA disabled.")
