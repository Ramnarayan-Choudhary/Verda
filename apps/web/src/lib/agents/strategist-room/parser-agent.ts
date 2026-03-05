import { makeAgentCall } from './agent-call';
import { PARSER_SYSTEM_PROMPT, PARSER_USER_PROMPT } from './prompts/parser';
import type { PaperAnalysis } from '@/types/strategist';

/**
 * Parser Agent: Extracts structured information from a research paper.
 * Returns title, authors, equations, architecture, datasets, metrics, claims, and hallucination risk.
 */
export async function runParserAgent(
    paperContext: string,
    documentId: string
): Promise<PaperAnalysis> {
    return makeAgentCall<PaperAnalysis>(
        'ParserAgent',
        PARSER_SYSTEM_PROMPT,
        PARSER_USER_PROMPT(paperContext),
        { documentId },
        { temperature: 0.1, maxTokens: 2800 }
    );
}
