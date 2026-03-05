"""External API clients for research literature."""

from shared.external.arxiv import ArxivClient
from shared.external.papers_with_code import PapersWithCodeClient
from shared.external.semantic_scholar import SemanticScholarClient
from shared.external.types import PaperMetadata, WebSearchResult
from shared.external.web_search import WebSearchClient

__all__ = [
    "ArxivClient",
    "SemanticScholarClient",
    "PapersWithCodeClient",
    "WebSearchClient",
    "PaperMetadata",
    "WebSearchResult",
]
