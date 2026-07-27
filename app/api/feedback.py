"""
Feedback endpoints: generate + fetch the final report, and download the PDF.

  POST /feedback/{interview_id}/generate  -> runs the feedback agent, persists score, builds PDF
  GET  /feedback/{interview_id}           -> returns the stored report (generates if missing)
  GET  /feedback/{interview_id}/pdf       -> streams the PDF file
"""
import os

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.agents.feedback_agent import get_feedback_agent
from app.core.logger import logger
from app.db.models import InterviewStatus
from app.db.mongodb import InterviewRepository
from app.schemas.feedback import FeedbackReport
from app.services.report import generate_pdf_report

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/{interview_id}/generate", response_model=FeedbackReport)
async def generate_feedback(interview_id: str):
    interview = await InterviewRepository.get(interview_id)
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")

    if not interview.turns:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interview has no turns to evaluate")

    agent = get_feedback_agent()
    report = await agent.generate(interview)

    interview.overall_score = report.overall_score
    interview.recommendation = report.recommendation
    interview.status = InterviewStatus.COMPLETED

    try:
        pdf_path = generate_pdf_report(interview, report)
        interview.report_path = pdf_path
        report.pdf_available = True
    except Exception as exc:  # noqa: BLE001
        logger.error("PDF generation failed for interview {}: {}", interview_id, exc)
        report.pdf_available = False

    await InterviewRepository.replace(interview)
    return report


@router.get("/{interview_id}", response_model=FeedbackReport)
async def get_feedback(interview_id: str):
    interview = await InterviewRepository.get(interview_id)
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")

    if interview.overall_score is None:
        # Not generated yet - generate on demand.
        return await generate_feedback(interview_id)

    agent = get_feedback_agent()
    report = await agent.generate(interview)  # regenerate narrative content for freshness
    report.pdf_available = bool(interview.report_path and os.path.exists(interview.report_path))
    return report


@router.get("/{interview_id}/pdf")
async def download_feedback_pdf(interview_id: str):
    interview = await InterviewRepository.get(interview_id)
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    if not interview.report_path or not os.path.exists(interview.report_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not generated yet")
    return FileResponse(
        interview.report_path,
        media_type="application/pdf",
        filename=f"interview-report-{interview.candidate_name.replace(' ', '_')}.pdf",
    )
