"""CampaignOrchestrator: coordinates MarketingAgent → DesignerAgent → QAAgent pipeline."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Optional
import structlog
from sqlalchemy.orm import Session

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
            # Step 1: Gather knowledge context
            knowledge_context = ""
            if request.use_knowledge:
                knowledge_context = await self._gather_knowledge(request, db)
                if knowledge_context:
                    result.pipeline_steps.append("knowledge_retrieval")

            # Step 2: Gather chat history context
            chat_context = ""
            if request.use_chat_history:
                chat_context = self._gather_chat_context(request, db)

            # Step 3: Load template if specified
            template = None
            if request.template_id:
                from app.core.models import CampaignTemplate
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
            )
            result.subject = text.get("subject", "")
            result.body = text.get("body", "")
            result.variables = text.get("variables", {})

            if text.get("error"):
                result.error = text["error"]
                return result

            # Step 5: DesignerAgent generates HTML (email only)
            if request.channel == "email":
                result.pipeline_steps.append("designer")
                result.html = await self._designer.generate_html(
                    template=template,
                    subject=result.subject,
                    body=result.body,
                    variables=result.variables,
                    tenant_id=request.tenant_id,
                )

            # Step 6: QAAgent validates
            result.pipeline_steps.append("qa")
            qa = self._qa.validate(
                channel=request.channel,
                subject=result.subject,
                body=result.body,
                html=result.html,
                tenant_id=request.tenant_id,
            )
            result.qa_passed = qa.passed
            result.qa_issues = qa.issues
            result.qa_suggestions = qa.suggestions

        except Exception as e:
            logger.error("campaign_orchestrator.failed", error=str(e), tenant_id=request.tenant_id)
            result.error = str(e)

        return result

    async def _gather_knowledge(self, request: CampaignGenerationRequest, db: Session) -> str:
        try:
            from app.knowledge.knowledge_manager import KnowledgeManager
            from app.core.models import Tenant
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

    def _gather_chat_context(self, request: CampaignGenerationRequest, db: Session) -> str:
        try:
            from app.core.models import ChatMessage
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
