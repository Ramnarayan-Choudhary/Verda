"""
VREDA.ai Advanced Hypothesis Generation Module.

A multi-agent, knowledge-grounded pipeline that generates, refines, and ranks
novel research hypotheses from scientific papers.

Architecture inspired by:
- AI Co-Scientist (arXiv:2502.18864) — multi-agent debate-evolve loop
- Knowledge-grounded generation (arXiv:2510.09901) — KG novelty checks
- Overgeneration with diversity (arXiv:2409.04109) — seed generation + Elo ranking
"""

from vreda_hypothesis.main import generate_hypotheses

__version__ = "0.1.0"
__all__ = ["generate_hypotheses"]
