#!/usr/bin/env python3
"""Ingest Athletik Movement knowledge base documents into ChromaDB.

Run inside the ariia-core container:
    python3 scripts/ingest_athletik_movement_kb.py
"""

import sys
import os

# Ensure app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.knowledge.ingest import ingest_tenant_knowledge

def main():
    print("=" * 60)
    print("Athletik Movement Knowledge Base Ingest")
    print("=" * 60)
    
    # Check if knowledge files exist
    kb_dir = "data/knowledge/tenants/athletik-movement"
    if not os.path.exists(kb_dir):
        print(f"ERROR: Knowledge directory not found: {kb_dir}")
        sys.exit(1)
    
    md_files = [f for f in os.listdir(kb_dir) if f.endswith(".md")]
    print(f"Found {len(md_files)} knowledge documents:")
    for f in sorted(md_files):
        filepath = os.path.join(kb_dir, f)
        size = os.path.getsize(filepath)
        print(f"  - {f} ({size} bytes)")
    
    print()
    print("Starting ingest...")
    
    result = ingest_tenant_knowledge(
        tenant_id=2,
        tenant_slug="athletik-movement"
    )
    
    print()
    print(f"Result: {result}")
    print()
    
    if result.get("status") == "ok":
        print(f"SUCCESS: {result.get('chunks', 0)} chunks ingested into collection '{result.get('collection')}'")
    else:
        print(f"WARNING: Ingest returned status '{result.get('status')}'")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
