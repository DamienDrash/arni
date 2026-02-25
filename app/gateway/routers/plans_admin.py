from fastapi import APIRouter, Depends, HTTPException, Body
from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.models import Plan
from app.core.billing_sync import push_to_stripe, sync_from_stripe, get_stripe_client
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/admin/plans", tags=["admin-plans"])

class PlanUpdate(BaseModel):
    name: str
    price_monthly_cents: int
    is_active: bool = True

@router.get("")
async def list_all_plans(user: AuthContext = Depends(get_current_user)):
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        return db.query(Plan).order_by(Plan.price_monthly_cents.asc()).all()
    finally:
        db.close()

@router.post("")
async def create_plan(
    name: str = Body(...), 
    slug: str = Body(...), 
    price: int = Body(...),
    user: AuthContext = Depends(get_current_user)
):
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        if db.query(Plan).filter(Plan.slug == slug).first():
            raise HTTPException(status_code=400, detail="Slug already exists")
        
        plan = Plan(name=name, slug=slug, price_monthly_cents=price)
        db.add(plan)
        db.commit()
        await push_to_stripe(db, plan)
        return plan
    finally:
        db.close()

@router.patch("/{plan_id}")
async def update_plan(
    plan_id: int, 
    data: PlanUpdate, 
    user: AuthContext = Depends(get_current_user)
):
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan: raise HTTPException(status_code=404)
        
        plan.name = data.name
        plan.price_monthly_cents = data.price_monthly_cents
        plan.is_active = data.is_active
        
        db.commit()
        await push_to_stripe(db, plan)
        return plan
    finally:
        db.close()

@router.delete("/{plan_id}")
async def delete_plan(plan_id: int, user: AuthContext = Depends(get_current_user)):
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan: raise HTTPException(status_code=404)
        
        # Archive in Stripe first if possible
        s = get_stripe_client()
        if s and plan.stripe_price_id:
            try:
                price = s.Price.retrieve(plan.stripe_price_id)
                s.Product.modify(price.product, active=False)
            except: pass
            
        db.delete(plan)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()

@router.post("/cleanup")
async def cleanup_orphaned_plans(user: AuthContext = Depends(get_current_user)):
    """Remove all plans that have no Stripe Price ID."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        count = db.query(Plan).filter(Plan.stripe_price_id == None).delete(synchronize_session=False)
        db.commit()
        return {"status": "ok", "deleted_count": count}
    finally:
        db.close()

@router.get("/addons")
async def list_available_addons(user: AuthContext = Depends(get_current_user)):
    require_role(user, {"system_admin"})
    from app.core.billing_sync import get_stripe_client
    s = get_stripe_client()
    if not s: return []
    try:
        products = s.Product.list(active=True, limit=100)
        addons = []
        for prod in products.data:
            name_lower = prod.name.lower()
            if "add-on" in name_lower or "addon" in name_lower or "extension" in name_lower:
                prices = s.Price.list(product=prod.id, active=True, limit=1)
                price_id = prices.data[0].id if prices.data else "no-price"
                price_amount = prices.data[0].unit_amount if prices.data else 0
                
                addons.append({
                    "id": prod.id,
                    "name": prod.name.split(":")[-1].strip() if ":" in prod.name else prod.name.replace("ARIIA Add-on", "").strip(),
                    "price": price_amount,
                    "stripe_price_id": price_id
                })
        return addons
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/addons")
async def create_addon(
    name: str = Body(...),
    price: int = Body(...),
    user: AuthContext = Depends(get_current_user)
):
    require_role(user, {"system_admin"})
    s = get_stripe_client()
    if not s: raise HTTPException(status_code=402)
    try:
        prod = s.Product.create(name=f"ARIIA Add-on: {name}")
        p = s.Price.create(
            product=prod.id,
            unit_amount=price,
            currency="eur",
            recurring={"interval": "month"}
        )
        return {"id": prod.id, "stripe_price_id": p.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-now")
async def trigger_manual_sync(user: AuthContext = Depends(get_current_user)):
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        await sync_from_stripe(db)
        return {"status": "ok"}
    finally:
        db.close()
