import { makeAgentCall } from './agent-call';
import { BRAINSTORMER_SYSTEM_PROMPT, BRAINSTORMER_USER_PROMPT, ENHANCED_BRAINSTORMER_SYSTEM_PROMPT, ENHANCED_BRAINSTORMER_USER_PROMPT } from './prompts/brainstormer';
import type {
    PaperAnalysis,
    CodePathAssessment,
    BrainstormerOutput,
} from '@/types/strategist';
import type { ResearchIntelligence } from '@/types/research-intelligence';

/**
 * Brainstormer Agent: Generates 3 forward hypotheses for a research paper.
 * Types: Scale, Modality-Shift, Architecture-Ablation.
 *
 * When ResearchIntelligence is provided, generates evidence-grounded hypotheses
 * with novelty assessment, experiment design, and references to related work.
 *
 * Supports conversational refinement — takes previous hypotheses and user feedback.
 */
export async function runBrainstormerAgent(
    paperContext: string,
    paperAnalysis: PaperAnalysis,
    codePath: CodePathAssessment,
    userMessage: string,
    previousHypotheses: BrainstormerOutput | null,
    refinementHistory: { message: string; timestamp: string }[],
    documentId: string,
    researchIntelligence?: ResearchIntelligence | null
): Promise<BrainstormerOutput> {
    const hasIntelligence = researchIntelligence &&
        (researchIntelligence.related_work.papers.length > 0 ||
         researchIntelligence.citation_graph.reference_count > 0);

    const systemPrompt = hasIntelligence
        ? ENHANCED_BRAINSTORMER_SYSTEM_PROMPT
        : BRAINSTORMER_SYSTEM_PROMPT;

    const userPrompt = hasIntelligence
        ? ENHANCED_BRAINSTORMER_USER_PROMPT(
            paperContext,
            paperAnalysis,
            codePath,
            userMessage,
            previousHypotheses,
            refinementHistory,
            researchIntelligence!
        )
        : BRAINSTORMER_USER_PROMPT(
            paperContext,
            paperAnalysis,
            codePath,
            userMessage,
            previousHypotheses,
            refinementHistory
        );

    return makeAgentCall<BrainstormerOutput>(
        'BrainstormerAgent',
        systemPrompt,
        userPrompt,
        { documentId },
        { temperature: 0.7 }
    );
}
