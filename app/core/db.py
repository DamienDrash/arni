from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import event
import contextvars
import os

# Tenant context for Row Level Security (RLS) or logging
tenant_context = contextvars.ContextVar("tenant_context", default=None)

# Mandatory PostgreSQL Connection
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Special case for local testing/CI
IS_TEST = os.getenv("PYTEST_CURRENT_TEST") is not None or os.getenv("ENVIRONMENT") == "testing"

if (not SQLALCHEMY_DATABASE_URL or not SQLALCHEMY_DATABASE_URL.startswith("postgresql")) and not IS_TEST:
    # In a Premium SaaS, we do not allow silent fallbacks to local files.
    raise RuntimeError(
        "CRITICAL: DATABASE_URL must be a valid PostgreSQL connection string. "
        "SQLite is no longer supported for ARIIA v1.4+ production/dev environments."
    )

if IS_TEST and not SQLALCHEMY_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = "sqlite:///./test_ariia.db"

# Optimized PostgreSQL Engine with Pooling
if SQLALCHEMY_DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=20,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
else:
    # SQLite for testing
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@event.listens_for(engine, "checkout")
def set_tenant_id_context(dbapi_connection, connection_record, connection_proxy):
    """Propagate the current tenant_id to PostgreSQL for Audit/RLS purposes."""
    tenant_id = tenant_context.get()
    
    # We use a raw cursor to set the local variable in the session
    # This is a standard pattern for multi-tenant Postgres apps.
    cursor = dbapi_connection.cursor()
    try:
        if tenant_id is not None:
            # Setting a local variable that can be used in RLS policies or Triggers
            cursor.execute(f"SET LOCAL app.current_tenant_id = '{tenant_id}';")
        else:
            cursor.execute("RESET app.current_tenant_id;")
    except Exception:
        # Best effort for context propagation
        pass
    finally:
        cursor.close()

# Base class for models
Base = declarative_base()

def run_migrations():
    """Bootstrap the database schema. In production, use Alembic instead."""
    Base.metadata.create_all(bind=engine)

# FastAPI Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
