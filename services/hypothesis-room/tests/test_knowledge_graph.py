"""Integration tests for Knowledge Graph — entity extraction + novelty signals."""

from __future__ import annotations

import pytest

from vreda_hypothesis.knowledge.graph import PaperKnowledgeGraph, _extract_entities, NoveltySignal
from vreda_hypothesis.models import PaperMetadata, PaperSummary


class TestEntityExtraction:
    """Test the domain-aware entity vocabulary extraction."""

    def test_extracts_architectures(self):
        text = "We use a transformer with self-attention and CNN backbone."
        entities = _extract_entities(text)
        assert "transformer" in entities
        assert "self-attention" in entities
        assert "cnn" in entities

    def test_extracts_models(self):
        text = "We fine-tune GPT-4 and compare against BERT and LLaMA."
        entities = _extract_entities(text)
        assert "gpt-4" in entities
        assert "bert" in entities
        assert "llama" in entities

    def test_extracts_datasets(self):
        text = "Evaluation on ImageNet, CIFAR-10, and MMLU benchmarks."
        entities = _extract_entities(text)
        assert "imagenet" in entities
        assert "cifar-10" in entities
        assert "mmlu" in entities

    def test_extracts_training_techniques(self):
        text = "We apply LoRA fine-tuning with contrastive learning and knowledge distillation."
        entities = _extract_entities(text)
        assert "lora" in entities
        assert "fine-tuning" in entities
        assert "contrastive learning" in entities
        assert "knowledge distillation" in entities

    def test_extracts_metrics(self):
        text = "We measure accuracy, BLEU score, and FID for image quality."
        entities = _extract_entities(text)
        assert "accuracy" in entities
        assert "bleu" in entities
        assert "fid" in entities

    def test_extracts_concepts(self):
        text = "We study the scaling law and hallucination in chain-of-thought reasoning."
        entities = _extract_entities(text)
        assert "scaling law" in entities
        assert "hallucination" in entities
        assert "chain-of-thought" in entities

    def test_empty_text(self):
        assert _extract_entities("") == []

    def test_case_insensitive(self):
        text = "TRANSFORMER with Self-Attention"
        entities = _extract_entities(text)
        assert "transformer" in entities
        assert "self-attention" in entities


class TestPaperKnowledgeGraph:
    """Test the PaperKnowledgeGraph class."""

    def test_add_paper(self, sample_paper_metadata, sample_paper_summary):
        kg = PaperKnowledgeGraph()
        kg.add_paper(sample_paper_metadata, summary=sample_paper_summary, source="primary")

        assert kg.graph.number_of_nodes() == 1
        assert kg.primary_id == "1706.03762"

        # Node should have extracted entities
        node_data = kg.graph.nodes[kg.primary_id]
        assert len(node_data["entities"]) > 0
        assert "self-attention" in node_data["entities"]

    def test_add_relationship(self, sample_paper_metadata):
        kg = PaperKnowledgeGraph()
        kg.add_paper(sample_paper_metadata, source="primary")
        kg.add_paper(
            PaperMetadata(title="BERT", arxiv_id="1810.04805"),
            source="related",
        )
        kg.add_relationship("1706.03762", "1810.04805", relation="cites", evidence="BERT extends transformers")

        assert kg.graph.number_of_edges() == 1

    def test_ingest_related_papers(self, sample_paper_metadata):
        kg = PaperKnowledgeGraph()
        kg.add_paper(sample_paper_metadata, source="primary")

        related = [
            PaperMetadata(title="BERT", arxiv_id="1810.04805", abstract="Language model"),
            PaperMetadata(title="GPT-2", arxiv_id="1901.09876", abstract="Generative model"),
        ]
        kg.ingest_related_papers(related, relation="cites")

        assert kg.graph.number_of_nodes() == 3  # primary + 2 related
        assert kg.graph.number_of_edges() == 2  # 2 citation edges

    def test_novelty_signal(self, sample_paper_metadata, sample_paper_summary):
        kg = PaperKnowledgeGraph()
        kg.add_paper(sample_paper_metadata, summary=sample_paper_summary, source="primary")

        # Text that overlaps heavily with the paper
        signal = kg.novelty_signal("self-attention transformer for NLP")
        assert isinstance(signal, NoveltySignal)
        assert signal.overlap_ratio > 0
        assert len(signal.related_entities) > 0

        # Text with no overlap
        signal2 = kg.novelty_signal("quantum computing for drug discovery")
        assert signal2.overlap_ratio < signal.overlap_ratio

    def test_novelty_signal_empty(self):
        kg = PaperKnowledgeGraph()
        signal = kg.novelty_signal("anything")
        assert signal.overlap_ratio == 0.0

    def test_relation_summary(self, sample_paper_metadata, sample_paper_summary):
        kg = PaperKnowledgeGraph()
        kg.add_paper(sample_paper_metadata, summary=sample_paper_summary, source="primary")
        summary = kg.relation_summary()
        assert "nodes=1" in summary

    def test_serialize(self, sample_paper_metadata):
        kg = PaperKnowledgeGraph()
        kg.add_paper(sample_paper_metadata, source="primary")
        data = kg.serialize()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1
