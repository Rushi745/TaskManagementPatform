from typing import Annotated

from pydantic import Field, StringConstraints, field_validator

from app.schemas.common import Base, Title


class KBCreate(Base):
    title: Title
    content: str = Field(min_length=20, max_length=50000)
    tags: list[Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]] = []

    @field_validator("tags")
    @classmethod
    def _tags(cls, v):
        return [t.lower() for t in v if t][:8]


class BriefRequest(Base):
    person_id: str
    mode: str = Field("missed", pattern="^(missed|takeover)$")
