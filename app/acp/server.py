"""ARIIA v1.4 – ACP Server (WebSocket).

@BACKEND: Sprint 6a, Task 6a.1
WebSocket endpoint for IDE integration and control.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.acp.refactor import RefactoringEngine
from app.acp.rollback import RollbackManager
from app.acp.sandbox import Sandbox
from config.settings import get_settings

logger = structlog.get_logger()

router = APIRouter(tags=["ACP"])


class ACPHandler:
    """Handles ACP WebSocket connections."""

    def __init__(self, websocket: WebSocket) -> None:
        self._ws = websocket
        self._root = "."  # Project root
        self._sandbox = Sandbox(self._root)
        self._rollback = RollbackManager(self._root)
        self._refactor = RefactoringEngine(self._sandbox)

    async def handle_message(self, data: dict[str, Any]) -> None:
        """Process incoming ACP command."""
        cmd = data.get("command")
        payload = data.get("payload", {})
        request_id = data.get("id")

        try:
            if cmd == "exec":
                await self._handle_exec(payload, request_id)
            elif cmd == "analyze":
                await self._handle_analyze(payload, request_id)
            elif cmd == "rollback":
                await self._handle_rollback(payload, request_id)
            else:
                await self._send_error(request_id, f"Unknown command: {cmd}")

        except Exception as e:
            logger.error("acp.handler_error", error=str(e))
            await self._send_error(request_id, str(e))

    async def _handle_exec(self, payload: dict[str, Any], req_id: str | None) -> None:
        """Execute shell command in sandbox."""
        cmd_list = payload.get("cmd", [])
        cwd = payload.get("cwd")

        code, stdout, stderr = self._sandbox.run_safe(cmd_list, cwd)
        
        await self._send_response(req_id, {
            "returncode": code,
            "stdout": stdout,
            "stderr": stderr,
        })

    async def _handle_analyze(self, payload: dict[str, Any], req_id: str | None) -> None:
        """Analyze file for issues."""
        path = payload.get("path")
        if not path:
             await self._send_error(req_id, "Missing path")
             return

        issues = self._refactor.analyze_file(path)
        await self._send_response(req_id, {
            "issues": [
                {
                    "file": i.file_path,
                    "line": i.line_number,
                    "type": i.issue_type,
                    "msg": i.message,
                    "severity": i.severity
                }
                for i in issues
            ]
        })

    async def _handle_rollback(self, payload: dict[str, Any], req_id: str | None) -> None:
        """Create or revert checkpoint."""
        action = payload.get("action")  # create/revert
        name = payload.get("name")

        if action == "create":
            tag = self._rollback.create_checkpoint(name)
            await self._send_response(req_id, {"tag": tag})
        elif action == "revert":
            self._rollback.rollback_to(name)
            await self._send_response(req_id, {"status": "reverted"})
        else:
            await self._send_error(req_id, "Invalid action")

    async def _send_response(self, req_id: str | None, data: dict[str, Any]) -> None:
        await self._ws.send_json({
            "id": req_id,
            "status": "ok",
            "data": data,
        })

    async def _send_error(self, req_id: str | None, msg: str) -> None:
        await self._ws.send_json({
            "id": req_id,
            "status": "error",
            "error": msg,
        })


@router.websocket("/acp/ws")
async def acp_websocket(websocket: WebSocket) -> None:
    """ACP WebSocket Endpoint."""
    await websocket.accept()
    
    # Auth check (simple token)
    # Clients must send {"auth": "SECRET"} as first message
    try:
        auth_msg = await websocket.receive_json()
        settings = get_settings()
        secret = getattr(settings, "acp_secret", "ariia-acp-secret")
        
        if auth_msg.get("auth") != secret:
            await websocket.close(code=1008)
            return
            
        handler = ACPHandler(websocket)
        while True:
            data = await websocket.receive_json()
            await handler.handle_message(data)
            
    except WebSocketDisconnect:
        logger.info("acp.disconnect")
    except Exception as e:
        logger.error("acp.error", error=str(e))
        try:
            await websocket.close(code=1011)
        except:
            pass
