"""ARIIA v1.4 – Admin WebSocket Router.

Handles real-time control (Ghost Mode) and admin interventions.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.gateway.dependencies import (
    redis_bus,
    active_websockets,
    telegram_bot,
)
from app.gateway.schemas import SystemEvent, Platform
from app.gateway.persistence import persistence
from app.gateway.utils import send_to_user, broadcast_to_admins

logger = structlog.get_logger()
router = APIRouter(tags=["admin"])

@router.websocket("/ws/control")
async def websocket_control(ws: WebSocket) -> None:
    """WebSocket endpoint for Admin Dashboard & Ghost Mode.

    Bidirectional channel for real-time control:
    - Admin can observe live messages (Ghost Mode)
    - Admin can inject messages into conversations
    - System events are pushed to connected admins
    """
    await ws.accept()
    active_websockets.append(ws)
    client_id = str(uuid4())[:8]
    logger.info("ws.connected", client_id=client_id, total=len(active_websockets))

    # Notify via Redis
    event = SystemEvent(
        event_type="admin.connected",
        source="gateway",
        payload={"client_id": client_id},
        severity="info",
    )
    try:
        system_tid = persistence.get_system_tenant_id()
        channel = redis_bus.get_tenant_channel(RedisBus.CHANNEL_EVENTS, system_tid)
        await redis_bus.publish(channel, event.model_dump_json())
    except Exception:
        pass  # Redis may not be available

    try:
        while True:
            data = await ws.receive_text()
            logger.debug("ws.received", client_id=client_id, length=len(data))
            
            try:
                payload = json.loads(data)
                
                if payload.get("type") == "intervention":
                     # DEBUG LOG: See exactly what frontend sends
                     logger.info("ws.intervention_received", payload=payload)
                     
                     user_id = payload.get("user_id")
                     content = payload.get("content")
                     subtype = payload.get("subtype") # e.g. "request_contact"
                     
                     # Robust Platform Handling: Default to whatsapp, lower(), strip()
                     platform_str = payload.get("platform", "whatsapp").lower().strip()
                     
                     try:
                         platform = Platform(platform_str)
                     except ValueError:
                         logger.warning("ws.invalid_platform", platform=platform_str, default="whatsapp")
                         platform = Platform.WHATSAPP

                     if user_id:
                         # Case A: Contact Request (Special Flow)
                         if subtype == "request_contact" and platform == Platform.TELEGRAM:
                             msg_text = content or "Um deinen Account zu verifizieren, teile bitte deine Nummer."
                             await telegram_bot.send_contact_request(user_id, msg_text)
                             logger.info("admin.contact_request", user_id=user_id)
                             
                             # Log as Assistant Message
                             await persistence.save_message( 
                                 user_id=user_id,
                                 role="assistant",
                                 content=f"[System] Contact Request: {msg_text}",
                                 platform=platform,
                                 metadata={"source": "admin", "type": "contact_request"},
                                 tenant_id=persistence.get_system_tenant_id(), # TODO: Resolve from auth/slug
                             )
                             
                         # Case B: Standard Message
                         elif content:
                             logger.info("admin.intervention", user_id=user_id, content=content, platform=platform)
                             
                             # Send to User
                             await send_to_user(user_id, platform, content)
                             
                             # Save to DB (Persistence)
                             # We use "assistant" role but mark it as admin in metadata
                             # NOTE: DB calls should be async wrapped.
                             import asyncio
                             asyncio.create_task(asyncio.to_thread(
                                 persistence.save_message,
                                 user_id=user_id,
                                 role="assistant",
                                 content=content,
                                 platform=platform,
                                 metadata={"source": "admin", "type": "intervention"},
                                 tenant_id=persistence.get_system_tenant_id(), # TODO: Resolve from auth/slug
                             ))
                         
                         # Broadcast back to Admins (so others see it)
                         if content or subtype == "request_contact": # Only broadcast if content exists, or we construct a fake one for req_contact
                             response_content = content or "[System Requested Contact]"
                             await broadcast_to_admins({
                                 "type": "ghost.message_out",
                                 "message_id": f"admin-{datetime.now().timestamp()}",
                                 "user_id": "Admin",
                                 "response": response_content,
                                 "platform": platform
                             })
                         
            except json.JSONDecodeError:
                # Echo legacy fallback
                await ws.send_json({
                    "type": "echo",
                    "client_id": client_id,
                    "data": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.error("ws.handler_failed", error=str(e), data_preview=data[:100])
    except WebSocketDisconnect:
        if ws in active_websockets:
            active_websockets.remove(ws)
        logger.info("ws.disconnected", client_id=client_id, total=len(active_websockets))
