"""
Interviewer agent: owns the conversational flow. Decides, turn by turn,
whether to follow up, escalate/de-escalate difficulty, or wrap up - using
the evaluator's assessment of the candidate's last answer as its main signal.
"""
from typing import Optional

from app.core.config import settings
from app.core.logger import logger
from app.core.prompts import INTERVIEWER_FIRST_QUESTION_PROMPT, INTERVIEWER_SYSTEM_PROMPT
from app.db.models import EvaluationScore, Interview, Turn, TurnRole
from app.services.llm import get_llm_service
from app.services.scoring import next_difficulty


class InterviewerAgent:
    def __init__(self):
        self.llm = get_llm_service()

    async def opening_question(self, interview: Interview) -> dict:
        prompt = INTERVIEWER_FIRST_QUESTION_PROMPT.format(
            role=interview.role,
            experience_level=interview.experience_level,
            focus_areas=", ".join(interview.focus_areas) or "general technical fundamentals",
            difficulty=interview.current_difficulty,
        )
        try:
            data = await self.llm.complete_json(
                INTERVIEWER_SYSTEM_PROMPT.format(role=interview.role, experience_level=interview.experience_level),
                prompt,
                max_tokens=300,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Interviewer agent failed on opening question, using fallback: {}", exc)
            data = {
                "action": "NEW_QUESTION",
                "message": (
                    f"Hi {interview.candidate_name}, thanks for joining. Let's start with something "
                    f"foundational for a {interview.role} role - can you walk me through how you'd "
                    f"approach designing a rate limiter for a public API?"
                ),
                "target_subtopic": "system design fundamentals",
            }
        return data

    async def next_turn(
        self,
        interview: Interview,
        last_evaluation: Optional[EvaluationScore],
        is_final_turn: bool,
    ) -> dict:
        if is_final_turn:
            return {
                "action": "CLOSING",
                "message": (
                    f"That's all the questions I have for you today, {interview.candidate_name}. "
                    "Thanks for walking me through your thinking - you'll get detailed feedback shortly."
                ),
                "target_subtopic": None,
            }

        transcript = self._render_transcript(interview)
        eval_block = "No prior evaluation." if last_evaluation is None else (
            f"correctness={last_evaluation.correctness}/10, depth={last_evaluation.depth}/10, "
            f"communication={last_evaluation.communication}/10, confidence={last_evaluation.confidence}/10, "
            f"weak_or_vague={last_evaluation.is_weak_or_vague}, gaps={last_evaluation.key_gaps}, "
            f"note='{last_evaluation.one_line_note}'"
        )

        system = INTERVIEWER_SYSTEM_PROMPT.format(role=interview.role, experience_level=interview.experience_level)
        user = (
            f"Focus areas: {', '.join(interview.focus_areas) or 'general technical fundamentals'}\n"
            f"Current difficulty: {interview.current_difficulty}\n\n"
            f"Conversation so far:\n{transcript}\n\n"
            f"Evaluator's assessment of candidate's last answer:\n{eval_block}\n"
        )

        try:
            data = await self.llm.complete_json(system, user, max_tokens=350)
        except Exception as exc:  # noqa: BLE001
            logger.error("Interviewer agent failed on next_turn, using fallback: {}", exc)
            data = {
                "action": "NEW_QUESTION",
                "message": "Let's move on - can you tell me about a time you had to debug a tricky production issue?",
                "target_subtopic": "debugging",
            }
        return data

    def compute_next_difficulty(self, interview: Interview, last_evaluation: EvaluationScore) -> str:
        return next_difficulty(interview.current_difficulty, settings.difficulty_ladder, last_evaluation)

    @staticmethod
    def _render_transcript(interview: Interview) -> str:
        lines = []
        for turn in interview.turns:
            speaker = "Interviewer" if turn.role == TurnRole.INTERVIEWER else "Candidate"
            lines.append(f"{speaker}: {turn.text}")
        return "\n".join(lines) if lines else "(no turns yet)"


_interviewer_agent: "InterviewerAgent | None" = None


def get_interviewer_agent() -> InterviewerAgent:
    global _interviewer_agent
    if _interviewer_agent is None:
        _interviewer_agent = InterviewerAgent()
    return _interviewer_agent
