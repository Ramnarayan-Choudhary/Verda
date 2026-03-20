"""External API clients for research literature."""

from shared.external.arxiv import ArxivClient
from shared.external.citation_network import CitationNetworkExplorer
from shared.external.openai_web_search import OpenAIWebSearchClient
from shared.external.papers_with_code import PapersWithCodeClient
from shared.external.semantic_scholar import SemanticScholarClient
from shared.external.types import PaperMetadata, WebSearchResult
from shared.external.web_search import WebSearchClient

__all__ = [
    "ArxivClient",
    "CitationNetworkExplorer",
    "OpenAIWebSearchClient",
    "SemanticScholarClient",
    "PapersWithCodeClient",
    "WebSearchClient",
    "PaperMetadata",
    "WebSearchResult",
]
