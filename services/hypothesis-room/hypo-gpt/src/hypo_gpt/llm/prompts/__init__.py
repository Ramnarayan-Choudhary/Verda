"""Prompt placeholders for the GPT engine layers."""

from hypo_gpt.llm.prompts.cartography import CARTOGRAPHY_PROMPT
from hypo_gpt.llm.prompts.intelligence import INTELLIGENCE_PROMPT
from hypo_gpt.llm.prompts.judges import JUDGES_PROMPT
from hypo_gpt.llm.prompts.portfolio import PORTFOLIO_PROMPT
from hypo_gpt.llm.prompts.strategies import STRATEGY_PROMPTS
from hypo_gpt.llm.prompts.tribunal import TRIBUNAL_PROMPT

__all__ = [
    "INTELLIGENCE_PROMPT",
    "CARTOGRAPHY_PROMPT",
    "STRATEGY_PROMPTS",
    "TRIBUNAL_PROMPT",
    "JUDGES_PROMPT",
    "PORTFOLIO_PROMPT",
]
