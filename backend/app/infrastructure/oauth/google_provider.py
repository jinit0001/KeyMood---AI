"""
Google OAuth2 provider adapter — verifies the `id_token` a client submits
to POST /auth/google (API_SPEC.md §1). Uses Google's official verification
library against GOOGLE_CLIENT_ID; never trusts an unverified token.

Implements app.domain.auth.ports.OAuthProvider (structurally).
"""
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.exceptions import InvalidGoogleTokenError
from app.domain.auth.entities import OAuthUserInfo


class GoogleOAuthProvider:
    def __init__(self, client_id: str):
        self._client_id = client_id

    def verify_id_token(self, raw_id_token: str) -> OAuthUserInfo:
        if not self._client_id:
            raise InvalidGoogleTokenError("Google OAuth is not configured.")
        try:
            payload = google_id_token.verify_oauth2_token(
                raw_id_token, google_requests.Request(), self._client_id
            )
        except ValueError as exc:  # google-auth raises ValueError on any verification failure
            raise InvalidGoogleTokenError() from exc

        if payload.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            raise InvalidGoogleTokenError()

        return OAuthUserInfo(
            provider_user_id=payload["sub"],
            email=payload["email"],
            email_verified=bool(payload.get("email_verified", False)),
            display_name=payload.get("name"),
        )
