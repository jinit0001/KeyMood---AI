from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)


class RegisterResponse(BaseModel):
    user_id: str
    email_verification_sent: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyEmailResponse(BaseModel):
    verified: bool


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    reset_email_sent: bool


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=1, max_length=128)


class ResetPasswordResponse(BaseModel):
    reset: bool


class GoogleAuthRequest(BaseModel):
    id_token: str


class RefreshRequest(BaseModel):
    refresh_token: str
