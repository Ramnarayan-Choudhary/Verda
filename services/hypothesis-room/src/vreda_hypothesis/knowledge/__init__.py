"""Knowledge infrastructure — NetworkX graph + Supabase pgvector store."""

from .graph import PaperKnowledgeGraph, NoveltySignal
from .vector_store import VectorStoreClient

__all__ = ["PaperKnowledgeGraph", "NoveltySignal", "VectorStoreClient"]
