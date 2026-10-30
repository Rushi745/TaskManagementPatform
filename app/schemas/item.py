from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import Base, Title, check_date

Status = Literal["open", "in_progress", "blocked", "done", "dropped"]
Priority = Literal["low", "medium", "high"]


class ItemCreate(Base):
    title: Title
    description: str = Field("", max_length=2000)
    owner_id: str | None = None
    due_date: str | None = None
    priority: Priority = "medium"
    meeting_id: str

    @field_validator("due_date")
    @classmethod
    def _due(cls, v):
        return check_date(v)


class ItemUpdate(Base):
    status: Status | None = None
    owner_id: str | None = None
    due_date: str | None = None
    priority: Priority | None = None
    note: str | None = Field(None, max_length=500)

    @field_validator("due_date")
    @classmethod
    def _due(cls, v):
        return check_date(v)


class ItemClose(Base):
    status: Literal["done", "dropped"]
    outcome: str | None = Field(None, max_length=2000)


class ItemReopen(Base):
    note: str | None = Field(None, max_length=500)
