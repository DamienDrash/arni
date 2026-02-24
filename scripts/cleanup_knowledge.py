import os
import glob
import re
from app.knowledge.store import KnowledgeStore

# Local implementation of collection name logic to avoid DB imports
def collection_name_for_slug(tenant_slug: str) -> str:
    safe = re.sub(r"[^a-z0-9_-]", "_", (tenant_slug or "system").lower())
    return f"ariia_knowledge_{safe}"

# Patterns for unwanted/temp files
PATTERNS = [
    "data/knowledge/governance-*.md",
    "data/knowledge/members/member-*.md"
]

def cleanup():
    # 1. Identify files
    files_to_delete = []
    for pattern in PATTERNS:
        files_to_delete.extend(glob.glob(pattern))
    
    if not files_to_delete:
        print("Keine zu löschenden Dateien gefunden.")
        return

    print(f"Gefundene Dateien zum Löschen: {len(files_to_delete)}")
    
    # 2. Deletion from ChromaDB
    try:
        system_store = KnowledgeStore(collection_name="ariia_knowledge_system")
        for f_path in files_to_delete:
            filename = os.path.basename(f_path)
            # Delete entries where 'source' metadata matches the filename
            system_store.delete_by_metadata({"source": filename})
            print(f"Datenbank-Einträge für {filename} in 'system' gelöscht (falls vorhanden).")
    except Exception as e:
        print(f"Warnung: Datenbank-Cleanup fehlgeschlagen (ChromaDB möglicherweise nicht erreichbar): {e}")
    
    # 3. Physical Deletion
    for f_path in files_to_delete:
        try:
            if os.path.exists(f_path):
                os.remove(f_path)
                print(f"Physisch gelöscht: {f_path}")
        except Exception as e:
            print(f"Fehler beim Löschen von {f_path}: {e}")

    print("Cleanup abgeschlossen.")

if __name__ == "__main__":
    cleanup()
