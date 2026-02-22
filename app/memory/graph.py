"""ARNI v1.4 – GraphRAG Knowledge Graph.

@BACKEND: Sprint 4, Task 4.6
In-memory NetworkX graph for member fact relationships.
"""

import networkx as nx
import structlog

logger = structlog.get_logger()


class FactGraph:
    """In-memory knowledge graph using NetworkX.

    Stores member facts as nodes and relationships as edges.
    """

    def __init__(self) -> None:
        self._graph = nx.DiGraph()

    def add_fact(self, user_id: str, relation: str, entity: str) -> None:
        """Add a fact to the knowledge graph.

        Creates: (Member:user_id) --[relation]--> (Entity:entity)

        Args:
            user_id: Member identifier (source node).
            relation: Relationship type (e.g. HAS_INJURY, TRAINS, PREFERS).
            entity: Target entity (e.g. 'Knie', 'Yoga', '18:00').
        """
        member_node = f"member:{user_id}"
        entity_node = f"entity:{entity.lower()}"

        self._graph.add_node(member_node, type="member", id=user_id)
        self._graph.add_node(entity_node, type="entity", label=entity)
        self._graph.add_edge(member_node, entity_node, relation=relation)

        logger.debug(
            "graph.fact_added",
            user_id=user_id,
            relation=relation,
            entity=entity,
        )

    def query_user(self, user_id: str) -> list[dict[str, str]]:
        """Get all facts for a user from the graph.

        Args:
            user_id: Member identifier.

        Returns:
            List of {relation, entity} dicts.
        """
        member_node = f"member:{user_id}"
        if member_node not in self._graph:
            return []

        facts = []
        for _, target, data in self._graph.out_edges(member_node, data=True):
            entity_data = self._graph.nodes.get(target, {})
            facts.append({
                "relation": data.get("relation", "unknown"),
                "entity": entity_data.get("label", target),
            })
        return facts

    def remove_user(self, user_id: str) -> bool:
        """Remove all nodes and edges for a user (GDPR Art. 17).

        Returns:
            True if user existed in graph.
        """
        member_node = f"member:{user_id}"
        if member_node not in self._graph:
            return False

        # Remove connected entity nodes that are only linked to this user
        edges = list(self._graph.out_edges(member_node))
        for _, target in edges:
            if self._graph.in_degree(target) <= 1:
                self._graph.remove_node(target)

        self._graph.remove_node(member_node)
        logger.info("graph.user_removed", user_id=user_id)
        return True

    def get_stats(self) -> dict[str, int]:
        """Get graph statistics."""
        return {
            "nodes": self._graph.number_of_nodes(),
            "edges": self._graph.number_of_edges(),
            "members": sum(
                1 for _, d in self._graph.nodes(data=True)
                if d.get("type") == "member"
            ),
        }
