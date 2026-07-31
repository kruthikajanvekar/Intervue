from typing import List, Optional

from pydantic import BaseModel, Field

from app.db.models import EvaluationScore, InterviewStatus


class StartInterviewRequest(BaseModel):
    candidate_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=120, examples=["Backend Engineer"])
    experience_level: str = Field(default="mid", examples=["junior", "mid", "senior"])
    focus_areas: List[str] = Field(default_factory=list, examples=[["system design", "python", "sql"]])


class StartInterviewResponse(BaseModel):
    interview_id: str
    session_token: str
    question_text: str
    question_audio_base64: Optional[str] = None
    subtopic: Optional[str] = None
    difficulty: str


class SubmitAnswerRequest(BaseModel):
    """Candidate answer, either as raw text (typed) or base64-encoded audio to be transcribed."""

    answer_text: Optional[str] = None
    answer_audio_base64: Optional[str] = None
    audio_format: str = "webm"


class SubmitAnswerResponse(BaseModel):
    interview_id: str
    transcribed_text: Optional[str] = None
    evaluation: Optional[EvaluationScore] = None
    next_action: str
    next_question_text: str
    next_question_audio_base64: Optional[str] = None
    subtopic: Optional[str] = None
    difficulty: str
    is_final: bool
    questions_asked: int
    max_questions: int


class InterviewSummary(BaseModel):
    interview_id: str
    candidate_name: str
    role: str
    status: InterviewStatus
    questions_asked: int
    overall_score: Optional[int] = None
    recommendation: Optional[str] = None


class InterviewDetail(BaseModel):
    interview_id: str
    candidate_name: str
    role: str
    experience_level: str
    status: InterviewStatus
    current_difficulty: str
    questions_asked: int
    overall_score: Optional[int] = None
    recommendation: Optional[str] = None
    report_path: Optional[str] = None
