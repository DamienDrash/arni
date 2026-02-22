import asyncio
import httpx
import sys
import json
import logging

# Add project root to path
sys.path.append("/root/.openclaw/workspace/arni")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("token_simulation")

async def main():
    base_url = "http://localhost:8000"
    
    # 1. Generate Token (Admin)
    logger.info("1. Generating Token for Member M-1005...")
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{base_url}/admin/tokens", json={
            "member_id": "M-1005",
            "phone_number": "+49151555666"
        })
        if res.status_code != 200:
            logger.error(f"Failed to generate token: {res.text}")
            return
            
        data = res.json()
        token = data["token"]
        logger.info(f"✅ Token Generated: {token}")
        
    # 2. Simulate User sending Token (Telegram Webhook)
    logger.info(f"2. Simulating User sending token: {token}")
    payload = {
        "message": {
            "message_id": 9901,
            "from": {"id": 7473721797, "username": "dmc", "first_name": "Damien"},
            "chat": {"id": 7473721797, "type": "private"},
            "date": 1700000000,
            "text": token, # The user types this
            "platform": "telegram"
        }
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{base_url}/webhook/telegram", json=payload)
        logger.info(f"Webhook Status: {res.status_code}")
        
    # 3. Verify Database (via Admin Chats API)
    logger.info("3. Verifying Database State...")
    async with httpx.AsyncClient() as client:
        # Give async tasks a moment to writing to DB
        await asyncio.sleep(1) 
        
        res = await client.get(f"{base_url}/admin/chats")
        sessions = res.json()
        
        verified = False
        for s in sessions:
            if str(s["user_id"]) == "7473721797":
                logger.info(f"Session Found: {s}")
                if s.get("member_id") == "M-1005":
                    verified = True
                    break
        
        if verified:
            logger.info("🎉 SUCCESS: Member ID 'M-1005' is linked!")
        else:
            logger.error("❌ FAILURE: Member ID not linked.")

if __name__ == "__main__":
    asyncio.run(main())
