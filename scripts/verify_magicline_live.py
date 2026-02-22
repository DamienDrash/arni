"""Verify Magicline Live Integration.

This script connects to the REAL Magicline API (Sandbox) using .env credentials.
It searches for the user 'dfrigewski@gmail.com' and fetches their data.
"""
import asyncio
import os
import structlog
from dotenv import load_dotenv
from app.integrations.magicline import get_client

# Setup
load_dotenv()
logger = structlog.get_logger()

def verify_live():
    print("🔌 Connecting to Magicline API...")
    client = get_client()
    
    if not client:
        print("❌ Error: Client configuration missing.")
        return

    # 1. Search User
    target_email = "dfrigewski@gmail.com"
    print(f"🔍 Searching for user: {target_email}")
    
    try:
        # Note: customer_search might return a list or dict depending on API
        results = client.customer_search(email=target_email)
        
        # Check if list or dict
        if isinstance(results, dict):
            # API usually returns {"result": [...]} or just [...]
            # The client usually unwraps it if I recall correctly, checking code...
            # In client.py: return response.json()
            pass
            
        # The tool `magicline.py` handles this:
        # search_res = client.customer_search(email="...")
        
        print(f"📄 Raw Search Result Type: {type(results)}")
        
        # Adjust based on likely response structure (list of dicts)
        candidates = results
        if isinstance(results, dict) and "result" in results:
            candidates = results["result"]
            
        if not candidates:
            print("❌ User not found in Magicline Sandbox!")
            print("   (Ensure 'dfrigewski@gmail.com' exists in the Sandbox environment)")
            return

        user = candidates[0]
        user_id = user.get("id")
        first_name = user.get("firstName")
        last_name = user.get("lastName")
        
        print(f"✅ User Found: {first_name} {last_name} (ID: {user_id})")
        
        # 2. Get Contracts (Status)
        print("💳 Fetching Contracts...")
        contracts = client.customer_contracts(user_id)
        if hasattr(contracts, "get"):
             contracts = contracts.get("result", contracts) # unwrap if needed
             
        if contracts:
            for c in contracts:
                rate = c.get("rateName", "Unknown Rate")
                status = c.get("status", "Unknown")
                end = c.get("endDate", "N/A")
                print(f"   - {rate} [{status}] bis {end}")
        else:
            print("   (No active contracts found)")

        # 3. Get Check-ins
        print("📍 Fetching Check-ins (Last 30 days)...")
        # client.customer_checkins requires date
        from datetime import date, timedelta
        start_date = (date.today() - timedelta(days=30)).isoformat()
        
        checkins = client.customer_checkins(user_id, from_date=start_date)
        if hasattr(checkins, "get"):
             checkins = checkins.get("result", checkins)

        if checkins:
            for ci in checkins[:5]: # Show max 5
                print(f"   - Check-in: {ci.get('checkInDateTime')}")
        else:
            print("   (No check-ins in last 30 days)")

    except Exception as e:
        print(f"❌ API Call Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_live()
