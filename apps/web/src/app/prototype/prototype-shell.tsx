'use client';

import { useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent } from 'react';
import {
  Bot,
  ChevronRight,
  CircleDot,
  FileText,
  FlaskConical,
  Lightbulb,
  Moon,
  Orbit,
  Search,
  ShieldCheck,
  Sparkles,
  Sun,
  Upload,
  Workflow,
} from 'lucide-react';
import styles from './prototype.module.css';

type CanvasTab = 'evidence' | 'arena' | 'execution' | 'manifest';
type ThemeMode = 'light' | 'dark';
type RoomId = 'library' | 'hypothesis' | 'experiment' | 'results' | 'writing';
type EventLevel = 'info' | 'warn' | 'success';
type RoomState = 'pending' | 'active' | 'done';
type QuestDomain = 'ai_ml' | 'comp_bio' | 'simulation' | 'drug_discovery';
type ComposerIntakeAction = 'upload_pdf' | 'fetch_arxiv';

interface PrototypeShellProps {
  fontVars: string;
}

interface WhyThisOne {
  evidenceAnchors: string[];
  constraintFit: string;
  riskCheck: string;
  rationale: string;
}

interface Hypothesis {
  id: string;
  title: string;
  oneLiner: string;
  expected: string;
  whyNow: string;
  whyThisOne: WhyThisOne;
  cost: string;
  confidence: number;
  risk: 'low' | 'medium' | 'high';
  scores: {
    novelty: number;
    feasibility: number;
    impact: number;
    grounding: number;
    testability: number;
    clarity: number;
  };
  refinementCount: number;
  lastRefinement: string | null;
}

interface AgentEvent {
  id: string;
  time: string;
  room: RoomId;
  level: EventLevel;
  roomState: Exclude<RoomState, 'pending'>;
  message: string;
  hypothesisId?: string;
}

interface QuestHistoryItem {
  id: string;
  title: string;
  domain: QuestDomain;
  updatedAt: string;
  roomStateSummary: Record<RoomId, RoomState>;
}

interface DomainSeed {
  hypotheses: Hypothesis[];
  events: AgentEvent[];
  paperSet: { id: string; title: string; detail: string }[];
  commandChips: string[];
}

const roomTracks: { id: RoomId; label: string }[] = [
  { id: 'library', label: 'Library' },
  { id: 'hypothesis', label: 'Hypothesis Arena' },
  { id: 'experiment', label: 'Experiment' },
  { id: 'results', label: 'Results & Data Analysis' },
  { id: 'writing', label: 'Paper Writing' },
];

const domainLabels: Record<QuestDomain, string> = {
  ai_ml: 'AI/ML',
  comp_bio: 'Computational Biology',
  simulation: 'Simulation',
  drug_discovery: 'Drug Discovery',
};

const defaultRoomStateSummary: Record<RoomId, RoomState> = {
  library: 'pending',
  hypothesis: 'pending',
  experiment: 'pending',
  results: 'pending',
  writing: 'pending',
};

const initialQuestHistory: QuestHistoryItem[] = [
  {
    id: 'q-ai-01',
    title: 'Retrieval Cost Stabilization',
    domain: 'ai_ml',
    updatedAt: '2m ago',
    roomStateSummary: {
      library: 'done',
      hypothesis: 'active',
      experiment: 'pending',
      results: 'pending',
      writing: 'pending',
    },
  },
  {
    id: 'q-bio-01',
    title: 'Cell Signaling Perturbation',
    domain: 'comp_bio',
    updatedAt: '18m ago',
    roomStateSummary: {
      library: 'done',
      hypothesis: 'done',
      experiment: 'active',
      results: 'pending',
      writing: 'pending',
    },
  },
  {
    id: 'q-sim-01',
    title: 'Turbulence Runtime Envelope',
    domain: 'simulation',
    updatedAt: '1h ago',
    roomStateSummary: {
      library: 'done',
      hypothesis: 'done',
      experiment: 'done',
      results: 'active',
      writing: 'pending',
    },
  },
  {
    id: 'q-drug-01',
    title: 'Lead Prioritization Frontier',
    domain: 'drug_discovery',
    updatedAt: '4h ago',
    roomStateSummary: {
      library: 'done',
      hypothesis: 'done',
      experiment: 'done',
      results: 'done',
      writing: 'active',
    },
  },
];

const seededDataByDomain: Record<QuestDomain, DomainSeed> = {
  ai_ml: {
    hypotheses: [
      {
        id: 'h1',
        title: 'Adaptive Retrieval-Gated Distillation',
        oneLiner: 'Trigger expensive distillation only when retrieval entropy crosses uncertainty threshold.',
        expected: 'Reduce token spend while preserving answer quality on scientific QA benchmarks.',
        whyNow: 'Current spending spikes cluster around uncertain contexts where adaptive gating is most effective.',
        whyThisOne: {
          evidenceAnchors: [
            'E-12: entropy spikes align with low confidence windows in 3 benchmark runs.',
            'E-21: 22% of total cost is concentrated in the final 14% of generation steps.',
            'E-34: critic notes gating threshold is controllable via existing evaluator hooks.',
          ],
          constraintFit: 'Fits 72-hour window and the current GPU cap by reusing existing retrieval/evaluator pipeline.',
          riskCheck: 'Risk: threshold instability on long contexts. Mitigation: enforce rollback checkpoint and safe fallback.',
          rationale: 'Best near-term ROI with measurable quality guardrails and low integration risk.',
        },
        cost: '$38',
        confidence: 0.78,
        risk: 'medium',
        scores: {
          novelty: 82,
          feasibility: 74,
          impact: 86,
          grounding: 76,
          testability: 81,
          clarity: 79,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h2',
        title: 'Citation-Neighborhood Curriculum',
        oneLiner: 'Order training examples by citation proximity to improve factual convergence speed.',
        expected: 'Improve consistency and reduce contradiction rates with lower training cycles.',
        whyNow: 'Citation graph context already exists in the pipeline but is unused as a training signal.',
        whyThisOne: {
          evidenceAnchors: [
            'E-07: citation adjacency correlates with fewer contradictory completions in prior runs.',
            'E-29: ranked context windows show lower drift in topological clusters.',
            'E-41: parser and scout outputs share stable entity lineage map.',
          ],
          constraintFit: 'Requires only ranking logic and dataset ordering changes; no extra infra purchase.',
          riskCheck: 'Risk: overfitting to narrow literature clusters. Mitigation: add held-out cross-cluster validation.',
          rationale: 'Strong grounding and high feasibility make it a reliable baseline-upgrade path.',
        },
        cost: '$24',
        confidence: 0.81,
        risk: 'low',
        scores: {
          novelty: 77,
          feasibility: 86,
          impact: 79,
          grounding: 84,
          testability: 78,
          clarity: 82,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h3',
        title: 'Dual-Critic Hallucination Guard',
        oneLiner: 'Apply symbolic + semantic critic checks before final response commit.',
        expected: 'Lower hallucination rate in long-form answers under noisy retrieval conditions.',
        whyNow: 'Critic disagreement has emerged as a reliable predictor for unstable outputs.',
        whyThisOne: {
          evidenceAnchors: [
            'E-09: symbolic checker catches unit/logic mismatches missed by semantic reviewer.',
            'E-31: critic disagreement predicts 67% of failed fact checks.',
            'E-43: verification prompts are already available for reuse in this stage.',
          ],
          constraintFit: 'Integrates in existing critic stage with low additional runtime.',
          riskCheck: 'Risk: false positives may suppress valid outputs. Mitigation: confidence threshold tuning.',
          rationale: 'Most defensible safety gain with immediate product trust impact.',
        },
        cost: '$17',
        confidence: 0.85,
        risk: 'low',
        scores: {
          novelty: 69,
          feasibility: 89,
          impact: 74,
          grounding: 88,
          testability: 90,
          clarity: 83,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h4',
        title: 'Constraint-Relaxed Error Envelope',
        oneLiner: 'Relax retrieval precision in controlled stages to map factual drift boundaries.',
        expected: 'Produce precise failure envelopes for safer manifest decisions and fallback policies.',
        whyNow: 'We still lack controlled stress boundaries before committing to final experiment manifests.',
        whyThisOne: {
          evidenceAnchors: [
            'E-14: drift rises sharply after top-k retrieval is reduced below 6.',
            'E-27: previous manifests failed without explicit envelope thresholds.',
            'E-39: accountant budget model can absorb staged perturbation cost.',
          ],
          constraintFit: 'Single test sweep can run within current budget and weekend execution window.',
          riskCheck: 'Risk: noisy outcomes if stress intervals are too coarse. Mitigation: use fixed perturbation increments.',
          rationale: 'Improves decision safety by quantifying failure boundaries before deployment.',
        },
        cost: '$21',
        confidence: 0.8,
        risk: 'medium',
        scores: {
          novelty: 73,
          feasibility: 83,
          impact: 71,
          grounding: 80,
          testability: 87,
          clarity: 77,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
    ],
    events: [
      {
        id: 'e1',
        time: '20:32:04',
        room: 'library',
        level: 'info',
        roomState: 'active',
        message: 'Library ingest started for arXiv:2602.23318 and linked references.',
      },
      {
        id: 'e2',
        time: '20:32:48',
        room: 'library',
        level: 'success',
        roomState: 'done',
        message: 'Parse, storage, and index sync completed for research packet.',
      },
      {
        id: 'e3',
        time: '20:33:10',
        room: 'hypothesis',
        level: 'info',
        roomState: 'active',
        message: 'Hypothesis intelligence merged from citation graph and repository signal.',
        hypothesisId: 'h2',
      },
      {
        id: 'e4',
        time: '20:33:41',
        room: 'hypothesis',
        level: 'warn',
        roomState: 'active',
        message: 'Critic flagged threshold sensitivity for Adaptive Retrieval-Gated Distillation.',
        hypothesisId: 'h1',
      },
      {
        id: 'e5',
        time: '20:34:06',
        room: 'hypothesis',
        level: 'success',
        roomState: 'done',
        message: 'Top-4 hypotheses ranked with budget-ready scoring metadata.',
      },
      {
        id: 'e6',
        time: '20:34:30',
        room: 'experiment',
        level: 'info',
        roomState: 'active',
        message: 'Experiment draft initialized with baseline and rollback checkpoints.',
        hypothesisId: 'h3',
      },
      {
        id: 'e7',
        time: '20:34:56',
        room: 'experiment',
        level: 'success',
        roomState: 'done',
        message: 'Experiment setup validated and queued for execution readiness.',
      },
      {
        id: 'e8',
        time: '20:35:12',
        room: 'results',
        level: 'info',
        roomState: 'active',
        message: 'Results and data analysis stream started for variance and drift checks.',
      },
      {
        id: 'e9',
        time: '20:35:36',
        room: 'results',
        level: 'success',
        roomState: 'done',
        message: 'Result analytics completed with anomaly and confidence summaries.',
      },
      {
        id: 'e10',
        time: '20:35:58',
        room: 'writing',
        level: 'info',
        roomState: 'active',
        message: 'Paper writing scaffold generated with linked evidence and citation placeholders.',
      },
      {
        id: 'e11',
        time: '20:36:20',
        room: 'writing',
        level: 'success',
        roomState: 'done',
        message: 'Writing package finalized with manifest-aligned claims and caveats.',
      },
    ],
    paperSet: [
      { id: 'p1', title: 'Primary Paper', detail: 'arXiv:2602.23318 · 12 chunks indexed · parser complete' },
      { id: 'p2', title: 'Support Evidence 01', detail: 'Semantic Scholar pull · 2 contradictory findings tagged' },
      { id: 'p3', title: 'Support Evidence 02', detail: 'PWC reference path · repo health score 82' },
      { id: 'p4', title: 'Support Evidence 03', detail: 'Citation cluster map · 19 linked references' },
    ],
    commandChips: [
      'Import arXiv: 2602.23318',
      'Generate 5 new hypotheses',
      'Run budget simulation',
      'Compare top 2 hypotheses',
    ],
  },
  comp_bio: {
    hypotheses: [
      {
        id: 'h1',
        title: 'Pathway-Aware Perturbation Ranking',
        oneLiner: 'Prioritize perturbations by pathway centrality and known compensatory routes.',
        expected: 'Increase hit-rate of biologically plausible hypotheses under limited wet-lab cycles.',
        whyNow: 'Current candidate ranking is signal-rich but pathway context is underused.',
        whyThisOne: {
          evidenceAnchors: [
            'E-03: key signaling nodes recur across top differential-expression studies.',
            'E-16: pathway overlap explains 61% of prior assay wins.',
            'E-28: knowledge graph already encodes ligand-receptor and pathway links.',
          ],
          constraintFit: 'Fits low-compute profile and narrows expensive assay candidates early.',
          riskCheck: 'Risk: pathway databases may contain stale entries. Mitigation: cross-source consensus filter.',
          rationale: 'Best grounded route to reduce false leads before lab handoff.',
        },
        cost: '$41',
        confidence: 0.79,
        risk: 'medium',
        scores: {
          novelty: 75,
          feasibility: 78,
          impact: 88,
          grounding: 84,
          testability: 72,
          clarity: 80,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h2',
        title: 'Cross-Cellline Response Calibration',
        oneLiner: 'Calibrate candidate scoring by inter-cellline response variance before ranking.',
        expected: 'Reduce single-line bias and improve transferability to broader biological contexts.',
        whyNow: 'Recent datasets show drift when models are trained on one dominant cellline.',
        whyThisOne: {
          evidenceAnchors: [
            'E-10: baseline model confidence drops 18% on unseen cellline cohorts.',
            'E-18: variance-aware weighting improved external validation in archived runs.',
            'E-30: available metadata supports fast variance bucket creation.',
          ],
          constraintFit: 'Pure data-layer calibration, no new wet-lab dependency.',
          riskCheck: 'Risk: noisy metadata may overcorrect ranking. Mitigation: min-sample threshold per bucket.',
          rationale: 'Improves robustness with minimal implementation overhead.',
        },
        cost: '$26',
        confidence: 0.83,
        risk: 'low',
        scores: {
          novelty: 72,
          feasibility: 87,
          impact: 81,
          grounding: 86,
          testability: 77,
          clarity: 84,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h3',
        title: 'Assay Noise Rejection Envelope',
        oneLiner: 'Learn assay-specific noise envelopes to filter unstable biological readouts.',
        expected: 'Lower false-positive progression into expensive follow-up experiments.',
        whyNow: 'Noise signatures are present in historical runs but not used in triage decisions.',
        whyThisOne: {
          evidenceAnchors: [
            'E-08: three assays contribute most variance outliers in current pipeline.',
            'E-24: critic observed instability patterns tied to assay batches.',
            'E-37: repeatability metadata is sufficient for envelope fitting.',
          ],
          constraintFit: 'Uses existing results logs and can be tested in one sprint.',
          riskCheck: 'Risk: aggressive filtering may hide weak true positives. Mitigation: dual-threshold review lane.',
          rationale: 'Directly cuts expensive downstream noise while preserving exploratory coverage.',
        },
        cost: '$19',
        confidence: 0.82,
        risk: 'low',
        scores: {
          novelty: 68,
          feasibility: 88,
          impact: 76,
          grounding: 87,
          testability: 89,
          clarity: 80,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h4',
        title: 'Mechanism-First Replication Ladder',
        oneLiner: 'Sequence replication tasks by mechanistic confidence before broad validation.',
        expected: 'Improve throughput by validating strongest mechanism candidates first.',
        whyNow: 'Replication load is rising and current ordering is mostly chronological.',
        whyThisOne: {
          evidenceAnchors: [
            'E-11: mechanism-aligned replications reached conclusive outcomes 1.7x faster.',
            'E-25: literature map identifies high-confidence mechanism clusters.',
            'E-40: budget model supports staged replication ladder.',
          ],
          constraintFit: 'Aligns with limited experiment slots and existing planner logic.',
          riskCheck: 'Risk: deprioritized long-tail ideas may be delayed. Mitigation: reserve exploration quota.',
          rationale: 'Balances scientific rigor and practical throughput under resource constraints.',
        },
        cost: '$23',
        confidence: 0.8,
        risk: 'medium',
        scores: {
          novelty: 71,
          feasibility: 82,
          impact: 79,
          grounding: 82,
          testability: 85,
          clarity: 78,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
    ],
    events: [
      {
        id: 'e1',
        time: '11:12:08',
        room: 'library',
        level: 'info',
        roomState: 'active',
        message: 'Library ingest started for pathway screening packet and assay logs.',
      },
      {
        id: 'e2',
        time: '11:12:39',
        room: 'library',
        level: 'success',
        roomState: 'done',
        message: 'Parse, storage, and biological ontology links completed.',
      },
      {
        id: 'e3',
        time: '11:13:05',
        room: 'hypothesis',
        level: 'info',
        roomState: 'active',
        message: 'Hypothesis arena merged pathway graph with baseline expression signatures.',
        hypothesisId: 'h1',
      },
      {
        id: 'e4',
        time: '11:13:44',
        room: 'hypothesis',
        level: 'warn',
        roomState: 'active',
        message: 'Critic flagged cellline transfer risk for top-ranked perturbation path.',
        hypothesisId: 'h2',
      },
      {
        id: 'e5',
        time: '11:14:02',
        room: 'hypothesis',
        level: 'success',
        roomState: 'done',
        message: 'Top-4 biologically grounded hypotheses ranked and budget tagged.',
      },
      {
        id: 'e6',
        time: '11:14:31',
        room: 'experiment',
        level: 'info',
        roomState: 'active',
        message: 'Experiment design initialized with assay repeatability constraints.',
        hypothesisId: 'h3',
      },
      {
        id: 'e7',
        time: '11:14:52',
        room: 'experiment',
        level: 'success',
        roomState: 'done',
        message: 'Experiment protocol passes variance and sample-size gate checks.',
      },
      {
        id: 'e8',
        time: '11:15:19',
        room: 'results',
        level: 'info',
        roomState: 'active',
        message: 'Results analysis started for differential response and confidence bands.',
      },
      {
        id: 'e9',
        time: '11:15:51',
        room: 'results',
        level: 'success',
        roomState: 'done',
        message: 'Result diagnostics complete with anomaly and replication notes.',
      },
      {
        id: 'e10',
        time: '11:16:12',
        room: 'writing',
        level: 'info',
        roomState: 'active',
        message: 'Paper section scaffold created for method, caveats, and validation plan.',
      },
      {
        id: 'e11',
        time: '11:16:36',
        room: 'writing',
        level: 'success',
        roomState: 'done',
        message: 'Draft writing package finalized with evidence-linked claims.',
      },
    ],
    paperSet: [
      { id: 'p1', title: 'Primary Packet', detail: 'Cell signaling benchmark paper · 16 chunks indexed' },
      { id: 'p2', title: 'Support Evidence 01', detail: 'Pathway atlas extract · receptor map linked' },
      { id: 'p3', title: 'Support Evidence 02', detail: 'Assay variance logs · 3 unstable assays tagged' },
      { id: 'p4', title: 'Support Evidence 03', detail: 'Citation cluster map · oncology lineage focused' },
    ],
    commandChips: [
      'Import assay metadata',
      'Generate perturbation hypotheses',
      'Run replicate-cost simulation',
      'Compare mechanism pathways',
    ],
  },
  simulation: {
    hypotheses: [
      {
        id: 'h1',
        title: 'Adaptive Mesh Triggering Policy',
        oneLiner: 'Increase mesh granularity only when instability signals cross dynamic thresholds.',
        expected: 'Reduce simulation cost while preserving critical error bounds in turbulent regions.',
        whyNow: 'Current runtimes spike from always-on high-resolution zones.',
        whyThisOne: {
          evidenceAnchors: [
            'E-05: 64% of runtime is spent in zones with low residual change.',
            'E-17: instability detector already available from baseline solver logs.',
            'E-32: prior adaptive runs retained accuracy within target error limits.',
          ],
          constraintFit: 'Runs on current compute budget with no additional cluster requirement.',
          riskCheck: 'Risk: missed micro-instabilities. Mitigation: add conservative guard band around trigger thresholds.',
          rationale: 'Highest compute savings with bounded numerical risk.',
        },
        cost: '$44',
        confidence: 0.77,
        risk: 'medium',
        scores: {
          novelty: 79,
          feasibility: 73,
          impact: 89,
          grounding: 78,
          testability: 80,
          clarity: 76,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h2',
        title: 'Boundary-Condition Sensitivity Ladder',
        oneLiner: 'Rank parameter sensitivity by boundary-condition stress sequences before full sweeps.',
        expected: 'Find brittle parameter zones early and reduce failed long-run jobs.',
        whyNow: 'Recent failures cluster around boundary handling rather than core solver logic.',
        whyThisOne: {
          evidenceAnchors: [
            'E-13: boundary variants account for most divergence events in overnight runs.',
            'E-22: partial sweeps identify brittle zones in <20% of full run time.',
            'E-36: event rail shows repeated critic warnings on boundary assumptions.',
          ],
          constraintFit: 'Lightweight pre-sweep step slots into existing execution board.',
          riskCheck: 'Risk: incomplete coverage if ladder is too narrow. Mitigation: dynamic expansion on warning triggers.',
          rationale: 'Improves reliability before committing expensive compute blocks.',
        },
        cost: '$27',
        confidence: 0.82,
        risk: 'low',
        scores: {
          novelty: 74,
          feasibility: 85,
          impact: 78,
          grounding: 84,
          testability: 82,
          clarity: 85,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h3',
        title: 'Solver Drift Sentinel',
        oneLiner: 'Monitor drift signatures across checkpoints and trigger rollback before instability cascades.',
        expected: 'Lower wasted GPU hours from late-stage divergence.',
        whyNow: 'Rollback signals exist but are currently inspected after runs fail.',
        whyThisOne: {
          evidenceAnchors: [
            'E-09: drift rise precedes hard divergence by 2-3 checkpoints.',
            'E-24: rollback checkpoints are already logged but not automated.',
            'E-42: low false-positive drift threshold found in historical data.',
          ],
          constraintFit: 'Minimal integration work and no changes to solver core.',
          riskCheck: 'Risk: excess rollback cycles. Mitigation: confidence-weighted trigger escalation.',
          rationale: 'Fast safety multiplier for compute-heavy scenarios.',
        },
        cost: '$18',
        confidence: 0.84,
        risk: 'low',
        scores: {
          novelty: 67,
          feasibility: 90,
          impact: 75,
          grounding: 89,
          testability: 88,
          clarity: 82,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h4',
        title: 'Cross-Fidelity Alignment Envelope',
        oneLiner: 'Map agreement bands between low-fidelity and high-fidelity models for faster planning.',
        expected: 'Accelerate design iteration by trusting low-fidelity runs within validated regions.',
        whyNow: 'Teams still overuse high-fidelity runs even in stable operating ranges.',
        whyThisOne: {
          evidenceAnchors: [
            'E-15: low/high fidelity outputs align in 58% of operating envelope.',
            'E-26: misalignment clusters around known turbulence transition bands.',
            'E-38: results pipeline can export alignment diagnostics without new storage.',
          ],
          constraintFit: 'Directly supports time-constrained runs by reducing expensive high-fidelity usage.',
          riskCheck: 'Risk: hidden mismatch zones. Mitigation: hard guardrails around transition regions.',
          rationale: 'Creates actionable trust boundaries for cheaper iteration loops.',
        },
        cost: '$25',
        confidence: 0.79,
        risk: 'medium',
        scores: {
          novelty: 72,
          feasibility: 81,
          impact: 77,
          grounding: 83,
          testability: 84,
          clarity: 79,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
    ],
    events: [
      {
        id: 'e1',
        time: '09:02:11',
        room: 'library',
        level: 'info',
        roomState: 'active',
        message: 'Library ingest started for solver logs, mesh profiles, and benchmark papers.',
      },
      {
        id: 'e2',
        time: '09:02:43',
        room: 'library',
        level: 'success',
        roomState: 'done',
        message: 'Parse, storage, and simulation metadata indexing completed.',
      },
      {
        id: 'e3',
        time: '09:03:09',
        room: 'hypothesis',
        level: 'info',
        roomState: 'active',
        message: 'Hypothesis arena integrated instability diagnostics with solver trace context.',
        hypothesisId: 'h1',
      },
      {
        id: 'e4',
        time: '09:03:36',
        room: 'hypothesis',
        level: 'warn',
        roomState: 'active',
        message: 'Critic flagged brittle boundary assumptions in sensitivity ladder branch.',
        hypothesisId: 'h2',
      },
      {
        id: 'e5',
        time: '09:03:58',
        room: 'hypothesis',
        level: 'success',
        roomState: 'done',
        message: 'Top-4 simulation hypotheses ranked with compute-aware cost envelopes.',
      },
      {
        id: 'e6',
        time: '09:04:21',
        room: 'experiment',
        level: 'info',
        roomState: 'active',
        message: 'Experiment board prepared with mesh trigger checkpoints and rollback policy.',
        hypothesisId: 'h3',
      },
      {
        id: 'e7',
        time: '09:04:49',
        room: 'experiment',
        level: 'success',
        roomState: 'done',
        message: 'Execution plan validated against runtime and memory limits.',
      },
      {
        id: 'e8',
        time: '09:05:10',
        room: 'results',
        level: 'info',
        roomState: 'active',
        message: 'Results analysis running on residual drift and fidelity alignment windows.',
      },
      {
        id: 'e9',
        time: '09:05:39',
        room: 'results',
        level: 'success',
        roomState: 'done',
        message: 'Diagnostics complete with runtime savings and error-bound summary.',
      },
      {
        id: 'e10',
        time: '09:06:01',
        room: 'writing',
        level: 'info',
        roomState: 'active',
        message: 'Report draft seeded with solver assumptions and reproducibility checklist.',
      },
      {
        id: 'e11',
        time: '09:06:27',
        room: 'writing',
        level: 'success',
        roomState: 'done',
        message: 'Writing package finalized with validated runtime findings.',
      },
    ],
    paperSet: [
      { id: 'p1', title: 'Primary Packet', detail: 'Turbulence benchmark paper · 14 chunks indexed' },
      { id: 'p2', title: 'Support Evidence 01', detail: 'Solver telemetry dataset · 8 drift windows marked' },
      { id: 'p3', title: 'Support Evidence 02', detail: 'Boundary condition notes · critic annotations attached' },
      { id: 'p4', title: 'Support Evidence 03', detail: 'Fidelity comparison log · 3 regime transitions tagged' },
    ],
    commandChips: [
      'Import runtime telemetry',
      'Generate 4 simulation hypotheses',
      'Run mesh-cost stress test',
      'Compare fidelity envelopes',
    ],
  },
  drug_discovery: {
    hypotheses: [
      {
        id: 'h1',
        title: 'Pocket Dynamics Prioritized Screening',
        oneLiner: 'Rank compounds by binding-pocket dynamics stability before expensive docking batches.',
        expected: 'Improve early hit quality and reduce wasted screening throughput.',
        whyNow: 'Current shortlist quality drops when static pocket assumptions dominate ranking.',
        whyThisOne: {
          evidenceAnchors: [
            'E-04: dynamic-pocket features correlate with top assay confirmations.',
            'E-19: static-only ranking misses conformationally robust candidates.',
            'E-33: trajectory snippets are already available in evidence packet.',
          ],
          constraintFit: 'Uses existing trajectory artifacts and stays within compute budget ceiling.',
          riskCheck: 'Risk: over-prioritizing dynamic features may ignore ADMET constraints. Mitigation: add dual gate.',
          rationale: 'Raises hit relevance early without changing downstream lab process.',
        },
        cost: '$46',
        confidence: 0.76,
        risk: 'medium',
        scores: {
          novelty: 81,
          feasibility: 72,
          impact: 90,
          grounding: 77,
          testability: 75,
          clarity: 78,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h2',
        title: 'ADMET-Aware Lead Reweighting',
        oneLiner: 'Reweight lead ranking with ADMET proxies before final synthesis recommendation.',
        expected: 'Reduce late-stage attrition in candidate progression.',
        whyNow: 'Recent pipeline reviews show potent leads failing due to avoidable ADMET issues.',
        whyThisOne: {
          evidenceAnchors: [
            'E-06: 47% of dropped leads failed after ADMET evaluation.',
            'E-23: proxy models provide reliable early warning on toxicity channels.',
            'E-35: budget model favors early rejection over late synthesis failure.',
          ],
          constraintFit: 'No additional wet-lab dependency; this is a scoring-layer update.',
          riskCheck: 'Risk: conservative bias may suppress novel chemotypes. Mitigation: novelty reserve lane.',
          rationale: 'Strong feasibility and immediate cost-risk reduction.',
        },
        cost: '$28',
        confidence: 0.84,
        risk: 'low',
        scores: {
          novelty: 70,
          feasibility: 88,
          impact: 84,
          grounding: 87,
          testability: 80,
          clarity: 86,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h3',
        title: 'Negative-Control Guided Triaging',
        oneLiner: 'Inject structured negative controls to detect false-positive scaffolds early.',
        expected: 'Improve confidence in shortlisted compounds before assay investment.',
        whyNow: 'False positives are still surfacing after costly handoff stages.',
        whyThisOne: {
          evidenceAnchors: [
            'E-08: top false positives share recurring scaffold artifacts.',
            'E-20: negative-control checks reduce spurious signal retention by 31%.',
            'E-42: critic highlights weak disconfirmation strategy in current workflow.',
          ],
          constraintFit: 'Fits current execution board with lightweight pre-assay checks.',
          riskCheck: 'Risk: too many negatives can slow exploration. Mitigation: cap negative-control volume per cycle.',
          rationale: 'Improves reliability of each progression decision under tight budgets.',
        },
        cost: '$20',
        confidence: 0.83,
        risk: 'low',
        scores: {
          novelty: 66,
          feasibility: 91,
          impact: 77,
          grounding: 89,
          testability: 90,
          clarity: 81,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
      {
        id: 'h4',
        title: 'Mechanism Coverage Diversity Gate',
        oneLiner: 'Force mechanism diversity in the top candidate set before final recommendation.',
        expected: 'Prevent over-concentration on one mechanism and improve portfolio resilience.',
        whyNow: 'Current top sets over-index one familiar mechanism pathway.',
        whyThisOne: {
          evidenceAnchors: [
            'E-12: top 10 list currently maps to only two mechanism families.',
            'E-27: prior diverse portfolios had better downstream survival rates.',
            'E-39: mechanism tags already present in evidence graph context.',
          ],
          constraintFit: 'Pure ranking rule update with minimal runtime overhead.',
          riskCheck: 'Risk: diversity pressure may lower immediate potency. Mitigation: potency floor constraint.',
          rationale: 'Balances short-term potency with longer-term discovery resilience.',
        },
        cost: '$22',
        confidence: 0.81,
        risk: 'medium',
        scores: {
          novelty: 74,
          feasibility: 83,
          impact: 79,
          grounding: 82,
          testability: 84,
          clarity: 80,
        },
        refinementCount: 0,
        lastRefinement: null,
      },
    ],
    events: [
      {
        id: 'e1',
        time: '14:21:03',
        room: 'library',
        level: 'info',
        roomState: 'active',
        message: 'Library ingest started for docking logs, ADMET proxies, and lead history.',
      },
      {
        id: 'e2',
        time: '14:21:37',
        room: 'library',
        level: 'success',
        roomState: 'done',
        message: 'Parse and storage complete with chemistry metadata cross-links.',
      },
      {
        id: 'e3',
        time: '14:22:06',
        room: 'hypothesis',
        level: 'info',
        roomState: 'active',
        message: 'Hypothesis arena merged pocket dynamics signals with lead quality history.',
        hypothesisId: 'h1',
      },
      {
        id: 'e4',
        time: '14:22:41',
        room: 'hypothesis',
        level: 'warn',
        roomState: 'active',
        message: 'Critic flagged potential novelty collapse in potency-only branch.',
        hypothesisId: 'h4',
      },
      {
        id: 'e5',
        time: '14:23:02',
        room: 'hypothesis',
        level: 'success',
        roomState: 'done',
        message: 'Top-4 lead-selection hypotheses ranked with risk-weighted scores.',
      },
      {
        id: 'e6',
        time: '14:23:28',
        room: 'experiment',
        level: 'info',
        roomState: 'active',
        message: 'Experiment protocol configured for screening triage and holdout validation.',
        hypothesisId: 'h3',
      },
      {
        id: 'e7',
        time: '14:23:53',
        room: 'experiment',
        level: 'success',
        roomState: 'done',
        message: 'Execution protocol validated for compute, budget, and safety constraints.',
      },
      {
        id: 'e8',
        time: '14:24:15',
        room: 'results',
        level: 'info',
        roomState: 'active',
        message: 'Results analysis started for hit precision and attrition risk deltas.',
      },
      {
        id: 'e9',
        time: '14:24:40',
        room: 'results',
        level: 'success',
        roomState: 'done',
        message: 'Result package complete with efficacy-risk tradeoff summary.',
      },
      {
        id: 'e10',
        time: '14:25:03',
        room: 'writing',
        level: 'info',
        roomState: 'active',
        message: 'Paper writing draft initialized with lead rationale and caveat blocks.',
      },
      {
        id: 'e11',
        time: '14:25:31',
        room: 'writing',
        level: 'success',
        roomState: 'done',
        message: 'Writing package finalized with mechanism and validation references.',
      },
    ],
    paperSet: [
      { id: 'p1', title: 'Primary Packet', detail: 'Lead optimization study · 13 chunks indexed' },
      { id: 'p2', title: 'Support Evidence 01', detail: 'Docking trajectory set · 5 conformations tracked' },
      { id: 'p3', title: 'Support Evidence 02', detail: 'ADMET proxy table · 9 high-risk compounds tagged' },
      { id: 'p4', title: 'Support Evidence 03', detail: 'Mechanism cluster map · 4 pathway families linked' },
    ],
    commandChips: [
      'Import lead table',
      'Generate 4 discovery hypotheses',
      'Run ADMET stress-check',
      'Compare mechanism diversity',
    ],
  },
};

function cloneHypotheses(hypotheses: Hypothesis[]): Hypothesis[] {
  return hypotheses.map((hypothesis) => ({
    ...hypothesis,
    scores: { ...hypothesis.scores },
    whyThisOne: {
      ...hypothesis.whyThisOne,
      evidenceAnchors: [...hypothesis.whyThisOne.evidenceAnchors],
    },
  }));
}

function roomSummaryState(summary: Record<RoomId, RoomState>): RoomState {
  const values = Object.values(summary);
  if (values.includes('active')) return 'active';
  if (values.every((value) => value === 'done')) return 'done';
  return 'pending';
}

export default function PrototypeShell({ fontVars }: PrototypeShellProps) {
  const MIN_LEFT_PANEL_WIDTH = 250;
  const MAX_LEFT_PANEL_WIDTH = 500;
  const MIN_RIGHT_PANEL_WIDTH = 280;
  const MAX_RIGHT_PANEL_WIDTH = 520;
  const MIN_TOP_SECTION_HEIGHT = 180;
  const MAX_TOP_SECTION_HEIGHT = 460;

  const [tab, setTab] = useState<CanvasTab>('arena');
  const [theme, setTheme] = useState<ThemeMode>('light');
  const [questHistory, setQuestHistory] = useState<QuestHistoryItem[]>(initialQuestHistory);
  const [selectedQuestId, setSelectedQuestId] = useState<string>(initialQuestHistory[0].id);
  const [eventFilter, setEventFilter] = useState<'all' | RoomId>('all');
  const [visibleEvents, setVisibleEvents] = useState(3);
  const [refinementDrafts, setRefinementDrafts] = useState<Record<string, string>>({});
  const [leftPanelWidth, setLeftPanelWidth] = useState(300);
  const [rightPanelWidth, setRightPanelWidth] = useState(330);
  const [topSectionHeight, setTopSectionHeight] = useState(280);
  const [composerIntakeState, setComposerIntakeState] = useState<{
    action: ComposerIntakeAction;
    message: string;
  } | null>(null);

  const selectedQuest = useMemo(
    () => questHistory.find((quest) => quest.id === selectedQuestId) ?? questHistory[0],
    [questHistory, selectedQuestId]
  );

  const selectedDomain = selectedQuest?.domain ?? 'ai_ml';
  const activeSeed = seededDataByDomain[selectedDomain];
  const baseEvents = activeSeed.events;

  const [hypotheses, setHypotheses] = useState<Hypothesis[]>(cloneHypotheses(activeSeed.hypotheses));
  const [selectedHypothesisId, setSelectedHypothesisId] = useState<string>(activeSeed.hypotheses[0].id);

  const resetQuestWorkspace = (domain: QuestDomain) => {
    const seed = seededDataByDomain[domain];
    setHypotheses(cloneHypotheses(seed.hypotheses));
    setSelectedHypothesisId(seed.hypotheses[0].id);
    setRefinementDrafts({});
    setVisibleEvents(3);
    setEventFilter('all');
    setTab('arena');
  };

  const activateQuest = (quest: QuestHistoryItem) => {
    setSelectedQuestId(quest.id);
    resetQuestWorkspace(quest.domain);
  };

  useEffect(() => {
    if (visibleEvents >= baseEvents.length) return;
    const timer = window.setInterval(() => {
      setVisibleEvents((prev) => Math.min(prev + 1, baseEvents.length));
    }, 1800);
    return () => window.clearInterval(timer);
  }, [visibleEvents, baseEvents.length]);

  useEffect(() => {
    if (!composerIntakeState) return;
    const timer = window.setTimeout(() => setComposerIntakeState(null), 2200);
    return () => window.clearTimeout(timer);
  }, [composerIntakeState]);

  const streamedEvents = useMemo(() => baseEvents.slice(0, visibleEvents), [baseEvents, visibleEvents]);

  const roomStates = useMemo(() => {
    const states: Record<RoomId, RoomState> = {
      library: 'pending',
      hypothesis: 'pending',
      experiment: 'pending',
      results: 'pending',
      writing: 'pending',
    };

    for (const event of streamedEvents) {
      states[event.room] = event.roomState;
    }

    return states;
  }, [streamedEvents]);

  const activeEvents = useMemo(
    () => streamedEvents.filter((event) => (eventFilter === 'all' ? true : event.room === eventFilter)),
    [streamedEvents, eventFilter]
  );

  const selectedHypothesis = useMemo(
    () => hypotheses.find((item) => item.id === selectedHypothesisId) ?? hypotheses[0],
    [hypotheses, selectedHypothesisId]
  );

  const updateDraft = (id: string, value: string) => {
    setRefinementDrafts((prev) => ({ ...prev, [id]: value }));
  };

  const applyRefinement = (id: string) => {
    const draft = refinementDrafts[id]?.trim();
    if (!draft) return;

    setHypotheses((prev) =>
      prev.map((item) => {
        if (item.id !== id) return item;
        return {
          ...item,
          oneLiner: `${item.oneLiner} Added direction: ${draft}.`,
          whyNow: `${item.whyNow} User note: ${draft}.`,
          confidence: Math.min(0.99, Number((item.confidence + 0.01).toFixed(2))),
          scores: {
            ...item.scores,
            clarity: Math.min(100, item.scores.clarity + 2),
            grounding: Math.min(100, item.scores.grounding + 1),
            feasibility: Math.min(100, item.scores.feasibility + 1),
          },
          whyThisOne: {
            ...item.whyThisOne,
            rationale: `${item.whyThisOne.rationale} Updated with user refinement: ${draft}.`,
            evidenceAnchors: [item.whyThisOne.evidenceAnchors[0], item.whyThisOne.evidenceAnchors[1], `User refinement: ${draft}`],
          },
          refinementCount: item.refinementCount + 1,
          lastRefinement: draft,
        };
      })
    );

    setSelectedHypothesisId(id);
    setRefinementDrafts((prev) => ({ ...prev, [id]: '' }));
  };

  const addNewQuest = () => {
    const domainCycle: QuestDomain[] = ['ai_ml', 'comp_bio', 'simulation', 'drug_discovery'];
    const nextDomain = domainCycle[questHistory.length % domainCycle.length];
    const newQuest: QuestHistoryItem = {
      id: `q-${Date.now()}`,
      title: `${domainLabels[nextDomain]} Exploration ${questHistory.length + 1}`,
      domain: nextDomain,
      updatedAt: 'just now',
      roomStateSummary: { ...defaultRoomStateSummary },
    };

    setQuestHistory((prev) => [newQuest, ...prev]);
    setSelectedQuestId(newQuest.id);
    resetQuestWorkspace(nextDomain);
  };

  const triggerIntake = (action: ComposerIntakeAction) => {
    setComposerIntakeState({
      action,
      message: action === 'upload_pdf' ? 'Upload flow staged in chat composer (prototype).' : 'arXiv fetch flow staged in chat composer (prototype).',
    });
  };

  const beginHorizontalResize = (side: 'left' | 'right', event: ReactMouseEvent<HTMLDivElement>) => {
    if (window.innerWidth <= 1040) return;
    event.preventDefault();

    const startX = event.clientX;
    const initialLeftWidth = leftPanelWidth;
    const initialRightWidth = rightPanelWidth;

    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';

    const onMouseMove = (moveEvent: MouseEvent) => {
      const delta = moveEvent.clientX - startX;
      if (side === 'left') {
        setLeftPanelWidth(Math.max(MIN_LEFT_PANEL_WIDTH, Math.min(MAX_LEFT_PANEL_WIDTH, initialLeftWidth + delta)));
        return;
      }
      setRightPanelWidth(Math.max(MIN_RIGHT_PANEL_WIDTH, Math.min(MAX_RIGHT_PANEL_WIDTH, initialRightWidth - delta)));
    };

    const onMouseUp = () => {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  };

  const beginVerticalResize = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (window.innerWidth <= 1040) return;
    event.preventDefault();

    const startY = event.clientY;
    const initialHeight = topSectionHeight;

    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'row-resize';

    const onMouseMove = (moveEvent: MouseEvent) => {
      const delta = moveEvent.clientY - startY;
      setTopSectionHeight(Math.max(MIN_TOP_SECTION_HEIGHT, Math.min(MAX_TOP_SECTION_HEIGHT, initialHeight + delta)));
    };

    const onMouseUp = () => {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  };

  return (
    <div className={`${styles.root} ${fontVars} ${theme === 'dark' ? styles.themeDark : styles.themeLight}`}>
      <header className={styles.topBar}>
        <div className={styles.brandBlock}>
          <div className={styles.brandMark}>
            <Orbit size={18} />
          </div>
          <div>
            <p className={styles.brandTitle}>VREDA Mission Control</p>
            <p className={styles.brandSub}>Solo Research Workspace Prototype</p>
          </div>
        </div>

        <div className={styles.roomChipBar}>
          {roomTracks.map((room) => (
            <div
              key={room.id}
              className={`${styles.roomChip} ${
                roomStates[room.id] === 'active'
                  ? styles.roomChipActive
                  : roomStates[room.id] === 'done'
                    ? styles.roomChipDone
                    : styles.roomChipPending
              }`}
            >
              <span className={styles.roomDot} />
              <span>{room.label}</span>
            </div>
          ))}
        </div>

        <button className={styles.themeToggle} onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
          {theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}
          {theme === 'light' ? 'Dusk View' : 'Light View'}
        </button>
      </header>

      <div className={styles.workspace}>
        <aside className={styles.leftRail} style={{ width: leftPanelWidth }}>
          <div className={`${styles.leftSection} ${styles.leftTopSection}`} style={{ height: topSectionHeight }}>
            <p className={styles.sectionLabel}>Research</p>
            <button className={styles.newQuestButton} onClick={addNewQuest}>
              <FlaskConical size={14} /> New Research Quest
            </button>

            <p className={styles.sectionLabel}>History</p>
            <div className={styles.historyList}>
              {questHistory.map((quest) => {
                const rowState = roomSummaryState(quest.id === selectedQuestId ? roomStates : quest.roomStateSummary);
                return (
                  <button
                    key={quest.id}
                    className={`${styles.historyItem} ${quest.id === selectedQuestId ? styles.historyItemActive : ''}`}
                    onClick={() => activateQuest(quest)}
                  >
                    <div className={styles.historyTop}>
                      <span
                        className={`${styles.historyStateDot} ${
                          rowState === 'active'
                            ? styles.historyDotActive
                            : rowState === 'done'
                              ? styles.historyDotDone
                              : styles.historyDotPending
                        }`}
                      />
                      <p>{quest.title}</p>
                    </div>
                    <div className={styles.historyMeta}>
                      <span className={`${styles.domainBadge} ${styles[`domain_${quest.domain}`]}`}>{domainLabels[quest.domain]}</span>
                      <span>{quest.updatedAt}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div
            className={styles.resizeHandleRow}
            onMouseDown={beginVerticalResize}
            role="separator"
            aria-label="Resize research and activity sections"
            aria-orientation="horizontal"
          />

          <div className={`${styles.leftSection} ${styles.eventRailSection}`}>
            <div className={styles.eventRailHeader}>
              <p className={styles.sectionLabel}>Agent Event Activity</p>
              <span>{activeEvents.length} live</span>
            </div>

            <div className={styles.eventFilters}>
              <button className={eventFilter === 'all' ? styles.eventFilterActive : ''} onClick={() => setEventFilter('all')}>
                All
              </button>
              {roomTracks.map((room) => (
                <button
                  key={room.id}
                  className={eventFilter === room.id ? styles.eventFilterActive : ''}
                  onClick={() => setEventFilter(room.id)}
                >
                  {room.label}
                </button>
              ))}
            </div>

            <div className={styles.eventList}>
              {activeEvents.map((event) => (
                <button
                  key={event.id}
                  className={styles.eventItem}
                  onClick={() => {
                    if (event.hypothesisId) {
                      setSelectedHypothesisId(event.hypothesisId);
                      setTab('arena');
                    }
                  }}
                >
                  <div className={styles.eventItemTop}>
                    <span>{event.time}</span>
                    <span>{roomTracks.find((room) => room.id === event.room)?.label}</span>
                  </div>
                  <p>{event.message}</p>
                  <span
                    className={`${styles.eventLevelBadge} ${
                      event.level === 'success' ? styles.eventSuccess : event.level === 'warn' ? styles.eventWarn : styles.eventInfo
                    }`}
                  >
                    {event.level}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <div
          className={styles.resizeHandleCol}
          onMouseDown={(event) => beginHorizontalResize('left', event)}
          role="separator"
          aria-label="Resize left and center panels"
          aria-orientation="vertical"
        />

        <main className={styles.canvas}>
          <nav className={styles.canvasTabs}>
            <button className={`${styles.tabButton} ${tab === 'evidence' ? styles.tabActive : ''}`} onClick={() => setTab('evidence')}>
              <Search size={14} /> Evidence Map
            </button>
            <button className={`${styles.tabButton} ${tab === 'arena' ? styles.tabActive : ''}`} onClick={() => setTab('arena')}>
              <Lightbulb size={14} /> Hypothesis Arena
            </button>
            <button className={`${styles.tabButton} ${tab === 'execution' ? styles.tabActive : ''}`} onClick={() => setTab('execution')}>
              <Workflow size={14} /> Execution Board
            </button>
            <button className={`${styles.tabButton} ${tab === 'manifest' ? styles.tabActive : ''}`} onClick={() => setTab('manifest')}>
              <ShieldCheck size={14} /> Manifest Studio
            </button>
          </nav>

          {tab === 'arena' && (
            <section className={styles.arenaView}>
              <div className={styles.arenaHeader}>
                <div>
                  <p className={styles.arenaEyebrow}>
                    {domainLabels[selectedDomain]} · {selectedQuest.title}
                  </p>
                  <h1>Hypothesis Arena</h1>
                  <p>Cards stay concise. Detailed decision intelligence stays in Inspector.</p>
                </div>
                <button className={styles.primaryAction}>
                  Continue to Budget <ChevronRight size={14} />
                </button>
              </div>

              <div className={styles.hypothesisGrid}>
                {hypotheses.map((hypothesis) => (
                  <article
                    key={hypothesis.id}
                    className={`${styles.hypothesisCard} ${hypothesis.id === selectedHypothesisId ? styles.hypothesisSelected : ''}`}
                    onClick={() => setSelectedHypothesisId(hypothesis.id)}
                  >
                    <div className={styles.hypothesisTop}>
                      <h3>{hypothesis.title}</h3>
                      <span className={styles.costPill}>{hypothesis.cost}</span>
                    </div>
                    <p className={styles.hypothesisSummary}>{hypothesis.oneLiner}</p>
                    <div className={styles.metricRow}>
                      <span>confidence {hypothesis.confidence}</span>
                      <span>refinements {hypothesis.refinementCount}</span>
                    </div>

                    <div className={styles.refineInline} onClick={(event) => event.stopPropagation()}>
                      <input
                        value={refinementDrafts[hypothesis.id] ?? ''}
                        onChange={(event) => updateDraft(hypothesis.id, event.target.value)}
                        placeholder="Add idea for this hypothesis..."
                        aria-label={`Refine ${hypothesis.title}`}
                      />
                      <button onClick={() => applyRefinement(hypothesis.id)}>Apply</button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}

          {tab === 'evidence' && (
            <section className={styles.evidenceView}>
              <div className={styles.evidenceHeader}>
                <h2>Evidence Map</h2>
                <p>Paper set and evidence graph stay here for verification context.</p>
              </div>

              <div className={styles.evidenceGrid}>
                <article className={styles.evidenceCard}>
                  <div className={styles.evidenceCardHead}>
                    <FileText size={14} />
                    <span>Paper Set</span>
                  </div>
                  <div className={styles.paperList}>
                    {activeSeed.paperSet.map((paper) => (
                      <div key={paper.id} className={styles.paperItem}>
                        <p>{paper.title}</p>
                        <span>{paper.detail}</span>
                      </div>
                    ))}
                  </div>
                </article>

                <article className={styles.evidenceCard}>
                  <div className={styles.evidenceCardHead}>
                    <Search size={14} />
                    <span>Evidence Graph Snapshot</span>
                  </div>
                  <div className={styles.graphMock}>
                    <div className={styles.graphNode}>Primary</div>
                    <div className={styles.graphNode}>Contradiction</div>
                    <div className={styles.graphNode}>Replication</div>
                    <div className={styles.graphNode}>Code Ref</div>
                    <div className={styles.graphNode}>Benchmarks</div>
                  </div>
                </article>
              </div>
            </section>
          )}

          {tab === 'execution' && (
            <section className={styles.placeholderPanel}>
              <h2>Execution Board</h2>
              <p>Compare Path A vs Path B with timeline, infra needs, and risk delta before implementation.</p>
            </section>
          )}

          {tab === 'manifest' && (
            <section className={styles.placeholderPanel}>
              <h2>Manifest Studio</h2>
              <p>Final experiment contract with checkpoints, guardrails, and exportable run instructions.</p>
            </section>
          )}
        </main>

        <div
          className={styles.resizeHandleCol}
          onMouseDown={(event) => beginHorizontalResize('right', event)}
          role="separator"
          aria-label="Resize center and inspector panels"
          aria-orientation="vertical"
        />

        <aside className={styles.inspector} style={{ width: rightPanelWidth }}>
          <p className={styles.sectionLabel}>Inspector</p>

          <div className={styles.inspectCard}>
            <p className={styles.inspectTitle}>Selected Hypothesis</p>
            <h3>{selectedHypothesis.title}</h3>
            <p>{selectedHypothesis.expected}</p>

            <div className={styles.inspectMetricsSix}>
              <div>
                <span>Novelty</span>
                <strong>{selectedHypothesis.scores.novelty}</strong>
              </div>
              <div>
                <span>Feasibility</span>
                <strong>{selectedHypothesis.scores.feasibility}</strong>
              </div>
              <div>
                <span>Impact</span>
                <strong>{selectedHypothesis.scores.impact}</strong>
              </div>
              <div>
                <span>Grounding</span>
                <strong>{selectedHypothesis.scores.grounding}</strong>
              </div>
              <div>
                <span>Testability</span>
                <strong>{selectedHypothesis.scores.testability}</strong>
              </div>
              <div>
                <span>Clarity</span>
                <strong>{selectedHypothesis.scores.clarity}</strong>
              </div>
            </div>

            <div className={styles.decisionMeta}>
              <span>Confidence: {selectedHypothesis.confidence}</span>
              <span>Cost: {selectedHypothesis.cost}</span>
              <span>Risk: {selectedHypothesis.risk}</span>
            </div>

            <p className={styles.whyNow}>
              <strong>Why now:</strong> {selectedHypothesis.whyNow}
            </p>
            {selectedHypothesis.lastRefinement && (
              <p className={styles.lastRefinement}>
                <strong>Last refinement:</strong> {selectedHypothesis.lastRefinement}
              </p>
            )}
          </div>

          <div className={styles.inspectCard}>
            <p className={styles.inspectTitle}>Why This One</p>
            <div className={styles.validationBlock}>
              <p>
                <strong>Evidence Anchors</strong>
              </p>
              <ul className={styles.anchorList}>
                {selectedHypothesis.whyThisOne.evidenceAnchors.map((anchor) => (
                  <li key={anchor}>{anchor}</li>
                ))}
              </ul>
              <p>
                <strong>Constraint Fit:</strong> {selectedHypothesis.whyThisOne.constraintFit}
              </p>
              <p>
                <strong>Risk Check:</strong> {selectedHypothesis.whyThisOne.riskCheck}
              </p>
              <p>
                <strong>Decision Rationale:</strong> {selectedHypothesis.whyThisOne.rationale}
              </p>
            </div>
          </div>

          <div className={styles.inspectCard}>
            <p className={styles.inspectTitle}>Recent Activity</p>
            <ul className={styles.activityList}>
              {activeEvents.slice(-4).map((event) => (
                <li key={event.id}>
                  <CircleDot size={12} />
                  {event.message}
                </li>
              ))}
            </ul>
          </div>

          <div className={styles.inspectCard}>
            <p className={styles.inspectTitle}>Provenance</p>
            <p className={styles.provenanceRow}>
              <Bot size={12} /> {streamedEvents.length} events tracked
            </p>
            <p className={styles.provenanceRow}>
              <Sparkles size={12} /> 5 room states derived automatically
            </p>
          </div>
        </aside>
      </div>

      <footer className={styles.commandDock}>
        <div className={styles.chipRow}>
          {activeSeed.commandChips.map((chip) => (
            <button key={chip} className={styles.commandChip}>
              {chip}
            </button>
          ))}
        </div>

        <div className={styles.intakeRow}>
          <button className={styles.intakeButton} onClick={() => triggerIntake('upload_pdf')}>
            <Upload size={13} /> Upload PDF
          </button>
          <button className={styles.intakeButton} onClick={() => triggerIntake('fetch_arxiv')}>
            <FileText size={13} /> Fetch arXiv
          </button>
          {composerIntakeState && <p className={styles.intakeNotice}>{composerIntakeState.message}</p>}
        </div>

        <div className={styles.commandInputRow}>
          <input
            aria-label="Command input"
            placeholder="Ask VREDA to compare hypotheses, search evidence, or prep final manifest..."
          />
          <button>Run Command</button>
        </div>
      </footer>
    </div>
  );
}
