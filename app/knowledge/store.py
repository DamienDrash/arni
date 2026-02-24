import os
import chromadb
import structlog
from chromadb.config import Settings

logger = structlog.get_logger()

# Constants
KNOWLEDGE_DB_PATH = "data/chroma_db"
DEFAULT_COLLECTION_NAME = "ariia_knowledge"

class KnowledgeStore:
    def __init__(self, collection_name: str = DEFAULT_COLLECTION_NAME, db_path: str = KNOWLEDGE_DB_PATH):
        """Initialize ChromaDB Client."""
        self.collection_name = collection_name or DEFAULT_COLLECTION_NAME
        self.db_path = db_path or KNOWLEDGE_DB_PATH
        settings = Settings(
            anonymized_telemetry=False,
            is_persistent=True,
        )
        try:
            # Ensure directory exists
            os.makedirs(self.db_path, exist_ok=True)
            
            self.client = chromadb.PersistentClient(
                path=self.db_path,
                settings=settings
            )
            self.collection = self.client.get_or_create_collection(name=self.collection_name)
            logger.info("knowledge.store.initialized", path=self.db_path, collection=self.collection_name)
        except Exception as e:
            logger.error("knowledge.store.init_failed", error=str(e))
            raise

    def add_documents(self, documents: list[str], metadatas: list[dict], ids: list[str]) -> None:
        """Add documents to the store (fails if IDs already exist — prefer upsert_documents)."""
        try:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
            logger.info("knowledge.store.added", count=len(documents))
        except Exception as e:
            logger.error("knowledge.store.add_failed", error=str(e))
            raise

    def upsert_documents(self, documents: list[str], metadatas: list[dict], ids: list[str]) -> None:
        """Upsert documents — safe to call on every re-ingest (no duplicate errors)."""
        try:
            self.collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
            logger.info("knowledge.store.upserted", count=len(documents))
        except Exception as e:
            logger.error("knowledge.store.upsert_failed", error=str(e))
            raise

    def query(self, query_text: str, n_results: int = 3) -> dict:
        """Query the store for relevant documents."""
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            return results
        except Exception as e:
            logger.error("knowledge.store.query_failed", error=str(e))
            return {}

    def count(self) -> int:
        """Return number of documents in store."""
        return self.collection.count()

    def delete_documents(self, ids: list[str]) -> None:
        """Remove specific documents from the store by ID."""
        try:
            self.collection.delete(ids=ids)
            logger.info("knowledge.store.deleted", count=len(ids))
        except Exception as e:
            logger.error("knowledge.store.delete_failed", error=str(e))

    def delete_by_metadata(self, where_filter: dict) -> None:
        """Remove documents matching metadata filters."""
        try:
            self.collection.delete(where=where_filter)
            logger.info("knowledge.store.deleted_by_filter", filter=where_filter)
        except Exception as e:
            logger.error("knowledge.store.delete_by_filter_failed", error=str(e))

    def reset(self):
        """Delete and recreate collection (Use with caution)."""
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(self.collection_name)
            logger.info("knowledge.store.reset")
        except Exception as e:
             logger.error("knowledge.store.reset_failed", error=str(e))
