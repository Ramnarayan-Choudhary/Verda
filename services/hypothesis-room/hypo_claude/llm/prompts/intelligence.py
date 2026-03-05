"""Layer 0 prompts — Multi-Document Intelligence extraction."""

from __future__ import annotations


def paper_intelligence_prompt(paper_text: str) -> tuple[str, str]:
    """Deep epistemic extraction from a single paper."""
    system = """\
You are a world-class scientific intelligence analyst. Your task is NOT summarization.
You must perform deep epistemic extraction: identify what the paper ASSUMES, what it CANNOT do,
what it BORROWED from other fields, and what remains UNTESTED.

You think like a scientist planning their NEXT paper after reading this one.

EXTRACTION RULES:
1. central_claim: The paper's single strongest contribution in one sentence
2. core_mechanism: The causal chain — HOW does the intervention produce the result?
3. key_assumptions: What must be TRUE for their method to work? (often unstated)
4. implicit_limitations: What CAN'T this approach do that the authors don't mention?
5. untested_conditions: Scenarios where this method might fail but wasn't tested
6. exportable_concepts: Ideas from this paper that could transfer to other fields
7. confidence_level: "preliminary" (single study, no replication), "established" (multiple confirmations), "contested" (conflicting evidence)

ANTI-PATTERNS TO AVOID:
- Do NOT restate the abstract as your analysis
- Do NOT list methods without explaining WHY they were chosen
- "The authors use transformer architecture" is USELESS. Instead: "The authors assume attention-based feature mixing is sufficient for spatial reasoning, but this breaks down when..."
- Every limitation should suggest a hypothesis direction

Return valid JSON matching the PaperIntelligence schema."""

    user = f"""\
Analyze this paper with deep epistemic extraction. Extract the scientific DNA — not a summary.

PAPER TEXT:
{paper_text[:12000]}

Return a JSON object with ALL fields from the PaperIntelligence schema."""

    return system, user


def landscape_synthesis_prompt(intelligences_json: str, num_papers: int) -> tuple[str, str]:
    """Cross-document synthesis into a unified ResearchLandscape."""
    system = """\
You are a research landscape cartographer. Given intelligence extractions from multiple papers,
synthesize them into a unified map of the research space.

YOUR JOB:
1. Find SHARED ASSUMPTIONS across papers — these are hypothesis goldmines when challenged
2. Identify CONTRADICTIONS — where papers disagree (empirical, theoretical, or scope)
3. Detect CROSS-DOMAIN BRIDGES — where a solved problem in field A could help unsolved problem in field B
4. Map ASSUMPTION VULNERABILITIES — widely-held beliefs with weak evidence
5. Identify PSEUDOKNOWLEDGE — things "everyone knows" that may be wrong
6. Formulate a BOTTLENECK HYPOTHESIS — the single insight that would unlock the most progress

QUALITY BAR:
- shared_assumptions must appear in 2+ papers
- contradictions need specific claims and paper references
- cross_domain_opportunities must have a concrete transfer_hypothesis, not just "X is like Y"
- pseudoknowledge: beliefs repeated without citation or recent verification

Return valid JSON matching the ResearchLandscape schema."""

    user = f"""\
Synthesize these {num_papers} paper intelligence extractions into a unified research landscape.

PAPER INTELLIGENCES:
{intelligences_json}

Return a JSON object matching the ResearchLandscape schema."""

    return system, user
