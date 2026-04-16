from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Float

from app.core.db import Base, TenantScopedMixin


class ChatSession(Base, TenantScopedMixin):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    platform = Column(String)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_message_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    user_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    email = Column(String, nullable=True)
    member_id = Column(String, nullable=True)


class ChatMessage(Base, TenantScopedMixin):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    metadata_json = Column(Text, nullable=True)


class MemberFeedback(Base, TenantScopedMixin):
    __tablename__ = "member_feedback"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class StudioMember(Base, TenantScopedMixin):
    __tablename__ = "studio_members"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, index=True, nullable=False)
    member_number = Column(String, index=True, nullable=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    phone_number = Column(String, nullable=True)
    email = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    preferred_language = Column(String, nullable=True)
    member_since = Column(DateTime(timezone=True), nullable=True)
    is_paused = Column(Boolean, nullable=True, default=False)
    pause_info = Column(Text, nullable=True)
    contract_info = Column(Text, nullable=True)
    additional_info = Column(Text, nullable=True)
    checkin_stats = Column(Text, nullable=True)
    recent_bookings = Column(Text, nullable=True)
    enriched_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(String, default="manual", nullable=False)
    source_id = Column(String, nullable=True)
    tags = Column(Text, nullable=True)
    custom_fields = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class MemberCustomColumn(Base, TenantScopedMixin):
    __tablename__ = "member_custom_columns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    field_type = Column(String, nullable=False)
    options = Column(Text, nullable=True)
    position = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_member_column_slug"),
    )


class MemberImportLog(Base, TenantScopedMixin):
    __tablename__ = "member_import_logs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    status = Column(String, nullable=False)
    total_rows = Column(Integer, default=0)
    imported = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    error_log = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MemberSegment(Base, TenantScopedMixin):
    __tablename__ = "member_segments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    filter_json = Column(Text, nullable=True)
    is_dynamic = Column(Boolean, nullable=False, default=True)
    member_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ScheduledFollowUp(Base, TenantScopedMixin):
    __tablename__ = "scheduled_follow_ups"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("studio_members.id"), nullable=True, index=True)
    conversation_id = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    ai_context_json = Column(Text, nullable=True)
    follow_up_at = Column(DateTime(timezone=True), nullable=False)
    message_template = Column(Text, nullable=True)
    channel = Column(String, nullable=False, default="whatsapp")
    status = Column(String, nullable=False, default="pending")
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ContactConsent(Base):
    __tablename__ = "contact_consents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(Integer, nullable=False)
    channel = Column(String(50), nullable=False)
    consent_given = Column(Boolean, nullable=False, default=True)
    given_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    consent_source = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    optin_token = Column(String(255), nullable=True, unique=True)


__all__ = [
    "ChatMessage",
    "ChatSession",
    "ContactConsent",
    "MemberCustomColumn",
    "MemberFeedback",
    "MemberImportLog",
    "MemberSegment",
    "ScheduledFollowUp",
    "StudioMember",
]
