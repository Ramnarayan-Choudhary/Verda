'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BadgeCheck,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleDot,
  Filter,
  FlaskConical,
  Gauge,
  Moon,
  Scale,
  Send,
  ShieldAlert,
  Sparkles,
  Sun,
  Wallet,
  Workflow,
  Wrench,
} from 'lucide-react';
import styles from './prototype2.module.css';
import {
  AGENT_EVENTS,
  AGENT_LABELS,
  COMMAND_CHIPS,
  HYPOTHESES,
  MISSION_BRIEF,
  PIPELINE_TIMELINE,
  SCENARIOS,
  type AgentEvent,
  type CriticVerdict,
  type DecisionSnapshot,
  type RankerVerdict,
  type ScenarioPreset,
  type WarRoomAgent,
  type WarRoomHypothesis,
} from './prototype2-data';

type ThemeMode = 'light' | 'dark';
type EventFilter = 'all' | WarRoomAgent;
type BiasTarget = 'cost' | 'novelty' | 'feasibility';

interface Prototype2ShellProps {
  fontVars: string;
}

const agentOrder: EventFilter[] = ['all', 'parser', 'scout', 'critic', 'ranker', 'accountant'];

const verdictWeight: Record<CriticVerdict, number> = {
  strong: 6,
  viable: 0,
  weak: -7,
};

const rankerWeight: Record<RankerVerdict, number> = {
  promote: 4,
  hold: 0,
  demote: -5,
};

const riskPenalty = {
  low: 0,
  medium: -2,
  high: -5,
} as const;

function computeScore(
  hypothesis: WarRoomHypothesis,
  scenario: ScenarioPreset,
  biasTarget: BiasTarget,
  biasStrength: number,
  maxCost: number
) {
  const costEfficiency = Math.max(0, 100 - (hypothesis.costUsd / maxCost) * 100);
  const base =
    hypothesis.scores.novelty * 0.22 +
    hypothesis.scores.feasibility * 0.26 +
    hypothesis.scores.impact * 0.18 +
    hypothesis.scores.grounding * 0.14 +
    hypothesis.scores.testability * 0.12 +
    hypothesis.scores.clarity * 0.08;

  const scenarioAdjustment =
    hypothesis.scores.novelty * scenario.adjustments.novelty * 0.12 +
    hypothesis.scores.feasibility * scenario.adjustments.feasibility * 0.12 +
    costEfficiency * scenario.adjustments.cost * 0.16;

  const normalizedBias = biasStrength / 100;
  let biasAdjustment = 0;
  if (biasTarget === 'novelty') biasAdjustment = hypothesis.scores.novelty * normalizedBias * 0.18;
  if (biasTarget === 'feasibility')
    biasAdjustment = hypothesis.scores.feasibility * normalizedBias * 0.18;
  if (biasTarget === 'cost') biasAdjustment = costEfficiency * normalizedBias * 0.18;

  const finalScore =
    base +
    scenarioAdjustment +
    biasAdjustment +
    verdictWeight[hypothesis.criticVerdict] +
    rankerWeight[hypothesis.rankerVerdict] +
    riskPenalty[hypothesis.riskLevel];

  return Number(finalScore.toFixed(1));
}

function isConflict(hypothesis: WarRoomHypothesis) {
  return (
    (hypothesis.criticVerdict === 'weak' && hypothesis.rankerVerdict === 'promote') ||
    (hypothesis.criticVerdict === 'strong' && hypothesis.rankerVerdict === 'demote')
  );
}

function buildDecisionSnapshot(
  scenario: ScenarioPreset,
  ranked: { hypothesis: WarRoomHypothesis; score: number }[]
): DecisionSnapshot {
  const recommended = ranked[0];
  const runnerUp = ranked[1] ?? ranked[0];
  return {
    scenarioId: scenario.id,
    recommendedHypothesisId: recommended.hypothesis.id,
    runnerUpHypothesisId: runnerUp.hypothesis.id,
    reason:
      scenario.id === 'conservative'
        ? 'Recommendation prioritizes feasibility and budget safety under strict constraints.'
        : scenario.id === 'aggressive'
          ? 'Recommendation prioritizes impact and novelty with acceptable budget expansion.'
          : 'Recommendation balances novelty, feasibility, and controlled cost variance.',
    budgetEnvelope: `$${Math.min(recommended.hypothesis.costUsd, runnerUp.hypothesis.costUsd)} - $${Math.max(recommended.hypothesis.costUsd, runnerUp.hypothesis.costUsd)}`,
    riskEnvelope:
      recommended.hypothesis.riskLevel === 'low' && runnerUp.hypothesis.riskLevel === 'low'
        ? 'Low risk envelope'
        : 'Low to medium risk envelope',
  };
}

export default function Prototype2Shell({ fontVars }: Prototype2ShellProps) {
  const [theme, setTheme] = useState<ThemeMode>('light');
  const [scenarioId, setScenarioId] = useState<ScenarioPreset['id']>('balanced');
  const [eventFilter, setEventFilter] = useState<EventFilter>('all');
  const [biasTarget, setBiasTarget] = useState<BiasTarget>('feasibility');
  const [biasStrength, setBiasStrength] = useState(55);
  const [visibleEventCount, setVisibleEventCount] = useState(3);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(AGENT_EVENTS[0]?.id ?? null);
  const [selectedHypothesisId, setSelectedHypothesisId] = useState<string>(HYPOTHESES[0].id);
  const [leftPanelOpen, setLeftPanelOpen] = useState(true);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [commandInput, setCommandInput] = useState('');
  const [simulationFeedback, setSimulationFeedback] = useState(
    'War Room initialized. Choose a scenario and inspect active agent disagreements.'
  );

  useEffect(() => {
    if (visibleEventCount >= AGENT_EVENTS.length) return;
    const timer = window.setInterval(() => {
      setVisibleEventCount((prev) => Math.min(prev + 1, AGENT_EVENTS.length));
    }, 1800);
    return () => window.clearInterval(timer);
  }, [visibleEventCount]);

  const scenario = useMemo(
    () => SCENARIOS.find((item) => item.id === scenarioId) ?? SCENARIOS[1],
    [scenarioId]
  );

  const maxCost = useMemo(() => Math.max(...HYPOTHESES.map((item) => item.costUsd)), []);

  const rankedHypotheses = useMemo(() => {
    return HYPOTHESES.map((hypothesis) => ({
      hypothesis,
      score: computeScore(hypothesis, scenario, biasTarget, biasStrength, maxCost),
      hasConflict: isConflict(hypothesis),
    })).sort((a, b) => b.score - a.score);
  }, [scenario, biasTarget, biasStrength, maxCost]);

  const recommended = rankedHypotheses[0];
  const comparisonPair = rankedHypotheses.slice(0, 2);

  const selectedHypothesis =
    rankedHypotheses.find((item) => item.hypothesis.id === selectedHypothesisId)?.hypothesis ??
    recommended.hypothesis;

  const visibleEvents = AGENT_EVENTS.slice(0, visibleEventCount);
  const filteredEvents = visibleEvents.filter((event) =>
    eventFilter === 'all' ? true : event.agent === eventFilter
  );

  const selectedEvent = visibleEvents.find((event) => event.id === selectedEventId) ?? null;
  const highlightedHypothesisIds = new Set(selectedEvent?.hypothesisIds ?? []);

  const decision = useMemo(
    () =>
      buildDecisionSnapshot(
        scenario,
        rankedHypotheses.map((item) => ({ hypothesis: item.hypothesis, score: item.score }))
      ),
    [scenario, rankedHypotheses]
  );

  const handleEventClick = (event: AgentEvent) => {
    setSelectedEventId(event.id);
    if (event.hypothesisIds.length > 0) {
      setSelectedHypothesisId(event.hypothesisIds[0]);
    }
  };

  const simulateAction = (action: 'approve' | 'revise' | 'budget') => {
    if (action === 'approve') {
      setSimulationFeedback(
        `Manifest draft started from ${selectedHypothesis.title}. Budget envelope ${decision.budgetEnvelope}.`
      );
    } else if (action === 'revise') {
      setSimulationFeedback(
        `Revision request sent to Critic + Ranker for ${selectedHypothesis.title} with scenario ${scenario.label}.`
      );
    } else {
      setSimulationFeedback(
        `Budget simulation complete: ${selectedHypothesis.title} projected at $${selectedHypothesis.costUsd} ± $5.`
      );
    }
  };

  const runCommand = (raw: string) => {
    const command = raw.trim().toLowerCase();
    if (!command) return;

    if (command.includes('feasibility')) {
      setBiasTarget('feasibility');
      setBiasStrength(82);
      setSimulationFeedback('Feasibility bias increased. Ranking now favors deployable hypotheses.');
      return;
    }

    if (command.includes('cost')) {
      setBiasTarget('cost');
      setBiasStrength(78);
      setScenarioId('conservative');
      setSimulationFeedback('Cost stress test active. Scenario switched to Conservative.');
      return;
    }

    if (command.includes('critic')) {
      setEventFilter('critic');
      setSimulationFeedback('Event filter set to Critic. Showing objections and risk notes only.');
      return;
    }

    setSimulationFeedback(`Command simulated: "${raw}". No backend calls were made.`);
  };

  const handleCommandSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    runCommand(commandInput);
    setCommandInput('');
  };

  return (
    <div
      className={`${styles.root} ${fontVars} ${theme === 'dark' ? styles.themeDark : styles.themeLight}`}
    >
      <header className={styles.header}>
        <div className={styles.headerBrand}>
          <div className={styles.brandIcon}>
            <Workflow size={18} />
          </div>
          <div>
            <p className={styles.headerTitle}>VREDA Agent War Room</p>
            <p className={styles.headerSub}>Solo Research Arbitration Console</p>
          </div>
        </div>

        <div className={styles.headerMission}>
          <p>{MISSION_BRIEF.mission}</p>
          <span>{MISSION_BRIEF.paperPacket}</span>
        </div>

        <div className={styles.headerStatus}>
          <span className={styles.swarmStatus}>
            <CircleDot size={12} />
            Swarm Active · {visibleEventCount}/{AGENT_EVENTS.length} events
          </span>
          <span className={styles.confidence}>
            <Gauge size={12} />
            Confidence trend: rising
          </span>
        </div>

        <button
          className={styles.themeToggle}
          onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
        >
          {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
          {theme === 'light' ? 'Dusk View' : 'Light View'}
        </button>
      </header>

      <div className={styles.timelineRow}>
        {PIPELINE_TIMELINE.map((step) => (
          <div key={step.id} className={styles.timelineStep}>
            <span
              className={`${styles.timelineDot} ${
                step.state === 'done'
                  ? styles.timelineDone
                  : step.state === 'active'
                    ? styles.timelineActive
                    : styles.timelinePending
              }`}
            />
            <span>{step.label}</span>
          </div>
        ))}
      </div>

      <div className={styles.layout}>
        <main className={styles.center}>
          <div className={styles.canvasBar}>
            <div className={styles.filterGroup}>
              <Filter size={13} />
              {agentOrder.map((item) => (
                <button
                  key={item}
                  className={`${styles.filterChip} ${eventFilter === item ? styles.filterChipActive : ''}`}
                  onClick={() => setEventFilter(item)}
                >
                  {item === 'all' ? 'All' : AGENT_LABELS[item]}
                </button>
              ))}
            </div>

            <div className={styles.biasControls}>
              <span>Bias target</span>
              <div className={styles.segmented}>
                {(['cost', 'novelty', 'feasibility'] as BiasTarget[]).map((target) => (
                  <button
                    key={target}
                    className={`${styles.segmentBtn} ${biasTarget === target ? styles.segmentBtnActive : ''}`}
                    onClick={() => setBiasTarget(target)}
                  >
                    {target}
                  </button>
                ))}
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={biasStrength}
                onChange={(event) => setBiasStrength(Number(event.target.value))}
              />
              <span className={styles.biasValue}>{biasStrength}%</span>
            </div>
          </div>

          <section className={styles.eventMatrix}>
            <div className={styles.eventRail}>
              <div className={styles.panelTitle}>Agent Event Rail</div>
              <div className={styles.eventList}>
                {filteredEvents.map((event) => (
                  <button
                    key={event.id}
                    className={`${styles.eventItem} ${selectedEventId === event.id ? styles.eventItemActive : ''}`}
                    onClick={() => handleEventClick(event)}
                  >
                    <div className={styles.eventMeta}>
                      <span>{event.at}</span>
                      <span>{AGENT_LABELS[event.agent]}</span>
                    </div>
                    <p>{event.message}</p>
                    <span className={`${styles.eventLevel} ${styles[`level${event.level}`]}`}>
                      {event.level}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className={styles.matrixPanel}>
              <div className={styles.panelTitle}>Hypothesis Arbitration Matrix</div>
              <div className={styles.tableWrap}>
                <table>
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Hypothesis</th>
                      <th>Composite</th>
                      <th>Novelty</th>
                      <th>Feasibility</th>
                      <th>Cost</th>
                      <th>Critic</th>
                      <th>Ranker</th>
                      <th>Conflict</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rankedHypotheses.map((row, index) => {
                      const highlighted =
                        highlightedHypothesisIds.size > 0 &&
                        highlightedHypothesisIds.has(row.hypothesis.id);
                      return (
                        <tr
                          key={row.hypothesis.id}
                          className={`${selectedHypothesis.id === row.hypothesis.id ? styles.rowSelected : ''} ${highlighted ? styles.rowHighlighted : ''}`}
                          onClick={() => setSelectedHypothesisId(row.hypothesis.id)}
                        >
                          <td>{index + 1}</td>
                          <td>
                            <span className={styles.hypothesisName}>{row.hypothesis.title}</span>
                          </td>
                          <td>{row.score}</td>
                          <td>{row.hypothesis.scores.novelty}</td>
                          <td>{row.hypothesis.scores.feasibility}</td>
                          <td>${row.hypothesis.costUsd}</td>
                          <td>{row.hypothesis.criticVerdict}</td>
                          <td>{row.hypothesis.rankerVerdict}</td>
                          <td>
                            {row.hasConflict ? (
                              <span className={styles.conflictBadge}>
                                <AlertTriangle size={11} /> conflict
                              </span>
                            ) : (
                              <span className={styles.clearBadge}>
                                <CheckCircle2 size={11} /> aligned
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className={styles.compareRow}>
                {comparisonPair.map((item) => (
                  <article key={item.hypothesis.id} className={styles.compareCard}>
                    <div className={styles.compareHead}>
                      <h4>{item.hypothesis.title}</h4>
                      <span>{item.score}</span>
                    </div>
                    <p>{item.hypothesis.oneLiner}</p>
                    <div className={styles.compareMeta}>
                      <span>
                        <Wallet size={12} /> ${item.hypothesis.costUsd}
                      </span>
                      <span>
                        <Scale size={12} /> {item.hypothesis.riskLevel}
                      </span>
                      <span>
                        <BadgeCheck size={12} /> {item.hypothesis.confidence}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </section>
        </main>

        <aside
          className={`${styles.leftPanel} ${!leftPanelOpen ? styles.panelCollapsed : ''}`}
        >
          <div className={styles.panelHeader}>
            <h3>Mission Briefing</h3>
            <button className={styles.collapseToggle} onClick={() => setLeftPanelOpen((prev) => !prev)}>
              {leftPanelOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>
          <div className={styles.panelBody}>
            <p className={styles.objective}>{MISSION_BRIEF.objective}</p>
            <div className={styles.constraintGrid}>
              <div>
                <span>Budget Cap</span>
                <strong>${scenario.budgetCapUsd}</strong>
              </div>
              <div>
                <span>Time Cap</span>
                <strong>{scenario.timeCapHours}h</strong>
              </div>
              <div>
                <span>Compute</span>
                <strong>{scenario.computeProfile}</strong>
              </div>
            </div>

            <div className={styles.scenarioList}>
              <p>Scenario Presets</p>
              {SCENARIOS.map((item) => (
                <button
                  key={item.id}
                  className={`${styles.scenarioBtn} ${item.id === scenario.id ? styles.scenarioBtnActive : ''}`}
                  onClick={() => setScenarioId(item.id)}
                >
                  <span>{item.label}</span>
                  <small>{item.description}</small>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <aside
          className={`${styles.rightPanel} ${!rightPanelOpen ? styles.panelCollapsed : ''}`}
        >
          <div className={styles.panelHeader}>
            <h3>Decision Console</h3>
            <button className={styles.collapseToggle} onClick={() => setRightPanelOpen((prev) => !prev)}>
              {rightPanelOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>
          <div className={styles.panelBody}>
            <div className={styles.recommendationBadge}>
              <Sparkles size={12} />
              Recommended now: {recommended.hypothesis.title}
            </div>

            <article className={styles.selectedCard}>
              <h4>{selectedHypothesis.title}</h4>
              <p>{selectedHypothesis.oneLiner}</p>
              <div className={styles.scoreGrid}>
                {Object.entries(selectedHypothesis.scores).map(([key, value]) => (
                  <div key={key}>
                    <span>{key}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>
              <div className={styles.decisionLine}>
                <span>
                  <Wallet size={12} /> Cost ${selectedHypothesis.costUsd}
                </span>
                <span>
                  <ShieldAlert size={12} /> Risk {selectedHypothesis.riskLevel}
                </span>
                <span>
                  <Gauge size={12} /> Confidence {selectedHypothesis.confidence}
                </span>
              </div>
              <p className={styles.whyNowTitle}>Why now</p>
              <p className={styles.whyNowBody}>{selectedHypothesis.whyNow}</p>
              <p className={styles.gapLine}>
                <Wrench size={12} />
                Gap target: {selectedHypothesis.gapTarget}
              </p>
              <p className={styles.evidenceLine}>
                <FlaskConical size={12} />
                Evidence links: {selectedHypothesis.evidenceRefs.join(', ')}
              </p>
            </article>

            <div className={styles.actionRow}>
              <button onClick={() => simulateAction('approve')}>Approve</button>
              <button onClick={() => simulateAction('revise')}>Request Revision</button>
              <button onClick={() => simulateAction('budget')}>Run Budget Simulation</button>
            </div>

            <div className={styles.snapshot}>
              <p>Decision Snapshot</p>
              <span>Scenario: {decision.scenarioId}</span>
              <span>Reason: {decision.reason}</span>
              <span>Budget envelope: {decision.budgetEnvelope}</span>
              <span>Risk envelope: {decision.riskEnvelope}</span>
            </div>
          </div>
        </aside>
      </div>

      <footer className={styles.commandBar}>
        <div className={styles.commandChips}>
          {COMMAND_CHIPS.map((chip) => (
            <button
              key={chip}
              onClick={() => {
                setCommandInput(chip);
                runCommand(chip);
              }}
            >
              {chip}
            </button>
          ))}
        </div>
        <form className={styles.commandForm} onSubmit={handleCommandSubmit}>
          <input
            value={commandInput}
            onChange={(event) => setCommandInput(event.target.value)}
            placeholder="Type tactical command for War Room simulation..."
            aria-label="War room command"
          />
          <button type="submit">
            <Send size={14} />
            Run
          </button>
        </form>
        <div className={styles.commandFeedback}>
          <Bot size={13} />
          {simulationFeedback}
        </div>
      </footer>
    </div>
  );
}
