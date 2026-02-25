import stripe
import asyncio
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.models import Plan
from app.core.db import Base

# Sandbox Keys provided by user
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_placeholder")
stripe.api_key = STRIPE_SECRET_KEY

# DB Connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://ariia:ariia_dev_password@ariia-postgres:5432/ariia")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

PLANS_DEF = [
    {
        "slug": "starter",
        "name": "Starter",
        "price_monthly": 7900,  # cents
        "price_yearly": 75600,  # 63 * 12
        "features": {
            "max_channels": 1,
            "max_connectors": 0,
            "max_monthly_messages": 500,
            "max_members": 500,
            "ai_tier": "basic",
            "monthly_tokens": 100000,
            "whatsapp_enabled": True,
            "telegram_enabled": False,
            "email_channel_enabled": False,
            "sms_enabled": False,
            "voice_enabled": False,
            "instagram_enabled": False,
            "facebook_enabled": False,
            "google_business_enabled": False,
            "memory_analyzer_enabled": False,
            "custom_prompts_enabled": False,
            "advanced_analytics_enabled": False,
            "branding_enabled": False,
            "audit_log_enabled": False,
            "api_access_enabled": False,
            "automation_enabled": False,
            "churn_prediction_enabled": False,
            "vision_ai_enabled": False,
            "white_label_enabled": False,
            "sla_guarantee_enabled": False,
            "on_premise_enabled": False
        }
    },
    {
        "slug": "professional",
        "name": "Professional",
        "price_monthly": 19900,
        "price_yearly": 190800,
        "features": {
            "max_channels": 3,
            "max_connectors": 1,
            "max_monthly_messages": 2000,
            "max_members": None, # Unlimited
            "ai_tier": "standard",
            "monthly_tokens": 500000,
            "whatsapp_enabled": True,
            "telegram_enabled": True,
            "email_channel_enabled": True,
            "sms_enabled": True,
            "voice_enabled": False,
            "instagram_enabled": True,
            "facebook_enabled": True,
            "google_business_enabled": False,
            "memory_analyzer_enabled": True,
            "custom_prompts_enabled": True,
            "advanced_analytics_enabled": True,
            "branding_enabled": True,
            "audit_log_enabled": True,
            "api_access_enabled": True,
            "automation_enabled": False,
            "churn_prediction_enabled": False,
            "vision_ai_enabled": False,
            "white_label_enabled": False,
            "sla_guarantee_enabled": False,
            "on_premise_enabled": False
        }
    },
    {
        "slug": "business",
        "name": "Business",
        "price_monthly": 39900,
        "price_yearly": 382800,
        "features": {
            "max_channels": 99,
            "max_connectors": 99,
            "max_monthly_messages": 10000,
            "max_members": None,
            "ai_tier": "premium",
            "monthly_tokens": 2000000,
            "whatsapp_enabled": True,
            "telegram_enabled": True,
            "email_channel_enabled": True,
            "sms_enabled": True,
            "voice_enabled": True,
            "instagram_enabled": True,
            "facebook_enabled": True,
            "google_business_enabled": True,
            "memory_analyzer_enabled": True,
            "custom_prompts_enabled": True,
            "advanced_analytics_enabled": True,
            "branding_enabled": True,
            "audit_log_enabled": True,
            "api_access_enabled": True,
            "automation_enabled": True,
            "churn_prediction_enabled": True,
            "vision_ai_enabled": True,
            "white_label_enabled": False,
            "sla_guarantee_enabled": False,
            "on_premise_enabled": False
        }
    },
    {
        "slug": "enterprise",
        "name": "Enterprise",
        "price_monthly": 0, # Custom
        "price_yearly": 0,
        "features": {
            "max_channels": 999,
            "max_connectors": 999,
            "max_monthly_messages": None,
            "max_members": None,
            "ai_tier": "unlimited",
            "monthly_tokens": 100000000,
            "whatsapp_enabled": True,
            "telegram_enabled": True,
            "email_channel_enabled": True,
            "sms_enabled": True,
            "voice_enabled": True,
            "instagram_enabled": True,
            "facebook_enabled": True,
            "google_business_enabled": True,
            "memory_analyzer_enabled": True,
            "custom_prompts_enabled": True,
            "advanced_analytics_enabled": True,
            "branding_enabled": True,
            "audit_log_enabled": True,
            "api_access_enabled": True,
            "automation_enabled": True,
            "churn_prediction_enabled": True,
            "vision_ai_enabled": True,
            "white_label_enabled": True,
            "sla_guarantee_enabled": True,
            "on_premise_enabled": True
        }
    }
]

ADDONS_DEF = [
    {"slug": "churn_prediction", "name": "Churn Prediction", "price": 4900},
    {"slug": "voice_pipeline", "name": "Voice Pipeline", "price": 7900},
    {"slug": "vision_ai", "name": "Vision AI", "price": 3900},
    {"slug": "extra_channel", "name": "Extra Channel", "price": 2900},
    {"slug": "extra_conversations", "name": "Extra Conversations (1k)", "price": 1900},
    {"slug": "extra_user", "name": "Extra User", "price": 1500},
    {"slug": "white_label", "name": "White Label", "price": 14900},
    {"slug": "api_access", "name": "API Access", "price": 9900},
    {"slug": "extra_connector", "name": "Extra Connector", "price": 4900},
]

def seed_stripe():
    print("--- Seeding Stripe & DB ---")
    session = SessionLocal()
    
    # 1. Plans
    for p_def in PLANS_DEF:
        print(f"Processing Plan: {p_def['name']}...")
        
        # Check if product exists in Stripe by searching name
        existing_products = stripe.Product.search(query=f"active:'true' AND name:'ARIIA {p_def['name']}'")
        if existing_products['data']:
            prod = existing_products['data'][0]
            print(f"  > Found existing Stripe Product: {prod.id}")
        else:
            prod = stripe.Product.create(name=f"ARIIA {p_def['name']}")
            print(f"  > Created Stripe Product: {prod.id}")

        # Check/Create Monthly Price
        price_id = None
        if p_def['price_monthly'] > 0:
            prices = stripe.Price.list(product=prod.id, active=True, type='recurring')
            # Very simple check: find first recurring monthly price
            found_price = next((p for p in prices.data if p.recurring.interval == 'month' and p.unit_amount == p_def['price_monthly']), None)
            
            if found_price:
                price_id = found_price.id
                print(f"  > Found existing Monthly Price: {price_id}")
            else:
                price = stripe.Price.create(
                    product=prod.id,
                    unit_amount=p_def['price_monthly'],
                    currency="eur",
                    recurring={"interval": "month"}
                )
                price_id = price.id
                print(f"  > Created Monthly Price: {price_id}")

        # Update DB
        plan = session.query(Plan).filter(Plan.slug == p_def['slug']).first()
        if not plan:
            plan = Plan(slug=p_def['slug'])
            session.add(plan)
        
        plan.name = p_def['name']
        plan.price_monthly_cents = p_def['price_monthly']
        plan.stripe_price_id = price_id # Primary monthly price
        
        # Apply features
        for key, val in p_def['features'].items():
            setattr(plan, key, val)
            
        session.commit()
        print(f"  > Synced to DB: {p_def['slug']}")

    # 2. Add-ons (Just creating products in Stripe for now, DB table is TenantAddon which links to these)
    # We don't have a "MasterAddon" table yet, usually these are hardcoded or config.
    # But we ensure they exist in Stripe for Checkout.
    for addon in ADDONS_DEF:
        print(f"Processing Addon: {addon['name']}...")
        existing = stripe.Product.search(query=f"active:'true' AND name:'ARIIA Add-on: {addon['name']}'")
        if existing['data']:
            prod = existing['data'][0]
        else:
            prod = stripe.Product.create(name=f"ARIIA Add-on: {addon['name']}")
            
        prices = stripe.Price.list(product=prod.id, active=True)
        found_price = next((p for p in prices.data if p.unit_amount == addon['price']), None)
        if not found_price:
            stripe.Price.create(
                product=prod.id,
                unit_amount=addon['price'],
                currency="eur",
                recurring={"interval": "month"}
            )
            print(f"  > Created Price for {addon['name']}")
        else:
            print(f"  > Price exists for {addon['name']}")

    session.close()
    print("--- Done ---")

if __name__ == "__main__":
    seed_stripe()
