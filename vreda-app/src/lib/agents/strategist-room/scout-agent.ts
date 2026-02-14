import { makeAgentCall } from './agent-call';
import { SCOUT_SYSTEM_PROMPT, SCOUT_USER_PROMPT, ENHANCED_SCOUT_SYSTEM_PROMPT, ENHANCED_SCOUT_USER_PROMPT } from './prompts/scout';
import type { PaperAnalysis, CodePathAssessment } from '@/types/strategist';
import type { ResearchIntelligence } from '@/types/research-intelligence';
import { logger } from '@/lib/logger';

/**
 * Scout Agent: Assesses code availability for a research paper.
 * Path A: Code/repo found — assesses quality, tech debt, reuse recommendation.
 * Path B: No code — maps formula-to-code gap with complexity estimates.
 *
 * When ResearchIntelligence is provided, uses REAL code discovery data
 * (Papers With Code + GitHub metrics) instead of just reading paper text.
 *
 * Validates output: Path B must have non-empty algorithms list (retries once if empty).
 */
export async function runScoutAgent(
    paperContext: string,
    paperAnalysis: PaperAnalysis,
    documentId: string,
    researchIntelligence?: ResearchIntelligence | null
): Promise<CodePathAssessment> {
    const hasRealCodeData = researchIntelligence?.code_discovery?.total_repos_found;

    const systemPrompt = hasRealCodeData
        ? ENHANCED_SCOUT_SYSTEM_PROMPT
        : SCOUT_SYSTEM_PROMPT;

    const userPrompt = researchIntelligence
        ? ENHANCED_SCOUT_USER_PROMPT(paperContext, paperAnalysis, researchIntelligence)
        : SCOUT_USER_PROMPT(paperContext, paperAnalysis);

    const call = () => makeAgentCall<CodePathAssessment>(
        'ScoutAgent',
        systemPrompt,
        userPrompt,
        { documentId },
        { temperature: 0.05 }
    );

    const result = await call();

    // Validate: Path B should always have algorithms to implement
    if (
        result.path === 'B' &&
        (!result.formula_to_code_gap?.algorithms_to_implement?.length)
    ) {
        logger.warn('Scout Agent returned Path B with empty algorithms, retrying', { documentId });
        const retry = await call();
        if (retry.path === 'B' && retry.formula_to_code_gap?.algorithms_to_implement?.length) {
            return retry;
        }
        logger.warn('Scout Agent retry also returned empty algorithms', { documentId });
    }

    return result;
}
