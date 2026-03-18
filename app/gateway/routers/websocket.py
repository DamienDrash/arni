"""ARIIA v1.4 – Admin WebSocket Router.

Handles real-time control (Ghost Mode) and admin interventions.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.auth import decode_access_token, _resolve_context_from_payload
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
    # Issue #3: Auth guard — must validate token before accepting the connection
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Unauthorized")
        return

    try:
        payload = decode_access_token(token)
        auth_ctx = _resolve_context_from_payload(payload)
    except Exception:
        await ws.close(code=4001, reason="Unauthorized")
        return

    if auth_ctx.role not in ("system_admin", "tenant_admin"):
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws.accept()

    # Derive resolved_tid from the validated auth context — never trust client-supplied value
    resolved_tid = auth_ctx.tenant_id
    if resolved_tid not in active_websockets:
        active_websockets[resolved_tid] = []
    active_websockets[resolved_tid].append(ws)
    
    client_id = str(uuid4())[:8]
    logger.info("ws.connected", client_id=client_id, tenant_id=resolved_tid, total=len(active_websockets[resolved_tid]))

    try:
        event = SystemEvent(
            event_type="admin.connected",
            source="gateway",
            payload={"client_id": client_id, "tenant_id": resolved_tid},
            severity="info",
        )
        from app.gateway.redis_bus import RedisBus
        channel = redis_bus.get_tenant_channel(RedisBus.CHANNEL_EVENTS, resolved_tid)
        await redis_bus.publish(channel, event.model_dump_json())
    except Exception:
        pass

    async def _heartbeat():
        try:
            while True:
                await asyncio.sleep(20)
                await ws.send_json({"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()})
        except Exception:
            pass

    import asyncio
    heartbeat_task = asyncio.create_task(_heartbeat())

    try:
        while True:
            data = await ws.receive_text()
            try:
                payload = json.loads(data)
                # ... (rest of logic)
                
                if payload.get("type") == "intervention":
                     user_id = payload.get("user_id")
                     content = payload.get("content")
                     subtype = payload.get("subtype")
                     # Use the connection's tenant_id for security
                     
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
                             # send_to_user already handles saving to DB! No need to call persistence.save_message here.
                             await send_to_user(user_id, platform, content, tenant_id=resolved_tid)
                         
                         if content or subtype == "request_contact":
                             response_content = content or "[System Requested Contact]"
                             await broadcast_to_admins({
                                 "type": "ghost.message_out",
                                 "message_id": f"admin-{datetime.now().timestamp()}",
                                 "user_id": user_id, # Target user ID
                                 "response": response_content,
                                 "platform": platform
                             }, tenant_id=resolved_tid)
                         
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
        if resolved_tid in active_websockets and ws in active_websockets[resolved_tid]:
            active_websockets[resolved_tid].remove(ws)
        logger.info("ws.disconnected", client_id=client_id, tenant_id=resolved_tid)
    except Exception as e:
        logger.error("ws.connection_error", error=str(e), client_id=client_id)
        if resolved_tid in active_websockets and ws in active_websockets[resolved_tid]:
            active_websockets[resolved_tid].remove(ws)
    finally:
        heartbeat_task.cancel()
