"""Shared serialization helpers for v2 state objects."""

from __future__ import annotations

import dataclasses
from typing import Any

from pydantic import BaseModel


def serialize(obj: Any) -> Any:
    """Convert dataclasses and pydantic models into plain JSON-safe structures."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    if isinstance(obj, dict):
        return {key: serialize(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [serialize(item) for item in obj]
    return obj


def deserialize_tree(payload: dict[str, Any]):
    """Rebuild IdeaTree from serialized payload."""
    from hypo_gpt.models import IdeaTree

    return IdeaTree.model_validate(payload)


def serialize_flow(flow: Any) -> str:
    """Compact flow serialization for prompt context."""
    if flow is None:
        return ""

    query = getattr(flow, "query", "")
    nodes = getattr(flow, "nodes", {})
    lines = [f"query: {query}", f"nodes ({len(nodes)} total):"]
    for node in nodes.values():
        node_id = getattr(node, "node_id", "")
        task_type = getattr(getattr(node, "task_type", None), "value", getattr(node, "task_type", ""))
        state = getattr(getattr(node, "state", None), "value", getattr(node, "state", ""))
        description = getattr(node, "description", "")
        lines.append(f"  {node_id} [{state}] {task_type}: {description[:100]}")
    return "\n".join(lines)
