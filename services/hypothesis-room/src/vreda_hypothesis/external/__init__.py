"""External API clients — arXiv, Semantic Scholar, PapersWithCode, Tavily, OpenAI web search."""

from .arxiv import ArxivClient
from .semantic_scholar import SemanticScholarClient
from .paperswithcode import PapersWithCodeClient
from .tavily import TavilySearchClient
from .openai_web_search import OpenAIWebSearchClient

__all__ = [
    "ArxivClient",
    "SemanticScholarClient",
    "PapersWithCodeClient",
    "TavilySearchClient",
    "OpenAIWebSearchClient",
]
