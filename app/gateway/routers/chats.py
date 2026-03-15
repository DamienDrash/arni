"""app/gateway/routers/chats.py — Chat Session Admin API.

Endpoints:
    GET  /admin/chats                          → List active chat sessions
    GET  /admin/chats/{session_id}/history     → Chat message history for a session
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import get_db
from app.core.models import ChatSession, ChatMessage

logger = structlog.get_logger()

router = APIRouter(prefix="/admin/chats", tags=["chats"])


@router.get("")
async def list_chats(
    limit: int = Query(50, ge=1, le=200),
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste aktiver Chat-Sessions für Admin-Dashboard."""
    require_role(user, {"system_admin", "tenant_admin"})

    try:
        q = db.query(ChatSession)
        if user.role != "system_admin":
            q = q.filter(ChatSession.tenant_id == user.tenant_id)
        sessions = (
            q.order_by(ChatSession.last_message_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": s.id,
                "user_id": s.user_id,
                "tenant_id": s.tenant_id,
                "platform": s.platform,
                "is_active": s.is_active,
                "user_name": s.user_name,
                "phone_number": s.phone_number,
                "email": s.email,
                "member_id": s.member_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "last_message_at": s.last_message_at.isoformat() if s.last_message_at else None,
            }
            for s in sessions
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("chats.list_sessions_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@router.get("/{session_id}/history")
async def get_chat_history(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Chat-Verlauf einer Session."""
    require_role(user, {"system_admin", "tenant_admin"})

    try:
        # Verify the session exists and belongs to the tenant
        session_q = db.query(ChatSession).filter(ChatSession.user_id == session_id)
        if user.role != "system_admin":
            session_q = session_q.filter(ChatSession.tenant_id == user.tenant_id)
        session = session_q.first()

        if not session:
            raise HTTPException(status_code=404, detail="Session nicht gefunden")

        messages = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.session_id == session_id,
                ChatMessage.tenant_id == session.tenant_id,
            )
            .order_by(ChatMessage.timestamp.asc())
            .limit(limit)
            .all()
        )

        return {
            "session_id": session_id,
            "tenant_id": session.tenant_id,
            "platform": session.platform,
            "user_name": session.user_name,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                    "metadata_json": m.metadata_json,
                }
                for m in messages
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("chats.get_history_failed", session_id=session_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Interner Serverfehler")
