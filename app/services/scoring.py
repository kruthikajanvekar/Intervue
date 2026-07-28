"""
Deterministic scoring helpers that sit alongside the LLM-based evaluator.
The evaluator agent judges each answer qualitatively; this module aggregates
those per-answer scores into interview-level numbers and drives the adaptive
difficulty logic, so the "difficulty changes based on performance" behavior
doesn't depend entirely on an LLM call.
"""
from typing import List

from app.db.models import EvaluationScore, Turn, TurnRole


def aggregate_overall_score(turns: List[Turn]) -> int:
    """Weighted average of per-answer scores, scaled to 0-100.

    Correctness and depth are weighted more heavily than communication and
    confidence, since this is a technical assessment first.
    """
    evaluated = [t for t in turns if t.role == TurnRole.CANDIDATE and t.evaluation]
    if not evaluated:
        return 0

    weights = {"correctness": 0.4, "depth": 0.3, "communication": 0.15, "confidence": 0.15}
    total = 0.0
    for t in evaluated:
        e = t.evaluation
        total += (
            e.correctness * weights["correctness"]
            + e.depth * weights["depth"]
            + e.communication * weights["communication"]
            + e.confidence * weights["confidence"]
        )
    avg_out_of_10 = total / len(evaluated)
    return round(avg_out_of_10 * 10)


def next_difficulty(current_difficulty: str, ladder: List[str], last_eval: EvaluationScore) -> str:
    """Adaptive difficulty: move up after a strong answer, down after a weak one, else hold."""
    idx = ladder.index(current_difficulty) if current_difficulty in ladder else 0
    strong = last_eval.average >= 7.5 and not last_eval.is_weak_or_vague
    weak = last_eval.average <= 4.5 or last_eval.is_weak_or_vague

    if strong and idx < len(ladder) - 1:
        return ladder[idx + 1]
    if weak and idx > 0:
        return ladder[idx - 1]
    return ladder[idx]


def recommendation_from_score(score: int) -> str:
    if score >= 85:
        return "strong_hire"
    if score >= 70:
        return "hire"
    if score >= 55:
        return "lean_hire"
    if score >= 40:
        return "lean_no_hire"
    return "no_hire"
