from datetime import datetime

from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    user_id: str
    display_name: str
    avatar_url: str | None
    bio: str | None
    timezone: str
    updated_at: datetime


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_url: str | None = None
    bio: str | None = Field(default=None, max_length=300)
    timezone: str | None = Field(default=None, max_length=64)
