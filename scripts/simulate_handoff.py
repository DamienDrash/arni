import redis
import os

# Connect to Redis
r = redis.from_url("redis://127.0.0.1:6379/0")

# User ID to simulate handoff for
USER_ID = "test_user_6ec4ec81" # The one from previous simulation if possible, or new one

# Set human mode
key = f"session:{USER_ID}:human_mode"
r.set(key, "true")

print(f"Set {key} to true. Handoff should appear in Dashboard.")
