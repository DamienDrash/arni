from __future__ import annotations

from dataclasses import dataclass

from app.core.db import SessionLocal
from app.core.models import StudioMember


def normalize_phone(value: str | None) -> str:
    if not value:
        return ""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    return digits


def phone_candidates(value: str | None) -> set[str]:
    normalized = normalize_phone(value)
    if not normalized:
        return set()

    candidates = {normalized}
    if normalized.startswith("49") and len(normalized) > 8:
        candidates.add(normalized[2:])
    if normalized.startswith("0") and len(normalized) > 8:
        candidates.add(f"49{normalized[1:]}")
    if len(normalized) >= 10:
        candidates.add(normalized[-10:])
    return {c for c in candidates if c}


@dataclass
class PhoneMatchResult:
    member_number: str | None
    customer_id: int
    first_name: str
    last_name: str
    email: str | None


def match_member_by_phone(phone_number: str | None, tenant_id: int | None = None) -> PhoneMatchResult | None:
    """Return exactly one member match for a phone number, else None."""
    requested = phone_candidates(phone_number)
    if not requested:
        return None

    db = SessionLocal()
    try:
        matches: list[StudioMember] = []
        q = db.query(StudioMember).filter(StudioMember.phone_number.isnot(None))
        if tenant_id is not None:
            q = q.filter(StudioMember.tenant_id == tenant_id)
        for row in q.all():
            row_candidates = phone_candidates(row.phone_number)
            if not row_candidates:
                continue
            if requested.intersection(row_candidates):
                matches.append(row)

        if len(matches) != 1:
            return None

        member = matches[0]
        return PhoneMatchResult(
            member_number=member.member_number,
            customer_id=member.customer_id,
            first_name=member.first_name,
            last_name=member.last_name,
            email=member.email,
        )
    finally:
        db.close()
