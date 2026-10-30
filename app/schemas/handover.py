from pydantic import Field, field_validator, model_validator

from app.schemas.common import Base, require_date


class HandoverPreview(Base):
    from_person_id: str
    leave_from: str
    leave_to: str

    @field_validator("leave_from", "leave_to")
    @classmethod
    def _dates(cls, v):
        return require_date(v)

    @model_validator(mode="after")
    def _order(self):
        if self.leave_to < self.leave_from:
            raise ValueError("leave_to must be on or after leave_from")
        return self


class Assignment(Base):
    item_id: str
    to_person_id: str
    context: str = Field("", max_length=2000)  # knowledge handed over with the item (AI draft, edited by a human)


class HandoverExecute(HandoverPreview):
    assignments: list[Assignment] = Field(min_length=1)
    note: str = Field("", max_length=500)
    brief: str = Field("", max_length=20000)
