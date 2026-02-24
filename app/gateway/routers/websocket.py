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
    get_telegram_bot,
)
from app.gateway.schemas import SystemEvent, Platform
from app.gateway.persistence import persistence
from app.gateway.utils import send_to_user, broadcast_to_admins

logger = structlog.get_logger()
router = APIRouter(tags=["admin"])

@router.websocket("/ws/control")
async def websocket_control(ws: WebSocket) -> None:
    """WebSocket endpoint for Admin Dashboard & Ghost Mode."""
    await ws.accept()
    active_websockets.append(ws)
    client_id = str(uuid4())[:8]
    logger.info("ws.connected", client_id=client_id, total=len(active_websockets))

    try:
        system_tid = persistence.get_system_tenant_id()
        event = SystemEvent(
            event_type="admin.connected",
            source="gateway",
            payload={"client_id": client_id},
            severity="info",
        )
        channel = redis_bus.get_tenant_channel(RedisBus.CHANNEL_EVENTS, system_tid)
        await redis_bus.publish(channel, event.model_dump_json())
    except Exception:
        pass

    try:
        while True:
            data = await ws.receive_text()
            try:
                payload = json.loads(data)
                
                if payload.get("type") == "intervention":
                     user_id = payload.get("user_id")
                     content = payload.get("content")
                     subtype = payload.get("subtype")
                     tenant_id = payload.get("tenant_id") # Try to get tenant_id from payload
                     
                     resolved_tid = tenant_id if tenant_id is not None else persistence.get_system_tenant_id()
                     
                     platform_str = payload.get("platform", "whatsapp").lower().strip()
                     try:
                         platform = Platform(platform_str)
                     except ValueError:
                         platform = Platform.WHATSAPP

                     if user_id:
                         if subtype == "request_contact" and platform == Platform.TELEGRAM:
                             msg_text = content or "Um deinen Account zu verifizieren, teile bitte deine Nummer."
                             tg_bot = get_telegram_bot(resolved_tid)
                             await tg_bot.send_contact_request(user_id, msg_text)
                             
                             await persistence.save_message( 
                                 user_id=user_id,
                                 role="assistant",
                                 content=f"[System] Contact Request: {msg_text}",
                                 platform=platform,
                                 metadata={"source": "admin", "type": "contact_request"},
                                 tenant_id=resolved_tid,
                             )
                             
                         elif content:
                             await send_to_user(user_id, platform, content, tenant_id=resolved_tid)
                             
                             import asyncio
                             asyncio.create_task(asyncio.to_thread(
                                 persistence.save_message,
                                 user_id=user_id,
                                 role="assistant",
                                 content=content,
                                 platform=platform,
                                 metadata={"source": "admin", "type": "intervention"},
                                 tenant_id=resolved_tid,
                             ))
                         
                         if content or subtype == "request_contact":
                             response_content = content or "[System Requested Contact]"
                             await broadcast_to_admins({
                                 "type": "ghost.message_out",
                                 "message_id": f"admin-{datetime.now().timestamp()}",
                                 "user_id": "Admin",
                                 "response": response_content,
                                 "platform": platform
                             })
                         
            except json.JSONDecodeError:
                await ws.send_json({
                    "type": "echo",
                    "client_id": client_id,
                    "data": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.error("ws.handler_failed", error=str(e))
    except WebSocketDisconnect:
        if ws in active_websockets:
            active_websockets.remove(ws)
        logger.info("ws.disconnected", client_id=client_id)
