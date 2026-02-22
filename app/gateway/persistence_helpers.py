import structlog
from app.gateway.schemas import InboundMessage, OutboundMessage
from app.gateway.persistence import persistence # Use shared singleton

logger = structlog.get_logger()
# persistence = PersistenceService() # Removed local instance

async def save_inbound_to_db(msg: InboundMessage):
    """Async wrapper to save inbound message."""
    try:
        # Run in threadpool if blocking, but SQLite is fast enough for low volume
        # For strict async, use run_in_executor
        persistence.save_message(
            user_id=str(msg.user_id),
            role="user",
            content=msg.content,
            platform=msg.platform,
            metadata=msg.metadata,
            tenant_id=msg.tenant_id,
        )
    except Exception as e:
        logger.error("persistence.save_inbound_failed", error=str(e))

async def save_outbound_to_db(msg: OutboundMessage):
    """Async wrapper to save outbound message."""
    try:
        persistence.save_message(
            user_id=str(msg.user_id),
            role="assistant",
            content=msg.content,
            platform=msg.platform,
            metadata={"reply_to": msg.reply_to},
            tenant_id=msg.tenant_id,
        )
    except Exception as e:
        logger.error("persistence.save_outbound_failed", error=str(e))
