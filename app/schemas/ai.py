"""Pydantic models for AI output. They double as the JSON schema sent to Gemini,
so every field is required (no defaults) to keep the schema simple for the model."""
from typing import Literal

from pydantic import BaseModel, Field


class RecapItem(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    owner: str | None  # must be a participant name or null
    due_date: str | None  # YYYY-MM-DD or null
    priority: Literal["low", "medium", "high"]
    evidence: str  # short quote from the notes supporting this item
    confidence: float = Field(ge=0, le=1)


class RecapOut(BaseModel):
    summary: str
    decisions: list[str]
    action_items: list[RecapItem]
    open_questions: list[str]


class BriefOut(BaseModel):
    headline: str
    what_happened: list[str]
    decisions_affecting_you: list[str]
    your_action_items: list[str]
    open_questions: list[str]
    read_next: list[str]


class LinkDecision(BaseModel):
    doc_id: str
    relevant: bool
    reason: str


class LinkOut(BaseModel):
    links: list[LinkDecision]


class HandoverItemNote(BaseModel):
    item_id: str
    context: str
    suggested_owner: str | None
    suggestion_reason: str | None


class HandoverBriefOut(BaseModel):
    overview: str
    items: list[HandoverItemNote]
    risks: list[str]
