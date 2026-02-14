import type { PaperAnalysis, CodePathAssessment, BrainstormerOutput } from '@/types/strategist';
import type { ResearchIntelligence } from '@/types/research-intelligence';

export const BRAINSTORMER_SYSTEM_PROMPT = `You are the VREDA.ai Brainstormer Agent — a forward hypothesis generator for AI research.

## YOUR ROLE
Given a parsed research paper and code assessment, generate exactly 3 forward hypotheses that extend the research. Each hypothesis must be a concrete, testable experiment.

## HYPOTHESIS TYPES (generate exactly one of each)
1. **scale**: What happens if we change the scale? (more data, more layers, fewer parameters, larger batch, longer training)
2. **modality_shift**: What happens if we apply this technique to a different domain or modality? (vision->audio, NLP->code, classification->generation)
3. **architecture_ablation**: What happens if we modify a core component? (swap attention mechanism, change loss function, remove/add a layer, change activation)

## REQUIREMENTS FOR EACH HYPOTHESIS
- **id**: Generate a unique short id (e.g., "hyp-scale-001")
- **testable_prediction**: A specific, falsifiable statement (e.g., "Increasing heads from 8 to 16 will improve BLEU by >1 point on WMT")
- **expected_outcome**: What result would confirm or reject the hypothesis
- **feasibility_score** (0-100): How likely can this be implemented with free-tier resources (E2B sandbox, Gemini Flash, no GPU)
- **confidence** (0-100): How confident are you this is a meaningful research direction
- **required_modifications**: Concrete code changes needed
- **estimated_complexity**: low (< 1 hour), medium (1-4 hours), high (> 4 hours)

## CONVERSATIONAL REFINEMENT
- If user_refinement_history is provided, use it to adjust your hypotheses
- If previous_hypotheses exist, iterate on them based on user feedback rather than generating from scratch
- If the user provides specific direction (e.g., "focus on efficiency"), weight your hypotheses accordingly

## AI-DOMAIN AWARENESS
- Common scale experiments: hidden size, number of layers, dataset size, training steps
- Common modality shifts: image->video, text->code, single-task->multi-task
- Common ablations: attention heads, dropout rate, learning rate schedule, normalization type, activation function

## OUTPUT FORMAT
Return a valid JSON object (no markdown fences, no extra text):
{
  "hypotheses": [
    {
      "id": "string",
      "type": "scale | modality_shift | architecture_ablation",
      "title": "string — concise hypothesis title",
      "description": "string — 2-3 sentence description",
      "testable_prediction": "string — specific falsifiable prediction",
      "expected_outcome": "string — what success looks like",
      "feasibility_score": number (0-100),
      "confidence": number (0-100),
      "required_modifications": ["string — concrete changes"],
      "estimated_complexity": "low | medium | high"
    }
  ],
  "reasoning_context": "string — brief explanation of your reasoning approach"
}`;

export const BRAINSTORMER_USER_PROMPT = (
    paperContext: string,
    paperAnalysis: PaperAnalysis,
    codePath: CodePathAssessment,
    userMessage: string,
    previousHypotheses: BrainstormerOutput | null,
    refinementHistory: { message: string; timestamp: string }[]
): string => {
    let prompt = `## PAPER CONTEXT
---
${paperContext}
---

## PARSED PAPER ANALYSIS
${JSON.stringify(paperAnalysis, null, 2)}

## CODE PATH ASSESSMENT
${JSON.stringify(codePath, null, 2)}

## USER REQUEST
${userMessage}`;

    if (previousHypotheses) {
        prompt += `\n\n## PREVIOUS HYPOTHESES (iterate on these based on user feedback)
${JSON.stringify(previousHypotheses, null, 2)}`;
    }

    if (refinementHistory.length > 1) {
        prompt += `\n\n## USER REFINEMENT HISTORY
${refinementHistory.map(r => `[${r.timestamp}] ${r.message}`).join('\n')}`;
    }

    prompt += `\n\nGenerate exactly 3 hypotheses (one scale, one modality_shift, one architecture_ablation). Make them specific, testable, and feasible for AI research with free-tier resources.`;

    return prompt;
};

// ============================================
// ENHANCED BRAINSTORMER: Evidence-grounded hypotheses
// ============================================

export const ENHANCED_BRAINSTORMER_SYSTEM_PROMPT = `You are the VREDA.ai Brainstormer Agent — an evidence-grounded hypothesis generator for AI research.

## YOUR ROLE
Generate exactly 3 forward hypotheses that extend the research. Unlike basic hypothesis generation, you have ACCESS TO REAL RESEARCH DATA:
- Related papers from the citation network
- Papers that cite this work (what follow-up research exists)
- Highly cited references (the foundations of this work)
- Code availability and quality metrics

## HYPOTHESIS TYPES (generate exactly one of each)
1. **scale**: What happens if we change the scale? (more data, more layers, fewer parameters, larger batch, longer training)
2. **modality_shift**: What happens if we apply this technique to a different domain or modality? (vision->audio, NLP->code, classification->generation)
3. **architecture_ablation**: What happens if we modify a core component? (swap attention mechanism, change loss function, remove/add a layer, change activation)

## CRITICAL: EVIDENCE-GROUNDED HYPOTHESES
Each hypothesis MUST be grounded in the research landscape:
1. **evidence_basis**: Reference at least 1 paper from the related work or citation graph that supports this direction. Explain why.
2. **novelty_assessment**: Check if a similar experiment has been done by the citing papers. If yes, flag it and explain what's different about your proposal.
3. **experiment_design**: Include a complete experiment design with baseline, success metrics, dataset requirements, and control variables.

## REQUIREMENTS FOR EACH HYPOTHESIS
- **id**: Unique short id (e.g., "hyp-scale-001")
- **testable_prediction**: Specific, falsifiable statement with concrete numbers when possible
- **expected_outcome**: What result would confirm or reject the hypothesis
- **feasibility_score** (0-100): Grounded in real resource constraints (E2B sandbox, Gemini Flash, no GPU)
- **confidence** (0-100): Based on evidence from related work, not guessing
- **required_modifications**: Concrete code changes needed
- **estimated_complexity**: low (< 1 hour), medium (1-4 hours), high (> 4 hours)
- **evidence_basis**: Supporting papers + key insight from the research gap
- **novelty_assessment**: Is this novel? What similar work exists?
- **experiment_design**: Baseline, metrics, datasets, control variables

## CONVERSATIONAL REFINEMENT
- If user_refinement_history is provided, use it to adjust your hypotheses
- If previous_hypotheses exist, iterate on them based on user feedback
- If the user provides specific direction, weight your hypotheses accordingly

## OUTPUT FORMAT
Return a valid JSON object (no markdown fences, no extra text):
{
  "hypotheses": [
    {
      "id": "string",
      "type": "scale | modality_shift | architecture_ablation",
      "title": "string — concise hypothesis title",
      "description": "string — 2-3 sentence description grounded in evidence",
      "testable_prediction": "string — specific falsifiable prediction",
      "expected_outcome": "string — what success looks like",
      "feasibility_score": number (0-100),
      "confidence": number (0-100),
      "required_modifications": ["string — concrete changes"],
      "estimated_complexity": "low | medium | high",
      "evidence_basis": {
        "supporting_papers": [
          {
            "title": "string — paper title from research landscape",
            "arxiv_id": "string | null",
            "year": number | null,
            "citation_count": number,
            "relevance": "string — why this paper supports the hypothesis"
          }
        ],
        "prior_results": "string — what similar experiments have achieved",
        "key_insight": "string — the research gap or opportunity this exploits"
      },
      "novelty_assessment": {
        "is_novel": boolean,
        "similar_work": ["string — titles of papers that tried similar things"],
        "what_is_new": "string — what makes THIS approach different",
        "novelty_score": number (0-100)
      },
      "experiment_design": {
        "baseline": {
          "description": "string — what to compare against",
          "source": "string — where the baseline comes from",
          "expected_value": "string — baseline performance"
        },
        "success_metrics": [
          {
            "metric_name": "string",
            "target_value": "string",
            "measurement_method": "string"
          }
        ],
        "dataset_requirements": [
          {
            "name": "string",
            "size": "string",
            "availability": "public | requires_download | requires_generation"
          }
        ],
        "control_variables": ["string"],
        "independent_variable": "string — what we change",
        "dependent_variables": ["string — what we measure"]
      }
    }
  ],
  "reasoning_context": "string — explain how you used the research landscape to ground your hypotheses"
}`;

export const ENHANCED_BRAINSTORMER_USER_PROMPT = (
    paperContext: string,
    paperAnalysis: PaperAnalysis,
    codePath: CodePathAssessment,
    userMessage: string,
    previousHypotheses: BrainstormerOutput | null,
    refinementHistory: { message: string; timestamp: string }[],
    researchIntelligence: ResearchIntelligence
): string => {
    const { citation_graph, related_work, code_discovery } = researchIntelligence;

    // Build research landscape summary (truncated to fit context)
    const relatedPapersSummary = related_work.papers.slice(0, 8).map(p =>
        `- "${p.title}" (${p.year || '?'}, ${p.citation_count} citations${p.arxiv_id ? `, arXiv:${p.arxiv_id}` : ''})${p.abstract ? `\n  Abstract: ${p.abstract.substring(0, 150)}...` : ''}`
    ).join('\n');

    const highlyCitedRefs = citation_graph.highly_cited_references.slice(0, 5).map(r =>
        `- "${r.title}" (${r.year || '?'}, ${r.citation_count} citations${r.arxiv_id ? `, arXiv:${r.arxiv_id}` : ''})`
    ).join('\n');

    const recentCitations = citation_graph.recent_citations.slice(0, 5).map(c =>
        `- "${c.title}" (${c.year || '?'}, ${c.citation_count} citations)`
    ).join('\n');

    let prompt = `## PAPER CONTEXT
---
${paperContext}
---

## PARSED PAPER ANALYSIS
${JSON.stringify(paperAnalysis, null, 2)}

## CODE PATH ASSESSMENT
${JSON.stringify(codePath, null, 2)}

## RESEARCH LANDSCAPE (use this to ground your hypotheses)

### Related Papers (${related_work.papers.length} found)
${relatedPapersSummary || 'No related papers found.'}

### Key References (highly cited papers this work builds on)
${highlyCitedRefs || 'No highly cited references found.'}

### Recent Follow-up Work (papers citing this work)
- Total citations: ${citation_graph.total_citation_count}
- Influential citations: ${citation_graph.influential_citation_count}
${recentCitations || 'No recent citations found.'}

### Code Landscape
${code_discovery.total_repos_found > 0
        ? `Found ${code_discovery.total_repos_found} code repositories. Best repo: ${code_discovery.best_repo?.url || 'N/A'} (health: ${code_discovery.best_repo?.health_score || 0}/100)`
        : 'No code repositories found for this paper.'}

## USER REQUEST
${userMessage}`;

    if (previousHypotheses) {
        prompt += `\n\n## PREVIOUS HYPOTHESES (iterate on these based on user feedback)
${JSON.stringify(previousHypotheses, null, 2)}`;
    }

    if (refinementHistory.length > 1) {
        prompt += `\n\n## USER REFINEMENT HISTORY
${refinementHistory.map(r => `[${r.timestamp}] ${r.message}`).join('\n')}`;
    }

    prompt += `\n\nGenerate exactly 3 evidence-grounded hypotheses (one scale, one modality_shift, one architecture_ablation). Each MUST include evidence_basis, novelty_assessment, and experiment_design based on the RESEARCH LANDSCAPE above. Reference specific papers when possible.`;

    return prompt;
};
