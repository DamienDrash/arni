
import os
import structlog
from functools import wraps
from typing import Any, Callable, Optional
from datetime import datetime

logger = structlog.get_logger()

# Minimal Stub if library is missing
try:
    from langfuse import Langfuse
    # from langfuse.decorators import observe # if using decorators
    HAS_LANGFUSE = True
except ImportError:
    HAS_LANGFUSE = False
    Langfuse = None

class ObservabilityService:
    """Enterprise-Grade Observability wrapper.
    
    Responsibilities:
    1. Initialize tracing client (LangFuse/Arize etc).
    2. Provide decorators/context managers for tracing functions.
    3. Graceful fallback if tracing fails or is disabled.
    """
    
    _instance: Optional["ObservabilityService"] = None

    def __init__(self):
        self.enabled = False
        self.client = None
        
        if HAS_LANGFUSE:
            # Check env vars
            pk = os.getenv("LANGFUSE_PUBLIC_KEY")
            sk = os.getenv("LANGFUSE_SECRET_KEY")
            host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

            if pk and sk:
                try:
                    self.client = Langfuse(
                        public_key=pk,
                        secret_key=sk,
                        host=host
                    )
                    self.enabled = True
                    logger.info("observability.init.success", provider="langfuse", methods=dir(self.client))
                except Exception as e:
                    logger.error("observability.init.failed", error=str(e))
            else:
                logger.warning("observability.disabled", reason="missing_keys")
        else:
            logger.warning("observability.disabled", reason="library_missing")

    @classmethod
    def get_instance(cls) -> "ObservabilityService":
        if cls._instance is None:
            cls._instance = ObservabilityService()
        return cls._instance

    def trace(self, **kwargs):
        """Manual trace creation."""
        if self.enabled and self.client:
            try:
                return self.client.trace(**kwargs)
            except AttributeError:
                logger.error("observability.trace_method_missing", methods=dir(self.client))
                return None
            except Exception as e:
                logger.error("observability.trace_failed", error=str(e))
                return None
        return None

    def flush(self):
        """Ensure all traces are sent."""
        if self.enabled and self.client:
            self.client.flush()

# Helper access
def get_obs() -> ObservabilityService:
    return ObservabilityService.get_instance()

def simple_trace(name: str):
    """Decorator to trace a function call as a span."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            obs = get_obs()
            if not obs.enabled:
                return await func(*args, **kwargs)
            
            # Start Span
            start_time = datetime.now()
            # We don't have a parent context easily here without modifying everything
            # In a real impl, we'd pass trace_id via context vars
            
            try:
                result = await func(*args, **kwargs)
                # obs.client.span(...) # Simplified
                return result
            except Exception as e:
                # obs.client.span(..., status="error")
                raise e
        return wrapper
    return decorator
