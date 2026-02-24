"""ARIIA Project Titan – Master Orchestrator.

@ARCH: Orchestrator-Worker Architecture
The MasterAgent is the only one talking to the user. It delegates tasks 
to specialized sub-agents and synthesizes the final response.
"""

import json
import structlog
from typing import List, Optional

from app.gateway.schemas import InboundMessage
from app.gateway.persistence import persistence
from app.swarm.base import AgentResponse, BaseAgent, AgentHandoff
from app.swarm.router.intents import Intent
from app.swarm.llm import LLMClient

# Specialized sub-agents (now acting as workers)
from app.swarm.agents.medic import AgentMedic
from app.swarm.agents.ops import AgentOps
from app.swarm.agents.sales import AgentSales
from app.swarm.agents.persona import AgentPersona
from app.swarm.agents.vision import AgentVision

logger = structlog.get_logger()

MASTER_SYSTEM_PROMPT = """
Du bist Arnold Prime, der Chef-Koordinator und Head-Coach von ARIIA. 
Deine Persona: Arnold Schwarzenegger meets Berliner Fitness-Coach. Direkt, motivierend, loyal.

DEINE AUFGABE:
Löse das Anliegen des Nutzers exzellent. Du bist der einzige Agent, der direkt mit dem Nutzer spricht.
Du hast ein Team von Spezialisten (Workers), die dir zuarbeiten.

WORKERS:
1. 'ops': Spezialist für Buchungen, Kurse, Trainer und Check-ins.
2. 'sales': Spezialist für Verträge, Preise, Kündigungen und Upgrades.
3. 'medic': Spezialist für Gesundheit, Schmerzen und Verletzungen (mit Disclaimer).
4. 'vision': Spezialist für Auslastung und Kamera-Analysen.
5. 'persona': Dein 'innerer Arnold' für Smalltalk und allgemeine Lebensberatung.

PROTOKOLL:
1. ANALYSIERE den User-Input.
2. PLANUNG: Entscheide, welche Worker du brauchst. Du kannst mehrere nacheinander aufrufen.
3. TOOL-CALL: Rufe Worker mit 'TOOL: worker_name("query")' auf. Du kannst mehrere Tools in eine Antwort schreiben!
4. SYNTHESE: Erhalte die Daten der Worker und erstelle eine finale, motivierende Antwort im Arnold-Style.

WICHTIG:
- Wenn ein Nutzer sich beschwert, deeskaliere ZUERST emotional (Arnold-Style), bevor du Worker fragst.
- Behalte das Langzeitgedächtnis (Memory) immer im Blick.
- Deine Antwort muss sich anfühlen wie aus einem Guss.
"""

class MasterAgent(BaseAgent):
    """The central brain of ARIIA Titan."""

    def __init__(self, llm: LLMClient):
        self._llm = llm
        self._workers = {
            "ops": AgentOps(),
            "sales": AgentSales(),
            "medic": AgentMedic(),
            "vision": AgentVision(),
            "persona": AgentPersona()
        }

    @property
    def name(self) -> str:
        return "master"

    @property
    def description(self) -> str:
        return "Master Orchestrator – The central brain of the swarm."

    async def handle(self, message: InboundMessage) -> AgentResponse:
        """The Orchestration Loop (Thought -> Action -> Observation -> Final)."""
        logger.info("master.orchestration.started", message_id=message.message_id)
        
        messages = [
            {"role": "system", "content": MASTER_SYSTEM_PROMPT},
            {"role": "user", "content": message.content}
        ]
        
        max_turns = 5
        for turn in range(max_turns):
            response = await self._chat_with_messages(messages, tenant_id=message.tenant_id)
            if not response:
                return AgentResponse(content="Hoppla, mein Team braucht gerade etwas länger. Versuchs gleich nochmal!", confidence=0.5)

            # Check for Worker Tool Calls (Parallel support)
            tool_calls = self._parse_multiple_tool_calls(response)
            if not tool_calls:
                # Final synthesis reached
                return AgentResponse(content=response, confidence=1.0)
            
            observations = []
            for worker_name, worker_query in tool_calls:
                logger.info("master.worker_call", worker=worker_name, query=worker_query, turn=turn+1)
                
                # Execute Worker
                if worker_name in self._workers:
                    worker = self._workers[worker_name]
                    worker_msg = InboundMessage(
                        **message.model_dump(exclude={"content"}),
                        content=worker_query
                    )
                    worker_res = await worker.handle(worker_msg)
                    observations.append(f"OBSERVATION from {worker_name}: {worker_res.content}")
                else:
                    observations.append(f"Error: Worker '{worker_name}' not found.")

            # Feed all back to Master in one go
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "\n".join(observations)})

        return AgentResponse(content="Ich habe viele Infos gesammelt. Kurz gesagt: Wir kümmern uns drum! Frag mich gleich nach den Details.", confidence=0.5)

    def _parse_multiple_tool_calls(self, response: str) -> list[tuple[str, str]]:
        import re
        # Look for all matches of TOOL: worker_name("query")
        matches = re.findall(r"TOOL:\s*(\w+)\s*\(\"(.*?)\"\)", response, re.IGNORECASE | re.DOTALL)
        return [(m[0].lower(), m[1]) for m in matches]
