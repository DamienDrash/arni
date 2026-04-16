from __future__ import annotations

import os
from typing import Any

import structlog
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.gateway.admin_shared import safe_tenant_slug, write_admin_audit

logger = structlog.get_logger()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
KNOWLEDGE_ROOT_DIR = os.path.join(BASE_DIR, "data", "knowledge")
TENANT_KNOWLEDGE_ROOT_DIR = os.path.join(KNOWLEDGE_ROOT_DIR, "tenants")
MEMORY_INSTRUCTIONS_PATH = os.path.join(KNOWLEDGE_ROOT_DIR, "member-memory-instructions.md")
SYSTEM_PROMPT_AGENTS = {"ops", "sales", "medic", "persona", "router"}
ALLOWED_AGENT_TEMPLATES = {"sales", "medic", "persona", "router", "ops", "concierge", "booking", "escalation"}


class AdminPromptsService:
    @staticmethod
    def require_change_reason(reason: str | None) -> str:
        normalized = (reason or "").strip()
        if len(normalized) < 8:
            raise HTTPException(status_code=422, detail="Change reason is required (min. 8 chars)")
        return normalized

    @staticmethod
    def tenant_knowledge_dir(user: AuthContext) -> str:
        if safe_tenant_slug(user) == "system":
            return KNOWLEDGE_ROOT_DIR
        path = os.path.join(TENANT_KNOWLEDGE_ROOT_DIR, safe_tenant_slug(user))
        try:
            os.makedirs(path, exist_ok=True)
        except PermissionError:
            return KNOWLEDGE_ROOT_DIR
        return path

    def tenant_prompt_path(self, user: AuthContext, agent: str) -> str:
        default_path = os.path.join(BASE_DIR, "app", "prompts", "templates", agent, "system.j2")
        if safe_tenant_slug(user) == "system":
            return default_path
        prompt_dir = os.path.join(self.tenant_knowledge_dir(user), "prompts", agent)
        try:
            os.makedirs(prompt_dir, exist_ok=True)
        except PermissionError:
            return default_path
        return os.path.join(prompt_dir, "system.j2")

    def tenant_memory_instructions_path(self, user: AuthContext) -> str:
        if safe_tenant_slug(user) == "system":
            return MEMORY_INSTRUCTIONS_PATH
        prompt_dir = os.path.join(self.tenant_knowledge_dir(user), "prompts")
        try:
            os.makedirs(prompt_dir, exist_ok=True)
        except PermissionError:
            return MEMORY_INSTRUCTIONS_PATH
        return os.path.join(prompt_dir, "member-memory-instructions.md")

    @staticmethod
    def agent_template_path(user: AuthContext, agent: str) -> str:
        prompt_dir = os.path.join(TENANT_KNOWLEDGE_ROOT_DIR, safe_tenant_slug(user), "prompts", agent)
        try:
            os.makedirs(prompt_dir, exist_ok=True)
        except PermissionError:
            pass
        return os.path.join(prompt_dir, "system.j2")

    @staticmethod
    def agent_default_template_path(agent: str) -> str:
        return os.path.join(BASE_DIR, "app", "prompts", "templates", agent, "system.j2")

    def get_agent_system_prompt(self, user: AuthContext, agent: str) -> dict[str, Any]:
        if agent not in SYSTEM_PROMPT_AGENTS:
            raise HTTPException(status_code=400, detail="Invalid agent")
        tenant_prompt_path = self.tenant_prompt_path(user, agent)
        default_path = os.path.join(BASE_DIR, "app", "prompts", "templates", agent, "system.j2")
        prompt_path = tenant_prompt_path if os.path.exists(tenant_prompt_path) else default_path
        if not os.path.exists(prompt_path):
            raise HTTPException(status_code=404, detail="Prompt not found")
        with open(prompt_path, "r", encoding="utf-8") as handle:
            content = handle.read()
        return {"filename": f"{agent}/system.j2", "content": content, "mtime": os.path.getmtime(prompt_path)}

    def save_agent_system_prompt(self, user: AuthContext, agent: str, *, content: str, base_mtime: float | None, reason: str | None) -> dict[str, Any]:
        if agent not in SYSTEM_PROMPT_AGENTS:
            raise HTTPException(status_code=400, detail="Invalid agent")
        normalized_reason = self.require_change_reason(reason)
        path = self.tenant_prompt_path(user, agent)
        if os.path.exists(path) and base_mtime is not None:
            current_mtime = os.path.getmtime(path)
            if abs(current_mtime - base_mtime) > 1e-6:
                raise HTTPException(status_code=409, detail="Prompt changed since last load")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        saved_mtime = os.path.getmtime(path)
        write_admin_audit(
            actor=user,
            action=f"prompt.{agent}.update",
            category="prompts",
            target_type="prompt_file",
            target_id=f"{agent}/system.j2",
            details={"reason": normalized_reason, "content_chars": len(content or ""), "mtime": saved_mtime},
        )
        logger.info("admin.agent_system_prompt_updated", agent=agent)
        return {"status": "updated", "mtime": saved_mtime}

    def get_member_memory_instructions(self, user: AuthContext) -> dict[str, Any]:
        path = self.tenant_memory_instructions_path(user)
        if not os.path.exists(path):
            from app.memory.member_memory_analyzer import DEFAULT_INSTRUCTIONS

            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(DEFAULT_INSTRUCTIONS)
            except PermissionError:
                with open(MEMORY_INSTRUCTIONS_PATH, "w", encoding="utf-8") as handle:
                    handle.write(DEFAULT_INSTRUCTIONS)
                path = MEMORY_INSTRUCTIONS_PATH
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        return {"filename": os.path.basename(path), "content": content, "mtime": os.path.getmtime(path)}

    def save_member_memory_instructions(self, user: AuthContext, *, content: str, base_mtime: float | None, reason: str | None) -> dict[str, Any]:
        normalized_reason = self.require_change_reason(reason)
        path = self.tenant_memory_instructions_path(user)
        if os.path.exists(path) and base_mtime is not None:
            current_mtime = os.path.getmtime(path)
            if abs(current_mtime - base_mtime) > 1e-6:
                raise HTTPException(status_code=409, detail="Prompt changed since last load")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
        except PermissionError:
            with open(MEMORY_INSTRUCTIONS_PATH, "w", encoding="utf-8") as handle:
                handle.write(content)
            path = MEMORY_INSTRUCTIONS_PATH
        saved_mtime = os.path.getmtime(path)
        write_admin_audit(
            actor=user,
            action="prompt.member_memory.update",
            category="prompts",
            target_type="prompt_file",
            target_id="member-memory-instructions.md",
            details={"reason": normalized_reason, "content_chars": len(content or ""), "mtime": saved_mtime},
        )
        logger.info("admin.member_memory_instructions_updated")
        return {"status": "updated", "mtime": saved_mtime}

    def get_agent_template(self, user: AuthContext, agent: str) -> dict[str, Any]:
        if agent not in ALLOWED_AGENT_TEMPLATES:
            raise HTTPException(status_code=404, detail=f"Unknown agent '{agent}'. Allowed: {sorted(ALLOWED_AGENT_TEMPLATES)}")
        tenant_path = self.agent_template_path(user, agent)
        default_path = self.agent_default_template_path(agent)
        is_custom = os.path.exists(tenant_path)
        active_path = tenant_path if is_custom else default_path
        if not os.path.exists(active_path):
            raise HTTPException(status_code=404, detail=f"No template found for agent '{agent}'")
        with open(active_path, "r", encoding="utf-8") as handle:
            content = handle.read()
        return {
            "agent": agent,
            "is_custom": is_custom,
            "filename": f"{agent}/system.j2",
            "content": content,
            "mtime": os.path.getmtime(active_path),
        }

    def save_agent_template(self, user: AuthContext, agent: str, *, content: str, base_mtime: float | None, reason: str | None) -> dict[str, Any]:
        if agent not in ALLOWED_AGENT_TEMPLATES:
            raise HTTPException(status_code=404, detail=f"Unknown agent '{agent}'. Allowed: {sorted(ALLOWED_AGENT_TEMPLATES)}")
        normalized_reason = self.require_change_reason(reason)
        path = self.agent_template_path(user, agent)
        if os.path.exists(path) and base_mtime is not None:
            current_mtime = os.path.getmtime(path)
            if abs(current_mtime - base_mtime) > 1e-6:
                raise HTTPException(status_code=409, detail="Template changed since last load")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        saved_mtime = os.path.getmtime(path)
        write_admin_audit(
            actor=user,
            action=f"prompt.agent.{agent}.update",
            category="prompts",
            target_type="agent_template",
            target_id=f"{agent}/system.j2",
            details={"reason": normalized_reason, "content_chars": len(content or ""), "mtime": saved_mtime},
        )
        logger.info("admin.agent_template_saved", agent=agent, tenant_id=user.tenant_id)
        return {"status": "updated", "agent": agent, "mtime": saved_mtime}

    def reset_agent_template(self, user: AuthContext, agent: str) -> dict[str, Any]:
        if agent not in ALLOWED_AGENT_TEMPLATES:
            raise HTTPException(status_code=404, detail=f"Unknown agent '{agent}'.")
        path = self.agent_template_path(user, agent)
        if os.path.exists(path):
            os.remove(path)
            write_admin_audit(
                actor=user,
                action=f"prompt.agent.{agent}.reset",
                category="prompts",
                target_type="agent_template",
                target_id=f"{agent}/system.j2",
                details={"reset_to_default": True},
            )
            return {"status": "reset", "agent": agent}
        return {"status": "already_default", "agent": agent}


service = AdminPromptsService()
