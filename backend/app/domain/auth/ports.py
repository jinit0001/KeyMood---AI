"""
Additional Auth domain ports (interfaces), per LLD.md §4-5: "an abstract
interface in domain/, a concrete implementation in ai_engines/ or
infrastructure/." EmailSender and OAuthProvider were initially defined
inside infrastructure/, which AuthService then imported directly — a
layering violation (services must depend only on domain interfaces).
Corrected here.
"""
from typing import Protocol

from app.domain.auth.entities import OAuthUserInfo


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body_text: str, body_html: str | None = None) -> None: ...


class OAuthProvider(Protocol):
    def verify_id_token(self, raw_id_token: str) -> OAuthUserInfo: ...
