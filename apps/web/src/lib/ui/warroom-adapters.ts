import type { Message, PipelineStep } from '@/types';
import type { BrainstormerOutput, BudgetQuote, PaperAnalysis, EnhancedHypothesis, GeneratorOutput } from '@/types/strategist';
import type { QuestDomain, QuestEvent, QuestRoom } from '@/types/quest';

export type WarRoomChipState = 'pending' | 'active' | 'done';

export interface WarRoomEvent {
  id: string;
  room: QuestRoom;
  level: 'info' | 'warn' | 'success' | 'error';
  status: 'active' | 'done' | 'warning' | 'error';
  message: string;
  timestamp: string;
  hypothesisId?: string;
}

export interface WarRoomHypothesis {
  id: string;
  title: string;
  oneLiner: string;
  expected: string;
  whyNow: string;
  confidence: number;
  cost: string;
  risk: 'low' | 'medium' | 'high';
  scores: {
    novelty: number;
    feasibility: number;
    impact: number;
    grounding: number;
    testability: number;
    clarity: number;
  };
  whyThisOne: {
    evidenceAnchors: string[];
    constraintFit: string;
    riskCheck: string;
    rationale: string;
  };
}

export interface WarRoomSnapshot {
  roomStates: Record<QuestRoom, WarRoomChipState>;
  events: WarRoomEvent[];
  hypotheses: WarRoomHypothesis[];
  paperAnalysis: PaperAnalysis | null;
  paperSet: { id: string; title: string; detail: string }[];
}

const ALL_ROOMS: QuestRoom[] = ['library', 'hypothesis', 'experiment', 'results', 'writing'];

const STEP_ROOM_MAP: Record<PipelineStep, QuestRoom> = {
  metadata: 'library',
  download: 'library',
  upload_storage: 'library',
  extract_text: 'library',
  chunking: 'library',
  embedding: 'library',
  storing_chunks: 'library',
  research_intelligence: 'hypothesis',
  strategist: 'hypothesis',
};

function toIsoTime(input: string): string {
  const parsed = Date.parse(input);
  if (Number.isNaN(parsed)) return input;
  return new Date(parsed).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function deriveRisk(enhanced: EnhancedHypothesis | null, fallback?: import('@/types/strategist').Hypothesis): 'low' | 'medium' | 'high' {
  const verdict = enhanced?.critic_assessment?.verdict ?? fallback?.critic_assessment?.verdict;
  if (verdict === 'weak') return 'high';
  if (verdict === 'viable') return 'medium';
  return 'low';
}

function deriveWhyThisOne(
  enhanced: EnhancedHypothesis | null,
  fallback: import('@/types/strategist').Hypothesis,
  budget: BudgetQuote | null
): WarRoomHypothesis['whyThisOne'] {
  const supporting = enhanced?.evidence_basis?.supporting_papers ?? fallback.evidence_basis?.supporting_papers ?? [];
  const anchors = supporting.slice(0, 3).map((paper, idx) => `${idx + 1}. ${paper.title}`);

  const complexity = enhanced?.estimated_complexity ?? fallback.estimated_complexity;
  const freeTier = budget?.free_tier_compatible ? 'free-tier compatible' : 'may require paid resources';

  return {
    evidenceAnchors: anchors.length > 0 ? anchors : ['Evidence will populate after analysis and hypothesis generation.'],
    constraintFit: `Complexity: ${complexity}. Budget profile: ${freeTier}.`,
    riskCheck:
      enhanced?.critic_assessment?.feasibility_issues?.join(' ') ||
      fallback.critic_assessment?.feasibility_issues?.join(' ') ||
      'Primary risks are currently within acceptable bounds for prototype execution.',
    rationale:
      enhanced?.related_work_summary ||
      fallback.novelty_assessment?.what_is_new ||
      fallback.description,
  };
}

function getLatestBudget(messages: Message[]): BudgetQuote | null {
  const latest = [...messages]
    .reverse()
    .find((message) => message.metadata?.type === 'budget_quote' && message.metadata?.budget_quote);
  return latest?.metadata?.budget_quote ?? null;
}

function getLatestPaperAnalysis(messages: Message[]): PaperAnalysis | null {
  const latest = [...messages]
    .reverse()
    .find((message) => message.metadata?.type === 'paper_analysis' && message.metadata?.paper_analysis);
  return latest?.metadata?.paper_analysis ?? null;
}

function getLatestHypothesisPayload(messages: Message[]): {
  brainstormer: BrainstormerOutput | null;
  pipeline: GeneratorOutput | null;
} {
  const latest = [...messages]
    .reverse()
    .find((message) => message.metadata?.type === 'hypothesis_options' && message.metadata?.brainstormer_output);

  return {
    brainstormer: latest?.metadata?.brainstormer_output ?? null,
    pipeline: latest?.metadata?.hypothesis_pipeline_output ?? null,
  };
}

export function deriveWarRoomSnapshot(messages: Message[], questEvents: QuestEvent[]): WarRoomSnapshot {
  const paperAnalysis = getLatestPaperAnalysis(messages);
  const latestBudget = getLatestBudget(messages);
  const { brainstormer, pipeline } = getLatestHypothesisPayload(messages);

  const enhancedById = new Map<string, EnhancedHypothesis>();
  for (const hypothesis of pipeline?.hypotheses ?? []) {
    enhancedById.set(hypothesis.id, hypothesis);
  }

  const hypotheses: WarRoomHypothesis[] = (brainstormer?.hypotheses ?? []).map((hypothesis) => {
    const enhanced = enhancedById.get(hypothesis.id) ?? null;
    const cost = latestBudget && latestBudget.hypothesis_id === hypothesis.id
      ? `$${latestBudget.summary.total_usd.toFixed(4)}`
      : 'Pending';

    return {
      id: hypothesis.id,
      title: hypothesis.title,
      oneLiner: enhanced?.short_hypothesis || hypothesis.description,
      expected: hypothesis.expected_outcome,
      whyNow: enhanced?.evidence_basis?.key_insight || hypothesis.evidence_basis?.key_insight || hypothesis.description,
      confidence: Number(((enhanced?.scores.grounding ?? hypothesis.confidence * 100) / 100).toFixed(2)),
      cost,
      risk: deriveRisk(enhanced, hypothesis),
      scores: {
        novelty: enhanced?.scores.novelty ?? Math.round((hypothesis.novelty_assessment?.novelty_score ?? 0.5) * 100),
        feasibility: enhanced?.scores.feasibility ?? Math.round(hypothesis.feasibility_score * 100),
        impact: enhanced?.scores.impact ?? 70,
        grounding: enhanced?.scores.grounding ?? Math.round(hypothesis.confidence * 100),
        testability: enhanced?.scores.testability ?? 72,
        clarity: enhanced?.scores.clarity ?? 74,
      },
      whyThisOne: deriveWhyThisOne(enhanced, hypothesis, latestBudget),
    };
  });

  const paperSet: WarRoomSnapshot['paperSet'] = paperAnalysis
    ? [
        {
          id: 'paper-primary',
          title: paperAnalysis.title,
          detail: `${paperAnalysis.domain.toUpperCase()} · ${paperAnalysis.authors.slice(0, 2).join(', ')}`,
        },
        ...paperAnalysis.key_claims.slice(0, 2).map((claim, idx) => ({
          id: `claim-${idx}`,
          title: `Claim ${idx + 1}`,
          detail: claim,
        })),
        ...paperAnalysis.datasets.slice(0, 1).map((dataset, idx) => ({
          id: `dataset-${idx}`,
          title: `Dataset: ${dataset.name}`,
          detail: `${dataset.size} · ${dataset.source}`,
        })),
      ]
    : [
        {
          id: 'paper-empty',
          title: 'No evidence loaded yet',
          detail: 'Upload a PDF or fetch an arXiv paper to populate the evidence map.',
        },
      ];

  const apiEvents: WarRoomEvent[] = questEvents.map((event) => ({
    id: event.id,
    room: event.room,
    level: event.level,
    status: event.status,
    message: event.message,
    timestamp: toIsoTime(event.created_at),
    hypothesisId: typeof event.metadata?.hypothesis_id === 'string' ? (event.metadata.hypothesis_id as string) : undefined,
  }));

  const fallbackEvents: WarRoomEvent[] = [];

  for (const message of messages) {
    if (message.metadata?.type === 'pipeline_progress' && message.metadata.pipeline_events) {
      for (const [index, event] of message.metadata.pipeline_events.entries()) {
        const room = event.step ? STEP_ROOM_MAP[event.step] : 'library';
        const level = event.type === 'warning' ? 'warn' : event.type === 'error' ? 'error' : event.type === 'complete' ? 'success' : 'info';
        const status = event.type === 'warning' ? 'warning' : event.type === 'error' ? 'error' : event.type === 'complete' ? 'done' : 'active';

        fallbackEvents.push({
          id: `${message.id}-pipeline-${index}`,
          room,
          level,
          status,
          message: event.message,
          timestamp: toIsoTime(message.created_at),
        });
      }
    }

    if (message.metadata?.type === 'hypothesis_options') {
      fallbackEvents.push({
        id: `${message.id}-hypothesis-options`,
        room: 'hypothesis',
        level: 'success',
        status: 'done',
        message: 'Hypothesis options are ready for review.',
        timestamp: toIsoTime(message.created_at),
      });
    }

    if (message.metadata?.type === 'paper_analysis') {
      fallbackEvents.push({
        id: `${message.id}-paper-analysis`,
        room: 'library',
        level: 'success',
        status: 'done',
        message: 'Paper analysis completed and evidence packet is ready.',
        timestamp: toIsoTime(message.created_at),
      });
    }

    if (message.metadata?.type === 'literature_search') {
      fallbackEvents.push({
        id: `${message.id}-literature-search`,
        room: 'library',
        level: 'info',
        status: 'done',
        message: 'Literature search results are available for import.',
        timestamp: toIsoTime(message.created_at),
      });
    }

    if (message.metadata?.type === 'error') {
      fallbackEvents.push({
        id: `${message.id}-error`,
        room: 'library',
        level: 'error',
        status: 'error',
        message: message.content.replace(/\*\*/g, '').slice(0, 180),
        timestamp: toIsoTime(message.created_at),
      });
    }

    if (message.metadata?.type === 'budget_quote') {
      fallbackEvents.push({
        id: `${message.id}-budget-quote`,
        room: 'hypothesis',
        level: 'success',
        status: 'done',
        message: 'Budget estimate generated for selected hypothesis.',
        timestamp: toIsoTime(message.created_at),
        hypothesisId: message.metadata.budget_quote?.hypothesis_id,
      });
    }

    if (message.metadata?.type === 'enhanced_manifest') {
      fallbackEvents.push({
        id: `${message.id}-manifest`,
        room: 'writing',
        level: 'success',
        status: 'done',
        message: 'Manifest finalized and approved.',
        timestamp: toIsoTime(message.created_at),
      });
    }
  }

  const events = apiEvents.length > 0 ? apiEvents : fallbackEvents;

  const roomStates: Record<QuestRoom, WarRoomChipState> = {
    library: 'pending',
    hypothesis: 'pending',
    experiment: 'pending',
    results: 'pending',
    writing: 'pending',
  };

  for (const room of ALL_ROOMS) {
    const roomEvents = events.filter((event) => event.room === room);
    if (roomEvents.length === 0) continue;

    const hasActive = roomEvents.some((event) => event.status === 'active' || event.status === 'warning' || event.status === 'error');
    const hasDone = roomEvents.some((event) => event.status === 'done');

    roomStates[room] = hasActive ? 'active' : hasDone ? 'done' : 'pending';
  }

  return {
    roomStates,
    events,
    hypotheses,
    paperAnalysis,
    paperSet,
  };
}

export function getDomainLabel(domain?: QuestDomain): string {
  switch (domain) {
    case 'comp_bio':
      return 'Computational Biology';
    case 'simulation':
      return 'Simulation';
    case 'drug_discovery':
      return 'Drug Discovery';
    case 'ai_ml':
    default:
      return 'AI/ML';
  }
}
