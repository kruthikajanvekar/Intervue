"""
Domain models. These double as the shape of documents stored in MongoDB
(collections: interviews, turns) and as the objects passed between agents.
We use plain dicts at the Motor boundary (Mongo's native format) and these
Pydantic models everywhere else for validation + editor support.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InterviewStatus(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class TurnRole(str, Enum):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class EvaluationScore(BaseModel):
    correctness: int = Field(ge=0, le=10)
    depth: int = Field(ge=0, le=10)
    communication: int = Field(ge=0, le=10)
    confidence: int = Field(ge=0, le=10)
    is_weak_or_vague: bool = False
    key_gaps: List[str] = Field(default_factory=list)
    one_line_note: str = ""

    @property
    def average(self) -> float:
        return round((self.correctness + self.depth + self.communication + self.confidence) / 4, 2)


class Turn(BaseModel):
    """One exchange unit: either the interviewer's question or the candidate's answer."""

    turn_id: str = Field(default_factory=_uuid)
    role: TurnRole
    text: str
    subtopic: Optional[str] = None
    difficulty: Optional[str] = None
    audio_url: Optional[str] = None
    evaluation: Optional[EvaluationScore] = None
    created_at: datetime = Field(default_factory=_now)


class Interview(BaseModel):
    interview_id: str = Field(default_factory=_uuid)
    candidate_name: str
    role: str
    experience_level: str = "mid"
    focus_areas: List[str] = Field(default_factory=list)
    status: InterviewStatus = InterviewStatus.CREATED
    current_difficulty: str = "easy"
    questions_asked: int = 0
    turns: List[Turn] = Field(default_factory=list)
    overall_score: Optional[int] = None
    recommendation: Optional[str] = None
    report_path: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    def to_mongo(self) -> dict:
        return self.model_dump(mode="json")

    @classmethod
    def from_mongo(cls, doc: dict) -> "Interview":
        doc = dict(doc)
        doc.pop("_id", None)
        return cls.model_validate(doc)
