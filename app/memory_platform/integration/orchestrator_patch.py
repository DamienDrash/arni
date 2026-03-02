"""Orchestrator Integration Patch – patches MasterAgentV2 to use the Memory Platform.

This module provides monkey-patch functions that replace the legacy
knowledge_base and member_memory tool handlers in the Orchestrator
with the new Memory Platform bridge.

Usage:
    from app.memory_platform.integration.orchestrator_patch import patch_orchestrator
    patch_orchestrator()

This is designed as a non-invasive integration: the original orchestrator
code remains unchanged, and the patch can be applied/removed at runtime.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


def patch_orchestrator() -> None:
    """Patch the MasterAgentV2 to use the Memory Platform.

    Replaces:
    - _handle_knowledge_base → uses Memory Platform hybrid search
    - _handle_member_memory → uses Memory Platform retrieval + facts
    - Adds proactive context surfacing to _build_system_prompt
    """
    try:
        from app.swarm.master.orchestrator_v2 import MasterAgentV2
        from app.memory_platform.integration import get_memory_platform_bridge

        bridge = get_memory_platform_bridge()

        # Store original methods for potential rollback
        _original_knowledge = getattr(MasterAgentV2, '_handle_knowledge_base', None)
        _original_memory = getattr(MasterAgentV2, '_handle_member_memory', None)
        _original_prompt = getattr(MasterAgentV2, '_build_system_prompt', None)

        async def _patched_knowledge_base(self, tc, message):
            """Patched knowledge_base handler using Memory Platform."""
            from app.swarm.tool_calling import ToolCallResult

            query = tc.arguments.get("query", "")
            top_k = tc.arguments.get("top_k", 5)

            try:
                content = await bridge.handle_knowledge_base_tool(
                    tenant_id=message.tenant_id,
                    query=query,
                    top_k=top_k,
                )
                return ToolCallResult(
                    tool_call_id=tc.id,
                    name="knowledge_base",
                    content=content,
                    success=True,
                )
            except Exception as e:
                logger.error("orchestrator_patch.knowledge_error", error=str(e))
                # Fallback to original handler
                if _original_knowledge:
                    return await _original_knowledge(self, tc, message)
                return ToolCallResult(
                    tool_call_id=tc.id,
                    name="knowledge_base",
                    content=f"Wissensdatenbank-Fehler: {str(e)}",
                    success=False,
                    error=str(e),
                )

        async def _patched_member_memory(self, tc, message):
            """Patched member_memory handler using Memory Platform."""
            from app.swarm.tool_calling import ToolCallResult

            query = tc.arguments.get("query", "")
            action = tc.arguments.get("action", "retrieve")

            try:
                content = await bridge.handle_member_memory_tool(
                    tenant_id=message.tenant_id,
                    user_id=message.user_id,
                    query=query,
                    action=action,
                )
                return ToolCallResult(
                    tool_call_id=tc.id,
                    name="member_memory",
                    content=content,
                    success=True,
                )
            except Exception as e:
                logger.error("orchestrator_patch.memory_error", error=str(e))
                # Fallback to original handler
                if _original_memory:
                    return await _original_memory(self, tc, message)
                return ToolCallResult(
                    tool_call_id=tc.id,
                    name="member_memory",
                    content=f"Memory-Fehler: {str(e)}",
                    success=False,
                    error=str(e),
                )

        async def _patched_build_system_prompt(self, message):
            """Patched system prompt builder with proactive context surfacing."""
            # Get the original prompt
            if _original_prompt:
                base_prompt = await _original_prompt(self, message)
            else:
                base_prompt = ""

            # Add proactive context from Memory Platform
            try:
                member_id = message.metadata.get("member_id") or message.user_id
                context = await bridge.build_agent_context(
                    tenant_id=message.tenant_id,
                    member_id=member_id,
                    query=message.content,
                )
                if context:
                    base_prompt += f"\n\n--- KONTEXT AUS DEM KUNDENGEDÄCHTNIS ---\n{context}\n--- ENDE KONTEXT ---"
            except Exception as e:
                logger.warning("orchestrator_patch.context_error", error=str(e))

            return base_prompt

        # Apply patches
        MasterAgentV2._handle_knowledge_base = _patched_knowledge_base
        MasterAgentV2._handle_member_memory = _patched_member_memory
        MasterAgentV2._build_system_prompt = _patched_build_system_prompt

        logger.info("orchestrator_patch.applied")

    except ImportError as e:
        logger.warning("orchestrator_patch.import_error", error=str(e))
    except Exception as e:
        logger.error("orchestrator_patch.error", error=str(e))


def patch_campaign_engine() -> None:
    """Patch the Campaign Engine to use the Memory Platform for knowledge context.

    Replaces the legacy KnowledgeManager search in the campaigns router
    with the Memory Platform's hybrid search.
    """
    try:
        from app.memory_platform.integration import get_memory_platform_bridge

        bridge = get_memory_platform_bridge()

        # The campaign router uses KnowledgeManager directly.
        # We patch KnowledgeManager.search to route through the bridge.
        from app.knowledge.knowledge_manager import KnowledgeManager

        _original_search = KnowledgeManager.search

        async def _patched_search(self, query, tenant_slug="", n_results=5, **kwargs):
            """Patched search that uses Memory Platform hybrid search."""
            try:
                # Determine tenant_id from slug
                tenant_id = getattr(self, '_tenant_id', 1)

                from app.memory_platform.retrieval import get_retrieval_service
                from app.memory_platform.models import SearchQuery

                service = get_retrieval_service()
                await service.initialise()

                search_query = SearchQuery(
                    query=query,
                    tenant_id=tenant_id,
                    top_k=n_results,
                    search_type="hybrid",
                    include_knowledge=True,
                    include_facts=False,
                )
                response = await service.search(search_query)

                # Convert to legacy format
                class LegacySearchResult:
                    def __init__(self, results):
                        self._results = results

                    @property
                    def has_results(self):
                        return len(self._results) > 0

                    def to_context_string(self, max_results=5):
                        parts = []
                        for r in self._results[:max_results]:
                            parts.append(r.content)
                        return "\n\n".join(parts)

                return LegacySearchResult(response.results)

            except Exception as e:
                logger.warning("campaign_patch.search_fallback", error=str(e))
                # Fallback to original
                return await _original_search(self, query, tenant_slug, n_results, **kwargs)

        KnowledgeManager.search = _patched_search
        logger.info("campaign_patch.applied")

    except ImportError as e:
        logger.warning("campaign_patch.import_error", error=str(e))
    except Exception as e:
        logger.error("campaign_patch.error", error=str(e))


def apply_all_patches() -> None:
    """Apply all integration patches."""
    patch_orchestrator()
    patch_campaign_engine()
    logger.info("memory_platform.all_patches_applied")
