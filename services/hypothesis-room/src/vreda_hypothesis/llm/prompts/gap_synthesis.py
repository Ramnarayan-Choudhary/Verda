"""Prompts for iterative gap synthesis — 3-round identify→check→refine loop.

Inspired by open_deep_research (LangChain): plan→search→read→synthesize→refine
before generating any hypothesis.
"""

from __future__ import annotations

from textwrap import dedent

from vreda_hypothesis.models import MetaGap, PaperMetadata, PaperSummary, ResearchFrame


def gap_identification_prompt(
    summary: PaperSummary,
    research_frame: ResearchFrame | None,
    related_papers: list[PaperMetadata],
    rag_context: list[str],
) -> tuple[str, str]:
    """Round 1: Identify 8-10 candidate research gaps."""
    system = dedent(
        """\
        You are a senior research analyst identifying actionable research gaps.

        Gap types (use these exact labels):
        - "empirical": Missing experiments, untested conditions, incomplete ablations
        - "theoretical": Unproven claims, missing proofs, weak theoretical grounding
        - "robustness": Not tested under adversarial/OOD/noisy/edge conditions
        - "scaling": Only tested at one scale — larger or smaller behavior unknown
        - "application": Technique not applied to promising adjacent domains

        Quality criteria for each gap:
        - Must be SPECIFIC: "No work tests [operator X] under [constraint Y] on [dataset class Z]"
        - Must explain WHY it matters: what changes in understanding if this gap is closed
        - Must cite nearest prior work that tried but failed to close it
        - Must be closable by a NAMED experiment (not just "more research needed")

        CRITICAL: Generate 8-10 candidate gaps. Be aggressive — later rounds will filter.
        Do NOT self-censor. Include gaps that might already be solved — Round 2 will check.

        Return JSON: {"gaps": [{"gap_id": "G1", "gap_type": "...", "statement": "...",
        "why_it_matters": "...", "nearest_prior_work": "...", "already_solved": false,
        "iteration_history": ["Round 1: initial identification"]}]}"""
    )

    frame_block = ""
    if research_frame:
        frame_block = dedent(
            f"""
            RESEARCH FRAME (atomic operators):
            - Task family: {research_frame.task_family}
            - Core operators: {', '.join(research_frame.core_operators) or 'not_stated'}
            - Core mechanism: {research_frame.core_mechanism or 'not_stated'}
            - Assumptions: {', '.join(research_frame.assumptions) or 'not_stated'}
            - Explicit limits: {', '.join(research_frame.explicit_limits) or 'not_stated'}
            - Implicit limits: {', '.join(research_frame.implicit_limits) or 'not_stated'}
            - Missing baselines: {', '.join(research_frame.missing_baselines) or 'not_stated'}
            - Untested axes: {', '.join(research_frame.untested_axes) or 'not_stated'}
            """
        )

    related_lines = "\n".join(
        f"- {p.title} ({p.year}, {p.citation_count} cit.): {p.abstract[:250]}..."
        for p in related_papers[:15]
    )
    rag_text = "\n".join(f"- {ctx[:300]}" for ctx in rag_context[:5])

    user = dedent(
        f"""\
        ANCHOR PAPER: {summary.title}
        Domain: {summary.domain}
        Methods: {', '.join(summary.methods)}
        Results: {', '.join(summary.results[:3])}
        Limitations: {', '.join(summary.limitations) or 'Not explicitly stated'}
        Contributions: {', '.join(summary.contributions[:3])}
        {frame_block}
        RELATED LITERATURE ({len(related_papers)} papers):
        {related_lines or 'No related papers retrieved.'}

        VECTOR STORE CONTEXT:
        {rag_text or 'No embeddings yet.'}

        Identify 8-10 candidate research gaps. Be specific and aggressive."""
    )
    return system, user


def gap_validation_prompt(
    gaps: list[MetaGap],
    related_papers: list[PaperMetadata],
    rag_context: list[str],
) -> tuple[str, str]:
    """Round 2: Check each gap against literature — mark already_solved if found."""
    system = dedent(
        """\
        You are a literature validation agent. For each candidate research gap,
        check whether existing literature ALREADY addresses or solves it.

        For each gap:
        1. Search the related papers list for evidence that this gap has been addressed
        2. Check the vector store context for relevant findings
        3. If a paper directly addresses the gap, set already_solved=true and explain in iteration_history
        4. If a paper partially addresses it, refine the gap statement to be more specific

        CRITICAL RULES:
        - A gap is "already_solved" ONLY if a paper directly and fully addresses it
        - Partial coverage means the gap should be NARROWED, not eliminated
        - Add "Round 2: [your finding]" to each gap's iteration_history

        Return the COMPLETE list of gaps with updated already_solved and iteration_history.
        Return JSON: {"gaps": [...all gaps with updates...]}"""
    )

    gaps_json = "\n".join(
        f"- [{g.gap_id}] ({g.gap_type}) {g.statement}\n  Why: {g.why_it_matters}\n  Prior: {g.nearest_prior_work}"
        for g in gaps
    )
    related_lines = "\n".join(
        f"- {p.title} ({p.year}): {p.abstract[:300]}"
        for p in related_papers[:15]
    )
    rag_text = "\n".join(f"- {ctx[:300]}" for ctx in rag_context[:8])

    user = dedent(
        f"""\
        CANDIDATE GAPS TO VALIDATE:
        {gaps_json}

        LITERATURE TO CHECK AGAINST:
        {related_lines or 'No papers available.'}

        VECTOR STORE CONTEXT:
        {rag_text or 'No context available.'}

        For each gap, determine if it's already solved. Update the gaps list."""
    )
    return system, user


def gap_refinement_prompt(
    gaps: list[MetaGap],
    research_frame: ResearchFrame | None,
) -> tuple[str, str]:
    """Round 3: Refine surviving gaps — sharpen statements, reject vague ones."""
    system = dedent(
        """\
        You are a senior NeurIPS reviewer performing final refinement of research gaps.

        For each surviving gap (already_solved=false):
        1. SHARPEN the statement: make it specific enough that a researcher could
           start an experiment TOMORROW based on it alone
        2. Ensure the statement follows the format:
           "No work tests [operator X] under [constraint Y] on [dataset class Z]"
        3. Verify why_it_matters explains what changes in understanding
        4. Check nearest_prior_work cites a real paper/method

        REJECTION CRITERIA — remove a gap if:
        - It cannot be closed by a NAMED experiment (dataset + metric + intervention)
        - The statement is too vague ("more research needed" type)
        - It duplicates another gap in the list

        QUALITY GATE:
        - Output 5-7 high-quality gaps MINIMUM
        - If fewer than 5 survive, you are being too aggressive — relax criteria slightly

        Add "Round 3: [refinement notes]" to each gap's iteration_history.

        Return JSON: {"gaps": [...surviving refined gaps...],
        "landscape_summary": "...", "dominant_trends": [...], "underexplored_areas": [...],
        "iterations_completed": 3}"""
    )

    gaps_json = "\n".join(
        f"- [{g.gap_id}] ({g.gap_type}) solved={g.already_solved}\n"
        f"  Statement: {g.statement}\n"
        f"  Why: {g.why_it_matters}\n"
        f"  Prior: {g.nearest_prior_work}\n"
        f"  History: {' → '.join(g.iteration_history)}"
        for g in gaps
    )

    frame_context = ""
    if research_frame:
        frame_context = (
            f"\nPaper operators: {', '.join(research_frame.core_operators)}\n"
            f"Core mechanism: {research_frame.core_mechanism}\n"
            f"Untested axes: {', '.join(research_frame.untested_axes)}\n"
        )

    user = dedent(
        f"""\
        GAPS AFTER LITERATURE VALIDATION:
        {gaps_json}
        {frame_context}
        Refine surviving gaps. Remove already_solved ones. Sharpen statements.
        Ensure 5-7 high-quality gaps survive."""
    )
    return system, user
