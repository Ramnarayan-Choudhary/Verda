"""Prompt for ResearchFrame extraction — atomic operator decomposition.

Inspired by AI-Researcher (HKUDS): breaks papers into atomic concepts
with exact named techniques, core mechanisms, and quantified claims.
"""

from __future__ import annotations

from textwrap import dedent

from vreda_hypothesis.models import PaperMetadata


def research_frame_prompt(paper_text: str, metadata: PaperMetadata | None = None) -> tuple[str, str]:
    """Return system/user prompts for ResearchFrame extraction."""
    system = dedent(
        """\
        You are a NeurIPS reviewer extracting the paper's operational mechanics.
        No summaries. Operators only.

        Your task is to decompose the paper into its atomic research components:

        1. **core_operators**: List EVERY specific named technique the paper uses or proposes.
           Examples: "LoRA", "STE (Straight-Through Estimator)", "cosine similarity loss",
           "multi-head cross-attention", "RoPE embeddings", "flash attention".
           NOT generic terms like "deep learning" or "neural network".

        2. **core_mechanism**: ONE sentence describing the specific intervention that drives
           the paper's results. Be precise — name the exact operation.
           Example: "Replacing full fine-tuning with low-rank adapter matrices (rank 4-16)
           injected into attention projection layers reduces trainable parameters by 99%
           while maintaining 95%+ of full fine-tuning performance."

        3. **claimed_gains**: For each operator, extract the EXACT quantitative claim.
           Include the condition under which the gain was measured.

        4. **assumptions**: What does the paper assume to be true but doesn't prove?
           Examples: "IID data", "English-only evaluation", "A100 GPU available",
           "pre-trained backbone frozen", "batch size > 32".

        5. **explicit_limits**: What do the authors explicitly say they did NOT test?
           Usually in "Limitations" or "Future Work" sections.

        6. **implicit_limits**: What would a domain expert notice is missing but the
           paper doesn't mention? Think about: other modalities, other languages,
           other scales, adversarial conditions, theoretical gaps.

        7. **missing_baselines**: Which SOTA methods should have been compared but weren't?
           Think about the most cited recent methods in this area.

        8. **untested_axes**: Which experimental dimensions were not explored?
           Examples: "scale" (larger/smaller models), "OOD" (out-of-distribution),
           "low-data" (few-shot), "adversarial", "quantization", "multilingual",
           "cross-domain", "temporal drift".

        RULES:
        - If a field cannot be filled from the paper, write "not_stated"
        - NEVER hallucinate — only extract what's actually in the paper
        - For implicit_limits and missing_baselines, you MAY use domain knowledge
          to identify what's missing, but label it clearly
        - core_operators must be SPECIFIC NAMED TECHNIQUES, not categories

        Return valid JSON matching the ResearchFrame schema."""
    )

    meta_block = ""
    if metadata:
        meta_block = (
            f"Title: {metadata.title}\n"
            f"Authors: {', '.join(metadata.authors[:5])}\n"
            f"Year: {metadata.year}\n"
            f"Abstract: {metadata.abstract[:500]}\n\n"
        )

    # Use more context than PaperSummary — ResearchFrame needs details
    truncated_text = paper_text[:15000]
    if len(paper_text) > 15000:
        # Include middle section (methods) + end (limitations/future work)
        mid_start = len(paper_text) // 3
        truncated_text += (
            "\n\n[...METHODS SECTION...]\n\n"
            + paper_text[mid_start:mid_start + 3000]
            + "\n\n[...LIMITATIONS/CONCLUSION...]\n\n"
            + paper_text[-3000:]
        )

    user = dedent(
        f"""\
        {meta_block}PAPER TEXT:
        ---
        {truncated_text}
        ---

        Extract the ResearchFrame with fields: task_family, core_operators (list),
        core_mechanism (string), claimed_gains (list of {{operator, gain, condition}}),
        assumptions (list), explicit_limits (list), implicit_limits (list),
        missing_baselines (list), untested_axes (list).

        Remember: operators only, no summaries. If a field cannot be filled, use "not_stated"."""
    )
    return system, user
