"""ARIIA Phase 3 Refactoring Tests – Intelligent Orchestration.

Tests for:
- MS 3.1: SupervisorAgent (ExecutionPlan, planning, execution)
- MS 3.2: SpecialistAgent profiles + VerificationAgent
- MS 3.3: OutputPipeline (PII, toxicity, confidence gate, brand voice, length)
- MS 3.4: HandoffAgent (escalation detection, ticket management)
"""
import asyncio
import json
import time
import pytest
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ENVIRONMENT", "testing")


# ═══════════════════════════════════════════════════════════════════════════════
# MS 3.1: SupervisorAgent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecutionPlan:
    """Test ExecutionPlan data structures."""

    def test_step_status_enum(self):
        from app.agent.runtime.supervisor import StepStatus
        assert StepStatus.PENDING == "pending"
        assert StepStatus.COMPLETED == "completed"
        assert StepStatus.FAILED == "failed"
        assert StepStatus.RUNNING == "running"
        assert StepStatus.SKIPPED == "skipped"

    def test_step_type_enum(self):
        from app.agent.runtime.supervisor import StepType
        assert StepType.TOOL_CALL == "tool_call"
        assert StepType.SPECIALIST == "specialist"
        assert StepType.VERIFICATION == "verification"
        assert StepType.HANDOFF == "handoff"
        assert StepType.SYNTHESIS == "synthesis"

    def test_execution_step_creation(self):
        from app.agent.runtime.supervisor import ExecutionStep, StepType, StepStatus
        step = ExecutionStep(
            id=0,
            type=StepType.TOOL_CALL,
            description="Test step",
            target="test_tool",
            parameters={"key": "value"},
        )
        assert step.id == 0
        assert step.type == StepType.TOOL_CALL
        assert step.status == StepStatus.PENDING
        assert step.confidence == 1.0
        assert step.depends_on == []

    def test_execution_plan_creation(self):
        from app.agent.runtime.supervisor import ExecutionPlan, ExecutionStep, StepType
        plan = ExecutionPlan(
            goal="Test goal",
            steps=[
                ExecutionStep(id=0, type=StepType.SPECIALIST, description="Step 1", target="booking"),
                ExecutionStep(id=1, type=StepType.SYNTHESIS, description="Step 2", target="synthesis"),
            ],
        )
        assert plan.goal == "Test goal"
        assert len(plan.steps) == 2
        assert len(plan.pending_steps) == 2
        assert len(plan.completed_steps) == 0
        assert not plan.completed

    def test_execution_plan_get_next_step(self):
        from app.agent.runtime.supervisor import ExecutionPlan, ExecutionStep, StepType, StepStatus
        plan = ExecutionPlan(
            goal="Test",
            steps=[
                ExecutionStep(id=0, type=StepType.TOOL_CALL, description="First", target="tool1"),
                ExecutionStep(id=1, type=StepType.SPECIALIST, description="Second", target="spec1", depends_on=[0]),
            ],
        )
        # First step should be returned (no deps)
        next_step = plan.get_next_step()
        assert next_step is not None
        assert next_step.id == 0

        # Mark first as completed
        plan.steps[0].status = StepStatus.COMPLETED
        next_step = plan.get_next_step()
        assert next_step is not None
        assert next_step.id == 1

    def test_execution_plan_dependency_blocking(self):
        from app.agent.runtime.supervisor import ExecutionPlan, ExecutionStep, StepType
        plan = ExecutionPlan(
            goal="Test",
            steps=[
                ExecutionStep(id=0, type=StepType.TOOL_CALL, description="First", target="tool1"),
                ExecutionStep(id=1, type=StepType.SPECIALIST, description="Second", target="spec1", depends_on=[0]),
            ],
        )
        # Step 1 depends on step 0, which is still pending
        # get_next_step should return step 0 (not step 1)
        next_step = plan.get_next_step()
        assert next_step.id == 0

    def test_execution_plan_summary(self):
        from app.agent.runtime.supervisor import ExecutionPlan, ExecutionStep, StepType, StepStatus
        plan = ExecutionPlan(
            goal="Test goal",
            steps=[
                ExecutionStep(id=0, type=StepType.TOOL_CALL, description="Do something", target="tool1"),
            ],
        )
        summary = plan.to_summary()
        assert "Test goal" in summary
        assert "Do something" in summary

    def test_plan_completed_and_failed_steps(self):
        from app.agent.runtime.supervisor import ExecutionPlan, ExecutionStep, StepType, StepStatus
        plan = ExecutionPlan(
            goal="Test",
            steps=[
                ExecutionStep(id=0, type=StepType.TOOL_CALL, description="A", target="t1"),
                ExecutionStep(id=1, type=StepType.SPECIALIST, description="B", target="s1"),
                ExecutionStep(id=2, type=StepType.SYNTHESIS, description="C", target="syn"),
            ],
        )
        plan.steps[0].status = StepStatus.COMPLETED
        plan.steps[1].status = StepStatus.FAILED
        plan.steps[1].error = "Test error"

        assert len(plan.completed_steps) == 1
        assert len(plan.failed_steps) == 1
        assert len(plan.pending_steps) == 1


class TestSupervisorAgent:
    """Test SupervisorAgent core functionality."""

    def test_supervisor_creation(self):
        from app.agent.runtime.supervisor import SupervisorAgent
        from unittest.mock import MagicMock
        llm = MagicMock()
        supervisor = SupervisorAgent(llm=llm, specialists={"booking": {"description": "Test"}})
        assert supervisor.name == "supervisor"
        assert supervisor.get_current_plan() is None

    def test_supervisor_register_specialist(self):
        from app.agent.runtime.supervisor import SupervisorAgent
        from unittest.mock import MagicMock
        llm = MagicMock()
        supervisor = SupervisorAgent(llm=llm)
        supervisor.register_specialist("test", {"description": "Test specialist"})
        assert "test" in supervisor._specialists

    def test_supervisor_register_tool(self):
        from app.agent.runtime.supervisor import SupervisorAgent
        from unittest.mock import MagicMock
        llm = MagicMock()
        supervisor = SupervisorAgent(llm=llm)
        supervisor.register_tool("test_tool", lambda: "result")
        assert "test_tool" in supervisor._tools

    def test_parse_plan_json(self):
        from app.agent.runtime.supervisor import SupervisorAgent
        from unittest.mock import MagicMock
        supervisor = SupervisorAgent(llm=MagicMock())

        # Test with plain JSON
        data = supervisor._parse_plan_json('{"goal": "test", "steps": []}')
        assert data["goal"] == "test"

        # Test with markdown code block
        data = supervisor._parse_plan_json('```json\n{"goal": "test2", "steps": []}\n```')
        assert data["goal"] == "test2"

    def test_build_plan(self):
        from app.agent.runtime.supervisor import SupervisorAgent, StepType
        from unittest.mock import MagicMock
        supervisor = SupervisorAgent(llm=MagicMock())

        plan_data = {
            "goal": "Kurs buchen",
            "steps": [
                {"id": 0, "type": "tool_call", "description": "Kursplan abrufen", "target": "get_schedule", "confidence": 0.9},
                {"id": 1, "type": "synthesis", "description": "Antwort erstellen", "target": "synthesis", "depends_on": [0]},
            ],
        }
        plan = supervisor._build_plan(plan_data)
        assert plan.goal == "Kurs buchen"
        assert len(plan.steps) == 2
        assert plan.steps[0].type == StepType.TOOL_CALL
        assert plan.steps[1].type == StepType.SYNTHESIS
        assert plan.steps[0].confidence == 0.9

    def test_build_plan_with_clarification(self):
        from app.agent.runtime.supervisor import SupervisorAgent
        from unittest.mock import MagicMock
        supervisor = SupervisorAgent(llm=MagicMock())

        plan_data = {
            "goal": "Unklar",
            "steps": [
                {"id": 0, "type": "clarification", "description": "Welchen Kurs?", "target": "clarify", "parameters": {"question": "Welchen Kurs möchten Sie buchen?"}},
            ],
        }
        plan = supervisor._build_plan(plan_data)
        assert plan.requires_clarification is True
        assert "Welchen Kurs" in plan.clarification_question

    def test_max_plan_steps_limit(self):
        from app.agent.runtime.supervisor import SupervisorAgent, MAX_PLAN_STEPS
        from unittest.mock import MagicMock
        supervisor = SupervisorAgent(llm=MagicMock())

        plan_data = {
            "goal": "Too many steps",
            "steps": [
                {"id": i, "type": "tool_call", "description": f"Step {i}", "target": f"tool{i}"}
                for i in range(20)
            ],
        }
        plan = supervisor._build_plan(plan_data)
        assert len(plan.steps) <= MAX_PLAN_STEPS


# ═══════════════════════════════════════════════════════════════════════════════
# MS 3.2: SpecialistAgent + VerificationAgent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpecialistProfiles:
    """Test specialist profile definitions."""

    def test_default_profiles_exist(self):
        from app.agent.specialists.profiles import DEFAULT_PROFILES
        assert "booking" in DEFAULT_PROFILES
        assert "contract" in DEFAULT_PROFILES
        assert "health" in DEFAULT_PROFILES
        assert "general" in DEFAULT_PROFILES

    def test_profile_attributes(self):
        from app.agent.specialists.profiles import BOOKING_SPECIALIST
        assert BOOKING_SPECIALIST.name == "booking"
        assert BOOKING_SPECIALIST.domain == "booking"
        assert len(BOOKING_SPECIALIST.capabilities) > 0
        assert len(BOOKING_SPECIALIST.constraints) > 0
        assert len(BOOKING_SPECIALIST.requires_confirmation_for) > 0
        assert BOOKING_SPECIALIST.temperature > 0

    def test_health_specialist_has_disclaimer(self):
        from app.agent.specialists.profiles import HEALTH_SPECIALIST
        assert "Disclaimer" in HEALTH_SPECIALIST.system_prompt or "disclaimer" in HEALTH_SPECIALIST.system_prompt.lower()
        assert "kein Arzt" in HEALTH_SPECIALIST.system_prompt

    def test_contract_specialist_confirmation(self):
        from app.agent.specialists.profiles import CONTRACT_SPECIALIST
        assert "kündigen" in CONTRACT_SPECIALIST.requires_confirmation_for

    def test_get_profile(self):
        from app.agent.specialists.profiles import get_profile
        profile = get_profile("booking")
        assert profile is not None
        assert profile.name == "booking"

        assert get_profile("nonexistent") is None

    def test_get_specialist_descriptions(self):
        from app.agent.specialists.profiles import get_specialist_descriptions
        descs = get_specialist_descriptions()
        assert len(descs) == 4
        assert "booking" in descs
        assert isinstance(descs["booking"], str)

    def test_profile_to_dict(self):
        from app.agent.specialists.profiles import BOOKING_SPECIALIST
        d = BOOKING_SPECIALIST.to_dict()
        assert d["name"] == "booking"
        assert "capabilities" in d
        assert "constraints" in d


class TestSpecialistAgent:
    """Test SpecialistAgent functionality."""

    def test_specialist_creation(self):
        from app.agent.specialists.base_specialist import SpecialistAgent, SpecialistProfile
        from unittest.mock import MagicMock
        profile = SpecialistProfile(
            name="test", display_name="Test", description="Test specialist",
            system_prompt="You are a test.", domain="test",
        )
        agent = SpecialistAgent(profile=profile, llm=MagicMock())
        assert agent.name == "test"
        assert agent.domain == "test"
        assert agent.description == "Test specialist"

    def test_specialist_builds_messages(self):
        from app.agent.specialists.base_specialist import SpecialistAgent, SpecialistProfile
        from unittest.mock import MagicMock
        profile = SpecialistProfile(
            name="test", display_name="Test", description="Test",
            system_prompt="System prompt", domain="test",
            constraints=["No bad things"],
        )
        agent = SpecialistAgent(profile=profile, llm=MagicMock())
        messages = agent._build_messages(
            "Test query",
            context={"member_name": "Max"},
            chat_history=[{"role": "user", "content": "Hi"}],
        )
        assert messages[0]["role"] == "system"
        assert "System prompt" in messages[0]["content"]
        assert "Max" in messages[0]["content"]
        assert "No bad things" in messages[0]["content"]
        assert len(messages) >= 3  # system + history + query

    def test_specialist_confirmation_check(self):
        from app.agent.specialists.base_specialist import SpecialistAgent, SpecialistProfile
        from unittest.mock import MagicMock
        profile = SpecialistProfile(
            name="test", display_name="Test", description="Test",
            system_prompt="Test", domain="test",
            requires_confirmation_for=["stornieren", "buchen"],
        )
        agent = SpecialistAgent(profile=profile, llm=MagicMock())
        assert agent._check_confirmation_required("Ich möchte stornieren") is True
        assert agent._check_confirmation_required("Wie ist das Wetter?") is False


class TestVerificationAgent:
    """Test VerificationAgent functionality."""

    def test_checklists_exist(self):
        from app.agent.specialists.verification_agent import CHECKLISTS
        assert "cancellation" in CHECKLISTS
        assert "booking" in CHECKLISTS
        assert "data_change" in CHECKLISTS
        assert "default" in CHECKLISTS

    def test_cancellation_checklist_items(self):
        from app.agent.specialists.verification_agent import CANCELLATION_CHECKLIST
        assert len(CANCELLATION_CHECKLIST) >= 4
        assert any("bestätigt" in item.lower() for item in CANCELLATION_CHECKLIST)
        assert any("kündigungsfrist" in item.lower() for item in CANCELLATION_CHECKLIST)

    def test_verification_result_creation(self):
        from app.agent.specialists.verification_agent import VerificationResult
        result = VerificationResult(
            passed=True,
            issues=[],
            summary="All checks passed",
            confidence=0.95,
        )
        assert result.passed is True
        assert result.confidence == 0.95
        d = result.to_dict()
        assert d["passed"] is True

    def test_verification_result_failed(self):
        from app.agent.specialists.verification_agent import VerificationResult
        result = VerificationResult(
            passed=False,
            issues=["Missing confirmation", "No date specified"],
            summary="Checks failed",
            confidence=0.8,
        )
        assert result.passed is False
        assert len(result.issues) == 2

    def test_verification_agent_creation(self):
        from app.agent.specialists.verification_agent import VerificationAgent
        from unittest.mock import MagicMock
        agent = VerificationAgent(llm=MagicMock())
        assert agent is not None

    def test_parse_verification_response_valid(self):
        from app.agent.specialists.verification_agent import VerificationAgent
        from unittest.mock import MagicMock
        agent = VerificationAgent(llm=MagicMock())
        response = json.dumps({
            "passed": True,
            "issues": [],
            "summary": "All good",
            "confidence": 0.9,
            "checklist_results": {"Check 1": True},
        })
        result = agent._parse_verification_response(response, ["Check 1"])
        assert result.passed is True
        assert result.confidence == 0.9

    def test_parse_verification_response_invalid(self):
        from app.agent.specialists.verification_agent import VerificationAgent
        from unittest.mock import MagicMock
        agent = VerificationAgent(llm=MagicMock())
        result = agent._parse_verification_response("not json at all", ["Check 1"])
        assert result.passed is False  # Conservative fallback


# ═══════════════════════════════════════════════════════════════════════════════
# MS 3.3: OutputPipeline Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestOutputPipeline:
    """Test OutputPipeline stages."""

    def _make_response(self, content: str, confidence: float = 0.9):
        from app.swarm.base import AgentResponse
        return AgentResponse(content=content, confidence=confidence)

    def test_pipeline_creation(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline()
        assert pipeline is not None

        config = PipelineConfig(pii_filter_enabled=False)
        pipeline2 = OutputPipeline(config=config)
        assert pipeline2._config.pii_filter_enabled is False

    def test_pii_filter_iban(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(
            brand_voice_enabled=False, toxicity_check_enabled=False,
            confidence_gate_enabled=False, length_guard_enabled=False,
        ))
        response = self._make_response("Ihre IBAN: DE89370400440532013000")
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert "IBAN-REDACTED" in result.content
        assert result.pii_detected is True
        assert result.pii_redacted_count >= 1

    def test_pii_filter_credit_card(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(
            brand_voice_enabled=False, toxicity_check_enabled=False,
            confidence_gate_enabled=False, length_guard_enabled=False,
        ))
        response = self._make_response("Karte: 4111-1111-1111-1111")
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert "KARTE-REDACTED" in result.content

    def test_pii_filter_email_not_redacted_by_default(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(
            pii_redact_emails=False,
            brand_voice_enabled=False, toxicity_check_enabled=False,
            confidence_gate_enabled=False, length_guard_enabled=False,
        ))
        response = self._make_response("Kontakt: test@example.com")
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert "test@example.com" in result.content  # Not redacted by default

    def test_pii_filter_email_redacted_when_enabled(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(
            pii_redact_emails=True,
            brand_voice_enabled=False, toxicity_check_enabled=False,
            confidence_gate_enabled=False, length_guard_enabled=False,
        ))
        response = self._make_response("Kontakt: test@example.com")
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert "EMAIL-REDACTED" in result.content

    def test_toxicity_blocks_harmful_content(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(
            pii_filter_enabled=False, brand_voice_enabled=False,
            confidence_gate_enabled=False, length_guard_enabled=False,
        ))
        response = self._make_response("Du bist ein Arschloch!")
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert result.toxicity_blocked is True
        assert "Nutzungsrichtlinien" in result.content

    def test_toxicity_passes_clean_content(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(
            pii_filter_enabled=False, brand_voice_enabled=False,
            confidence_gate_enabled=False, length_guard_enabled=False,
        ))
        response = self._make_response("Guten Tag, wie kann ich helfen?")
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert result.toxicity_blocked is False

    def test_confidence_gate_low_confidence(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(
            pii_filter_enabled=False, brand_voice_enabled=False,
            toxicity_check_enabled=False, length_guard_enabled=False,
            confidence_threshold=0.6,
        ))
        response = self._make_response("Vielleicht ist es so...", confidence=0.3)
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert result.confidence_gate_triggered is True
        assert "Hinweis" in result.content

    def test_confidence_gate_high_confidence(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(
            pii_filter_enabled=False, brand_voice_enabled=False,
            toxicity_check_enabled=False, length_guard_enabled=False,
        ))
        response = self._make_response("Der Kurs ist um 10 Uhr.", confidence=0.95)
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert result.confidence_gate_triggered is False

    def test_brand_voice_formal(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(
            pii_filter_enabled=False, toxicity_check_enabled=False,
            confidence_gate_enabled=False, length_guard_enabled=False,
            brand_voice_style="formal",
        ))
        response = self._make_response("Hey! Wie geht's?")
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert "Guten Tag" in result.content

    def test_length_guard_truncation(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(
            pii_filter_enabled=False, toxicity_check_enabled=False,
            confidence_gate_enabled=False, brand_voice_enabled=False,
            max_length=100,
        ))
        long_text = "Dies ist ein sehr langer Text. " * 50
        response = self._make_response(long_text)
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert len(result.content) < len(long_text)
        assert "gekürzt" in result.content

    def test_length_guard_padding_short(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(
            pii_filter_enabled=False, toxicity_check_enabled=False,
            confidence_gate_enabled=False, brand_voice_enabled=False,
            min_length=50,
        ))
        response = self._make_response("OK.")
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert "helfen" in result.content

    def test_pipeline_result_to_dict(self):
        from app.agent.runtime.output_pipeline import PipelineResult, PipelineAction
        result = PipelineResult(
            content="Test", original_content="Test",
            action=PipelineAction.PASS,
        )
        d = result.to_dict()
        assert d["action"] == "pass"
        assert d["was_modified"] is False

    def test_tenant_config_override(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig(confidence_threshold=0.6))
        config = pipeline._apply_tenant_config({"confidence_threshold": 0.8})
        assert config.confidence_threshold == 0.8

    def test_full_pipeline_pass_through(self):
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        pipeline = OutputPipeline(PipelineConfig())
        response = self._make_response(
            "Ihr nächster Kurs ist Yoga am Montag um 10:00 Uhr. Viel Spaß!",
            confidence=0.95,
        )
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert "Yoga" in result.content
        assert result.toxicity_blocked is False


# ═══════════════════════════════════════════════════════════════════════════════
# MS 3.4: HandoffAgent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestEscalationDetector:
    """Test escalation detection logic."""

    def test_detect_human_request(self):
        from app.agent.runtime.handoff import EscalationDetector, HandoffReason
        detector = EscalationDetector()
        result = detector.detect("Ich möchte mit einem Mitarbeiter sprechen")
        assert result is not None
        assert result[0] == HandoffReason.USER_REQUEST

    def test_detect_legal_matter(self):
        from app.agent.runtime.handoff import EscalationDetector, HandoffReason
        detector = EscalationDetector()
        result = detector.detect("Ich werde meinen Anwalt einschalten")
        assert result is not None
        assert result[0] == HandoffReason.LEGAL_MATTER

    def test_detect_complaint(self):
        from app.agent.runtime.handoff import EscalationDetector, HandoffReason
        detector = EscalationDetector()
        result = detector.detect("Ich möchte eine Beschwerde einreichen")
        assert result is not None
        assert result[0] == HandoffReason.COMPLAINT

    def test_detect_low_confidence(self):
        from app.agent.runtime.handoff import EscalationDetector, HandoffReason
        detector = EscalationDetector()
        result = detector.detect("Normale Frage", confidence=0.2)
        assert result is not None
        assert result[0] == HandoffReason.LOW_CONFIDENCE

    def test_detect_repeated_failure(self):
        from app.agent.runtime.handoff import EscalationDetector, HandoffReason
        detector = EscalationDetector()
        result = detector.detect("Normale Frage", failure_count=3)
        assert result is not None
        assert result[0] == HandoffReason.REPEATED_FAILURE

    def test_no_escalation_normal_message(self):
        from app.agent.runtime.handoff import EscalationDetector
        detector = EscalationDetector()
        result = detector.detect("Wann ist der nächste Yoga-Kurs?", confidence=0.9)
        assert result is None

    def test_priority_levels(self):
        from app.agent.runtime.handoff import EscalationDetector, HandoffPriority
        detector = EscalationDetector()
        # Legal = URGENT
        _, priority = detector.detect("Mein Anwalt wird sich melden")
        assert priority == HandoffPriority.URGENT
        # Human request = HIGH
        _, priority = detector.detect("Ich will mit einem Menschen reden")
        assert priority == HandoffPriority.HIGH


class TestHandoffManager:
    """Test HandoffManager ticket management."""

    def test_handoff_manager_creation(self):
        from app.agent.runtime.handoff import HandoffManager
        manager = HandoffManager()
        assert manager is not None

    def test_check_escalation(self):
        from app.agent.runtime.handoff import HandoffManager
        manager = HandoffManager()
        result = manager.check_escalation("Ich will einen Mitarbeiter")
        assert result is not None
        result = manager.check_escalation("Wann ist Yoga?")
        assert result is None

    def test_create_handoff_ticket(self):
        from app.agent.runtime.handoff import HandoffManager, HandoffStatus
        manager = HandoffManager()
        ticket = asyncio.get_event_loop().run_until_complete(
            manager.create_handoff(
                tenant_id=1,
                user_id="user123",
                reason="user_request",
                context="User wants human support",
                priority="high",
            )
        )
        assert ticket["ticket_id"].startswith("HO-")
        assert ticket["tenant_id"] == 1
        assert ticket["user_id"] == "user123"
        assert ticket["status"] == HandoffStatus.PENDING.value

    def test_get_user_message(self):
        from app.agent.runtime.handoff import HandoffManager, HandoffReason, HandoffPriority
        manager = HandoffManager()
        msg = manager.get_user_message(
            HandoffReason.USER_REQUEST, HandoffPriority.HIGH, "HO-12345678"
        )
        assert "Mitarbeiter" in msg
        assert "HO-12345678" in msg

    def test_get_user_message_complaint(self):
        from app.agent.runtime.handoff import HandoffManager, HandoffReason, HandoffPriority
        manager = HandoffManager()
        msg = manager.get_user_message(
            HandoffReason.COMPLAINT, HandoffPriority.HIGH, "HO-ABC"
        )
        assert "tut mir leid" in msg.lower() or "unzufrieden" in msg.lower()

    def test_get_pending_tickets(self):
        from app.agent.runtime.handoff import HandoffManager
        manager = HandoffManager()
        asyncio.get_event_loop().run_until_complete(
            manager.create_handoff(tenant_id=1, user_id="u1", reason="user_request")
        )
        asyncio.get_event_loop().run_until_complete(
            manager.create_handoff(tenant_id=2, user_id="u2", reason="complaint")
        )
        all_pending = manager.get_pending_tickets()
        assert len(all_pending) >= 2

        tenant1_pending = manager.get_pending_tickets(tenant_id=1)
        assert all(t.tenant_id == 1 for t in tenant1_pending)

    def test_resolve_ticket(self):
        from app.agent.runtime.handoff import HandoffManager, HandoffStatus
        manager = HandoffManager()
        ticket = asyncio.get_event_loop().run_until_complete(
            manager.create_handoff(tenant_id=1, user_id="u1", reason="user_request")
        )
        resolved = asyncio.get_event_loop().run_until_complete(
            manager.resolve_ticket(ticket["ticket_id"], resolution="Solved", resolved_by="admin")
        )
        assert resolved is not None
        assert resolved.status == HandoffStatus.RESOLVED
        assert resolved.resolved_at is not None

    def test_close_ticket(self):
        from app.agent.runtime.handoff import HandoffManager, HandoffStatus
        manager = HandoffManager()
        ticket = asyncio.get_event_loop().run_until_complete(
            manager.create_handoff(tenant_id=1, user_id="u1", reason="user_request")
        )
        closed = asyncio.get_event_loop().run_until_complete(
            manager.close_ticket(ticket["ticket_id"])
        )
        assert closed is not None
        assert closed.status == HandoffStatus.CLOSED

    def test_handoff_enums(self):
        from app.agent.runtime.handoff import HandoffPriority, HandoffReason, HandoffStatus
        assert HandoffPriority.URGENT == "urgent"
        assert HandoffReason.LEGAL_MATTER == "legal_matter"
        assert HandoffStatus.PENDING == "pending"

    def test_ticket_to_dict(self):
        from app.agent.runtime.handoff import HandoffTicket, HandoffReason, HandoffPriority, HandoffStatus
        ticket = HandoffTicket(
            ticket_id="HO-TEST",
            tenant_id=1,
            user_id="u1",
            reason=HandoffReason.USER_REQUEST,
            priority=HandoffPriority.HIGH,
        )
        d = ticket.to_dict()
        assert d["ticket_id"] == "HO-TEST"
        assert d["reason"] == "user_request"
        assert d["priority"] == "high"


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase3Integration:
    """Integration tests across Phase 3 modules."""

    def test_supervisor_with_specialist_profiles(self):
        """Test that SupervisorAgent can load specialist profiles."""
        from app.agent.runtime.supervisor import SupervisorAgent
        from app.agent.specialists.profiles import get_specialist_descriptions
        from unittest.mock import MagicMock

        descriptions = get_specialist_descriptions()
        supervisor = SupervisorAgent(
            llm=MagicMock(),
            specialists={name: {"description": desc} for name, desc in descriptions.items()},
        )
        assert len(supervisor._specialists) == 4

    def test_pipeline_with_pii_and_toxicity(self):
        """Test pipeline handles PII and toxicity together."""
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig
        from app.swarm.base import AgentResponse

        pipeline = OutputPipeline(PipelineConfig(
            confidence_gate_enabled=False, brand_voice_enabled=False,
            length_guard_enabled=False,
        ))
        # Clean content with IBAN
        response = AgentResponse(content="Ihre IBAN: DE89370400440532013000. Alles klar!", confidence=0.9)
        result = asyncio.get_event_loop().run_until_complete(pipeline.process(response))
        assert result.pii_detected is True
        assert result.toxicity_blocked is False

    def test_handoff_with_escalation_detection(self):
        """Test full flow: detect escalation → create ticket → get message."""
        from app.agent.runtime.handoff import HandoffManager

        manager = HandoffManager()
        escalation = manager.check_escalation("Ich will meinen Anwalt einschalten!")
        assert escalation is not None

        reason, priority = escalation
        ticket = asyncio.get_event_loop().run_until_complete(
            manager.create_handoff(
                tenant_id=1, user_id="angry_user",
                reason=reason, priority=priority,
                context="User threatened legal action",
            )
        )
        msg = manager.get_user_message(reason, priority, ticket["ticket_id"])
        assert ticket["ticket_id"] in msg

    def test_all_modules_importable(self):
        """Verify all Phase 3 modules can be imported."""
        from app.agent.runtime.supervisor import SupervisorAgent, ExecutionPlan, ExecutionStep
        from app.agent.specialists.base_specialist import SpecialistAgent, SpecialistProfile
        from app.agent.specialists.profiles import DEFAULT_PROFILES, get_profile
        from app.agent.specialists.verification_agent import VerificationAgent, VerificationResult
        from app.agent.runtime.output_pipeline import OutputPipeline, PipelineConfig, PipelineResult
        from app.agent.runtime.handoff import HandoffManager, EscalationDetector, HandoffTicket
        assert True  # If we got here, all imports work


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
