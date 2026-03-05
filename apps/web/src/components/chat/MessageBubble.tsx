'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ManifestCard from './ManifestCard';
import PaperAnalysisCard from './PaperAnalysisCard';
import CodePathCard from './CodePathCard';
import HypothesisSelector from './HypothesisSelector';
import BudgetCard from './BudgetCard';
import PaperSearchCard from './PaperSearchCard';
import PipelineProgressCard from './PipelineProgressCard';
import type { Message } from '@/types';
import type { PaperMetadata } from '@/lib/literature/types';
import { User, Bot } from 'lucide-react';

interface MessageBubbleProps {
    message: Message;
    onSelectHypothesis?: (hypothesisId: string) => void;
    onRefineHypotheses?: (message: string, hypothesisEngine: 'gpt' | 'claude') => void;
    onApproveBudget?: () => void;
    onImportPaper?: (paper: PaperMetadata) => void;
    importingPaper?: string | null;
    strategistLoading?: boolean;
}

export default function MessageBubble({
    message,
    onSelectHypothesis,
    onRefineHypotheses,
    onApproveBudget,
    onImportPaper,
    importingPaper,
    strategistLoading = false,
}: MessageBubbleProps) {
    const isUser = message.role === 'user';
    const metaType = message.metadata?.type;

    return (
        <div className={`message ${isUser ? 'user' : 'assistant'}`}>
            <div className="message-avatar">
                {isUser ? <User size={16} /> : <Bot size={16} />}
            </div>
            <div className="message-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                </ReactMarkdown>

                {/* Legacy Research Manifest */}
                {metaType === 'research_manifest' && message.metadata?.manifest && (
                    <ManifestCard manifest={message.metadata.manifest} />
                )}

                {/* Paper Analysis + Code Path (shown together) */}
                {metaType === 'paper_analysis' && message.metadata?.paper_analysis && (
                    <>
                        <PaperAnalysisCard analysis={message.metadata.paper_analysis} />
                        {message.metadata.code_path && (
                            <div style={{ marginTop: 8 }}>
                                <CodePathCard codePath={message.metadata.code_path} />
                            </div>
                        )}
                    </>
                )}

                {/* Hypothesis Options */}
                {metaType === 'hypothesis_options' && message.metadata?.brainstormer_output && (
                    <HypothesisSelector
                        brainstormerOutput={message.metadata.brainstormer_output}
                        pipelineOutput={message.metadata.hypothesis_pipeline_output}
                        onSelect={onSelectHypothesis || (() => {})}
                        onRefine={onRefineHypotheses || (() => {})}
                        disabled={strategistLoading}
                    />
                )}

                {/* Budget Quote */}
                {metaType === 'budget_quote' && message.metadata?.budget_quote && (
                    <BudgetCard
                        budget={message.metadata.budget_quote}
                        onApprove={onApproveBudget || (() => {})}
                        disabled={strategistLoading}
                    />
                )}

                {/* Enhanced Manifest (approved) — render as legacy ManifestCard */}
                {metaType === 'enhanced_manifest' && message.metadata?.enhanced_manifest && (
                    <ManifestCard manifest={{
                        hypothesis: message.metadata.enhanced_manifest.hypothesis.title,
                        variables: {
                            independent: message.metadata.enhanced_manifest.execution_plan.steps.map(s => s.description),
                            dependent: [],
                            controlled: [],
                        },
                        libraries: message.metadata.enhanced_manifest.code_path.code_found?.dependencies
                            || message.metadata.enhanced_manifest.code_path.formula_to_code_gap?.required_libraries
                            || [],
                        budget_estimate: {
                            tokens_used: message.metadata.enhanced_manifest.budget.token_costs.total_tokens,
                            estimated_cost_usd: message.metadata.enhanced_manifest.budget.summary.total_usd,
                        },
                        execution_steps: message.metadata.enhanced_manifest.execution_plan.steps.map(s => s.description),
                        anti_gravity_check: message.metadata.enhanced_manifest.anti_gravity_check,
                    }} />
                )}

                {/* Literature Search Results */}
                {metaType === 'literature_search' && message.metadata?.search_results && (
                    <PaperSearchCard
                        papers={message.metadata.search_results}
                        query={message.metadata.search_query || ''}
                        onImport={onImportPaper || (() => {})}
                        importing={importingPaper}
                    />
                )}

                {/* Pipeline Progress (live streaming) */}
                {metaType === 'pipeline_progress' && message.metadata?.pipeline_events && (
                    <PipelineProgressCard
                        events={message.metadata.pipeline_events}
                        title={message.metadata.pipeline_title || 'Processing...'}
                    />
                )}
            </div>
        </div>
    );
}
