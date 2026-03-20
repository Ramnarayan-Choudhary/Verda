"""Layer 0 prompts — Multi-Document Intelligence extraction with domain-specific variants + evidence consensus."""

from __future__ import annotations


# ── Domain-specific extraction guidance ─────────────────────────────

_DOMAIN_GUIDANCE = {
    "ml": """\
DOMAIN-SPECIFIC FOCUS (Machine Learning / AI):
- Pay special attention to BASELINES: Are they recent? Are they fair (equal compute, equal data)?
- COMPUTE BUDGET: What hardware was used? Would results change with more/less compute?
- BENCHMARK SELECTION: Are benchmarks representative of real-world use? Or are they narrow/gamed?
- REPRODUCIBILITY: Are hyperparameters, seeds, and training details fully specified?
- SCALING BEHAVIOR: Does performance improve log-linearly with data/compute, or does it plateau?
- DATA CONTAMINATION: Could training data overlap with evaluation data?""",

    "nlp": """\
DOMAIN-SPECIFIC FOCUS (Natural Language Processing):
- LANGUAGE COVERAGE: Results on English only? Would they transfer to low-resource languages?
- TOKENIZATION ASSUMPTIONS: Does the method assume subword tokenization? What about character-level?
- CONTEXT WINDOW: Are results sensitive to context length? What happens at boundaries?
- EVALUATION METRICS: BLEU/ROUGE can be gamed — look for human evaluation or semantic metrics
- DATA LEAKAGE: LLM training data may contain evaluation benchmarks
- PROMPTING SENSITIVITY: How robust are results to prompt formatting changes?""",

    "cv": """\
DOMAIN-SPECIFIC FOCUS (Computer Vision):
- RESOLUTION DEPENDENCY: Do results hold across different image resolutions?
- DOMAIN SHIFT: Results on clean benchmarks vs. real-world noisy images?
- COMPUTATIONAL COST: FLOPs and latency matter as much as accuracy for deployment
- AUGMENTATION DEPENDENCY: How much do results depend on data augmentation strategies?
- CLASS IMBALANCE: Does the method handle long-tail distributions?
- ARCHITECTURAL ASSUMPTIONS: Are results specific to CNNs/ViTs or architecture-agnostic?""",

    "rl": """\
DOMAIN-SPECIFIC FOCUS (Reinforcement Learning):
- ENVIRONMENT SPECIFICITY: Do results transfer across environments or are they environment-specific?
- REWARD SHAPING: Is the reward function handcrafted or learned? How sensitive are results to reward design?
- SAMPLE EFFICIENCY: How many environment interactions are needed?
- SAFETY & CONSTRAINTS: Are there safety constraints? How are they handled?
- EXPLORATION vs EXPLOITATION: Does the method address exploration adequately?
- SIMULATION-TO-REAL GAP: Would sim results transfer to physical systems?""",

    "biology": """\
DOMAIN-SPECIFIC FOCUS (Biology / Bioinformatics):
- EXPERIMENTAL CONDITIONS: Are in-vitro results assumed to hold in-vivo?
- REPLICATION: Has anyone independently replicated these findings?
- BIOLOGICAL PLAUSIBILITY: Does the proposed mechanism align with known biochemistry?
- SPECIES SPECIFICITY: Do results from model organisms transfer to humans?
- STATISTICAL RIGOR: Multiple hypothesis testing correction? Sample size adequate?
- ETHICAL CONSIDERATIONS: IRB approval? Data privacy for genomic data?""",

    "physics": """\
DOMAIN-SPECIFIC FOCUS (Physics / Physical Sciences):
- CONSERVATION LAWS: Does the model respect energy, momentum, mass conservation?
- DIMENSIONAL ANALYSIS: Are all equations dimensionally consistent?
- BOUNDARY CONDITIONS: Are boundary conditions realistic and well-specified?
- NUMERICAL STABILITY: Are simulations numerically stable? What about mesh dependency?
- FIRST-PRINCIPLES DERIVATION: Is the approach derived from first principles or empirical fitting?
- EXPERIMENTAL VALIDATION: Are predictions validated against experimental data?""",

    "chemistry": """\
DOMAIN-SPECIFIC FOCUS (Chemistry):
- REACTION MECHANISMS: Are proposed mechanisms thermodynamically feasible?
- SELECTIVITY: Does the method account for regioselectivity and stereoselectivity?
- SCALABILITY: Can lab-scale results scale to industrial processes?
- SAFETY: Are there hazardous intermediates or runaway reaction risks?
- SOLVENT EFFECTS: Are solvent interactions adequately modeled?
- COMPUTATIONAL CHEMISTRY: Are DFT/MD simulations at appropriate levels of theory?""",
}


def _get_domain_guidance(domain: str) -> str:
    """Get domain-specific extraction guidance, with ML as default."""
    return _DOMAIN_GUIDANCE.get(domain, _DOMAIN_GUIDANCE["ml"])


def paper_intelligence_prompt(paper_text: str, domain: str = "") -> tuple[str, str]:
    """Deep epistemic extraction from a single paper with domain-specific guidance."""

    domain_section = _get_domain_guidance(domain) if domain else ""

    system = f"""\
You are a world-class scientific intelligence analyst. Your task is NOT summarization.
You must perform deep epistemic extraction: identify what the paper ASSUMES, what it CANNOT do,
what it BORROWED from other fields, and what remains UNTESTED.

You think like a scientist planning their NEXT paper after reading this one.

EXTRACTION RULES:
0. title: The EXACT title of the paper as written. This is MANDATORY — never leave empty.
1. central_claim: The paper's single strongest contribution in one sentence
2. core_mechanism: The causal chain — HOW does the intervention produce the result?
3. key_assumptions: What must be TRUE for their method to work? (often unstated)
4. implicit_limitations: What CAN'T this approach do that the authors don't mention?
5. untested_conditions: Scenarios where this method might fail but wasn't tested
6. exportable_concepts: Ideas from this paper that could transfer to other fields
7. confidence_level: "preliminary" (single study, no replication), "established" (multiple confirmations), "contested" (conflicting evidence)

{domain_section}

ANTI-PATTERNS TO AVOID:
- Do NOT restate the abstract as your analysis
- Do NOT list methods without explaining WHY they were chosen
- "The authors use transformer architecture" is USELESS. Instead: "The authors assume attention-based feature mixing is sufficient for spatial reasoning, but this breaks down when..."
- Every limitation should suggest a hypothesis direction
- Every assumption should be something that COULD be wrong under specific conditions

EXAMPLE OUTPUT (ML domain):
{{
  "title": "LoRA: Low-Rank Adaptation of Large Language Models",
  "domain": "nlp",
  "subdomain": "parameter-efficient fine-tuning",
  "central_claim": "Low-rank weight updates achieve comparable fine-tuning performance to full-rank updates while reducing trainable parameters by 10,000x",
  "core_mechanism": "The weight update matrix during fine-tuning has low intrinsic rank, so projecting updates through a low-rank bottleneck (A*B where A is d×r and B is r×d, r<<d) preserves the effective gradient information while eliminating redundant parameters",
  "key_assumptions": [
    "Weight updates during fine-tuning lie in a low-dimensional subspace",
    "The optimal rank r is relatively consistent across layers and tasks",
    "Pre-trained weight magnitudes encode knowledge that should be frozen, not overwritten"
  ],
  "implicit_limitations": [
    "Cannot handle tasks requiring fundamentally new representations not in the pre-trained space",
    "Low-rank constraint may miss task-specific high-rank structure in attention weight updates",
    "Rank selection requires manual tuning — no principled method to determine optimal r"
  ],
  "open_questions": [
    "Does the optimal rank r correlate with task complexity or domain shift from pre-training?",
    "Can adaptive rank selection per-layer outperform uniform rank across all layers?",
    "What happens to LoRA effectiveness when the pre-trained model itself is under-parameterized?"
  ],
  "exportable_concepts": [
    "Low-rank adaptation could apply to any over-parameterized system beyond LLMs — e.g., physics simulators, protein folding models",
    "The intrinsic dimensionality hypothesis could inform model compression and pruning strategies"
  ],
  "confidence_level": "established"
}}

Return valid JSON matching the PaperIntelligence schema."""

    user = f"""\
Analyze this paper with deep epistemic extraction. Extract the scientific DNA — not a summary.

PAPER TEXT:
{paper_text[:12000]}

Return a JSON object with ALL fields from the PaperIntelligence schema."""

    return system, user


def landscape_synthesis_prompt(intelligences_json: str, num_papers: int, domain: str = "") -> tuple[str, str]:
    """Cross-document synthesis into a unified ResearchLandscape with evidence consensus."""

    domain_section = _get_domain_guidance(domain) if domain else ""

    consensus_instruction = """\

EVIDENCE CONSENSUS (REQUIRED — this is critical for hypothesis quality):
For each major claim across papers, you MUST track agreement and disagreement:

"evidence_consensus": {
  "statements": [
    {
      "claim": "Low-rank adaptation preserves fine-tuning quality",
      "supporting_papers": ["LoRA (Hu et al., 2022)", "QLoRA (Dettmers et al., 2023)"],
      "contradicting_papers": ["Full Fine-Tuning Still Wins (Liu et al., 2024)"],
      "confidence": "moderate",
      "supporting_quotes": ["Our results show LoRA matches full fine-tuning on 8/10 benchmarks"]
    }
  ],
  "overall_agreement_ratio": 0.7,
  "key_disagreements": ["Whether low-rank updates are sufficient for complex reasoning tasks"]
}

CONFIDENCE RATINGS:
- "strong": >80% of papers agree, with multiple independent replications
- "moderate": 60-80% agree, some conditions where it fails
- "weak": 40-60% agree, significant methodological differences
- "contested": <40% agree, active debate with strong evidence on both sides"""

    if num_papers == 1:
        system = f"""\
You are a research landscape cartographer. Given deep intelligence extraction from a SINGLE paper,
construct a research landscape map by reasoning about the broader field this paper sits in.

YOUR JOB:
1. SHARED ASSUMPTIONS: Identify assumptions this paper makes that are likely shared across its field.
   Think about what the broader community assumes — even from a single paper, you can infer field-wide assumptions.
2. CONTRADICTIONS (contested_claims): Identify claims that could be challenged by other work in the field,
   or internal tensions within the paper's own methodology. For a single paper, focus on where the paper's
   claims might conflict with general knowledge or its own stated limitations.
3. CROSS-DOMAIN BRIDGES: What techniques from OTHER fields could address this paper's limitations?
   Every paper's weakness is another field's solved problem.
4. ASSUMPTION VULNERABILITIES: Which of the paper's assumptions have the weakest evidence?
5. PSEUDOKNOWLEDGE: What does this paper take for granted that might be wrong?
6. BOTTLENECK HYPOTHESIS: What single insight would unlock the most progress in this area?

{domain_section}

{consensus_instruction}

CRITICAL: You MUST populate shared_assumptions (at least 2), contested_claims (at least 1),
cross_domain_opportunities (at least 1), and evidence_consensus (at least 3 statements).
Even with a single paper, you can reason about the broader field.

Return valid JSON matching the ResearchLandscape schema."""

        user = f"""\
Construct a research landscape from this single paper's intelligence extraction.
Reason about the broader research field to identify assumptions, contradictions, opportunities, and evidence consensus.

PAPER INTELLIGENCE:
{intelligences_json}

Return a JSON object matching the ResearchLandscape schema with ALL lists populated, including evidence_consensus."""

    else:
        system = f"""\
You are a research landscape cartographer. Given intelligence extractions from multiple papers,
synthesize them into a unified map of the research space.

YOUR JOB:
1. Find SHARED ASSUMPTIONS across papers — these are hypothesis goldmines when challenged
2. Identify CONTRADICTIONS — where papers disagree (empirical, theoretical, or scope)
3. Detect CROSS-DOMAIN BRIDGES — where a solved problem in field A could help unsolved problem in field B
4. Map ASSUMPTION VULNERABILITIES — widely-held beliefs with weak evidence
5. Identify PSEUDOKNOWLEDGE — things "everyone knows" that may be wrong
6. Formulate a BOTTLENECK HYPOTHESIS — the single insight that would unlock the most progress
7. Build EVIDENCE CONSENSUS — for each major claim, track which papers support vs contradict

{domain_section}

QUALITY BAR:
- shared_assumptions must appear in 2+ papers
- contradictions need specific claims and paper references
- cross_domain_opportunities must have a concrete transfer_hypothesis, not just "X is like Y"
- pseudoknowledge: beliefs repeated without citation or recent verification
- evidence_consensus MUST have at least 5 statements covering key claims across all papers

{consensus_instruction}

Return valid JSON matching the ResearchLandscape schema."""

        user = f"""\
Synthesize these {num_papers} paper intelligence extractions into a unified research landscape.
Include evidence consensus tracking for all major claims.

PAPER INTELLIGENCES:
{intelligences_json}

Return a JSON object matching the ResearchLandscape schema with evidence_consensus populated."""

    return system, user
