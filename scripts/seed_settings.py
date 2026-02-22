from sqlalchemy.orm import Session
from app.core.db import SessionLocal, engine, Base
from app.core.models import Setting

# Ensure tables exist
Base.metadata.create_all(bind=engine)

def seed_settings():
    db = SessionLocal()
    try:
        settings = [
            Setting(key="system_name", value="ARIIA Control Deck", description="Name of the system displayed in header"),
            Setting(key="notification_email", value="admin@example.com", description="Email for critical alerts"),
            Setting(key="handoff_threshold", value="0.8", description="Confidence score below which handoff is triggered"),
            Setting(key="maintenance_mode", value="false", description="If true, bot will reply with maintenance message"),
        ]
        
        for s in settings:
            # Check if exists
            existing = db.query(Setting).filter(Setting.key == s.key).first()
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
