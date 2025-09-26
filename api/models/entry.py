from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from uuid import uuid4

class EntryCreate(BaseModel):
    """Model for creating a new journal entry (user input)."""
    work: str = Field(
        min_length=1,
        max_length=256,
        description="What did you work on today?",
        json_schema_extra={"example": "Studied FastAPI and built my first API endpoints"}
    )
    struggle: str = Field(
        min_length=1,
        max_length=256,
        description="What's one thing you struggled with today?",
        json_schema_extra={"example": "Understanding async/await syntax and when to use it"}
    )
    intention: str = Field(
        min_length=1,
        max_length=256,
        description="What will you study/work on tomorrow?",
        json_schema_extra={"example": "Practice PostgreSQL queries and database design"}
    )

class Entry(BaseModel):
    
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the entry (UUID)."
    )
    work: str = Field(
        min_length=1,
        max_length=256,
        description="What did you work on today?"
    )
    struggle: str = Field(
        min_length=1,
        max_length=256,
        description="What’s one thing you struggled with today?"
    )
    intention: str = Field(
        min_length=1,
        max_length=256,
        description="What will you study/work on tomorrow?"
    )
    created_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the entry was created."
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the entry was last updated."
    )

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }
    
    #Custom field validator applied only to "data" fields. Converts input to a string, strips whitespace, and ensures non-empty strings.
    @field_validator("work", "struggle", "intention", mode="before")
    @classmethod
    def strip_whitespace(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        if not value:
            raise ValueError("Field cannot be empty")
        return value