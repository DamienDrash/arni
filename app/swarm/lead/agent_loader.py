"""Re-export get_agent_loader for convenience within the lead package."""

from app.swarm.registry.dynamic_loader import get_agent_loader

__all__ = ["get_agent_loader"]
