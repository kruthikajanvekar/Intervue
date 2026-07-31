"""
Unit tests for the deterministic pieces that don't require live network
calls: scoring aggregation and adaptive difficulty logic. Full end-to-end
interview flow tests (start -> answer -> feedback) require live/mocked
LLM, ElevenLabs, and MongoDB, and are best run as integration tests with
those dependencies mocked at the service layer (see conftest for patterns).
"""
from app.db.models import EvaluationScore, Turn, TurnRole
from app.services.scoring import aggregate_overall_score, next_difficulty, recommendation_from_score


def _turn(correctness, depth, communication, confidence, weak=False):
    return Turn(
        role=TurnRole.CANDIDATE,
        text="sample answer",
        evaluation=EvaluationScore(
            correctness=correctness,
            depth=depth,
            communication=communication,
            confidence=confidence,
            is_weak_or_vague=weak,
        ),
    )


def test_aggregate_overall_score_all_high():
    turns = [_turn(9, 9, 9, 9), _turn(10, 10, 9, 9)]
    score = aggregate_overall_score(turns)
    assert 85 <= score <= 100


def test_aggregate_overall_score_empty():
    assert aggregate_overall_score([]) == 0


def test_next_difficulty_escalates_on_strong_answer():
    strong = EvaluationScore(correctness=9, depth=9, communication=8, confidence=8, is_weak_or_vague=False)
    result = next_difficulty("easy", ["easy", "medium", "hard"], strong)
    assert result == "medium"


def test_next_difficulty_deescalates_on_weak_answer():
    weak = EvaluationScore(correctness=2, depth=2, communication=3, confidence=3, is_weak_or_vague=True)
    result = next_difficulty("medium", ["easy", "medium", "hard"], weak)
    assert result == "easy"


def test_next_difficulty_holds_on_middling_answer():
    mid = EvaluationScore(correctness=6, depth=6, communication=6, confidence=6, is_weak_or_vague=False)
    result = next_difficulty("medium", ["easy", "medium", "hard"], mid)
    assert result == "medium"


def test_recommendation_thresholds():
    assert recommendation_from_score(90) == "strong_hire"
    assert recommendation_from_score(75) == "hire"
    assert recommendation_from_score(60) == "lean_hire"
    assert recommendation_from_score(45) == "lean_no_hire"
    assert recommendation_from_score(20) == "no_hire"
