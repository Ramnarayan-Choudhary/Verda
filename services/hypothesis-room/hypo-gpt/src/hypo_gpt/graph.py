"""Lightweight graph topology metadata for the layered hypothesis pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphNode:
    name: str
    layer: str
    description: str


PIPELINE_NODES = [
    GraphNode("flow_search", "Layer 0", "Ingest and synthesize paper intelligence"),
    GraphNode("cartography", "Layer 1", "Build typed research space map"),
    GraphNode("memory_retrieve", "Layer 6", "Load positives/negatives from memory"),
    GraphNode("generate_round", "Layer 2", "Generate hypotheses across 7 strategies"),
    GraphNode("assess_parallel", "Layer 2", "Score novelty/feasibility/mechanism/executability"),
    GraphNode("mcgs_expand", "Layer 2", "Expand MCGS tree with operators and novelty guard"),
    GraphNode("tribunal", "Layer 3", "Run isolated 5-critic review"),
    GraphNode("panel_judge", "Layer 4", "Aggregate 3 independent judge perspectives"),
    GraphNode("portfolio", "Layer 5", "Fill risk-balanced portfolio with diversity constraints"),
    GraphNode("memory_store", "Layer 6", "Store successful and failed patterns"),
]


def describe_graph() -> list[dict[str, str]]:
    return [{"name": node.name, "layer": node.layer, "description": node.description} for node in PIPELINE_NODES]
