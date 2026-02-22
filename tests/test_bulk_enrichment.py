import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
from app.gateway.main import app
from app.core.db import SessionLocal
from app.core.models import StudioMember

@pytest.mark.anyio
async def test_enrich_all_members_enqueues_to_redis() -> None:
    from app.core.auth import get_current_user, AuthContext
    
    async def override_get_current_user() -> AuthContext:
        return AuthContext(user_id="admin", email="admin@test", tenant_id=1, tenant_slug="test", role="tenant_admin")
        
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Needs to be tested with a mocked redis to not depend on real redis server
    mock_redis = MagicMock()
    # Mock scard to return 5
    mock_redis.scard.return_value = 5
    
    db = SessionLocal()
    try:
        # Create some fake members
        db.query(StudioMember).filter(StudioMember.tenant_id == 1).delete()
        for i in range(5):
            db.add(StudioMember(
                tenant_id=1, customer_id=100+i, first_name=f"F{i}", last_name=f"L{i}"
            ))
        db.commit()
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("redis.from_url", return_value=mock_redis):
            resp = await ac.post("/admin/members/enrich-all")
            assert resp.status_code == 200
            data = resp.json()
            assert data["enqueued"] == 5
            # 5 * 6 seconds / 60 seconds = 0 minutes
            assert data["estimated_minutes"] == 0
            
            # Verify Redis calls
            mock_redis.sadd.assert_called()
            mock_redis.scard.assert_called_with("tenant:1:enrich_queue")
            
    app.dependency_overrides.clear()
