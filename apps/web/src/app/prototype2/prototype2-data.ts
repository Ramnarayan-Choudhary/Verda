export type WarRoomAgent = 'parser' | 'scout' | 'critic' | 'ranker' | 'accountant';
export type StrategistPhase =
  | 'ingest'
  | 'parse'
  | 'intelligence'
  | 'hypothesis'
  | 'budget'
  | 'manifest';
export type CriticVerdict = 'strong' | 'viable' | 'weak';
export type RankerVerdict = 'promote' | 'hold' | 'demote';
export type RiskLevel = 'low' | 'medium' | 'high';

export interface AgentEvent {
  id: string;
  at: string;
  agent: WarRoomAgent;
  phase: StrategistPhase;
  level: 'info' | 'ok' | 'warn';
  message: string;
  hypothesisIds: string[];
}

export interface DimensionScores {
  novelty: number;
  feasibility: number;
  impact: number;
  grounding: number;
  testability: number;
  clarity: number;
}

export interface WarRoomHypothesis {
  id: string;
  title: string;
  oneLiner: string;
  expectedOutcome: string;
  whyNow: string;
  gapTarget: string;
  evidenceRefs: string[];
  scores: DimensionScores;
  costUsd: number;
  estimatedHours: number;
  confidence: number;
  riskLevel: RiskLevel;
  criticVerdict: CriticVerdict;
  rankerVerdict: RankerVerdict;
  mitigation: string;
}

export interface ScenarioPreset {
  id: 'conservative' | 'balanced' | 'aggressive';
  label: string;
  description: string;
  budgetCapUsd: number;
  timeCapHours: number;
  computeProfile: string;
  adjustments: {
    novelty: number;
    feasibility: number;
    cost: number;
  };
}

export interface DecisionSnapshot {
  scenarioId: ScenarioPreset['id'];
  recommendedHypothesisId: string;
  runnerUpHypothesisId: string;
  reason: string;
  budgetEnvelope: string;
  riskEnvelope: string;
}

export const PIPELINE_TIMELINE: { id: StrategistPhase; label: string; state: 'done' | 'active' | 'pending' }[] = [
  { id: 'ingest', label: 'Ingest', state: 'done' },
  { id: 'parse', label: 'Parse', state: 'done' },
  { id: 'intelligence', label: 'Intelligence', state: 'done' },
  { id: 'hypothesis', label: 'Hypothesis', state: 'active' },
  { id: 'budget', label: 'Budget', state: 'pending' },
  { id: 'manifest', label: 'Manifest', state: 'pending' },
];

export const MISSION_BRIEF = {
  mission: 'Retrieval Cost Reduction for Scientific QA',
  paperPacket: 'arXiv:2602.23318 + 4 supporting papers',
  objective:
    'Produce one budget-safe hypothesis with measurable hallucination reduction while preserving answer quality.',
};

export const SCENARIOS: ScenarioPreset[] = [
  {
    id: 'conservative',
    label: 'Conservative',
    description: 'Optimize for reliability and low risk under strict budget controls.',
    budgetCapUsd: 25,
    timeCapHours: 18,
    computeProfile: '1x L4 equivalent',
    adjustments: { novelty: 0.1, feasibility: 0.45, cost: 0.45 },
  },
  {
    id: 'balanced',
    label: 'Balanced',
    description: 'Trade off novelty and feasibility while staying practical for solo execution.',
    budgetCapUsd: 40,
    timeCapHours: 28,
    computeProfile: '1x A10 equivalent',
    adjustments: { novelty: 0.3, feasibility: 0.4, cost: 0.3 },
  },
  {
    id: 'aggressive',
    label: 'Aggressive',
    description: 'Push novelty and impact with wider budget and experimentation room.',
    budgetCapUsd: 70,
    timeCapHours: 42,
    computeProfile: '1x A100 equivalent',
    adjustments: { novelty: 0.5, feasibility: 0.25, cost: 0.25 },
  },
];

export const HYPOTHESES: WarRoomHypothesis[] = [
  {
    id: 'h1',
    title: 'Dual-Critic Hallucination Guard',
    oneLiner:
      'Attach symbolic and semantic critics before final answer commit to catch unsupported claims.',
    expectedOutcome: '16-20% reduction in hallucination rate on long-form technical prompts.',
    whyNow:
      'Recent evidence shows critic disagreement is the strongest predictor of unstable scientific answers.',
    gapTarget: 'No low-cost verification stage for single-model inference in current literature.',
    evidenceRefs: ['E1', 'E3', 'E5'],
    scores: { novelty: 72, feasibility: 88, impact: 74, grounding: 86, testability: 90, clarity: 82 },
    costUsd: 18,
    estimatedHours: 14,
    confidence: 0.84,
    riskLevel: 'low',
    criticVerdict: 'strong',
    rankerVerdict: 'promote',
    mitigation: 'Limit critic pass to high-entropy spans to cap token overhead.',
  },
  {
    id: 'h2',
    title: 'Retrieval-Gated Distillation Trigger',
    oneLiner:
      'Use retrieval uncertainty to invoke distillation only where confidence dips, reducing unnecessary spend.',
    expectedOutcome: '30-35% token cost reduction with less than 1.5% quality drop.',
    whyNow:
      'Token spend spikes are concentrated in ambiguous sections where adaptive routing can gate expensive operations.',
    gapTarget: 'Sparse decision policies for distillation timing in RAG scientific tasks.',
    evidenceRefs: ['E2', 'E4'],
    scores: { novelty: 86, feasibility: 71, impact: 88, grounding: 77, testability: 78, clarity: 76 },
    costUsd: 34,
    estimatedHours: 24,
    confidence: 0.78,
    riskLevel: 'medium',
    criticVerdict: 'viable',
    rankerVerdict: 'promote',
    mitigation: 'Start with threshold sweeps using offline traces before online rollout.',
  },
  {
    id: 'h3',
    title: 'Citation-Neighborhood Curriculum',
    oneLiner:
      'Sequence training examples by citation proximity to prioritize foundational claims before edge cases.',
    expectedOutcome: 'Higher factual consistency and faster convergence on domain-specific evaluation sets.',
    whyNow:
      'Citation graph density is available and underused for curriculum ordering in scientific QA workflows.',
    gapTarget: 'Lack of graph-aware curriculum policy in scientist-facing copilots.',
    evidenceRefs: ['E1', 'E4', 'E6'],
    scores: { novelty: 80, feasibility: 79, impact: 82, grounding: 80, testability: 75, clarity: 79 },
    costUsd: 27,
    estimatedHours: 20,
    confidence: 0.8,
    riskLevel: 'medium',
    criticVerdict: 'viable',
    rankerVerdict: 'hold',
    mitigation: 'Use staged curriculum windows to avoid overfitting dense citation clusters.',
  },
  {
    id: 'h4',
    title: 'Constraint-Relaxed Error Stress Test',
    oneLiner:
      'Intentionally relax retrieval precision constraints to map where factual drift begins under pressure.',
    expectedOutcome: 'Sharper failure boundaries and better fallback routing rules.',
    whyNow:
      'No robust map exists for controlled degradation in today’s Strategist pipeline.',
    gapTarget: 'Missing stress-envelope characterization before manifest approval.',
    evidenceRefs: ['E3', 'E6'],
    scores: { novelty: 68, feasibility: 92, impact: 66, grounding: 72, testability: 86, clarity: 81 },
    costUsd: 16,
    estimatedHours: 10,
    confidence: 0.82,
    riskLevel: 'low',
    criticVerdict: 'strong',
    rankerVerdict: 'demote',
    mitigation: 'Run controlled subsets only; block escalation to production manifests.',
  },
];

export const AGENT_EVENTS: AgentEvent[] = [
  {
    id: 'E1',
    at: '20:32:10',
    agent: 'parser',
    phase: 'parse',
    level: 'ok',
    message: 'Parsed 12 variables and normalized claim taxonomy for hypothesis generator context.',
    hypothesisIds: ['h1', 'h3'],
  },
  {
    id: 'E2',
    at: '20:32:35',
    agent: 'scout',
    phase: 'intelligence',
    level: 'ok',
    message: 'Found two reusable pipelines for adaptive routing with compatible dependencies.',
    hypothesisIds: ['h2'],
  },
  {
    id: 'E3',
    at: '20:33:04',
    agent: 'critic',
    phase: 'hypothesis',
    level: 'warn',
    message: 'H2 flagged for sensitivity to retrieval threshold drift under noisy abstracts.',
    hypothesisIds: ['h2'],
  },
  {
    id: 'E4',
    at: '20:33:30',
    agent: 'ranker',
    phase: 'hypothesis',
    level: 'info',
    message: 'Boosted H2 for projected impact despite critic caution due to measurable cost gains.',
    hypothesisIds: ['h2', 'h3'],
  },
  {
    id: 'E5',
    at: '20:33:52',
    agent: 'accountant',
    phase: 'budget',
    level: 'ok',
    message: 'H1 fits free-tier adjacent budget envelope with narrow variance.',
    hypothesisIds: ['h1'],
  },
  {
    id: 'E6',
    at: '20:34:11',
    agent: 'critic',
    phase: 'hypothesis',
    level: 'info',
    message: 'H4 marked robust but lower upside; suggests fallback role in final manifest.',
    hypothesisIds: ['h4'],
  },
  {
    id: 'E7',
    at: '20:34:39',
    agent: 'ranker',
    phase: 'hypothesis',
    level: 'warn',
    message: 'Detected critic-ranker disagreement on H4 priority versus H2 expected utility.',
    hypothesisIds: ['h2', 'h4'],
  },
  {
    id: 'E8',
    at: '20:35:02',
    agent: 'accountant',
    phase: 'budget',
    level: 'info',
    message: 'Scenario sensitivity indicates conservative mode favors H1; aggressive mode favors H2.',
    hypothesisIds: ['h1', 'h2'],
  },
];

export const COMMAND_CHIPS = [
  'Re-rank with feasibility bias',
  'Stress-test cost',
  'Show critic objections',
];

export const AGENT_LABELS: Record<WarRoomAgent, string> = {
  parser: 'Parser',
  scout: 'Scout',
  critic: 'Critic',
  ranker: 'Ranker',
  accountant: 'Accountant',
};
