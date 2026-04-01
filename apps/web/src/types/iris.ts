/** IRIS (Interactive Research Ideation System) type definitions */

export interface IrisReviewScores {
    novelty?: number;
    clarity?: number;
    feasibility?: number;
    effectiveness?: number;
    impact?: number;
}

export interface IrisReviewFeedback {
    [aspect: string]: string;
}

export interface IrisMCTSNodeState {
    current_idea: string;
    depth: number;
    reward: number;
    hasReviews?: boolean;
    hasRetrieval?: boolean;
    hasFeedback?: boolean;
    isResearchGoal?: boolean;
    isCurrentNode?: boolean;
}

export interface IrisMCTSTreeNode {
    id: string;
    action: string;
    idea?: string;
    depth: number;
    reward: number;
    value: number;
    visits: number;
    isCurrentNode?: boolean;
    state: IrisMCTSNodeState;
    reviews?: {
        scores: IrisReviewScores;
        feedback?: IrisReviewFeedback;
        summary?: IrisReviewFeedback;
    } | null;
    children: IrisMCTSTreeNode[];
}

export interface IrisChatResponse {
    messages: Array<{ role: string; content: string }>;
    idea: string;
    initial_proposal?: string;
    review_scores?: IrisReviewScores;
    average_score?: number;
    input_mode?: 'paper_query' | 'query_only';
}

export interface IrisStepResponse {
    idea: string;
    nodeId?: string;
    action?: string;
    depth?: number;
    visits?: number;
    value?: number;
    review_scores?: IrisReviewScores;
    average_score?: number;
    messages?: Array<{ role: string; content: string }>;
}

export interface IrisReviewAspectData {
    aspect: string;
    score: number;
    summary?: string;
    feedback?: string;
    highlights?: Array<{
        text: string;
        category: string;
        review: string;
    }>;
}

export interface IrisKnowledgeSection {
    title: string;
    summary: string;
    content: string;
    citations?: Array<{
        id?: string;
        title: string;
        authors?: string[];
        year?: string;
        url?: string;
    }>;
}

export const IRIS_REVIEW_ASPECTS = [
    'lack_of_novelty',
    'assumptions',
    'vagueness',
    'feasibility_and_practicality',
    'overgeneralization',
    'overstatement',
    'evaluation_and_validation_issues',
    'justification_for_methods',
    'reproducibility',
    'contradictory_statements',
    'impact',
    'alignment',
    'ethical_and_social_considerations',
    'robustness',
] as const;

export type IrisReviewAspect = (typeof IRIS_REVIEW_ASPECTS)[number];

/** Node action color mapping for tree visualization */
export const IRIS_ACTION_COLORS: Record<string, string> = {
    research_goal: '#3b82f6',
    generate: '#4ade80',
    first_idea: '#4ade80',
    review_and_refine: '#fb923c',
    retrieve_and_refine: '#fbbf24',
    reflect_and_reframe: '#a78bfa',
    refresh_idea: '#22d3ee',
};
