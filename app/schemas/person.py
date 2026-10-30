import re
from typing import Annotated, Literal

from pydantic import StringConstraints, field_validator

from app.schemas.common import Base, check_date

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


class PersonCreate(Base):
    name: Name
    email: str
    role: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("Invalid email address")
        return v


class PersonUpdate(Base):
    role: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    status: Literal["active", "on_leave"] | None = None
