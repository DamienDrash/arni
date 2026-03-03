#!/usr/bin/env python3
"""Fix Athletik Movement tenant settings and register Calendly integration.

Run inside the ariia-core container:
    docker exec -it staging-ariia-core-1 python3 scripts/fix_athletik_movement_settings.py
"""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://ariia:ariia_dev_password@ariia-postgres:5432/ariia_staging"
)

TENANT_ID = 2

# ── Settings to UPDATE ──────────────────────────────────────────────────────

SETTINGS_UPDATES = {
    # Fix: Adresse laut Website (Liesenstraße 3, nicht Heidestraße 11)
    "studio_address": "Liesenstraße 3, 10115 Berlin",

    # Fix: Persona-Bio passend zum tatsächlichen Geschäftsmodell
    "persona_bio_text": (
        "Du bist ARIIA, der digitale Assistent von Athletik Movement. "
        "Athletik Movement ist KEIN Fitnessstudio und KEIN Gym – es ist eine Einzelpraxis "
        "für Bewegungstherapie und Personal Training in Berlin-Mitte, geführt von Niklas Jauch. "
        "Niklas arbeitet 1:1 mit Klienten, die unter Schmerzen, Bewegungseinschränkungen oder "
        "Fehlhaltungen leiden. Seine eigene Methode, der SmartMotionApproach, verbindet "
        "wissenschaftlich fundierte Bewegungswissenschaft mit innovativen Techniken zur "
        "nachhaltigen Schmerzreduktion. Du kommunizierst freundlich, professionell und "
        "empathisch. Du verwendest die Du-Form. Du gibst keine medizinischen Diagnosen "
        "und verweist bei medizinischen Fragen an Ärzte."
    ),

    # Fix: Medic-Disclaimer angepasst
    "medic_disclaimer_text": (
        "Hinweis: Die Beratung durch unseren digitalen Assistenten ersetzt keine ärztliche "
        "Diagnose oder Behandlung. Bei akuten Schmerzen, Verletzungen oder medizinischen "
        "Notfällen wenden Sie sich bitte an Ihren Arzt oder rufen Sie den Notruf 112 an. "
        "Athletik Movement bietet Bewegungstherapie und Personal Training an – keine "
        "medizinische Behandlung."
    ),
}

# ── Settings to INSERT (if not exist) ───────────────────────────────────────

SETTINGS_INSERTS = {
    "studio_phone": "+49 (0) 176 43265161",
    "studio_email": "info@athletik-movement.de",
    "studio_website": "https://athletik-movement.de",
    "studio_owner_name": "Niklas Jauch",
    "studio_business_type": "personal_training",  # Not a gym/studio
    "studio_description": (
        "Athletik Movement – Einzelpraxis für Bewegungstherapie und Personal Training. "
        "Inhaber Niklas Jauch arbeitet 1:1 mit Klienten nach dem SmartMotionApproach, "
        "einem ganzheitlichen System zur ursachenbasierten Schmerztherapie in 2 Stufen "
        "und 4 Phasen (MoveFlex + MoveSync)."
    ),
}


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        print("=" * 60)
        print("Athletik Movement – Settings Fix")
        print("=" * 60)

        # 1. Update existing settings
        print("\n── Updating existing settings ──")
        for key, value in SETTINGS_UPDATES.items():
            result = await conn.execute(
                text("UPDATE settings SET value = :val WHERE tenant_id = :tid AND key = :key"),
                {"val": value, "tid": TENANT_ID, "key": key}
            )
            status = "UPDATED" if result.rowcount > 0 else "NOT FOUND (will insert)"
            print(f"  {key}: {status}")

            if result.rowcount == 0:
                await conn.execute(
                    text("INSERT INTO settings (tenant_id, key, value) VALUES (:tid, :key, :val)"),
                    {"tid": TENANT_ID, "key": key, "val": value}
                )
                print(f"  {key}: INSERTED")

        # 2. Insert new settings (if not exist)
        print("\n── Inserting new settings ──")
        for key, value in SETTINGS_INSERTS.items():
            existing = await conn.execute(
                text("SELECT 1 FROM settings WHERE tenant_id = :tid AND key = :key"),
                {"tid": TENANT_ID, "key": key}
            )
            if existing.fetchone():
                print(f"  {key}: ALREADY EXISTS (skipped)")
            else:
                await conn.execute(
                    text("INSERT INTO settings (tenant_id, key, value) VALUES (:tid, :key, :val)"),
                    {"tid": TENANT_ID, "key": key, "val": value}
                )
                print(f"  {key}: INSERTED")

        # 3. Register Calendly in tenant_integrations (if table exists)
        print("\n── Registering Calendly integration ──")
        try:
            # Check if table exists
            table_check = await conn.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'tenant_integrations')")
            )
            table_exists = table_check.scalar()

            if table_exists:
                # Check if already registered
                existing = await conn.execute(
                    text("SELECT id FROM tenant_integrations WHERE tenant_id = :tid AND integration_id = 'calendly'"),
                    {"tid": TENANT_ID}
                )
                if existing.fetchone():
                    print("  Calendly: ALREADY REGISTERED")
                else:
                    # Get the integration_definition id for calendly
                    def_check = await conn.execute(
                        text("SELECT id FROM integration_definitions WHERE integration_id = 'calendly'")
                    )
                    def_row = def_check.fetchone()

                    if def_row:
                        await conn.execute(
                            text("""
                                INSERT INTO tenant_integrations 
                                (tenant_id, integration_id, definition_id, is_active, config)
                                VALUES (:tid, 'calendly', :def_id, true, '{}')
                            """),
                            {"tid": TENANT_ID, "def_id": def_row[0]}
                        )
                        print("  Calendly: REGISTERED ✓")
                    else:
                        # Fallback: insert without definition_id reference
                        await conn.execute(
                            text("""
                                INSERT INTO tenant_integrations 
                                (tenant_id, integration_id, is_active, config)
                                VALUES (:tid, 'calendly', true, '{}')
                            """),
                            {"tid": TENANT_ID}
                        )
                        print("  Calendly: REGISTERED (without definition_id)")
            else:
                print("  tenant_integrations table does not exist yet (migration not run)")
                print("  Calendly integration will be detected via settings fallback")
        except Exception as e:
            print(f"  Error registering Calendly: {e}")
            print("  Calendly will still work via settings-based detection")

        # 4. Verify
        print("\n── Verification ──")
        result = await conn.execute(
            text("SELECT key, LEFT(value::text, 80) FROM settings WHERE tenant_id = :tid ORDER BY key"),
            {"tid": TENANT_ID}
        )
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]}")

    await engine.dispose()
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
