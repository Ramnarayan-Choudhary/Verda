"""
Lightweight knowledge graph utilities used for novelty checks and grounding.

The graph captures entities (methods, datasets, models) as nodes and relations
between them (citations, co-occurrences, failure modes). Inspired by the
knowledge-grounded generation techniques outlined in arXiv:2510.09901.

Entity extraction now uses a comprehensive domain-aware vocabulary instead of
just 4 regex patterns — covers 100+ ML/AI terms for accurate novelty checking.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from typing import Iterable

import networkx as nx
import structlog

from vreda_hypothesis.models import PaperMetadata, PaperSummary

logger = structlog.get_logger(__name__)


# Comprehensive entity vocabulary organized by category
_ENTITY_VOCAB: dict[str, list[str]] = {
    # Architectures & Methods
    "architecture": [
        "transformer", "attention", "self-attention", "cross-attention", "multi-head attention",
        "cnn", "convolution", "resnet", "vit", "vision transformer", "swin",
        "diffusion", "ddpm", "score matching", "flow matching",
        "gan", "vae", "autoencoder", "variational",
        "lstm", "gru", "rnn", "recurrent",
        "graph neural network", "gnn", "gcn", "gat",
        "mamba", "state space model", "ssm",
        "mixture of experts", "moe",
        "nerf", "gaussian splatting",
        "unet", "encoder-decoder",
    ],
    # Training techniques
    "training": [
        "fine-tuning", "fine-tune", "lora", "qlora", "adapter",
        "pretraining", "pre-training", "self-supervised",
        "contrastive learning", "clip", "siamese",
        "reinforcement learning", "rlhf", "ppo", "dpo",
        "distillation", "knowledge distillation", "pruning", "quantization",
        "curriculum learning", "meta-learning", "few-shot", "zero-shot",
        "transfer learning", "domain adaptation",
        "batch normalization", "layer normalization", "dropout",
        "gradient accumulation", "mixed precision",
    ],
    # Models
    "model": [
        "gpt", "gpt-2", "gpt-3", "gpt-4", "gpt-4o",
        "bert", "roberta", "deberta", "electra", "xlnet",
        "t5", "flan-t5", "bart", "pegasus",
        "llama", "llama-2", "llama-3", "mistral", "mixtral", "phi",
        "claude", "gemini", "palm", "chinchilla",
        "stable diffusion", "dall-e", "midjourney",
        "clip", "blip", "florence",
        "whisper", "wav2vec",
        "sam", "segment anything",
        "dino", "dinov2",
    ],
    # Datasets & Benchmarks
    "dataset": [
        "imagenet", "cifar", "cifar-10", "cifar-100", "mnist", "fashion-mnist",
        "coco", "voc", "ade20k", "cityscapes",
        "laion", "cc3m", "cc12m", "datacomp",
        "squad", "glue", "superglue", "mmlu", "hellaswag",
        "wikitext", "c4", "the pile", "redpajama", "slimpajama",
        "humaneval", "mbpp", "gsm8k", "math",
        "librispeech", "commonvoice",
        "webvid", "howto100m",
    ],
    # Metrics
    "metric": [
        "accuracy", "precision", "recall", "f1", "f1-score",
        "bleu", "rouge", "meteor", "bertscore",
        "perplexity", "cross-entropy", "bce",
        "fid", "inception score", "clip score",
        "map", "iou", "dice",
        "auc", "roc",
        "psnr", "ssim", "lpips",
        "elo", "win rate",
        "flops", "throughput", "latency",
    ],
    # Concepts & Phenomena
    "concept": [
        "scaling law", "emergence", "in-context learning",
        "hallucination", "catastrophic forgetting", "mode collapse",
        "overfitting", "underfitting", "generalization",
        "interpretability", "explainability", "mechanistic interpretability",
        "alignment", "safety", "robustness", "adversarial",
        "multimodal", "cross-modal", "multi-task",
        "chain-of-thought", "reasoning", "tool use",
        "retrieval augmented generation", "rag",
        "tokenization", "embedding", "positional encoding",
        "attention sink", "kv cache", "flash attention",
        "sparsity", "efficiency", "compression",
        "bottleneck", "limitation", "failure",
    ],
}

# Flatten and compile patterns (case-insensitive, word-boundary)
_COMPILED_PATTERNS: list[tuple[str, re.Pattern]] = []
for _category, _terms in _ENTITY_VOCAB.items():
    for _term in _terms:
        # Escape regex special characters, match word boundaries
        pattern = re.compile(r"\b" + re.escape(_term) + r"\b", re.IGNORECASE)
        _COMPILED_PATTERNS.append((_term.lower(), pattern))


def _extract_entities(text: str) -> list[str]:
    """Extract scientific entities from text using domain vocabulary."""
    if not text:
        return []

    entities: set[str] = set()
    for canonical_name, pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            entities.add(canonical_name)

    return sorted(entities)


@dataclass
class NoveltySignal:
    """Structured novelty signal returned to filtering and critics."""

    overlap_ratio: float
    related_entities: list[str] = field(default_factory=list)
    supporting_papers: list[str] = field(default_factory=list)


class PaperKnowledgeGraph:
    """NetworkX-backed graph used for novelty checks and grounding."""

    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()
        self.primary_id: str | None = None

    def add_paper(self, metadata: PaperMetadata, summary: PaperSummary | None = None, source: str = "primary") -> None:
        """Add a paper node plus entity annotations."""
        node_id = metadata.arxiv_id or metadata.semantic_scholar_id or metadata.title
        if not node_id:
            logger.warning("knowledge_graph.missing_id", title=metadata.title)
            return

        entities = _extract_entities(metadata.abstract)
        if summary:
            entities.extend(_extract_entities(" ".join(summary.methods + summary.datasets + summary.limitations)))

        attributes = {
            "title": metadata.title,
            "year": metadata.year,
            "authors": metadata.authors,
            "source": source,
            "entities": sorted(set(entities)),
            "citation_count": metadata.citation_count,
        }
        self.graph.add_node(node_id, **attributes)
        if source == "primary":
            self.primary_id = node_id
        logger.debug("knowledge_graph.paper_added", node=node_id, entities=len(attributes["entities"]))

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        evidence: str | None = None,
        weight: float = 1.0,
    ) -> None:
        """Add a typed edge linking papers or entities."""
        if not source_id or not target_id:
            return
        self.graph.add_edge(
            source_id,
            target_id,
            key=f"{relation}:{len(self.graph.edges)}",
            relation=relation,
            evidence=evidence,
            weight=weight,
        )
        logger.debug("knowledge_graph.edge_added", source=source_id, target=target_id, relation=relation)

    def ingest_related_papers(self, papers: Iterable[PaperMetadata], relation: str) -> None:
        """Bulk-ingest related paper metadata."""
        anchor = self.primary_id or "primary"
        for paper in papers:
            self.add_paper(paper, source="external")
            target = paper.arxiv_id or paper.title
            if target:
                self.add_relationship(anchor, target, relation=relation, evidence=paper.title)

    def novelty_signal(self, text: str) -> NoveltySignal:
        """Compute a coarse novelty signal for a text snippet."""
        if not text.strip() or self.graph.number_of_nodes() == 0:
            return NoveltySignal(overlap_ratio=0.0, related_entities=[])

        entities = set(_extract_entities(text))
        if not entities:
            return NoveltySignal(overlap_ratio=0.0, related_entities=[])

        hits: list[str] = []
        supporting: list[str] = []
        for node, data in self.graph.nodes(data=True):
            node_entities = set(data.get("entities", []))
            overlap = entities & node_entities
            if overlap:
                hits.extend(sorted(overlap))
                supporting.append(data.get("title", node))

        overlap_ratio = len(set(hits)) / max(len(entities), 1)
        return NoveltySignal(
            overlap_ratio=min(1.0, overlap_ratio),
            related_entities=sorted(set(hits)),
            supporting_papers=supporting[:5],
        )

    def relation_summary(self) -> str:
        """Return a short text summary describing the current graph."""
        nodes = self.graph.number_of_nodes()
        edges = self.graph.number_of_edges()
        top_entities: list[str] = []

        for _, data in itertools.islice(self.graph.nodes(data=True), 5):
            top_entities.extend(data.get("entities", [])[:2])

        summary = f"Graph nodes={nodes}, edges={edges}. Frequent entities: {', '.join(sorted(set(top_entities))[:8])}"
        return summary

    def serialize(self) -> dict:
        """Serialize the graph for debugging or downstream visualization."""
        return {
            "nodes": [
                {"id": node, **data}
                for node, data in self.graph.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **data}
                for u, v, data in self.graph.edges(data=True)
            ],
        }
