"""
Auth routes. Paths, methods, status codes, and error codes match
API_SPEC.md §1 exactly — no contract changes.
"""
from fastapi import APIRouter, Depends, Response, status

from app.api.v1.auth.dependencies import get_auth_service, get_current_user
from app.api.v1.auth.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleAuthRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.domain.auth.entities import User
from app.services.auth_service import AuthService, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])

_settings = get_settings()


def _token_response(pair: TokenPair) -> TokenResponse:
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("register", _settings.RATE_LIMIT_REGISTER_PER_MIN))],
)
def register(payload: RegisterRequest, service: AuthService = Depends(get_auth_service)) -> RegisterResponse:
    user = service.register(payload.email, payload.password, payload.display_name)
    return RegisterResponse(user_id=str(user.id), email_verification_sent=not user.email_verified)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limiter("login", _settings.RATE_LIMIT_LOGIN_PER_MIN))],
)
def login(payload: LoginRequest, service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    pair = service.login(payload.email, payload.password)
    return _token_response(pair)


@router.post("/verify-email", response_model=VerifyEmailResponse)
def verify_email(payload: VerifyEmailRequest, service: AuthService = Depends(get_auth_service)) -> VerifyEmailResponse:
    service.verify_email(payload.token)
    return VerifyEmailResponse(verified=True)


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    dependencies=[Depends(rate_limiter("forgot_password", _settings.RATE_LIMIT_FORGOT_PASSWORD_PER_MIN))],
)
def forgot_password(
    payload: ForgotPasswordRequest, service: AuthService = Depends(get_auth_service)
) -> ForgotPasswordResponse:
    # Always 200 regardless of account existence — API_SPEC.md is explicit
    # this must not reveal whether an email is registered.
    service.request_password_reset(payload.email)
    return ForgotPasswordResponse(reset_email_sent=True)


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    payload: ResetPasswordRequest, service: AuthService = Depends(get_auth_service)
) -> ResetPasswordResponse:
    service.reset_password(payload.token, payload.new_password)
    return ResetPasswordResponse(reset=True)


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleAuthRequest, service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    pair = service.login_with_google(payload.id_token)
    return _token_response(pair)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    pair = service.refresh(payload.refresh_token)
    return _token_response(pair)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: RefreshRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    service.logout(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
