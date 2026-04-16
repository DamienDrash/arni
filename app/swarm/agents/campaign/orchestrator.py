"""CampaignOrchestrator: coordinates MarketingAgent → DesignerAgent → QAAgent pipeline."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Optional
import structlog
from sqlalchemy.orm import Session

from app.domains.campaigns.models import CampaignTemplate
from app.domains.identity.models import Tenant
from app.domains.support.models import ChatMessage

logger = structlog.get_logger()


@dataclass
class CampaignGenerationRequest:
    campaign_name: str
    channel: str
    tone: str
    prompt: str
    tenant_id: int
    template_id: Optional[int] = None
    use_knowledge: bool = True
    use_chat_history: bool = False
    generate_image: bool = False
    image_size: str = "1024x1024"
    image_quality: str = "standard"
    image_model_slug: Optional[str] = None
    created_by: Optional[int] = None


@dataclass
class CampaignGenerationResult:
    subject: str = ""
    body: str = ""
    html: str = ""
    variables: dict = field(default_factory=dict)
    qa_passed: bool = True
    qa_issues: list[str] = field(default_factory=list)
    qa_suggestions: list[str] = field(default_factory=list)
    pipeline_steps: list[str] = field(default_factory=list)
    error: Optional[str] = None
    image_asset_id: Optional[int] = None
    image_url: str = ""


class CampaignOrchestrator:
    def __init__(self, llm):
        from app.swarm.agents.campaign.marketing_agent import MarketingAgent
        from app.swarm.agents.campaign.designer_agent import DesignerAgent
        from app.swarm.agents.campaign.qa_agent import QAAgent
        self._llm = llm
        self._marketing = MarketingAgent()
        self._designer = DesignerAgent()
        self._qa = QAAgent()
        # Share LLM client with agents
        MarketingAgent.set_llm(llm)
        DesignerAgent.set_llm(llm)

    async def run(self, request: CampaignGenerationRequest, db: Session) -> CampaignGenerationResult:
        result = CampaignGenerationResult()

        try:
            # Resolve tenant slug and display name once
            tenant_slug = ""
            studio_name = ""
            try:
                tenant_obj = db.query(Tenant).filter(Tenant.id == request.tenant_id).first()
                tenant_slug = tenant_obj.slug if tenant_obj else "default"
                # Use the tenant's actual business name — never the platform name
                studio_name = tenant_obj.name if tenant_obj else ""
            except Exception:
                pass

            # Step 1: Gather knowledge context
            knowledge_context = ""
            if request.use_knowledge:
                knowledge_context = await self._gather_knowledge(request, db, tenant_slug=tenant_slug)
                if knowledge_context:
                    result.pipeline_steps.append("knowledge_retrieval")

            # Step 1.5: Gather integration context (active connectors for this tenant)
            integration_ctx = self._gather_integration_context(request.tenant_id)
            if integration_ctx.active:
                result.pipeline_steps.append("integration_context")

            # Step 2: Gather chat history context
            chat_context = ""
            if request.use_chat_history:
                chat_context = self._gather_chat_context(request, db)

            # Step 3: Load template if specified
            template = None
            if request.template_id:
                template = db.query(CampaignTemplate).filter(
                    CampaignTemplate.id == request.template_id,
                    CampaignTemplate.tenant_id == request.tenant_id,
                    CampaignTemplate.is_active.is_(True),
                ).first()

            # Step 4: MarketingAgent generates text
            result.pipeline_steps.append("marketing")
            text = await self._marketing.generate(
                campaign_name=request.campaign_name,
                channel=request.channel,
                tone=request.tone,
                prompt=request.prompt,
                knowledge_context=knowledge_context,
                chat_context=chat_context,
                tenant_id=request.tenant_id,
                integration_context=integration_ctx.to_agent_summary(),
                studio_name=studio_name,
            )
            result.subject = text.get("subject", "")
            result.body = text.get("body", "")
            result.html = text.get("html", "")  # MarketingAgent may already include html
            result.variables = text.get("variables", {})

            if text.get("error"):
                result.error = text["error"]
                return result

            # Step 4.5: Gather relevant media assets for email campaigns
            media_context = ""
            if request.channel == "email" and db:
                try:
                    from app.core.media_models import MediaAsset
                    from app.media.storage import get_public_url
                    from sqlalchemy import or_, cast
                    import sqlalchemy as sa

                    keywords = (request.campaign_name or request.prompt)[:60]
                    assets = db.query(MediaAsset).filter(
                        MediaAsset.tenant_id == request.tenant_id,
                        MediaAsset.mime_type != "image/webp",
                        or_(
                            MediaAsset.description.ilike(f"%{keywords}%"),
                            MediaAsset.display_name.ilike(f"%{keywords}%"),
                            cast(MediaAsset.tags, sa.Text).ilike(f"%{keywords}%"),
                        )
                    ).order_by(MediaAsset.created_at.desc()).limit(3).all()

                    # No fallback to unrelated recent images — only use keyword-matched assets
                    if assets:
                        lines = []
                        for a in assets:
                            url = get_public_url(tenant_slug, a.filename)
                            desc = a.description or a.display_name or a.alt_text or a.filename
                            tags = ", ".join(a.tags[:3]) if a.tags else ""
                            line = f"- {desc}"
                            if tags:
                                line += f" (Tags: {tags})"
                            line += f": {url}"
                            lines.append(line)
                        media_context = "\n".join(lines)
                        result.pipeline_steps.append("media_retrieval")
                except Exception as e:
                    logger.warning("campaign_orchestrator.media_context_failed", error=str(e))

            # Step 5: DesignerAgent generates HTML (email only)
            if request.channel == "email":
                result.pipeline_steps.append("designer")
                result.html = await self._designer.generate_html(
                    template=template,
                    subject=result.subject,
                    body=result.body,
                    variables=result.variables,
                    tenant_id=request.tenant_id,
                    media_context=media_context,
                    studio_name=studio_name,
                )

            # Step 6: QAAgent validates
            result.pipeline_steps.append("qa")
            qa = self._qa.validate(
                channel=request.channel,
                subject=result.subject,
                body=result.body,
                html=result.html,
                tenant_id=request.tenant_id,
                integration_ctx=integration_ctx,
            )
            result.qa_passed = qa.passed
            result.qa_issues = qa.issues
            result.qa_suggestions = qa.suggestions

            # Step 7: Optional image generation via MediaOrchestrator
            if request.generate_image:
                image_result = await self._run_image_generation(request, db, tenant_slug)
                if image_result and not image_result.error:
                    result.image_asset_id = image_result.asset_id
                    result.image_url = image_result.url
                    result.pipeline_steps.append("image_generation")
                elif image_result and image_result.error:
                    logger.warning(
                        "campaign_orchestrator.image_generation_failed",
                        error=image_result.error,
                        tenant_id=request.tenant_id,
                    )

        except Exception as e:
            logger.error("campaign_orchestrator.failed", error=str(e), tenant_id=request.tenant_id)
            result.error = str(e)

        return result

    def _gather_integration_context(self, tenant_id: int):
        """Return active integration context for this tenant (no API calls)."""
        from app.integrations.integration_context import IntegrationContextService
        return IntegrationContextService().get_context(tenant_id)

    async def _gather_knowledge(self, request: CampaignGenerationRequest, db: Session, *, tenant_slug: str = "") -> str:
        try:
            from app.knowledge.knowledge_manager import KnowledgeManager
            if not tenant_slug:
                tenant = db.query(Tenant).filter(Tenant.id == request.tenant_id).first()
                tenant_slug = tenant.slug if tenant else "default"
            km = KnowledgeManager()
            results = await km.search(
                query=request.prompt,
                tenant_slug=tenant_slug,
                n_results=5,
                include_shared=True,
            )
            if results.has_results:
                return results.to_context_string(max_results=5)
        except Exception as e:
            logger.warning("campaign_orchestrator.knowledge_failed", error=str(e))
        return ""

    async def _run_image_generation(self, request: CampaignGenerationRequest, db: Session, tenant_slug: str):
        """Run image generation via MediaOrchestrator (internal sub-component)."""
        try:
            from app.swarm.agents.media.orchestrator import MediaOrchestrator, MediaGenerationRequest

            media_orch = MediaOrchestrator(self._llm)
            media_req = MediaGenerationRequest(
                user_prompt=request.prompt,
                tenant_id=request.tenant_id,
                campaign_name=request.campaign_name,
                channel=request.channel,
                tone=request.tone,
                task_context="email" if request.channel == "email" else "general",
                size=request.image_size,
                quality=request.image_quality,
                created_by=request.created_by,
                model_slug=request.image_model_slug,
            )
            return await media_orch.run(media_req, db=db, tenant_slug=tenant_slug)
        except Exception as e:
            logger.error("campaign_orchestrator.image_generation_error", error=str(e))
            return None

    def _gather_chat_context(self, request: CampaignGenerationRequest, db: Session) -> str:
        try:
            from sqlalchemy import desc
            recent = db.query(ChatMessage).filter(
                ChatMessage.tenant_id == request.tenant_id,
                ChatMessage.role == "user",
            ).order_by(desc(ChatMessage.timestamp)).limit(20).all()
            topics = set()
            for msg in recent:
                if msg.content and len(msg.content) > 10:
                    topics.add(msg.content[:100])
            if topics:
                return "Aktuelle Mitglieder-Themen: " + "; ".join(list(topics)[:5])
        except Exception as e:
            logger.warning("campaign_orchestrator.chat_context_failed", error=str(e))
        return ""
