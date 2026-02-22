"""ARIIA v1.4 – Intent Definitions & Routing Table.

@BACKEND: Sprint 2, Task 2.3
Maps user intents to their corresponding Swarm Agents.
"""

from enum import Enum


class Intent(str, Enum):
    """User intent categories classified by the Router."""

    BOOKING = "booking"       # Schedule, reserve, check-in → Agent Ops
    SALES = "sales"           # Cancel, renew, contract, pricing → Agent Sales
    HEALTH = "health"         # Injury, pain, exercise advice → Agent Medic
    CROWD = "crowd"           # "Is it busy?", occupancy → Agent Vision
    SMALLTALK = "smalltalk"   # Greeting, chitchat, general → Persona Handler
    UNKNOWN = "unknown"       # Fallback if confidence too low


# Routing Table: Intent → Agent module name
ROUTING_TABLE: dict[Intent, str] = {
    Intent.BOOKING: "ops",
    Intent.SALES: "sales",
    Intent.HEALTH: "medic",
    Intent.CROWD: "vision",
    Intent.SMALLTALK: "persona",
}


