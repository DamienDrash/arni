import stripe
import structlog
from sqlalchemy.orm import Session
from app.core.models import Plan
from app.gateway.persistence import persistence

logger = structlog.get_logger()

def get_stripe_client():
    sk = persistence.get_setting("billing_stripe_secret_key", "", tenant_id=1)
    if not sk: return None
    stripe.api_key = sk
    return stripe

async def sync_from_stripe(db: Session):
    s = get_stripe_client()
    if not s: return
    
    try:
        products = s.Product.list(active=True)
        active_slugs = []
        for prod in products.data:
            if not prod.name.startswith("ARIIA"): continue
            
            # Extract clean slug
            slug = prod.name.replace("ARIIA ", "").replace("ARIIA Add-on: ", "").lower().strip().replace(" ", "-")
            if "add-on" in prod.name.lower(): continue 
            
            active_slugs.append(slug)
            
            # Fetch prices
            prices = s.Price.list(product=prod.id, active=True, limit=1)
            if not prices.data:
                price = s.Price.create(product=prod.id, unit_amount=0, currency="eur", recurring={"interval": "month"})
                price_id = price.id
                amount = 0
            else:
                price_id = prices.data[0].id
                amount = prices.data[0].unit_amount or 0
            
            plan = db.query(Plan).filter(Plan.slug == slug).first()
            if not plan:
                plan = Plan(slug=slug)
                db.add(plan)
            
            plan.name = prod.name.replace("ARIIA ", "")
            plan.stripe_price_id = price_id
            plan.price_monthly_cents = amount
            plan.is_active = True
            
        db.query(Plan).filter(Plan.slug.notin_(active_slugs)).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        logger.error("billing.sync_failed", error=str(e))

async def push_to_stripe(db: Session, plan: Plan):
    """Sync a local plan object to Stripe (Create/Update)."""
    s = get_stripe_client()
    if not s: return False
    
    try:
        product_name = f"ARIIA {plan.name}"
        
        # 1. Handle Product
        stripe_prod_id = None
        existing = s.Product.search(query=f"name:'{product_name}'")
        if existing.data:
            stripe_prod_id = existing.data[0].id
            s.Product.modify(stripe_prod_id, active=plan.is_active)
        else:
            prod = s.Product.create(name=product_name)
            stripe_prod_id = prod.id
            
        # 2. Handle Price (only if changed)
        create_new_price = True
        if plan.stripe_price_id:
            try:
                curr_price = s.Price.retrieve(plan.stripe_price_id)
                if curr_price.unit_amount == plan.price_monthly_cents:
                    create_new_price = False
            except: pass
        
        if create_new_price and plan.price_monthly_cents >= 0:
            # Archive old prices first
            old_prices = s.Price.list(product=stripe_prod_id, active=True)
            for op in old_prices.data:
                s.Price.modify(op.id, active=False)
                
            new_p = s.Price.create(
                product=stripe_prod_id,
                unit_amount=plan.price_monthly_cents,
                currency="eur",
                recurring={"interval": "month"}
            )
            plan.stripe_price_id = new_p.id
            
        db.commit()
        return True
    except Exception as e:
        logger.error("billing.push_to_stripe.failed", plan=plan.slug, error=str(e))
        return False
