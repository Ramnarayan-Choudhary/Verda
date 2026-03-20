from __future__ import annotations

import numpy as np

from hypo_gpt.models import IdeaTree, IdeaTreeNode


def get_frontier(tree: IdeaTree, min_score: float = 0.4) -> list[IdeaTreeNode]:
    out: list[IdeaTreeNode] = []
    for node in tree.nodes.values():
        if node.child_ids:
            continue
        if node.is_pruned:
            continue
        if node.hypothesis.composite_score < min_score:
            continue
        out.append(node)
    return out


def get_failed_nodes(tree: IdeaTree) -> list[IdeaTreeNode]:
    out: list[IdeaTreeNode] = []
    for node in tree.nodes.values():
        if node.metric_delta is not None and node.metric_delta < 0:
            out.append(node)
        elif node.hypothesis.composite_score < 0.35:
            out.append(node)
    return out


def semantic_novelty_guard(tree: IdeaTree, candidate_embedding: np.ndarray, threshold: float = 0.85) -> bool:
    for node in tree.nodes.values():
        if not node.embedding:
            continue
        emb = np.asarray(node.embedding, dtype=np.float32)
        sim = float(np.dot(candidate_embedding, emb) / ((np.linalg.norm(candidate_embedding) * np.linalg.norm(emb)) + 1e-9))
        if sim > threshold:
            return False
    return True
