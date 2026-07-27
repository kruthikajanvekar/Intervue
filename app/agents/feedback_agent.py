"""
Feedback agent: runs once, at the end of the interview, over the full
transcript + per-answer evaluator scores to produce the final structured
report (strengths, weaknesses, recommended topics, hire recommendation).
"""
import json

from app.core.logger import logger
from app.core.prompts import FEEDBACK_SYSTEM_PROMPT, FEEDBACK_USER_TEMPLATE
from app.db.models import Interview, TurnRole
from app.schemas.feedback import FeedbackReport, QuestionBreakdown
from app.services.llm import get_llm_service
from app.services.scoring import aggregate_overall_score, recommendation_from_score


class FeedbackAgent:
    def __init__(self):
        self.llm = get_llm_service()

    async def generate(self, interview: Interview) -> FeedbackReport:
        deterministic_score = aggregate_overall_score(interview.turns)
        fallback_recommendation = recommendation_from_score(deterministic_score)

        transcript_payload = []
        for turn in interview.turns:
            entry = {"role": turn.role.value, "text": turn.text, "subtopic": turn.subtopic}
            if turn.evaluation:
                entry["evaluation"] = turn.evaluation.model_dump()
            transcript_payload.append(entry)

        user_prompt = FEEDBACK_USER_TEMPLATE.format(
            role=interview.role,
            experience_level=interview.experience_level,
            num_questions=interview.questions_asked,
            transcript_json=json.dumps(transcript_payload, indent=2, default=str),
        )

        try:
            data = await self.llm.complete_json(FEEDBACK_SYSTEM_PROMPT, user_prompt, max_tokens=1200)
            breakdown = [QuestionBreakdown(**item) for item in data.get("per_question_breakdown", [])]
            return FeedbackReport(
                interview_id=interview.interview_id,
                overall_score=int(data.get("overall_score", deterministic_score)),
                recommendation=data.get("recommendation", fallback_recommendation),
                summary=data.get("summary", ""),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                communication_notes=data.get("communication_notes", ""),
                recommended_topics=data.get("recommended_topics", []),
                per_question_breakdown=breakdown,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Feedback agent failed, falling back to deterministic summary: {}", exc)
            return self._fallback_report(interview, deterministic_score, fallback_recommendation)

    @staticmethod
    def _fallback_report(interview: Interview, score: int, recommendation: str) -> FeedbackReport:
        breakdown = []
        for turn in interview.turns:
            if turn.role == TurnRole.CANDIDATE and turn.evaluation:
                breakdown.append(
                    QuestionBreakdown(
                        subtopic=turn.subtopic or "general",
                        score=round(turn.evaluation.average),
                        note=turn.evaluation.one_line_note or "No note available.",
                    )
                )
        return FeedbackReport(
            interview_id=interview.interview_id,
            overall_score=score,
            recommendation=recommendation,
            summary=(
                "Automated summary generation was unavailable, so this report was generated "
                "from raw per-answer scores instead of a narrative review."
            ),
            strengths=["See per-question breakdown for scoring detail."],
            weaknesses=["See per-question breakdown for scoring detail."],
            communication_notes="Not available - narrative generation failed.",
            recommended_topics=[],
            per_question_breakdown=breakdown,
        )


_feedback_agent: "FeedbackAgent | None" = None


def get_feedback_agent() -> FeedbackAgent:
    global _feedback_agent
    if _feedback_agent is None:
        _feedback_agent = FeedbackAgent()
    return _feedback_agent
