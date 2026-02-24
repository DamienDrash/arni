import argparse
import sys
import os

# Ensure app is in path
sys.path.append(os.getcwd())

from app.memory.member_memory_analyzer import analyze_member
from app.core.db import SessionLocal
from app.core.models import Tenant
import structlog

# Configure structlog
structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(),
)

def main():
    parser = argparse.ArgumentParser(description="Trigger immediate member memory analysis.")
    parser.add_argument("member_id", help="Member ID or Customer ID")
    parser.add_argument("--tenant-id", type=int, help="Tenant ID (optional)")
    parser.add_argument("--slug", help="Tenant Slug (optional)")
    
    args = parser.parse_args()
    
    tenant_id = args.tenant_id
    if args.slug and not tenant_id:
        db = SessionLocal()
        try:
            t = db.query(Tenant).filter(Tenant.slug == args.slug).first()
            if t:
                tenant_id = t.id
                print(f"Resolved slug '{args.slug}' to tenant_id {tenant_id}")
            else:
                print(f"Slug '{args.slug}' not found.")
                sys.exit(1)
        finally:
            db.close()
            
    print(f"Starting analysis for member {args.member_id} (tenant={tenant_id})...")
    try:
        analyze_member(args.member_id, tenant_id)
        print("Analysis complete.")
    except Exception as e:
        print(f"Analysis failed: {e}")

if __name__ == "__main__":
    main()
