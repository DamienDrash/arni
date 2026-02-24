"""Members CRUD Router — Manual management, custom columns, CSV import/export.

Provides endpoints for:
- Manual member creation, editing, deletion
- Bulk operations (create/update multiple members)
- CSV import with column mapping
- CSV export
- Custom column management (add/edit/delete/reorder)
- Import log history
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
from datetime import date, datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.models import MemberCustomColumn, MemberImportLog, StudioMember

router = APIRouter(prefix="/admin/members", tags=["members-crud"])
logger = structlog.get_logger()

VALID_SOURCES = {"manual", "magicline", "shopify", "woocommerce", "hubspot", "csv", "api"}
VALID_FIELD_TYPES = {"text", "number", "date", "select", "boolean"}


def _require_tenant_admin_or_system(user: AuthContext) -> None:
    require_role(user, {"system_admin", "tenant_admin"})


def _slugify(name: str) -> str:
    """Convert display name to a safe slug for custom_fields keys."""
    slug = name.strip().lower()
    slug = re.sub(r"[äÄ]", "ae", slug)
    slug = re.sub(r"[öÖ]", "oe", slug)
    slug = re.sub(r"[üÜ]", "ue", slug)
    slug = re.sub(r"[ß]", "ss", slug)
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug or "field"


def _next_customer_id(db, tenant_id: int) -> int:
    """Generate the next customer_id for manually created members."""
    max_id = (
        db.query(func.max(StudioMember.customer_id))
        .filter(StudioMember.tenant_id == tenant_id)
        .scalar()
    )
    return (max_id or 0) + 1


def _member_to_dict(row: StudioMember) -> dict[str, Any]:
    """Serialize a StudioMember to a JSON-safe dict."""
    return {
        "id": row.id,
        "customer_id": row.customer_id,
        "member_number": row.member_number,
        "first_name": row.first_name,
        "last_name": row.last_name,
        "date_of_birth": row.date_of_birth.isoformat() if row.date_of_birth else None,
        "phone_number": row.phone_number,
        "email": row.email,
        "gender": row.gender,
        "preferred_language": row.preferred_language,
        "member_since": row.member_since.isoformat() if row.member_since else None,
        "is_paused": row.is_paused,
        "source": row.source,
        "source_id": row.source_id,
        "tags": json.loads(row.tags) if row.tags else [],
        "custom_fields": json.loads(row.custom_fields) if row.custom_fields else {},
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class MemberCreate(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: str | None = None
    phone_number: str | None = None
    member_number: str | None = None
    date_of_birth: str | None = None  # ISO date
    gender: str | None = None
    preferred_language: str | None = None
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None
    notes: str | None = None
    source: str = "manual"


class MemberUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone_number: str | None = None
    member_number: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    preferred_language: str | None = None
    is_paused: bool | None = None
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None
    notes: str | None = None


class BulkMemberItem(BaseModel):
    first_name: str
    last_name: str
    email: str | None = None
    phone_number: str | None = None
    member_number: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    preferred_language: str | None = None
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None
    notes: str | None = None


class BulkMemberRequest(BaseModel):
    members: list[BulkMemberItem]
    source: str = "api"
    update_existing: bool = True  # Match by email/phone and update if exists


class CustomColumnCreate(BaseModel):
    name: str = Field(..., min_length=1)
    field_type: str = "text"
    options: list[str] | None = None  # For 'select' type
    is_visible: bool = True


class CustomColumnUpdate(BaseModel):
    name: str | None = None
    field_type: str | None = None
    options: list[str] | None = None
    is_visible: bool | None = None


class ColumnReorderRequest(BaseModel):
    column_ids: list[int]  # Ordered list of column IDs


# ─── Manual CRUD ──────────────────────────────────────────────────────────────

@router.post("")
async def create_member(
    body: MemberCreate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a single member manually."""
    _require_tenant_admin_or_system(user)
    source = body.source if body.source in VALID_SOURCES else "manual"

    db = SessionLocal()
    try:
        dob = None
        if body.date_of_birth:
            try:
                dob = date.fromisoformat(body.date_of_birth)
            except ValueError:
                raise HTTPException(status_code=422, detail="Ungültiges Datumsformat für date_of_birth (erwartet: YYYY-MM-DD)")

        member = StudioMember(
            tenant_id=user.tenant_id,
            customer_id=_next_customer_id(db, user.tenant_id),
            first_name=body.first_name.strip(),
            last_name=body.last_name.strip(),
            email=(body.email or "").strip() or None,
            phone_number=(body.phone_number or "").strip() or None,
            member_number=(body.member_number or "").strip() or None,
            date_of_birth=dob,
            gender=(body.gender or "").strip() or None,
            preferred_language=(body.preferred_language or "").strip().lower() or None,
            source=source,
            tags=json.dumps(body.tags, ensure_ascii=False) if body.tags else None,
            custom_fields=json.dumps(body.custom_fields, ensure_ascii=False) if body.custom_fields else None,
            notes=(body.notes or "").strip() or None,
            member_since=datetime.now(timezone.utc),
        )
        db.add(member)
        db.commit()
        db.refresh(member)
        logger.info("members.created", member_id=member.id, source=source, tenant_id=user.tenant_id)
        return _member_to_dict(member)
    finally:
        db.close()


@router.put("/{member_id}")
async def update_member(
    member_id: int,
    body: MemberUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Update an existing member. Works for any source."""
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        member = (
            db.query(StudioMember)
            .filter(StudioMember.id == member_id, StudioMember.tenant_id == user.tenant_id)
            .first()
        )
        if not member:
            raise HTTPException(status_code=404, detail="Mitglied nicht gefunden")

        update_data = body.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "date_of_birth" and value is not None:
                try:
                    value = date.fromisoformat(value)
                except ValueError:
                    raise HTTPException(status_code=422, detail="Ungültiges Datumsformat")
            if field == "tags" and value is not None:
                value = json.dumps(value, ensure_ascii=False)
            if field == "custom_fields" and value is not None:
                # Merge with existing custom_fields
                existing = json.loads(member.custom_fields) if member.custom_fields else {}
                existing.update(value)
                value = json.dumps(existing, ensure_ascii=False)
            if field == "preferred_language" and value:
                value = value.strip().lower()
            setattr(member, field, value)

        db.commit()
        db.refresh(member)
        logger.info("members.updated", member_id=member.id, tenant_id=user.tenant_id)
        return _member_to_dict(member)
    finally:
        db.close()


@router.delete("/{member_id}")
async def delete_member(
    member_id: int,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a member. Only allowed for manual/csv/api sources."""
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        member = (
            db.query(StudioMember)
            .filter(StudioMember.id == member_id, StudioMember.tenant_id == user.tenant_id)
            .first()
        )
        if not member:
            raise HTTPException(status_code=404, detail="Mitglied nicht gefunden")

        if member.source not in ("manual", "csv", "api"):
            raise HTTPException(
                status_code=409,
                detail=f"Mitglieder aus '{member.source}' können nicht manuell gelöscht werden. "
                       f"Entferne sie stattdessen im Quellsystem und synchronisiere erneut.",
            )

        db.delete(member)
        db.commit()
        logger.info("members.deleted", member_id=member_id, tenant_id=user.tenant_id)
        return {"status": "ok", "deleted_id": str(member_id)}
    finally:
        db.close()


# ─── Bulk Operations ─────────────────────────────────────────────────────────

@router.post("/bulk")
async def bulk_create_or_update(
    body: BulkMemberRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Bulk create or update members. Matches by email or phone_number if update_existing=true."""
    _require_tenant_admin_or_system(user)
    source = body.source if body.source in VALID_SOURCES else "api"

    db = SessionLocal()
    import_log = MemberImportLog(
        tenant_id=user.tenant_id,
        source=source,
        status="running",
        total_rows=len(body.members),
    )
    db.add(import_log)
    db.commit()

    created = 0
    updated = 0
    skipped = 0
    errors = 0
    error_details: list[dict] = []

    try:
        for idx, item in enumerate(body.members):
            try:
                existing = None
                if body.update_existing:
                    if item.email:
                        existing = (
                            db.query(StudioMember)
                            .filter(
                                StudioMember.tenant_id == user.tenant_id,
                                StudioMember.email == item.email.strip(),
                            )
                            .first()
                        )
                    if not existing and item.phone_number:
                        existing = (
                            db.query(StudioMember)
                            .filter(
                                StudioMember.tenant_id == user.tenant_id,
                                StudioMember.phone_number == item.phone_number.strip(),
                            )
                            .first()
                        )

                if existing:
                    for field in ("first_name", "last_name", "email", "phone_number", "member_number", "gender", "preferred_language"):
                        val = getattr(item, field, None)
                        if val is not None:
                            setattr(existing, field, val.strip() if isinstance(val, str) else val)
                    if item.tags is not None:
                        existing.tags = json.dumps(item.tags, ensure_ascii=False)
                    if item.custom_fields is not None:
                        old = json.loads(existing.custom_fields) if existing.custom_fields else {}
                        old.update(item.custom_fields)
                        existing.custom_fields = json.dumps(old, ensure_ascii=False)
                    if item.notes is not None:
                        existing.notes = item.notes.strip() or None
                    updated += 1
                else:
                    dob = None
                    if item.date_of_birth:
                        try:
                            dob = date.fromisoformat(item.date_of_birth)
                        except ValueError:
                            pass
                    member = StudioMember(
                        tenant_id=user.tenant_id,
                        customer_id=_next_customer_id(db, user.tenant_id),
                        first_name=item.first_name.strip(),
                        last_name=item.last_name.strip(),
                        email=(item.email or "").strip() or None,
                        phone_number=(item.phone_number or "").strip() or None,
                        member_number=(item.member_number or "").strip() or None,
                        date_of_birth=dob,
                        gender=(item.gender or "").strip() or None,
                        preferred_language=(item.preferred_language or "").strip().lower() or None,
                        source=source,
                        tags=json.dumps(item.tags, ensure_ascii=False) if item.tags else None,
                        custom_fields=json.dumps(item.custom_fields, ensure_ascii=False) if item.custom_fields else None,
                        notes=(item.notes or "").strip() or None,
                        member_since=datetime.now(timezone.utc),
                    )
                    db.add(member)
                    created += 1
            except Exception as e:
                errors += 1
                error_details.append({"row": idx, "error": str(e)})

        db.commit()
        import_log.status = "completed"
        import_log.imported = created
        import_log.updated = updated
        import_log.skipped = skipped
        import_log.errors = errors
        import_log.error_log = json.dumps(error_details, ensure_ascii=False) if error_details else None
        import_log.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("members.bulk_import", created=created, updated=updated, errors=errors, tenant_id=user.tenant_id)
        return {
            "status": "completed",
            "total": len(body.members),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "error_details": error_details[:20],  # Limit error details in response
        }
    except Exception as e:
        db.rollback()
        import_log.status = "failed"
        import_log.error_log = json.dumps([{"error": str(e)}])
        import_log.completed_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Bulk-Import fehlgeschlagen: {e}")
    finally:
        db.close()


# ─── CSV Import / Export ──────────────────────────────────────────────────────

@router.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Import members from a CSV file. Auto-detects column mapping."""
    _require_tenant_admin_or_system(user)

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Nur CSV-Dateien werden unterstützt")

    content = await file.read()
    # Try UTF-8 first, then latin-1
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text), delimiter=None)  # Auto-detect delimiter
    if not reader.fieldnames:
        # Try semicolon
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV-Datei konnte nicht gelesen werden")

    # Column mapping: flexible header matching
    COLUMN_MAP: dict[str, list[str]] = {
        "first_name": ["first_name", "vorname", "firstname", "first name", "given_name"],
        "last_name": ["last_name", "nachname", "lastname", "last name", "family_name", "surname"],
        "email": ["email", "e-mail", "e_mail", "mail", "email_address"],
        "phone_number": ["phone_number", "telefon", "phone", "tel", "mobile", "handy", "telefonnummer"],
        "member_number": ["member_number", "mitgliedsnummer", "member_id", "kundennummer", "customer_number"],
        "date_of_birth": ["date_of_birth", "geburtsdatum", "birthday", "dob", "birth_date"],
        "gender": ["gender", "geschlecht", "sex"],
        "preferred_language": ["preferred_language", "sprache", "language", "lang"],
        "notes": ["notes", "notizen", "bemerkung", "comment", "kommentar"],
    }

    def _find_mapping(headers: list[str]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        normalized_headers = {h.strip().lower(): h for h in headers}
        for field, aliases in COLUMN_MAP.items():
            for alias in aliases:
                if alias in normalized_headers:
                    mapping[field] = normalized_headers[alias]
                    break
        return mapping

    mapping = _find_mapping(list(reader.fieldnames))
    if "first_name" not in mapping and "last_name" not in mapping:
        # Try combined "name" column
        name_col = None
        for h in reader.fieldnames:
            if h.strip().lower() in ("name", "full_name", "fullname", "vollständiger name"):
                name_col = h
                break
        if not name_col:
            raise HTTPException(
                status_code=422,
                detail=f"Keine erkennbaren Spalten gefunden. Verfügbare Spalten: {', '.join(reader.fieldnames)}. "
                       f"Erwartet: Vorname/first_name und Nachname/last_name (oder Name/full_name).",
            )
        mapping["_full_name"] = name_col

    rows = list(reader)
    db = SessionLocal()
    import_log = MemberImportLog(
        tenant_id=user.tenant_id,
        source="csv",
        status="running",
        total_rows=len(rows),
    )
    db.add(import_log)
    db.commit()

    created = 0
    updated = 0
    skipped = 0
    errors = 0
    error_details: list[dict] = []

    # Collect unmapped columns as custom_fields
    mapped_headers = set(mapping.values())
    custom_headers = [h for h in reader.fieldnames if h not in mapped_headers and h != mapping.get("_full_name")]

    try:
        for idx, row in enumerate(rows):
            try:
                if "_full_name" in mapping:
                    full_name = (row.get(mapping["_full_name"]) or "").strip()
                    parts = full_name.split(None, 1)
                    first_name = parts[0] if parts else "-"
                    last_name = parts[1] if len(parts) > 1 else "-"
                else:
                    first_name = (row.get(mapping.get("first_name", ""), "") or "").strip()
                    last_name = (row.get(mapping.get("last_name", ""), "") or "").strip()

                if not first_name and not last_name:
                    skipped += 1
                    continue

                email = (row.get(mapping.get("email", ""), "") or "").strip() or None
                phone = (row.get(mapping.get("phone_number", ""), "") or "").strip() or None

                # Check for existing member by email or phone
                existing = None
                if email:
                    existing = db.query(StudioMember).filter(
                        StudioMember.tenant_id == user.tenant_id,
                        StudioMember.email == email,
                    ).first()
                if not existing and phone:
                    existing = db.query(StudioMember).filter(
                        StudioMember.tenant_id == user.tenant_id,
                        StudioMember.phone_number == phone,
                    ).first()

                # Build custom_fields from unmapped columns
                cf: dict[str, str] = {}
                for ch in custom_headers:
                    val = (row.get(ch, "") or "").strip()
                    if val:
                        cf[_slugify(ch)] = val

                dob = None
                dob_str = (row.get(mapping.get("date_of_birth", ""), "") or "").strip()
                if dob_str:
                    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
                        try:
                            dob = datetime.strptime(dob_str, fmt).date()
                            break
                        except ValueError:
                            continue

                if existing:
                    if first_name:
                        existing.first_name = first_name
                    if last_name:
                        existing.last_name = last_name
                    if email:
                        existing.email = email
                    if phone:
                        existing.phone_number = phone
                    mn = (row.get(mapping.get("member_number", ""), "") or "").strip()
                    if mn:
                        existing.member_number = mn
                    if dob:
                        existing.date_of_birth = dob
                    gender = (row.get(mapping.get("gender", ""), "") or "").strip()
                    if gender:
                        existing.gender = gender
                    lang = (row.get(mapping.get("preferred_language", ""), "") or "").strip().lower()
                    if lang:
                        existing.preferred_language = lang
                    notes = (row.get(mapping.get("notes", ""), "") or "").strip()
                    if notes:
                        existing.notes = notes
                    if cf:
                        old_cf = json.loads(existing.custom_fields) if existing.custom_fields else {}
                        old_cf.update(cf)
                        existing.custom_fields = json.dumps(old_cf, ensure_ascii=False)
                    updated += 1
                else:
                    member = StudioMember(
                        tenant_id=user.tenant_id,
                        customer_id=_next_customer_id(db, user.tenant_id),
                        first_name=first_name or "-",
                        last_name=last_name or "-",
                        email=email,
                        phone_number=phone,
                        member_number=(row.get(mapping.get("member_number", ""), "") or "").strip() or None,
                        date_of_birth=dob,
                        gender=(row.get(mapping.get("gender", ""), "") or "").strip() or None,
                        preferred_language=(row.get(mapping.get("preferred_language", ""), "") or "").strip().lower() or None,
                        source="csv",
                        notes=(row.get(mapping.get("notes", ""), "") or "").strip() or None,
                        custom_fields=json.dumps(cf, ensure_ascii=False) if cf else None,
                        member_since=datetime.now(timezone.utc),
                    )
                    db.add(member)
                    created += 1
            except Exception as e:
                errors += 1
                error_details.append({"row": idx + 2, "error": str(e)})

        db.commit()
        import_log.status = "completed"
        import_log.imported = created
        import_log.updated = updated
        import_log.skipped = skipped
        import_log.errors = errors
        import_log.error_log = json.dumps(error_details, ensure_ascii=False) if error_details else None
        import_log.completed_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "status": "completed",
            "total": len(rows),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "column_mapping": mapping,
            "custom_columns_detected": custom_headers,
            "error_details": error_details[:20],
        }
    except Exception as e:
        db.rollback()
        import_log.status = "failed"
        import_log.error_log = json.dumps([{"error": str(e)}])
        import_log.completed_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"CSV-Import fehlgeschlagen: {e}")
    finally:
        db.close()


@router.get("/export/csv")
async def export_csv(
    user: AuthContext = Depends(get_current_user),
    source: str | None = Query(None, description="Filter by source"),
) -> StreamingResponse:
    """Export all members as CSV."""
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        q = db.query(StudioMember).filter(StudioMember.tenant_id == user.tenant_id)
        if source:
            q = q.filter(StudioMember.source == source)
        rows = q.order_by(StudioMember.last_name, StudioMember.first_name).all()

        # Get custom columns for header
        columns = (
            db.query(MemberCustomColumn)
            .filter(MemberCustomColumn.tenant_id == user.tenant_id, MemberCustomColumn.is_visible.is_(True))
            .order_by(MemberCustomColumn.position)
            .all()
        )

        output = io.StringIO()
        base_fields = [
            "member_number", "first_name", "last_name", "email", "phone_number",
            "date_of_birth", "gender", "preferred_language", "source", "tags", "notes",
        ]
        custom_slugs = [c.slug for c in columns]
        custom_names = [c.name for c in columns]
        header = base_fields + custom_names

        writer = csv.DictWriter(output, fieldnames=header, extrasaction="ignore")
        writer.writeheader()

        for row in rows:
            cf = json.loads(row.custom_fields) if row.custom_fields else {}
            tags = json.loads(row.tags) if row.tags else []
            csv_row = {
                "member_number": row.member_number or "",
                "first_name": row.first_name,
                "last_name": row.last_name,
                "email": row.email or "",
                "phone_number": row.phone_number or "",
                "date_of_birth": row.date_of_birth.isoformat() if row.date_of_birth else "",
                "gender": row.gender or "",
                "preferred_language": row.preferred_language or "",
                "source": row.source or "",
                "tags": ", ".join(tags),
                "notes": row.notes or "",
            }
            for slug, name in zip(custom_slugs, custom_names):
                csv_row[name] = cf.get(slug, "")
            writer.writerow(csv_row)

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=members_export_{int(time.time())}.csv"},
        )
    finally:
        db.close()


# ─── Custom Columns ──────────────────────────────────────────────────────────

@router.get("/columns")
async def list_custom_columns(
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all custom columns for the tenant."""
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        columns = (
            db.query(MemberCustomColumn)
            .filter(MemberCustomColumn.tenant_id == user.tenant_id)
            .order_by(MemberCustomColumn.position)
            .all()
        )
        return [
            {
                "id": c.id,
                "name": c.name,
                "slug": c.slug,
                "field_type": c.field_type,
                "options": json.loads(c.options) if c.options else None,
                "position": c.position,
                "is_visible": c.is_visible,
            }
            for c in columns
        ]
    finally:
        db.close()


@router.post("/columns")
async def create_custom_column(
    body: CustomColumnCreate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new custom column for the tenant."""
    _require_tenant_admin_or_system(user)

    if body.field_type not in VALID_FIELD_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger field_type. Erlaubt: {', '.join(VALID_FIELD_TYPES)}")

    slug = _slugify(body.name)
    db = SessionLocal()
    try:
        existing = (
            db.query(MemberCustomColumn)
            .filter(MemberCustomColumn.tenant_id == user.tenant_id, MemberCustomColumn.slug == slug)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail=f"Spalte '{body.name}' (slug: {slug}) existiert bereits")

        max_pos = (
            db.query(func.max(MemberCustomColumn.position))
            .filter(MemberCustomColumn.tenant_id == user.tenant_id)
            .scalar()
        ) or 0

        column = MemberCustomColumn(
            tenant_id=user.tenant_id,
            name=body.name.strip(),
            slug=slug,
            field_type=body.field_type,
            options=json.dumps(body.options, ensure_ascii=False) if body.options else None,
            position=max_pos + 1,
            is_visible=body.is_visible,
        )
        db.add(column)
        db.commit()
        db.refresh(column)

        return {
            "id": column.id,
            "name": column.name,
            "slug": column.slug,
            "field_type": column.field_type,
            "options": body.options,
            "position": column.position,
            "is_visible": column.is_visible,
        }
    finally:
        db.close()


@router.put("/columns/{column_id}")
async def update_custom_column(
    column_id: int,
    body: CustomColumnUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Update a custom column."""
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        column = (
            db.query(MemberCustomColumn)
            .filter(MemberCustomColumn.id == column_id, MemberCustomColumn.tenant_id == user.tenant_id)
            .first()
        )
        if not column:
            raise HTTPException(status_code=404, detail="Spalte nicht gefunden")

        if body.name is not None:
            column.name = body.name.strip()
            column.slug = _slugify(body.name)
        if body.field_type is not None:
            if body.field_type not in VALID_FIELD_TYPES:
                raise HTTPException(status_code=422, detail=f"Ungültiger field_type")
            column.field_type = body.field_type
        if body.options is not None:
            column.options = json.dumps(body.options, ensure_ascii=False)
        if body.is_visible is not None:
            column.is_visible = body.is_visible

        db.commit()
        db.refresh(column)
        return {
            "id": column.id,
            "name": column.name,
            "slug": column.slug,
            "field_type": column.field_type,
            "options": json.loads(column.options) if column.options else None,
            "position": column.position,
            "is_visible": column.is_visible,
        }
    finally:
        db.close()


@router.delete("/columns/{column_id}")
async def delete_custom_column(
    column_id: int,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a custom column. Does NOT remove data from custom_fields."""
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        column = (
            db.query(MemberCustomColumn)
            .filter(MemberCustomColumn.id == column_id, MemberCustomColumn.tenant_id == user.tenant_id)
            .first()
        )
        if not column:
            raise HTTPException(status_code=404, detail="Spalte nicht gefunden")

        db.delete(column)
        db.commit()
        return {"status": "ok", "deleted_id": str(column_id)}
    finally:
        db.close()


@router.put("/columns/reorder")
async def reorder_columns(
    body: ColumnReorderRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Reorder custom columns by providing an ordered list of column IDs."""
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        columns = (
            db.query(MemberCustomColumn)
            .filter(MemberCustomColumn.tenant_id == user.tenant_id)
            .all()
        )
        col_map = {c.id: c for c in columns}
        for pos, cid in enumerate(body.column_ids):
            if cid in col_map:
                col_map[cid].position = pos
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


# ─── Import Logs ──────────────────────────────────────────────────────────────

@router.get("/import-logs")
async def list_import_logs(
    user: AuthContext = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """List recent import operations."""
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        logs = (
            db.query(MemberImportLog)
            .filter(MemberImportLog.tenant_id == user.tenant_id)
            .order_by(MemberImportLog.started_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": l.id,
                "source": l.source,
                "status": l.status,
                "total_rows": l.total_rows,
                "imported": l.imported,
                "updated": l.updated,
                "skipped": l.skipped,
                "errors": l.errors,
                "started_at": l.started_at.isoformat() if l.started_at else None,
                "completed_at": l.completed_at.isoformat() if l.completed_at else None,
            }
            for l in logs
        ]
    finally:
        db.close()
