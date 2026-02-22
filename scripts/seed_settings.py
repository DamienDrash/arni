from sqlalchemy.orm import Session
from app.core.db import SessionLocal, engine, Base
from app.core.models import Setting, Tenant

# Ensure tables exist
Base.metadata.create_all(bind=engine)

def seed_settings():
    db = SessionLocal()
    try:
        # Resolve system tenant
        system_tenant = db.query(Tenant).filter(Tenant.slug == "system").first()
        if not system_tenant:
            system_tenant = Tenant(slug="system", name="System")
            db.add(system_tenant)
            db.commit()
            db.refresh(system_tenant)
            
        tid = system_tenant.id
        
        settings = [
            Setting(tenant_id=tid, key="system_name", value="ARIIA Control Deck", description="Name of the system displayed in header"),
            Setting(tenant_id=tid, key="notification_email", value="admin@ariia.io", description="Email for critical alerts"),
            Setting(tenant_id=tid, key="handoff_threshold", value="0.8", description="Confidence score below which handoff is triggered"),
            Setting(tenant_id=tid, key="maintenance_mode", value="false", description="If true, bot will reply with maintenance message"),
        ]
        
        for s in settings:
            # Check if exists
            existing = db.query(Setting).filter(Setting.key == s.key, Setting.tenant_id == tid).first()
            if not existing:
                db.add(s)
                print(f"Added setting: {s.key}")
            else:
                print(f"Skipping existing: {s.key}")
        
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    seed_settings()
