from typing import List

from pydantic import BaseModel


class QuestionBreakdown(BaseModel):
    subtopic: str
    score: int
    note: str


class FeedbackReport(BaseModel):
    interview_id: str
    overall_score: int
    recommendation: str
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    communication_notes: str
    recommended_topics: List[str]
    per_question_breakdown: List[QuestionBreakdown]
    pdf_available: bool = False
