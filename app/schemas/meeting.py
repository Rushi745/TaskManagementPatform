from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import Base, Title, check_date, require_date


class Decision(Base):
    text: str = Field(min_length=3, max_length=500)
    made_by: str | None = None


def _clean_agenda(v):
    return [s.strip() for s in v if s and s.strip()] if v is not None else v


class MeetingCreate(Base):
    type: Literal["meeting", "handover"] = "meeting"
    title: Title
    date: str
    agenda: list[str] = []
    participant_ids: list[str] = []
    raw_notes: str = Field("", max_length=20000)
    from_person_id: str | None = None
    to_person_id: str | None = None

    @field_validator("date")
    @classmethod
    def _date(cls, v):
        return require_date(v)

    @field_validator("agenda")
    @classmethod
    def _agenda(cls, v):
        return _clean_agenda(v)

    @model_validator(mode="after")
    def _handover_needs_from(self):
        if self.type == "handover" and not self.from_person_id:
            raise ValueError("A handover requires from_person_id")
        return self


class MeetingUpdate(Base):
    title: Title | None = None
    date: str | None = None
    agenda: list[str] | None = None
    raw_notes: str | None = Field(None, max_length=20000)
    summary: str | None = Field(None, max_length=5000)
    decisions: list[Decision] | None = None
    attendance: dict[str, bool] | None = None  # person_id -> attended

    @field_validator("date")
    @classmethod
    def _date(cls, v):
        return check_date(v)

    @field_validator("agenda")
    @classmethod
    def _agenda(cls, v):
        return _clean_agenda(v)


class StatusChange(Base):
    status: Literal["scheduled", "completed", "archived"]


class NextMeeting(Base):
    title: Title
    date: str

    @field_validator("date")
    @classmethod
    def _date(cls, v):
        return require_date(v)
