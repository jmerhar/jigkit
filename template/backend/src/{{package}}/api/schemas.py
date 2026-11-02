"""Every request and response body. The interface's TypeScript types are generated from these
through the OpenAPI schema (`make openapi`), so a change here shows up there as a type error."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

#: The languages the interface is written in; a user's choice must be one of them.
LANGUAGES = ("en", "pt-PT")


class Out(BaseModel):
    """A response read straight from a table's row."""

    model_config = ConfigDict(from_attributes=True)


class SetupState(BaseModel):
    """Whether the first account still has to be made."""

    required: bool


class SetupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(max_length=200)
    language: str | None = None


class LoginIn(BaseModel):
    login: str = Field(max_length=100)
    password: str = Field(max_length=200)


class Me(BaseModel):
    """The user logged in, as the interface sees them."""

    id: int
    name: str
    login: str
    language: str | None
    #: Whether a test notification can be sent: NOTIFY_URL is set.
    notifications: bool


class MeUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    language: str | None = None


class PasswordChange(BaseModel):
    current: str = Field(max_length=200)
    new: str = Field(max_length=200)


class SessionOut(Out):
    id: int
    created_at: datetime
    last_seen_at: datetime
    user_agent: str
    current: bool = False


class PasskeyOut(Out):
    id: int
    label: str
    created_at: datetime
    last_used_at: datetime | None


class PasskeyIn(BaseModel):
    """A passkey to add: the authenticator's answer, as the browser serialises it."""

    label: str = Field(min_length=1, max_length=100)
    credential: dict[str, Any]


class PasskeyLogin(BaseModel):
    credential: dict[str, Any]


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field("", max_length=20_000)


class NoteOut(Out):
    id: int
    title: str
    body: str
    created_at: datetime
    updated_at: datetime
