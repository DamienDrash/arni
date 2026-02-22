import structlog
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.core.models import MemberFeedback, ChatSession
from datetime import datetime, timezone

router = APIRouter(tags=["feedback"])
logger = structlog.get_logger()

class FeedbackPayload(BaseModel):
    rating: int  # 1-5
    comment: str | None = None

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/feedback/{session_id}")
async def submit_feedback(session_id: str, payload: FeedbackPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Submit user satisfaction rating for a closed/finished conversation."""
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        
    chat_session = db.query(ChatSession).filter(ChatSession.user_id == session_id).first()
    tenant_id = chat_session.tenant_id if chat_session else 1
    
    # Optional: Prevent duplicate feedback for same session
    existing = db.query(MemberFeedback).filter(MemberFeedback.session_id == session_id).first()
    if existing:
        existing.rating = payload.rating
        existing.comment = payload.comment
        existing.updated_at = datetime.now(timezone.utc)
        logger.info("feedback.updated", session_id=session_id, rating=payload.rating)
    else:
        feedback = MemberFeedback(
            tenant_id=tenant_id,
            session_id=session_id,
            rating=payload.rating,
            comment=payload.comment
        )
        db.add(feedback)
        logger.info("feedback.submitted", session_id=session_id, rating=payload.rating)
        
    db.commit()
    return {"status": "ok"}
