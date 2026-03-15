from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import MemberFeedback, ChatSession

router = APIRouter(tags=["feedback"])
logger = structlog.get_logger()


class FeedbackPayload(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


@router.post("/feedback/{session_id}")
async def submit_feedback(
    session_id: str,
    payload: FeedbackPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Submit user satisfaction rating for a closed/finished conversation."""
    chat_session = db.query(ChatSession).filter(ChatSession.user_id == session_id).first()
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")

    existing = (
        db.query(MemberFeedback)
        .filter(
            MemberFeedback.session_id == session_id,
            MemberFeedback.tenant_id == chat_session.tenant_id,
        )
        .first()
    )

    if existing:
        existing.rating = payload.rating
        existing.comment = payload.comment
        existing.updated_at = datetime.now(timezone.utc)
        logger.info("feedback.updated", session_id=session_id, rating=payload.rating, tenant_id=chat_session.tenant_id)
    else:
        feedback = MemberFeedback(
            tenant_id=chat_session.tenant_id,
            session_id=session_id,
            rating=payload.rating,
            comment=payload.comment,
        )
        db.add(feedback)
        logger.info("feedback.submitted", session_id=session_id, rating=payload.rating, tenant_id=chat_session.tenant_id)

    db.commit()
    return {"status": "ok"}
