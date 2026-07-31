"""
Evaluator agent: scores a single candidate answer against the question that
was asked. This runs on every answer, before the interviewer agent decides
what to do next - the interviewer's decision is conditioned on this score.
"""
from app.core.logger import logger
from app.core.prompts import EVALUATOR_SYSTEM_PROMPT, EVALUATOR_USER_TEMPLATE
from app.db.models import EvaluationScore
from app.services.llm import get_llm_service


class EvaluatorAgent:
    def __init__(self):
        self.llm = get_llm_service()

    async def evaluate_answer(
        self, question: str, answer: str, difficulty: str, subtopic: str
    ) -> EvaluationScore:
        if not answer or not answer.strip():
            # No answer / empty transcription - score as a weak answer rather than erroring.
            return EvaluationScore(
                correctness=0,
                depth=0,
                communication=0,
                confidence=0,
                is_weak_or_vague=True,
                key_gaps=["No answer provided"],
                one_line_note="Candidate gave no discernible answer.",
            )

        user_prompt = EVALUATOR_USER_TEMPLATE.format(
            difficulty=difficulty, subtopic=subtopic, question=question, answer=answer
        )
        try:
            data = await self.llm.complete_json(EVALUATOR_SYSTEM_PROMPT, user_prompt, max_tokens=500)
            return EvaluationScore(**data)
        except Exception as exc:  # noqa: BLE001
            logger.error("Evaluator agent failed, falling back to neutral score: {}", exc)
            return EvaluationScore(
                correctness=5, depth=5, communication=5, confidence=5,
                is_weak_or_vague=False, key_gaps=[], one_line_note="Evaluation failed; neutral fallback score.",
            )


_evaluator_agent: "EvaluatorAgent | None" = None


def get_evaluator_agent() -> EvaluatorAgent:
    global _evaluator_agent
    if _evaluator_agent is None:
        _evaluator_agent = EvaluatorAgent()
    return _evaluator_agent
