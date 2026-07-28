"""
Generates the final PDF feedback report using reportlab. Kept separate from
the feedback agent so the "how we render a PDF" concern is independent from
"what the feedback content is".
"""
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import settings
from app.core.logger import logger
from app.db.models import Interview
from app.schemas.feedback import FeedbackReport


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(name="ReportTitle", fontSize=20, leading=24, spaceAfter=6, textColor=colors.HexColor("#1a1a2e"))
    )
    styles.add(ParagraphStyle(name="SectionHeader", fontSize=13, leading=16, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#16213e")))
    styles.add(ParagraphStyle(name="Body", fontSize=10.5, leading=15))
    styles.add(ParagraphStyle(name="BulletItem", fontSize=10.5, leading=15, leftIndent=14))
    return styles


def generate_pdf_report(interview: Interview, feedback: FeedbackReport) -> str:
    os.makedirs(settings.reports_dir, exist_ok=True)
    path = os.path.join(settings.reports_dir, f"{interview.interview_id}.pdf")

    styles = _styles()
    doc = SimpleDocTemplate(
        path, pagesize=letter,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    story = []

    story.append(Paragraph("Technical Interview Report", styles["ReportTitle"]))
    story.append(
        Paragraph(
            f"{interview.candidate_name} &mdash; {interview.role} "
            f"({interview.experience_level})<br/>"
            f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 12))

    score_table = Table(
        [
            ["Overall Score", "Recommendation", "Questions Asked"],
            [f"{feedback.overall_score}/100", feedback.recommendation.replace("_", " ").title(), str(interview.questions_asked)],
        ],
        colWidths=[2.2 * inch, 2.2 * inch, 1.8 * inch],
    )
    score_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(score_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Summary", styles["SectionHeader"]))
    story.append(Paragraph(feedback.summary, styles["Body"]))

    story.append(Paragraph("Strengths", styles["SectionHeader"]))
    for s in feedback.strengths:
        story.append(Paragraph(f"&bull; {s}", styles["BulletItem"]))

    story.append(Paragraph("Areas to Improve", styles["SectionHeader"]))
    for w in feedback.weaknesses:
        story.append(Paragraph(f"&bull; {w}", styles["BulletItem"]))

    story.append(Paragraph("Communication", styles["SectionHeader"]))
    story.append(Paragraph(feedback.communication_notes, styles["Body"]))

    story.append(Paragraph("Recommended Topics to Study", styles["SectionHeader"]))
    for t in feedback.recommended_topics:
        story.append(Paragraph(f"&bull; {t}", styles["BulletItem"]))

    story.append(Paragraph("Per-Question Breakdown", styles["SectionHeader"]))
    rows = [["Subtopic", "Score", "Note"]]
    for q in feedback.per_question_breakdown:
        rows.append([q.subtopic, f"{q.score}/10", q.note])
    breakdown_table = Table(rows, colWidths=[1.8 * inch, 0.8 * inch, 3.6 * inch])
    breakdown_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3460")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(breakdown_table)

    doc.build(story)
    logger.info("Generated PDF report at {}", path)
    return path
