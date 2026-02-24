#!/usr/bin/env python3
"""scripts/seed_stripe_products.py — Stripe-Produkte & Preise anlegen und DB-Plans verknüpfen.

Dieses Script erstellt die ARIIA-SaaS-Pläne als Stripe-Produkte mit
monatlichen Preisen und speichert die resultierenden `price_id`s in der
lokalen `plans`-Tabelle (Spalte `stripe_price_id`).

Voraussetzungen:
    - STRIPE_SECRET_KEY als Umgebungsvariable ODER in der DB-Settings
      (billing_stripe_secret_key) gesetzt
    - Die Datenbank muss erreichbar sein (DATABASE_URL)
    - `stripe` Python-Paket installiert (in pyproject.toml enthalten)

Verwendung:
    # Direkt mit Umgebungsvariable:
    STRIPE_SECRET_KEY=sk_test_... python scripts/seed_stripe_products.py

    # Oder im Docker-Container:
    docker compose exec ariia-core python scripts/seed_stripe_products.py

Optionen:
    --dry-run       Nur anzeigen, was erstellt würde (kein Stripe-API-Call)
    --force         Vorhandene stripe_price_id überschreiben
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure app modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import stripe
from app.core.db import SessionLocal
from app.core.models import Plan


# ── Plan-Definitionen (müssen mit PLAN_CATALOG in billing.py übereinstimmen) ──

STRIPE_PLANS = [
    {
        "slug": "starter",
        "product_name": "ARIIA Starter",
        "product_description": "WhatsApp KI-Support, bis zu 500 Mitglieder, 10.000 Nachrichten/Monat",
        "price_monthly_cents": 14900,  # €149/Monat
        "currency": "eur",
    },
    {
        "slug": "pro",
        "product_name": "ARIIA Pro",
        "product_description": "WhatsApp + Telegram + E-Mail, bis zu 2.500 Mitglieder, 50.000 Nachrichten/Monat, Memory Analyzer, Custom Prompts",
        "price_monthly_cents": 34900,  # €349/Monat
        "currency": "eur",
    },
    {
        "slug": "enterprise",
        "product_name": "ARIIA Enterprise",
        "product_description": "Alle Kanäle inkl. Voice + SMS, unbegrenzte Mitglieder & Nachrichten, Dedicated CSM, SLA-Garantie",
        "price_monthly_cents": 99900,  # €999/Monat
        "currency": "eur",
    },
]


def get_stripe_key() -> str:
    """Resolve Stripe secret key from env or DB settings."""
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if key:
        return key
    # Fallback: try DB settings
    try:
        from app.gateway.persistence import persistence
        key = (persistence.get_setting("billing_stripe_secret_key", "") or "").strip()
    except Exception:
        pass
    return key


def find_existing_product(product_name: str) -> str | None:
    """Search Stripe for an existing product by name. Returns product ID or None."""
    products = stripe.Product.search(query=f'name:"{product_name}"', limit=5)
    for p in products.get("data", []):
        if p.get("name") == product_name:
            return p["id"]
    return None


def find_existing_price(product_id: str, amount_cents: int, currency: str) -> str | None:
    """Find an active recurring price for a product matching amount and currency."""
    prices = stripe.Price.list(product=product_id, active=True, type="recurring", limit=20)
    for p in prices.get("data", []):
        if (
            p.get("unit_amount") == amount_cents
            and p.get("currency") == currency
            and p.get("recurring", {}).get("interval") == "month"
        ):
            return p["id"]
    return None


def seed_stripe_products(dry_run: bool = False, force: bool = False) -> None:
    """Create Stripe products/prices and update DB plans."""
    secret_key = get_stripe_key()
    if not secret_key:
        print("FEHLER: Kein Stripe Secret Key gefunden.")
        print("  Setze STRIPE_SECRET_KEY als Umgebungsvariable oder in den DB-Settings.")
        sys.exit(1)

    is_test = secret_key.startswith("sk_test_")
    mode = "TEST" if is_test else "LIVE"
    print(f"\n{'='*60}")
    print(f"  ARIIA Stripe Product Seeder ({mode} Modus)")
    print(f"{'='*60}\n")

    if not is_test:
        print("⚠️  ACHTUNG: Du verwendest einen LIVE Stripe-Key!")
        confirm = input("  Fortfahren? (ja/nein): ").strip().lower()
        if confirm not in ("ja", "j", "yes", "y"):
            print("Abgebrochen.")
            sys.exit(0)

    stripe.api_key = secret_key

    # Verify connection
    try:
        account = stripe.Account.retrieve()
        print(f"✓ Stripe-Konto: {account.get('settings', {}).get('dashboard', {}).get('display_name', account.get('id', '?'))}")
        print(f"  Account-ID: {account['id']}\n")
    except stripe.error.AuthenticationError:
        print("FEHLER: Stripe-Authentifizierung fehlgeschlagen. Prüfe den Secret Key.")
        sys.exit(1)

    db = SessionLocal()
    results = []

    try:
        for plan_def in STRIPE_PLANS:
            slug = plan_def["slug"]
            print(f"── Plan: {plan_def['product_name']} ({slug}) ──")

            # Check DB plan
            db_plan = db.query(Plan).filter(Plan.slug == slug, Plan.is_active.is_(True)).first()
            if not db_plan:
                print(f"  ⚠ Plan '{slug}' nicht in der DB gefunden. Überspringe.")
                results.append({"slug": slug, "status": "skipped", "reason": "not in DB"})
                continue

            if db_plan.stripe_price_id and not force:
                print(f"  ✓ Bereits verknüpft: {db_plan.stripe_price_id}")
                results.append({"slug": slug, "status": "exists", "price_id": db_plan.stripe_price_id})
                continue

            if dry_run:
                print(f"  [DRY-RUN] Würde Produkt '{plan_def['product_name']}' erstellen")
                print(f"  [DRY-RUN] Würde Preis {plan_def['price_monthly_cents']/100:.2f} EUR/Monat erstellen")
                results.append({"slug": slug, "status": "dry-run"})
                continue

            # 1. Find or create Stripe Product
            product_id = find_existing_product(plan_def["product_name"])
            if product_id:
                print(f"  ✓ Bestehendes Produkt gefunden: {product_id}")
            else:
                product = stripe.Product.create(
                    name=plan_def["product_name"],
                    description=plan_def["product_description"],
                    metadata={"ariia_plan_slug": slug},
                )
                product_id = product["id"]
                print(f"  ✓ Produkt erstellt: {product_id}")

            # 2. Find or create Stripe Price
            price_id = find_existing_price(
                product_id,
                plan_def["price_monthly_cents"],
                plan_def["currency"],
            )
            if price_id:
                print(f"  ✓ Bestehender Preis gefunden: {price_id}")
            else:
                price = stripe.Price.create(
                    product=product_id,
                    unit_amount=plan_def["price_monthly_cents"],
                    currency=plan_def["currency"],
                    recurring={"interval": "month"},
                    metadata={"ariia_plan_slug": slug},
                )
                price_id = price["id"]
                print(f"  ✓ Preis erstellt: {price_id} ({plan_def['price_monthly_cents']/100:.2f} EUR/Monat)")

            # 3. Update DB plan
            db_plan.stripe_price_id = price_id
            db.commit()
            print(f"  ✓ DB aktualisiert: plans.stripe_price_id = {price_id}")
            results.append({"slug": slug, "status": "ok", "product_id": product_id, "price_id": price_id})
            print()

    except Exception as exc:
        db.rollback()
        print(f"\nFEHLER: {exc}")
        sys.exit(1)
    finally:
        db.close()

    # Summary
    print(f"\n{'='*60}")
    print("  Zusammenfassung")
    print(f"{'='*60}")
    for r in results:
        status_icon = {"ok": "✓", "exists": "●", "dry-run": "○", "skipped": "⚠"}.get(r["status"], "?")
        price_info = r.get("price_id", r.get("reason", ""))
        print(f"  {status_icon} {r['slug']:15s} → {r['status']:10s} {price_info}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARIIA Stripe Product Seeder")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, was erstellt würde")
    parser.add_argument("--force", action="store_true", help="Vorhandene stripe_price_id überschreiben")
    args = parser.parse_args()
    seed_stripe_products(dry_run=args.dry_run, force=args.force)
