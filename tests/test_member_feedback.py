import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
from app.gateway.main import app
from app.core.db import SessionLocal
from app.core.models import MemberFeedback, ChatSession

@pytest.mark.anyio
async def test_member_feedback_submission_and_analytics() -> None:
    from app.core.auth import get_current_user, AuthContext
    
    async def override_get_current_user() -> AuthContext:
        return AuthContext(user_id="admin", email="admin@test", tenant_id=1, tenant_slug="test", role="tenant_admin")
        
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    db = SessionLocal()
    try:
        # Cleanup
        db.query(MemberFeedback).filter(MemberFeedback.tenant_id == 1).delete()
        db.query(ChatSession).filter(ChatSession.user_id == "test_session_1").delete()
        
        # Create a dummy chat session
        db.add(ChatSession(
            tenant_id=1, user_id="test_session_1", platform="whatsapp"
        ))
        db.commit()
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Submit feedback
        resp = await ac.post("/feedback/test_session_1", json={"rating": 5, "comment": "Great!"})
        assert resp.status_code == 200
        
        # Submit another feedback for a different session, but same tenant
        db = SessionLocal()
        db.add(ChatSession(tenant_id=1, user_id="test_session_2", platform="whatsapp"))
        db.commit()
        db.close()
        
        resp2 = await ac.post("/feedback/test_session_2", json={"rating": 4})
        assert resp2.status_code == 200
        
        # Check analytics endpoint
        analytics_resp = await ac.get("/admin/analytics/satisfaction")
        assert analytics_resp.status_code == 200
        
        data = analytics_resp.json()
        assert data["total"] == 2
        assert data["average"] == 4.5
        
    app.dependency_overrides.clear()
