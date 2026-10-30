"""Shared pydantic types and validators."""
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


class Base(BaseModel):
    """Base model: trims strings, ignores unknown fields."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")


def check_date(v):
    """Validate a YYYY-MM-DD string (or empty -> None)."""
    if v in (None, ""):
        return None
    try:
        datetime.strptime(str(v)[:10], "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date, use YYYY-MM-DD")
    return str(v)[:10]


def require_date(v):
    """Like check_date but the value is mandatory."""
    d = check_date(v)
    if not d:
        raise ValueError("Date is required")
    return d
