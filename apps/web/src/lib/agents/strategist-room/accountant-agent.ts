import { makeAgentCall } from './agent-call';
import { ACCOUNTANT_SYSTEM_PROMPT, ACCOUNTANT_USER_PROMPT } from './prompts/accountant';
import type {
    PaperAnalysis,
    CodePathAssessment,
    Hypothesis,
    BudgetQuote,
} from '@/types/strategist';

/**
 * Accountant Agent: Estimates computational budget for a selected hypothesis.
 * Calculates: token costs, compute costs, API costs, storage costs.
 * Includes 20% contingency and free-tier compatibility check.
 */
export async function runAccountantAgent(
    paperAnalysis: PaperAnalysis,
    codePath: CodePathAssessment,
    selectedHypothesis: Hypothesis,
    documentId: string
): Promise<BudgetQuote> {
    return makeAgentCall<BudgetQuote>(
        'AccountantAgent',
        ACCOUNTANT_SYSTEM_PROMPT,
        ACCOUNTANT_USER_PROMPT(paperAnalysis, codePath, selectedHypothesis),
        { documentId, hypothesisId: selectedHypothesis.id },
        { temperature: 0.1, maxTokens: 2400 }
    );
}
