"""MediaOrchestrator: coordinates ImagePromptAgent → ImageGenerationAgent → ImageQAAgent → ImageAnalysisAgent pipeline."""
from __future__ import annotations
import structlog
from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.orm import Session

logger = structlog.get_logger()


@dataclass
class MediaGenerationRequest:
    user_prompt: str
    tenant_id: int
    task_context: str = "general"   # "hero"|"email"|"thumbnail"|"background"|"product"
    channel: str = "email"
    tone: str = "professional"
    campaign_name: str = ""
    size: str = "1024x1024"
    quality: str = "standard"
    created_by: Optional[int] = None
    model_slug: Optional[str] = None  # explicit model override from user


@dataclass
class MediaGenerationResult:
    asset_id: Optional[int] = None
    url: str = ""
    qa_passed: bool = True
    qa_score: int = 8
    qa_issues: list[str] = field(default_factory=list)
    qa_suggestions: list[str] = field(default_factory=list)
    pipeline_steps: list[str] = field(default_factory=list)
    retries: int = 0
    revised_prompt: str = ""
    error: Optional[str] = None


# Internal sub-component — not a managed orchestrator. Use via CampaignOrchestrator.
class MediaOrchestrator:
    def __init__(self, llm):
        from app.swarm.agents.media.prompt_agent import ImagePromptAgent
        from app.swarm.agents.media.generation_agent import ImageGenerationAgent
        from app.swarm.agents.media.analysis_agent import ImageAnalysisAgent
        from app.swarm.agents.media.qa_agent import ImageQAAgent

        self._llm = llm
        self._prompt_agent = ImagePromptAgent()
        self._generation_agent = ImageGenerationAgent()
        self._analysis_agent = ImageAnalysisAgent()
        self._qa_agent = ImageQAAgent()

        ImagePromptAgent.set_llm(llm)
        ImageGenerationAgent.set_llm(llm)
        ImageAnalysisAgent.set_llm(llm)
        ImageQAAgent.set_llm(llm)

    async def run(
        self,
        request: MediaGenerationRequest,
        db: Session,
        tenant_slug: str,
    ) -> MediaGenerationResult:
        result = MediaGenerationResult()
        max_retries = 2

        try:
            from app.media.service import MediaService
            from app.media.storage import save_bytes, get_public_url

            svc = MediaService(db=db, tenant_id=request.tenant_id, tenant_slug=tenant_slug)

            # Step 1: Enrich prompt
            result.pipeline_steps.append("prompt_enrichment")
            enriched_prompt = await self._prompt_agent.enrich(
                user_prompt=request.user_prompt,
                tenant_id=request.tenant_id,
                channel=request.channel,
                tone=request.tone,
                campaign_name=request.campaign_name,
                db=db,
            )

            # Steps 2-4: Generate → QA (with retry)
            image_bytes = None
            provider_slug = ""
            revised_prompt = enriched_prompt
            qa_result = None
            metadata = {}

            for attempt in range(max_retries + 1):
                if attempt > 0:
                    result.retries += 1
                    # Refine prompt with QA feedback
                    if qa_result and qa_result.issues:
                        enriched_prompt = enriched_prompt + f" Avoid: {qa_result.issues[0]}."
                    if qa_result and qa_result.suggestions:
                        enriched_prompt = enriched_prompt + f" Prefer: {qa_result.suggestions[0]}."
                    result.pipeline_steps.append(f"generation_retry_{attempt}")
                else:
                    result.pipeline_steps.append("generation")

                # Step 2: Generate image
                svc.check_image_gen_quota()
                image_bytes, provider_slug, revised_prompt = await self._generation_agent.generate(
                    prompt=enriched_prompt,
                    tenant_id=request.tenant_id,
                    size=request.size,
                    quality=request.quality,
                    db=db,
                    model_slug=request.model_slug,
                )

                # Step 3: Extract technical metadata (Pillow, no LLM)
                try:
                    metadata = MediaService._extract_image_metadata(image_bytes)
                except Exception:
                    metadata = {}

                # Step 4: QA validation (visual + rules via GPT-4o Vision)
                result.pipeline_steps.append("qa")
                qa_result = await self._qa_agent.validate_visual(
                    image_bytes=image_bytes,
                    channel=request.channel,
                    task_context=request.task_context,
                    tenant_id=request.tenant_id,
                )

                if qa_result.passed:
                    break
                elif attempt >= max_retries:
                    # Exceeded retries — proceed anyway but flag QA failure
                    break

            result.qa_passed = qa_result.passed if qa_result else True
            result.qa_score = qa_result.score if qa_result else 8
            result.qa_issues = qa_result.issues if qa_result else []
            result.qa_suggestions = qa_result.suggestions if qa_result else []
            result.revised_prompt = revised_prompt

            # Step 5: Save to disk + DB
            result.pipeline_steps.append("storage")
            svc.check_storage_quota(bytes_to_add=len(image_bytes))
            filename, file_size = await save_bytes(image_bytes, tenant_slug, ".png")

            asset = svc.record_ai_generated(
                filename=filename,
                file_size=file_size,
                mime_type="image/png",
                prompt=request.user_prompt,
                provider_slug=provider_slug,
                created_by=request.created_by,
                image_data=image_bytes,
            )

            svc.increment_image_gen_usage()
            svc.increment_storage_usage(file_size)

            # Step 6: Vision analysis (semantic metadata)
            result.pipeline_steps.append("analysis")
            analysis = await self._analysis_agent.describe(
                image_bytes=image_bytes,
                tenant_id=request.tenant_id,
            )
            if analysis:
                asset.description = analysis.get("description")
                asset.tags = analysis.get("tags")
                if analysis.get("alt_text"):
                    asset.alt_text = analysis.get("alt_text")
                asset.usage_context = analysis.get("usage_context")
                if analysis.get("dominant_colors"):
                    asset.dominant_colors = analysis.get("dominant_colors")
                if analysis.get("brightness"):
                    asset.brightness = analysis.get("brightness")
                db.commit()

            url = get_public_url(tenant_slug, filename)
            result.asset_id = asset.id
            result.url = url

            logger.info(
                "media_orchestrator.complete",
                asset_id=asset.id,
                tenant_id=request.tenant_id,
                retries=result.retries,
                qa_passed=result.qa_passed,
                steps=result.pipeline_steps,
            )

        except Exception as e:
            logger.error("media_orchestrator.failed", error=str(e), tenant_id=request.tenant_id)
            result.error = str(e)

        return result
