from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from app.core.db import Base, TenantScopedMixin


class Campaign(Base, TenantScopedMixin):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String, nullable=False, default="broadcast")
    status = Column(String, nullable=False, default="draft")
    channel = Column(String, nullable=False, default="email")
    target_type = Column(String, nullable=False, default="all_members")
    target_filter_json = Column(Text, nullable=True)
    template_id = Column(Integer, ForeignKey("campaign_templates.id"), nullable=True)
    content_subject = Column(String, nullable=True)
    content_body = Column(Text, nullable=True)
    content_html = Column(Text, nullable=True)
    ai_prompt = Column(Text, nullable=True)
    ai_generated_content = Column(Text, nullable=True)
    preview_token = Column(String, nullable=True, unique=True, index=True)
    preview_expires_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    stats_total = Column(Integer, nullable=False, default=0)
    stats_sent = Column(Integer, nullable=False, default=0)
    stats_delivered = Column(Integer, nullable=False, default=0)
    stats_opened = Column(Integer, nullable=False, default=0)
    stats_clicked = Column(Integer, nullable=False, default=0)
    stats_failed = Column(Integer, nullable=False, default=0)
    is_ab_test = Column(Boolean, nullable=False, default=False)
    ab_winner_variant = Column(String, nullable=True)
    ab_test_percentage = Column(Integer, nullable=False, default=20)
    ab_test_duration_hours = Column(Integer, nullable=False, default=4)
    ab_test_metric = Column(String(30), nullable=False, default="open_rate")
    ab_test_auto_send = Column(Boolean, nullable=False, default=True)
    budget_planned = Column(Float, nullable=True)
    budget_spent = Column(Float, nullable=True)
    calendar_color = Column(String(7), nullable=True)
    smart_send_enabled = Column(Boolean, nullable=False, default=False)
    featured_image_url = Column(String(512), nullable=True)
    featured_image_asset_id = Column(Integer, nullable=True)
    attachment_url = Column(String(512), nullable=True)
    attachment_filename = Column(String(255), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CampaignTemplate(Base, TenantScopedMixin):
    __tablename__ = "campaign_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String, nullable=False, default="email")
    header_html = Column(Text, nullable=True)
    footer_html = Column(Text, nullable=True)
    body_template = Column(Text, nullable=True)
    variables_json = Column(Text, nullable=True)
    primary_color = Column(String, nullable=True, default="#6C5CE7")
    logo_url = Column(String, nullable=True)
    featured_image_url = Column(String(512), nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CampaignVariant(Base):
    __tablename__ = "campaign_variants"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    variant_name = Column(String, nullable=False, default="A")
    content_subject = Column(String, nullable=True)
    content_body = Column(Text, nullable=True)
    content_html = Column(Text, nullable=True)
    percentage = Column(Integer, nullable=False, default=50)
    stats_sent = Column(Integer, nullable=False, default=0)
    stats_opened = Column(Integer, nullable=False, default=0)
    stats_clicked = Column(Integer, nullable=False, default=0)
    is_winner = Column(Boolean, nullable=False, default=False)
    winner_selected_at = Column(DateTime(timezone=True), nullable=True)
    winner_metric = Column(String(30), nullable=True)
    confidence_level = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CampaignRecipient(Base, TenantScopedMixin):
    __tablename__ = "campaign_recipients"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("studio_members.id"), nullable=True, index=True)
    contact_id = Column(Integer, nullable=True, index=True)
    channel = Column(String, nullable=True)
    variant_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    clicked_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    current_step = Column(Integer, nullable=True, default=1)
    converted_at = Column(DateTime(timezone=True), nullable=True)
    conversion_value = Column(Float, nullable=True)
    offer_slug = Column(String(64), nullable=True)


class CampaignOffer(Base):
    __tablename__ = "campaign_offers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    slug = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    confirmation_message = Column(Text, nullable=False)
    attachment_url = Column(String(512), nullable=True)
    attachment_filename = Column(String(256), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_campaign_offer_slug"),)


__all__ = [
    "Campaign",
    "CampaignOffer",
    "CampaignRecipient",
    "CampaignTemplate",
    "CampaignVariant",
]
