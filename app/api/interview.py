"""
Interview lifecycle endpoints:

  POST /interviews/start           -> creates an interview, returns first question (+ audio)
  POST /interviews/{id}/answer     -> submits candidate answer, returns evaluation + next question
  GET  /interviews/{id}            -> interview status/summary
  GET  /interviews                 -> list recent interviews

Auth: `start` is open (candidate hasn't got a token yet). Every other route
requires the bearer session token minted at start time, scoped to that
interview_id, so one candidate can't read/mutate another's session.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.evaluator import get_evaluator_agent
from app.agents.interviewer import get_interviewer_agent
from app.core.logger import logger
from app.core.security import create_session_token, verify_session_token
from app.db.models import Interview, InterviewStatus, Turn, TurnRole
from app.db.mongodb import InterviewRepository
from app.core.config import settings
from app.schemas.interview import (
    InterviewDetail,
    InterviewSummary,
    StartInterviewRequest,
    StartInterviewResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from app.services.elevenlabs import get_elevenlabs_service
from app.services.whisper import get_whisper_service

router = APIRouter(prefix="/interviews", tags=["interviews"])


async def _get_owned_interview(interview_id: str, token_interview_id: str) -> Interview:
    if interview_id != token_interview_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match this interview")
    interview = await InterviewRepository.get(interview_id)
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return interview


@router.post("/start", response_model=StartInterviewResponse)
async def start_interview(payload: StartInterviewRequest):
    interviewer = get_interviewer_agent()
    tts = get_elevenlabs_service()

    interview = Interview(
        candidate_name=payload.candidate_name,
        role=payload.role,
        experience_level=payload.experience_level,
        focus_areas=payload.focus_areas,
        status=InterviewStatus.IN_PROGRESS,
        current_difficulty=settings.difficulty_ladder[0],
    )

    opening = await interviewer.opening_question(interview)
    question_text = opening.get("message", "Let's begin - tell me about a recent project you're proud of.")
    subtopic = opening.get("target_subtopic")

    turn = Turn(
        role=TurnRole.INTERVIEWER,
        text=question_text,
        subtopic=subtopic,
        difficulty=interview.current_difficulty,
    )
    interview.turns.append(turn)
    interview.questions_asked = 1

    await InterviewRepository.create(interview)

    audio_b64 = ""
    try:
        audio_b64 = await tts.synthesize(question_text)
    except Exception as exc:  # noqa: BLE001
        logger.error("TTS synthesis failed for opening question: {}", exc)

    token = create_session_token(interview.interview_id)
    logger.info("Started interview {} for {}", interview.interview_id, payload.candidate_name)

    return StartInterviewResponse(
        interview_id=interview.interview_id,
        session_token=token,
        question_text=question_text,
        question_audio_base64=audio_b64 or None,
        subtopic=subtopic,
        difficulty=interview.current_difficulty,
    )


@router.post("/{interview_id}/answer", response_model=SubmitAnswerResponse)
async def submit_answer(
    interview_id: str,
    payload: SubmitAnswerRequest,
    token_interview_id: str = Depends(verify_session_token),
):
    interview = await _get_owned_interview(interview_id, token_interview_id)

    if interview.status != InterviewStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interview is not in progress")

    # 1. Get answer text (transcribe audio if that's what was sent)
    answer_text = (payload.answer_text or "").strip()
    if not answer_text and payload.answer_audio_base64:
        whisper = get_whisper_service()
        try:
            answer_text = await whisper.transcribe_base64_audio(payload.answer_audio_base64, payload.audio_format)
        except Exception as exc:  # noqa: BLE001
            logger.error("Transcription failed for interview {}: {}", interview_id, exc)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Could not transcribe audio") from exc

    if not answer_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No answer text or audio provided")

    last_question_turn = next((t for t in reversed(interview.turns) if t.role == TurnRole.INTERVIEWER), None)
    subtopic = last_question_turn.subtopic if last_question_turn else None
    question_text = last_question_turn.text if last_question_turn else ""

    # 2. Evaluate the answer
    evaluator = get_evaluator_agent()
    evaluation = await evaluator.evaluate_answer(
        question=question_text, answer=answer_text, difficulty=interview.current_difficulty, subtopic=subtopic or "general"
    )

    candidate_turn = Turn(
        role=TurnRole.CANDIDATE,
        text=answer_text,
        subtopic=subtopic,
        difficulty=interview.current_difficulty,
        evaluation=evaluation,
    )
    interview.turns.append(candidate_turn)

    # 3. Adaptive difficulty
    interviewer = get_interviewer_agent()
    interview.current_difficulty = interviewer.compute_next_difficulty(interview, evaluation)

    # 4. Decide if this was the last question
    is_final_turn = interview.questions_asked >= settings.max_questions_per_interview

    next_data = await interviewer.next_turn(interview, evaluation, is_final_turn)
    next_action = next_data.get("action", "NEW_QUESTION")
    next_message = next_data.get("message", "Thanks - let's continue.")
    next_subtopic = next_data.get("target_subtopic")

    is_final = next_action == "CLOSING"

    if not is_final:
        interviewer_turn = Turn(
            role=TurnRole.INTERVIEWER,
            text=next_message,
            subtopic=next_subtopic,
            difficulty=interview.current_difficulty,
        )
        interview.turns.append(interviewer_turn)
        if next_action == "NEW_QUESTION":
            interview.questions_asked += 1
    else:
        interview.turns.append(Turn(role=TurnRole.INTERVIEWER, text=next_message, subtopic=None))
        interview.status = InterviewStatus.COMPLETED

    await InterviewRepository.replace(interview)

    audio_b64 = ""
    tts = get_elevenlabs_service()
    try:
        audio_b64 = await tts.synthesize(next_message)
    except Exception as exc:  # noqa: BLE001
        logger.error("TTS synthesis failed mid-interview {}: {}", interview_id, exc)

    return SubmitAnswerResponse(
        interview_id=interview.interview_id,
        transcribed_text=answer_text,
        evaluation=evaluation,
        next_action=next_action,
        next_question_text=next_message,
        next_question_audio_base64=audio_b64 or None,
        subtopic=next_subtopic,
        difficulty=interview.current_difficulty,
        is_final=is_final,
        questions_asked=interview.questions_asked,
        max_questions=settings.max_questions_per_interview,
    )


@router.get("/{interview_id}", response_model=InterviewDetail)
async def get_interview(interview_id: str):
    interview = await InterviewRepository.get(interview_id)
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return InterviewDetail(
        interview_id=interview.interview_id,
        candidate_name=interview.candidate_name,
        role=interview.role,
        experience_level=interview.experience_level,
        status=interview.status,
        current_difficulty=interview.current_difficulty,
        questions_asked=interview.questions_asked,
        overall_score=interview.overall_score,
        recommendation=interview.recommendation,
        report_path=interview.report_path,
    )


@router.get("", response_model=list[InterviewSummary])
async def list_interviews(limit: int = 20):
    interviews = await InterviewRepository.list_recent(limit=limit)
    return [
        InterviewSummary(
            interview_id=i.interview_id,
            candidate_name=i.candidate_name,
            role=i.role,
            status=i.status,
            questions_asked=i.questions_asked,
            overall_score=i.overall_score,
            recommendation=i.recommendation,
        )
        for i in interviews
    ]
