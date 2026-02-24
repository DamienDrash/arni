import sys
import os
from unittest.mock import MagicMock, patch

# Mock infrastructure
sys.path.append(os.getcwd())
sys.modules["app.core.db"] = MagicMock()
mock_persistence = MagicMock()
sys.modules["app.gateway.persistence"] = mock_persistence
mock_persistence.persistence = MagicMock()

# Import what we need to test
from app.gateway.admin import delete_integration_config
from app.core.auth import AuthContext

async def test_deletion_logic():
    # Setup test user context
    user = AuthContext(
        user_id=1,
        email="admin@test.com",
        tenant_id=2,
        tenant_slug="getimpulse",
        role="tenant_admin"
    )
    
    print("--- TESTING INTEGRATION DELETION ---")
    
    # Simulate calling the delete endpoint for 'whatsapp'
    # This should trigger delete_settings_by_prefix with 'meta_' AND delete_setting 'whatsapp_mode'
    print("Calling delete_integration_config for 'whatsapp'...")
    await delete_integration_config(provider="whatsapp", user=user)
    
    # Verify the calls
    try:
        mock_persistence.persistence.delete_settings_by_prefix.assert_called_with("meta_", tenant_id=2)
        mock_persistence.persistence.delete_setting.assert_called_with("whatsapp_mode", tenant_id=2)
        print("✅ SUCCESS: Logic correctly called deletion methods with proper prefixes and tenant scoping.")
    except AssertionError as e:
        print(f"❌ FAILURE: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_deletion_logic())
