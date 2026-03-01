"""Contacts Refactoring – Phase 1: New normalized contact data model.

Revision ID: cf01_contacts_v2
Revises: (latest)
Create Date: 2026-03-01

Creates the following tables:
- contacts (core entity replacing studio_members)
- contact_identifiers (identity resolution)
- contact_activities (timeline / audit)
- contact_notes (rich-text notes)
- contact_tags (tag definitions)
- contact_tag_associations (many-to-many)
- contact_custom_field_definitions (EAV schema)
- contact_custom_field_values (EAV data)
- contact_segments (targeting)
- contact_import_logs (import tracking)
"""

from alembic import op
import sqlalchemy as sa

revision = "cf01_contacts_v2"
down_revision = None  # Will be set to latest existing migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── contacts ──────────────────────────────────────────────────────────
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("first_name", sa.String(255), nullable=False),
        sa.Column("last_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=True, index=True),
        sa.Column("phone", sa.String(50), nullable=True, index=True),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("preferred_language", sa.String(10), nullable=True, server_default="de"),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("lifecycle_stage", sa.String(50), nullable=False, server_default="subscriber"),
        sa.Column("source", sa.String(100), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("consent_email", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("consent_sms", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("consent_phone", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("consent_whatsapp", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("gdpr_accepted_at", sa.DateTime(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("external_ids", sa.Text(), nullable=True),
        sa.Column("legacy_member_id", sa.Integer(), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_contacts_tenant_email", "contacts", ["tenant_id", "email"])
    op.create_index("ix_contacts_tenant_phone", "contacts", ["tenant_id", "phone"])
    op.create_index("ix_contacts_tenant_lifecycle", "contacts", ["tenant_id", "lifecycle_stage"])
    op.create_index("ix_contacts_tenant_source", "contacts", ["tenant_id", "source"])
    op.create_index("ix_contacts_tenant_deleted", "contacts", ["tenant_id", "deleted_at"])

    # ── contact_identifiers ───────────────────────────────────────────────
    op.create_table(
        "contact_identifiers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("identifier_type", sa.String(50), nullable=False),
        sa.Column("identifier_value", sa.String(500), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ci_tenant_type_value", "contact_identifiers", ["tenant_id", "identifier_type", "identifier_value"])
    op.create_unique_constraint("uq_contact_identifier", "contact_identifiers", ["tenant_id", "identifier_type", "identifier_value"])

    # ── contact_activities ────────────────────────────────────────────────
    op.create_table(
        "contact_activities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("activity_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("performed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("performed_by_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ca_contact_created", "contact_activities", ["contact_id", "created_at"])
    op.create_index("ix_ca_tenant_type", "contact_activities", ["tenant_id", "activity_type"])

    # ── contact_notes ─────────────────────────────────────────────────────
    op.create_table(
        "contact_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── contact_tags ──────────────────────────────────────────────────────
    op.create_table(
        "contact_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(7), nullable=True, server_default="#6C5CE7"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_contact_tag_name", "contact_tags", ["tenant_id", "name"])

    # ── contact_tag_associations ──────────────────────────────────────────
    op.create_table(
        "contact_tag_associations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("contact_tags.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_contact_tag_assoc", "contact_tag_associations", ["contact_id", "tag_id"])

    # ── contact_custom_field_definitions ──────────────────────────────────
    op.create_table(
        "contact_custom_field_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("field_slug", sa.String(100), nullable=False),
        sa.Column("field_type", sa.String(50), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("options_json", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_custom_field_slug", "contact_custom_field_definitions", ["tenant_id", "field_slug"])

    # ── contact_custom_field_values ───────────────────────────────────────
    op.create_table(
        "contact_custom_field_values",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("field_definition_id", sa.Integer(), sa.ForeignKey("contact_custom_field_definitions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_custom_field_value", "contact_custom_field_values", ["contact_id", "field_definition_id"])

    # ── contact_segments ──────────────────────────────────────────────────
    op.create_table(
        "contact_segments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("filter_json", sa.Text(), nullable=True),
        sa.Column("is_dynamic", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("contact_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── contact_import_logs ───────────────────────────────────────────────
    op.create_table(
        "contact_import_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("filename", sa.String(500), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("contact_import_logs")
    op.drop_table("contact_segments")
    op.drop_table("contact_custom_field_values")
    op.drop_table("contact_custom_field_definitions")
    op.drop_table("contact_tag_associations")
    op.drop_table("contact_tags")
    op.drop_table("contact_notes")
    op.drop_table("contact_activities")
    op.drop_table("contact_identifiers")
    op.drop_table("contacts")
