#!/usr/bin/env python3
"""seed_demo_tenant.py — Erstellt Demo-Mandant mit anonymisierten GETIMPULSE-ähnlichen Daten.

Verwendung:
    python scripts/seed_demo_tenant.py [--reset]

    --reset   Löscht demo-Tenant + alle Daten vor dem Neustarten (idempotent)

Erzeugt:
    - Tenant "ariia-demo" mit tenant_admin Benutzer
    - 15 anonymisierte StudioMember (Namens- und Kontaktanonymisierung)
    - 60 ChatSessions mit realistischen Gesprächsverläufen (WhatsApp + Telegram)
    - Vollständige Settings inkl. Magicline-Platzhalter (kein echter API-Key)
    - Plan: Starter (auto-assigned)

Verifikation:
    Nach dem Script: python scripts/seed_demo_tenant.py --verify
"""

import sys
import os
import json
import random
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Projekt-Root ins sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:////app/data/ariia.db")

from app.core.db import SessionLocal, engine, Base
from app.core.auth import hash_password, normalize_tenant_slug
from app.core.models import (
    Tenant, UserAccount, StudioMember, ChatSession, ChatMessage,
    Plan, Subscription, AuditLog,
)

Base.metadata.create_all(bind=engine)

# ── Anonymisierte Demo-Daten (GETIMPULSE-Profil, vollständig fiktiv) ──────────

DEMO_SLUG = "ariia-demo"
DEMO_NAME = "ARIIA Demo Studio"
DEMO_ADMIN_EMAIL = "demo@ariia.demo"
DEMO_ADMIN_PASSWORD = "Demo!ariia2026"

# Anonymisierte Mitglieder — Vornamen aus dt. Top-100, Nachnamen mit Initiale
DEMO_MEMBERS = [
    {"first": "Lena",    "last": "M.", "gender": "FEMALE", "lang": "de", "since_days": 420, "active": True},
    {"first": "Tobias",  "last": "K.", "gender": "MALE",   "lang": "de", "since_days": 310, "active": True},
    {"first": "Sarah",   "last": "B.", "gender": "FEMALE", "lang": "de", "since_days": 180, "active": True},
    {"first": "Markus",  "last": "H.", "gender": "MALE",   "lang": "de", "since_days": 730, "active": True},
    {"first": "Julia",   "last": "S.", "gender": "FEMALE", "lang": "de", "since_days": 90,  "active": True},
    {"first": "Felix",   "last": "W.", "gender": "MALE",   "lang": "de", "since_days": 550, "active": False},
    {"first": "Anna",    "last": "L.", "gender": "FEMALE", "lang": "de", "since_days": 60,  "active": True},
    {"first": "David",   "last": "R.", "gender": "MALE",   "lang": "en", "since_days": 200, "active": True},
    {"first": "Emma",    "last": "T.", "gender": "FEMALE", "lang": "de", "since_days": 140, "active": True},
    {"first": "Max",     "last": "G.", "gender": "MALE",   "lang": "de", "since_days": 800, "active": True},
    {"first": "Lisa",    "last": "F.", "gender": "FEMALE", "lang": "de", "since_days": 30,  "active": True},
    {"first": "Jonas",   "last": "P.", "gender": "MALE",   "lang": "de", "since_days": 365, "active": False},
    {"first": "Marie",   "last": "N.", "gender": "FEMALE", "lang": "de", "since_days": 250, "active": True},
    {"first": "Kevin",   "last": "D.", "gender": "MALE",   "lang": "de", "since_days": 120, "active": True},
    {"first": "Sophie",  "last": "C.", "gender": "FEMALE", "lang": "en", "since_days": 75,  "active": True},
]

# Typische Fitness-Studio Support-Szenarien (anonymisiert, realistisch)
CHAT_INTENTS = [
    {
        "intent": "kurs_buchung",
        "user_msgs": [
            "Hallo! Gibt es noch freie Plätze im Spinning-Kurs morgen früh?",
            "Wann ist der nächste Yoga-Kurs?",
            "Kann ich mich noch für Pilates anmelden?",
        ],
        "ai_replies": [
            "Hey! 🎉 Ja, im Spinning Kurs morgen um 07:30 Uhr sind noch 3 Plätze frei! Soll ich dich direkt eintragen?",
            "Der nächste Yoga-Kurs ist am Mittwoch um 18:00 Uhr mit Kursleiter Thomas. Noch 8 Plätze frei!",
            "Für Pilates am Donnerstag (19:00 Uhr) ist noch 1 Platz verfügbar. Möchtest du ihn reservieren?",
        ],
        "escalated": False,
        "confidence": 0.92,
    },
    {
        "intent": "mitgliedschaft_info",
        "user_msgs": [
            "Was kostet eine Mitgliedschaft bei euch?",
            "Gibt es ein Probetraining?",
            "Kann ich die Mitgliedschaft pausieren?",
        ],
        "ai_replies": [
            "Unsere Tarife: Flex ab 29,90€/Monat (monatlich kündbar), Standard 24,90€ (12 Monate), Premium 39,90€ inkl. Kurse & Sauna. Welcher passt zu dir?",
            "Ja! Wir bieten ein kostenloses Probetraining an. Wann möchtest du vorbeikommen? 💪",
            "Klar! Du kannst deine Mitgliedschaft bis zu 3 Monate im Jahr pausieren. Melde dich einfach an der Rezeption.",
        ],
        "escalated": False,
        "confidence": 0.88,
    },
    {
        "intent": "kuendigung",
        "user_msgs": [
            "Ich möchte kündigen.",
            "Wie kann ich meinen Vertrag beenden?",
            "Ich will meine Mitgliedschaft zum nächsten Monat kündigen.",
        ],
        "ai_replies": [
            "Oh nein, das tut mir leid zu hören! 😔 Darf ich fragen warum? Vielleicht kann ich helfen? Falls du pausieren möchtest, ist das auch eine Option.",
            "Die Kündigung ist schriftlich per E-Mail an kuendigung@studio.de möglich. Möchtest du, dass ich dir das Formular schicke?",
            "Ich verbinde dich gerade mit unserem Team für die Kündigungsanfrage. 🤝",
        ],
        "escalated": True,
        "confidence": 0.72,
    },
    {
        "intent": "oeffnungszeiten",
        "user_msgs": [
            "Wie lange habt ihr heute geöffnet?",
            "Ist das Studio am Sonntag geöffnet?",
            "Was sind eure Öffnungszeiten?",
        ],
        "ai_replies": [
            "Heute (Mo-Fr) sind wir bis 22:00 Uhr geöffnet!",
            "Ja! Sonntags haben wir von 09:00 bis 18:00 Uhr geöffnet. 🌟",
            "Öffnungszeiten:\nMo-Fr: 06:00–22:00 Uhr\nSa: 08:00–20:00 Uhr\nSo: 09:00–18:00 Uhr",
        ],
        "escalated": False,
        "confidence": 0.97,
    },
    {
        "intent": "technisches_problem",
        "user_msgs": [
            "Die App funktioniert nicht bei mir.",
            "Ich kann mich nicht in der App einloggen.",
            "Mein QR-Code zum Einchecken wird nicht erkannt.",
        ],
        "ai_replies": [
            "Das tut mir leid! Welches Betriebssystem nutzt du? Manchmal hilft es, die App neu zu installieren oder den Cache zu leeren.",
            "Versuche bitte, dein Passwort zurückzusetzen. Der Link dazu: app.studio.de/reset. Klappt das?",
            "Ich leite das an unser Tech-Team weiter. Einfach kurz an der Rezeption vorbeischauen, sie helfen dir sofort!",
        ],
        "escalated": True,
        "confidence": 0.61,
    },
    {
        "intent": "trainer_anfrage",
        "user_msgs": [
            "Ich hätte gerne Personal Training.",
            "Welche Trainer sind verfügbar?",
            "Kann ich eine Ernährungsberatung buchen?",
        ],
        "ai_replies": [
            "Super! 💪 Wir haben 3 erfahrene Personal Trainer. Soll ich einen Termin für ein kostenloses Erstgespräch vereinbaren?",
            "Aktuell verfügbar: Thomas (Kraft+Ausdauer), Jana (Yoga+Mobility), Michael (CrossFit). Interesse?",
            "Ja! Ernährungsberatung bieten wir mit unserer Ökotraphologin Mia an. Ersttermin 45 Min für 49€.",
        ],
        "escalated": False,
        "confidence": 0.85,
    },
]

PLATFORMS = ["whatsapp", "whatsapp", "whatsapp", "telegram"]  # WhatsApp-gewichtet


# ── Helper ─────────────────────────────────────────────────────────────────────

def _rand_past(max_days: int = 30) -> datetime:
    """Zufälliger Zeitpunkt in der Vergangenheit (UTC)."""
    delta_hours = random.randint(1, max_days * 24)
    return datetime.now(timezone.utc) - timedelta(hours=delta_hours)


def _phone() -> str:
    """Anonymisierte Telefonnummer im deutschen Format."""
    return f"+491{random.randint(50,79)}{random.randint(10000000, 99999999)}"


def _user_id(member_num: str, platform: str) -> str:
    return f"demo_{platform}_{member_num}"


# ── Haupt-Script ───────────────────────────────────────────────────────────────

def delete_demo_tenant(db) -> None:
    """Löscht den Demo-Tenant und alle zugehörigen Daten (Reihenfolge beachten)."""
    tenant = db.query(Tenant).filter(Tenant.slug == DEMO_SLUG).first()
    if not tenant:
        print(f"  ℹ Kein Tenant '{DEMO_SLUG}' gefunden — nichts zu löschen.")
        return
    tid = tenant.id
    # Löschreihenfolge: abhängige Tabellen zuerst
    deleted_msgs   = db.query(ChatMessage).filter(ChatMessage.tenant_id == tid).delete()
    deleted_sess   = db.query(ChatSession).filter(ChatSession.tenant_id == tid).delete()
    deleted_members = db.query(StudioMember).filter(StudioMember.tenant_id == tid).delete()
    from app.core.models import Setting
    deleted_settings = db.query(Setting).filter(Setting.tenant_id == tid).delete()
    db.query(Subscription).filter(Subscription.tenant_id == tid).delete()
    db.query(AuditLog).filter(AuditLog.tenant_id == tid).delete()
    db.query(UserAccount).filter(UserAccount.tenant_id == tid).delete()
    db.delete(tenant)
    db.commit()
    print(
        f"  ✓ Demo-Tenant gelöscht: {deleted_msgs} Nachrichten, "
        f"{deleted_sess} Sessions, {deleted_members} Mitglieder, "
        f"{deleted_settings} Settings."
    )


def seed_demo_tenant() -> None:
    db = SessionLocal()
    try:
        # ── 1. Tenant anlegen ──────────────────────────────────────────────────
        existing = db.query(Tenant).filter(Tenant.slug == DEMO_SLUG).first()
        if existing:
            print(f"  ℹ Tenant '{DEMO_SLUG}' existiert bereits (id={existing.id}). Nutze ihn.")
            tenant = existing
        else:
            tenant = Tenant(slug=DEMO_SLUG, name=DEMO_NAME, is_active=True)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"  ✓ Tenant '{DEMO_SLUG}' erstellt (id={tenant.id})")

        tid = tenant.id

        # ── 2. Demo-Admin-Benutzer ─────────────────────────────────────────────
        existing_user = db.query(UserAccount).filter(UserAccount.email == DEMO_ADMIN_EMAIL).first()
        if not existing_user:
            admin = UserAccount(
                tenant_id=tid,
                email=DEMO_ADMIN_EMAIL,
                full_name="ARIIA Demo Admin",
                role="tenant_admin",
                password_hash=hash_password(DEMO_ADMIN_PASSWORD),
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print(f"  ✓ Admin-User '{DEMO_ADMIN_EMAIL}' erstellt")
        else:
            print(f"  ℹ Admin-User '{DEMO_ADMIN_EMAIL}' existiert bereits")

        # ── 3. Starter-Plan zuweisen ───────────────────────────────────────────
        existing_sub = db.query(Subscription).filter(Subscription.tenant_id == tid).first()
        if not existing_sub:
            starter = db.query(Plan).filter(Plan.slug == "starter", Plan.is_active.is_(True)).first()
            if starter:
                db.add(Subscription(tenant_id=tid, plan_id=starter.id, status="active"))
                db.commit()
                print(f"  ✓ Starter-Plan zugewiesen")
        else:
            print(f"  ℹ Subscription bereits vorhanden")

        # ── 4. Settings seeden (Demo-Studio-Profil) ────────────────────────────
        from app.gateway.persistence import persistence as _ps
        from app.core.prompt_builder import seed_prompt_settings

        demo_settings = {
            "studio_name":             DEMO_NAME,
            "studio_short_name":       "ARIIA Demo",
            "agent_display_name":      "ARIIA",
            "studio_locale":           "de-DE",
            "studio_timezone":         "Europe/Berlin",
            "studio_emergency_number": "112",
            "studio_address":          "Musterstraße 1, 10115 Berlin (Demo)",
            "tenant_display_name":     DEMO_NAME,
            "tenant_timezone":         "Europe/Berlin",
            "tenant_locale":           "de-DE",
            "checkin_enabled":         "false",
            "magicline_base_url":      "",  # kein echter Key im Demo-Tenant
            "magicline_api_key":       "",
            "magicline_studio_id":     "",
            "magicline_tenant_id":     "",
            "magicline_auto_sync_enabled": "false",
            "sales_prices_text": (
                "🏋️ **Demo Studio Tarife:**\n"
                "- Flex: 29,90€/Monat (monatlich kündbar)\n"
                "- Standard: 24,90€/Monat (12 Monate Laufzeit)\n"
                "- Premium: 39,90€/Monat (Kurse + Sauna + PT)"
            ),
            "persona_bio_text": (
                "Persönlichkeit: Cool, motivierend, direkt. "
                "Du bist ARIIA, der KI-Assistent von ARIIA Demo Studio. "
                "Sprache immer Deutsch, kurze Sätze, freundlich."
            ),
        }
        for key, val in demo_settings.items():
            try:
                _ps.upsert_setting(key, val, tenant_id=tid)
            except Exception as e:
                print(f"  ⚠ Setting '{key}' konnte nicht gesetzt werden: {e}")
        print(f"  ✓ {len(demo_settings)} Settings gesetzt")

        # ── 5. Anonymisierte StudioMember ─────────────────────────────────────
        members_created = 0
        member_records: list[StudioMember] = []
        for i, m in enumerate(DEMO_MEMBERS, start=1000):
            member_num = str(1_000_000 + i)
            existing_member = db.query(StudioMember).filter(
                StudioMember.tenant_id == tid,
                StudioMember.customer_id == i,
            ).first()
            if existing_member:
                member_records.append(existing_member)
                continue

            since = datetime.now(timezone.utc) - timedelta(days=m["since_days"])
            checkin_data = {
                "total_30d": random.randint(4, 20),
                "total_90d": random.randint(12, 60),
                "avg_per_week": round(random.uniform(1.5, 4.5), 1),
                "last_visit": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 14))).isoformat(),
                "status": "AKTIV" if m["active"] else "INAKTIV",
                "source": "checkin",
            }
            member = StudioMember(
                tenant_id=tid,
                customer_id=i,
                member_number=member_num,
                first_name=m["first"],
                last_name=m["last"],
                phone_number=_phone(),
                email=f"demo.member.{i}@example-ariia.demo",
                gender=m["gender"],
                preferred_language=m["lang"],
                member_since=since,
                is_paused=not m["active"],
                checkin_stats=json.dumps(checkin_data),
                enriched_at=datetime.now(timezone.utc),
                created_at=since,
            )
            db.add(member)
            member_records.append(member)
            members_created += 1

        db.commit()
        print(f"  ✓ {members_created} Mitglieder erstellt ({len(member_records)} gesamt)")

        # ── 6. ChatSessions + Nachrichten ──────────────────────────────────────
        sessions_created = 0
        messages_created = 0

        for member in member_records:
            num_sessions = random.randint(1, 5)
            for s_idx in range(num_sessions):
                platform = random.choice(PLATFORMS)
                user_id = _user_id(str(member.customer_id), platform) + f"_s{s_idx}"

                existing_session = db.query(ChatSession).filter(
                    ChatSession.user_id == user_id,
                    ChatSession.tenant_id == tid,
                ).first()
                if existing_session:
                    continue

                session_time = _rand_past(30)
                session = ChatSession(
                    user_id=user_id,
                    tenant_id=tid,
                    platform=platform,
                    user_name=f"{member.first_name} {member.last_name}",
                    phone_number=member.phone_number,
                    member_id=str(member.customer_id),
                    created_at=session_time,
                    last_message_at=session_time + timedelta(minutes=random.randint(2, 45)),
                    is_active=False,
                )
                db.add(session)
                db.commit()
                db.refresh(session)
                sessions_created += 1

                # Nachrichten für diese Session
                intent = random.choice(CHAT_INTENTS)
                msg_time = session_time
                num_exchanges = random.randint(1, 3)

                for ex in range(num_exchanges):
                    user_txt = random.choice(intent["user_msgs"])
                    ai_txt   = random.choice(intent["ai_replies"])

                    user_msg = ChatMessage(
                        session_id=user_id,
                        tenant_id=tid,
                        role="user",
                        content=user_txt,
                        timestamp=msg_time,
                        metadata_json=json.dumps({
                            "channel": platform,
                            "intent": intent["intent"],
                        }),
                    )
                    db.add(user_msg)
                    msg_time += timedelta(seconds=random.randint(10, 120))

                    is_last = ex == num_exchanges - 1
                    ai_meta = {
                        "channel": platform,
                        "intent": intent["intent"],
                        "confidence": intent["confidence"] + random.uniform(-0.05, 0.05),
                        "escalated": intent["escalated"] if is_last else False,
                    }
                    ai_msg = ChatMessage(
                        session_id=user_id,
                        tenant_id=tid,
                        role="assistant",
                        content=ai_txt,
                        timestamp=msg_time,
                        metadata_json=json.dumps(ai_meta),
                    )
                    db.add(ai_msg)
                    msg_time += timedelta(seconds=random.randint(5, 30))
                    messages_created += 2

                db.commit()

        print(f"  ✓ {sessions_created} Sessions, {messages_created} Nachrichten erstellt")

    finally:
        db.close()


def verify_demo_tenant() -> None:
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == DEMO_SLUG).first()
        if not tenant:
            print(f"  ✗ Tenant '{DEMO_SLUG}' nicht gefunden!")
            return
        tid = tenant.id
        members = db.query(StudioMember).filter(StudioMember.tenant_id == tid).count()
        sessions = db.query(ChatSession).filter(ChatSession.tenant_id == tid).count()
        messages = db.query(ChatMessage).filter(ChatMessage.tenant_id == tid).count()
        users    = db.query(UserAccount).filter(UserAccount.tenant_id == tid).count()
        sub      = db.query(Subscription).filter(Subscription.tenant_id == tid).first()
        print(f"\n  Demo-Tenant Verifikation:")
        print(f"    Tenant:      {tenant.name} (id={tid}, slug={tenant.slug})")
        print(f"    Benutzer:    {users}")
        print(f"    Mitglieder:  {members}")
        print(f"    Sessions:    {sessions}")
        print(f"    Nachrichten: {messages}")
        print(f"    Plan:        {'Starter' if sub else '❌ KEIN PLAN!'}")
        print(f"\n  Login: {DEMO_ADMIN_EMAIL} / {DEMO_ADMIN_PASSWORD}")
        ok = members >= 10 and sessions >= 10 and messages >= 20 and sub
        print(f"\n  Ergebnis: {'✅ OK' if ok else '⚠️ Unvollständig'}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARIIA Demo-Tenant Seeding Script")
    parser.add_argument("--reset",  action="store_true", help="Demo-Tenant vor dem Seeden löschen")
    parser.add_argument("--verify", action="store_true", help="Nur Verifikation (kein Seeding)")
    args = parser.parse_args()

    if args.verify:
        print("\n🔍 ARIIA Demo-Tenant Verifikation...\n")
        verify_demo_tenant()
        sys.exit(0)

    print("\n🌱 ARIIA Demo-Tenant Seeding...")
    print(f"   Ziel: '{DEMO_SLUG}' ({DEMO_NAME})")
    print(f"   {len(DEMO_MEMBERS)} Mitglieder · {len(CHAT_INTENTS)} Intent-Templates · Platforms: WhatsApp, Telegram\n")

    db = SessionLocal()
    try:
        if args.reset:
            print("🗑  --reset: Alte Demo-Daten werden gelöscht...")
            delete_demo_tenant(db)
    finally:
        db.close()

    try:
        seed_demo_tenant()
        print("\n✅ Seeding abgeschlossen!\n")
        verify_demo_tenant()
    except Exception as e:
        import traceback
        print(f"\n❌ Fehler beim Seeding: {e}")
        traceback.print_exc()
        sys.exit(1)
