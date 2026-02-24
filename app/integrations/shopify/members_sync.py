"""app/integrations/shopify/members_sync.py — Shopify to StudioMember Sync (PR 2).

Fetches customers from Shopify Admin API and upserts them into StudioMember table.
"""
from datetime import datetime, timezone
import json
import httpx
import structlog
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.models import StudioMember, MemberImportLog
from app.gateway.persistence import persistence

logger = structlog.get_logger()

async def run_sync(tenant_id: int):
    """Full customer sync from Shopify."""
    db = SessionLocal()
    log = MemberImportLog(
        tenant_id=tenant_id,
        source="shopify",
        status="running",
        created_at=datetime.now(timezone.utc)
    )
    db.add(log)
    db.commit()
    
    try:
        # 1. Load Credentials
        prefix = f"integration_shopify_{tenant_id}"
        domain = persistence.get_setting(f"{prefix}_domain")
        token = persistence.get_setting(f"{prefix}_access_token")
        
        if not domain or not token:
            raise ValueError("Shopify credentials missing")
            
        # 2. Fetch from Shopify (simplified pagination)
        url = f"https://{domain}/admin/api/2024-01/customers.json"
        headers = {"X-Shopify-Access-Token": token}
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            customers = data.get("customers", [])
            
        log.total_rows = len(customers)
        imported = 0
        updated = 0
        
        # 3. Process & Upsert
        for c in customers:
            source_id = str(c["id"])
            email = c.get("email")
            
            existing = db.query(StudioMember).filter(
                StudioMember.tenant_id == tenant_id,
                StudioMember.source == "shopify",
                StudioMember.source_id == source_id
            ).first()
            
            if existing:
                existing.first_name = c.get("first_name", existing.first_name)
                existing.last_name = c.get("last_name", existing.last_name)
                existing.email = email
                existing.phone_number = c.get("phone")
                updated += 1
            else:
                new_mem = StudioMember(
                    tenant_id=tenant_id,
                    customer_id=0, # placeholder
                    first_name=c.get("first_name", ""),
                    last_name=c.get("last_name", ""),
                    email=email,
                    phone_number=c.get("phone"),
                    source="shopify",
                    source_id=source_id,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(new_mem)
                imported += 1
                
        db.commit()
        log.status = "completed"
        log.imported = imported
        log.updated = updated
        db.commit()
        
        # Update usage record
        from app.core.feature_gates import FeatureGate
        gate = FeatureGate(tenant_id)
        count = db.query(StudioMember).filter(StudioMember.tenant_id == tenant_id).count()
        gate.set_active_members(count)
        
    except Exception as e:
        logger.error("shopify.sync_failed", tenant_id=tenant_id, error=str(e))
        log.status = "failed"
        log.error_log = str(e)
        db.commit()
    finally:
        db.close()
