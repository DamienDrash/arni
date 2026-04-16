from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domains.identity.models import Tenant
from app.domains.knowledge.models import IngestionJobStatus
from app.domains.platform.models import Setting
from app.domains.support.models import ChatMessage, ChatSession
from app.gateway.schemas import Platform


class PersistenceRepository:
    """Focused data access for persistence settings/tenant lookups."""

    def get_tenant_by_slug(self, db: Session, slug: str) -> Tenant | None:
        return db.query(Tenant).filter(Tenant.slug == slug).first()

    def get_tenant_by_id(self, db: Session, tenant_id: int) -> Tenant | None:
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def list_settings_by_tenant(self, db: Session, tenant_id: int) -> list[Setting]:
        return db.query(Setting).filter(Setting.tenant_id == tenant_id).all()

    def get_setting_row(self, db: Session, key: str) -> Setting | None:
        return db.query(Setting).filter(Setting.key == key).first()

    def get_legacy_setting_row(self, db: Session, tenant_id: int, key: str) -> Setting | None:
        return (
            db.query(Setting)
            .filter(Setting.tenant_id == tenant_id, Setting.key == key)
            .first()
        )

    def upsert_setting_row(
        self,
        db: Session,
        *,
        tenant_id: int,
        key: str,
        value: str,
        description: str | None = None,
    ) -> Setting:
        row = self.get_setting_row(db, key)
        if row:
            row.tenant_id = tenant_id
            row.key = key
            row.value = value
            if description is not None:
                row.description = description
            return row
        row = Setting(tenant_id=tenant_id, key=key, value=value, description=description)
        db.add(row)
        return row

    def delete_setting_row(self, db: Session, key: str) -> bool:
        row = self.get_setting_row(db, key)
        if not row:
            return False
        db.delete(row)
        return True

    def delete_settings_by_prefix(self, db: Session, tenant_id: int, prefix: str) -> int:
        cursor = db.query(Setting).filter(Setting.tenant_id == tenant_id, Setting.key.like(f"{prefix}%"))
        count = cursor.count()
        if count > 0:
            cursor.delete(synchronize_session=False)
        return count

    def count_messages_for_tenant(self, db: Session, tenant_id: int) -> int:
        return db.query(ChatMessage).filter(ChatMessage.tenant_id == tenant_id).count()

    def count_sessions_for_tenant(self, db: Session, tenant_id: int) -> int:
        return db.query(ChatSession).filter(ChatSession.tenant_id == tenant_id).count()

    def list_recent_sessions(
        self,
        db: Session,
        tenant_id: int,
        *,
        limit: int = 10,
        active_only: bool = False,
    ) -> list[ChatSession]:
        query = db.query(ChatSession).filter(ChatSession.tenant_id == tenant_id)
        if active_only:
            query = query.filter(ChatSession.is_active.is_(True))
        return query.order_by(ChatSession.last_message_at.desc()).limit(limit).all()

    def get_session_by_user_id(self, db: Session, tenant_id: int, user_id: str) -> ChatSession | None:
        return (
            db.query(ChatSession)
            .filter(ChatSession.user_id == user_id, ChatSession.tenant_id == tenant_id)
            .first()
        )

    def get_session_global(self, db: Session, user_id: str) -> ChatSession | None:
        return db.query(ChatSession).filter(ChatSession.user_id == user_id).first()

    def create_session(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: str,
        platform: Platform | str,
        user_name: str | None = None,
        phone_number: str | None = None,
        member_id: str | None = None,
    ) -> ChatSession:
        platform_str = platform.value if isinstance(platform, Platform) else str(platform)
        session = ChatSession(
            user_id=user_id,
            tenant_id=tenant_id,
            platform=platform_str,
            user_name=user_name,
            phone_number=phone_number,
            member_id=member_id,
        )
        db.add(session)
        db.flush()
        return session

    def update_session_identity(
        self,
        session: ChatSession,
        *,
        user_name: str | None = None,
        phone_number: str | None = None,
        member_id: str | None = None,
    ) -> bool:
        updated = False
        if user_name and session.user_name != user_name:
            session.user_name = user_name
            updated = True
        if phone_number and session.phone_number != phone_number:
            session.phone_number = phone_number
            updated = True
        if member_id and session.member_id != member_id:
            session.member_id = member_id
            updated = True
        return updated

    def add_message(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: str,
        role: str,
        content: str,
        metadata_json: str | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=user_id,
            tenant_id=tenant_id,
            role=role,
            content=content,
            metadata_json=metadata_json,
        )
        db.add(message)
        db.flush()
        return message

    def touch_session_activity(self, session: ChatSession) -> None:
        session.last_message_at = datetime.now(timezone.utc)
        session.is_active = True

    def list_chat_history(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: str,
        limit: int = 50,
    ) -> list[ChatMessage]:
        rows = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == user_id, ChatMessage.tenant_id == tenant_id)
            .order_by(ChatMessage.timestamp.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return rows

    def delete_chat_history(self, db: Session, *, tenant_id: int, user_id: str) -> int:
        return (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == user_id, ChatMessage.tenant_id == tenant_id)
            .delete(synchronize_session=False)
        )

    def set_session_link(
        self,
        db: Session,
        *,
        tenant_id: int,
        user_id: str,
        member_id: str | None,
    ) -> bool:
        session = self.get_session_by_user_id(db, tenant_id, user_id)
        if not session:
            return False
        session.member_id = member_id
        return True


persistence_repo = PersistenceRepository()
