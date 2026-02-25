import json
import os

# Updated MASTER_KEYS to include all sections
MASTER_KEYS = [
    "common", "sidebar", "settings", "tenants", "live", "members", "memberMemory", 
    "navbar", "hero", "stats", "features", "cta", "footer"
]

def deep_merge(target, source):
    for key, value in source.items():
        if isinstance(value, dict):
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            deep_merge(target[key], value)
        else:
            if key not in target:
                target[key] = value
    return target

def sync_locales():
    locales_dir = "frontend/locales"
    with open(f"{locales_dir}/en.json", "r") as f:
        en_master = json.load(f)
    
    files = [f for f in os.listdir(locales_dir) if f.endswith(".json") and f not in ["en.json"]]
    
    for filename in files:
        path = f"{locales_dir}/{filename}"
        with open(path, "r") as f:
            try:
                current = json.load(f)
            except:
                current = {}
        
        # Merge master into current
        synced = deep_merge(current, en_master)
        
        # Clean up keys not in master (optional, but keeps files clean)
        cleaned = {}
        for section in MASTER_KEYS:
            if section in synced:
                cleaned[section] = synced[section]
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
            print(f"Synced {filename}")

if __name__ == "__main__":
    sync_locales()
