#!/usr/bin/env python3
"""CLI script to migrate legacy knowledge and member memory data to the Memory Platform.

Usage:
    python scripts/migrate_knowledge.py --tenant-id 1 --dry-run
    python scripts/migrate_knowledge.py --tenant-id 1
    python scripts/migrate_knowledge.py --tenant-id 1 --knowledge-dir /path/to/knowledge
    python scripts/migrate_knowledge.py --tenant-id 1 --member-memory-dir /path/to/memory
"""

import argparse
import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(
        description="Migrate legacy ARIIA knowledge and member memory data to the Memory Platform."
    )
    parser.add_argument(
        "--tenant-id",
        type=int,
        default=1,
        help="Tenant ID to migrate data for (default: 1)",
    )
    parser.add_argument(
        "--knowledge-dir",
        type=str,
        default="",
        help="Path to legacy knowledge markdown files (auto-detected if empty)",
    )
    parser.add_argument(
        "--member-memory-dir",
        type=str,
        default="",
        help="Path to legacy member memory markdown files (auto-detected if empty)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be migrated, don't actually migrate",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Path to write the migration report JSON",
    )

    args = parser.parse_args()

    # Auto-detect directories if not specified
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if not args.knowledge_dir:
        # Try common locations
        candidates = [
            os.path.join(project_root, "data", "knowledge"),
            os.path.join(project_root, "knowledge"),
        ]
        for candidate in candidates:
            if os.path.isdir(candidate):
                args.knowledge_dir = candidate
                break

    if not args.member_memory_dir:
        candidates = [
            os.path.join(project_root, "data", "member_memory"),
            os.path.join(project_root, "member_memory"),
        ]
        for candidate in candidates:
            if os.path.isdir(candidate):
                args.member_memory_dir = candidate
                break

    print("=" * 60)
    print("ARIIA Memory Platform – Data Migration")
    print("=" * 60)
    print(f"  Tenant ID:         {args.tenant_id}")
    print(f"  Knowledge Dir:     {args.knowledge_dir or '(nicht gefunden)'}")
    print(f"  Member Memory Dir: {args.member_memory_dir or '(nicht gefunden)'}")
    print(f"  Dry Run:           {args.dry_run}")
    print("=" * 60)

    if not args.knowledge_dir and not args.member_memory_dir:
        print("\nKeine Datenverzeichnisse gefunden. Migration abgebrochen.")
        sys.exit(1)

    # Run migration
    from app.memory_platform.migration import run_migration

    result = asyncio.run(
        run_migration(
            tenant_id=args.tenant_id,
            knowledge_dir=args.knowledge_dir,
            member_memory_dir=args.member_memory_dir,
            dry_run=args.dry_run,
        )
    )

    # Print results
    print("\n" + "=" * 60)
    print("Migration Report")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))

    # Write report to file if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nReport gespeichert: {args.output}")

    # Exit code based on errors
    total_errors = (
        result.get("knowledge_files", {}).get("errors", 0)
        + result.get("member_memory_files", {}).get("errors", 0)
    )
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
