'use client';

import { useEffect, useMemo, useRef, useState, type ChangeEvent, type KeyboardEvent, type MouseEvent as ReactMouseEvent } from 'react';
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
  Sun,
  Upload,
  Workflow,
  PanelBottomOpen,
  PanelBottomClose,
} from 'lucide-react';
import type { Conversation, Message } from '@/types';
import type { QuestDomain, QuestRoom } from '@/types/quest';
import { useQuestEvents } from '@/lib/ui/useQuestEvents';
import { deriveWarRoomSnapshot, getDomainLabel } from '@/lib/ui/warroom-adapters';
import styles from './warroom.module.css';

type CanvasTab = 'evidence' | 'arena' | 'execution' | 'manifest';
type ThemeMode = 'light' | 'dark';

type RoomState = 'pending' | 'active' | 'done';

interface WarRoomShellProps {
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  messages: Message[];
  isLoading: boolean;
  streamingText: string;
  strategistLoading: boolean;
  isProcessing: boolean;
  hypothesisEngine: 'gpt' | 'claude';
  onHypothesisEngineChange: (engine: 'gpt' | 'claude') => void;
  onSelectHypothesis: (hypothesisId: string) => void;
  onRefineHypotheses: (message: string, hypothesisEngine: 'gpt' | 'claude') => void;
  onApproveBudget: () => void;
  onSendMessage: (message: string) => void;
  onUploadFile: (file: File) => void;
  onFetchArxiv?: (arxivId: string) => void;
  inputDisabled?: boolean;
}

const roomTracks: { id: QuestRoom; label: string }[] = [
  { id: 'library', label: 'Library' },
  { id: 'hypothesis', label: 'Hypothesis Arena' },
  { id: 'experiment', label: 'Experiment' },
  { id: 'results', label: 'Results & Data Analysis' },
  { id: 'writing', label: 'Paper Writing' },
];

const commandChips = [
  'Generate 5 new hypotheses',
  'Run budget simulation',
  'Compare top 2 hypotheses',
  'Show critic objections',
];

const domainCommandChips: Record<QuestDomain, string[]> = {
  ai_ml: ['Import arXiv: 2602.23318', 'Generate 5 new hypotheses', 'Run budget simulation', 'Compare top 2 hypotheses'],
  comp_bio: ['Import pathway packet', 'Generate perturbation hypotheses', 'Run assay cost simulation', 'Compare top 2 hypotheses'],
  simulation: ['Import simulation report', 'Generate envelope hypotheses', 'Run runtime budget simulation', 'Compare top 2 hypotheses'],
  drug_discovery: ['Import compound dossier', 'Generate lead hypotheses', 'Run assay budget simulation', 'Compare top 2 hypotheses'],
};

const domainClassMap: Record<QuestDomain, string> = {
  ai_ml: styles.domain_ai_ml,
  comp_bio: styles.domain_comp_bio,
  simulation: styles.domain_simulation,
  drug_discovery: styles.domain_drug_discovery,
};

const MIN_LEFT_PANEL_WIDTH = 250;
const MAX_LEFT_PANEL_WIDTH = 500;
const MIN_RIGHT_PANEL_WIDTH = 280;
const MAX_RIGHT_PANEL_WIDTH = 520;
const MIN_TOP_SECTION_HEIGHT = 180;
const MAX_TOP_SECTION_HEIGHT = 460;

function roomStateFromConversation(conversation: Conversation, activeId: string | null): RoomState {
  if (conversation.id === activeId) return 'active';
  return 'done';
}

function formatRelativeTime(input: string): string {
  const ts = Date.parse(input);
  if (Number.isNaN(ts)) return 'now';

  const diffSec = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (diffSec < 60) return 'just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  const diffDay = Math.floor(diffHour / 24);
  return `${diffDay}d ago`;
}

function formatClockTime(input: string): string {
  const ts = Date.parse(input);
  if (Number.isNaN(ts)) return '';
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function getMessageTypeLabel(message: Message): string | null {
  const type = message.metadata?.type;
  if (!type || type === 'text') return null;
  if (type === 'pipeline_progress') return 'Pipeline';
  if (type === 'paper_analysis') return 'Paper Analysis';
  if (type === 'hypothesis_options') return 'Hypotheses';
  if (type === 'budget_quote') return 'Budget';
  if (type === 'enhanced_manifest') return 'Manifest';
  if (type === 'literature_search') return 'Literature Search';
  if (type === 'pdf_upload') return 'Upload';
  if (type === 'error') return 'Error';
  return type;
}

function normalizeMessageContent(content: string): string {
  return content.replace(/\*\*/g, '').trim();
}

export default function WarRoomShell({
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  messages,
  isLoading,
  streamingText,
  strategistLoading,
  isProcessing,
  hypothesisEngine,
  onHypothesisEngineChange,
  onSelectHypothesis,
  onRefineHypotheses,
  onApproveBudget,
  onSendMessage,
  onUploadFile,
  onFetchArxiv,
  inputDisabled = false,
}: WarRoomShellProps) {
  const initialTheme = (): ThemeMode => {
    if (typeof window === 'undefined') return 'light';
    const saved = window.localStorage.getItem('warroom:theme');
    return saved === 'dark' ? 'dark' : 'light';
  };

  const initialLeftPanelWidth = (): number => {
    if (typeof window === 'undefined') return 300;
    const saved = Number.parseInt(window.localStorage.getItem('warroom:leftWidth') || '', 10);
    if (Number.isNaN(saved)) return 300;
    return Math.max(MIN_LEFT_PANEL_WIDTH, Math.min(MAX_LEFT_PANEL_WIDTH, saved));
  };

  const initialRightPanelWidth = (): number => {
    if (typeof window === 'undefined') return 330;
    const saved = Number.parseInt(window.localStorage.getItem('warroom:rightWidth') || '', 10);
    if (Number.isNaN(saved)) return 330;
    return Math.max(MIN_RIGHT_PANEL_WIDTH, Math.min(MAX_RIGHT_PANEL_WIDTH, saved));
  };

  const initialTopSectionHeight = (): number => {
    if (typeof window === 'undefined') return 260;
    const saved = Number.parseInt(window.localStorage.getItem('warroom:topHeight') || '', 10);
    if (Number.isNaN(saved)) return 260;
    return Math.max(MIN_TOP_SECTION_HEIGHT, Math.min(MAX_TOP_SECTION_HEIGHT, saved));
  };

  const initialTranscriptOpen = (): boolean => {
    if (typeof window === 'undefined') return true;
    return window.localStorage.getItem('warroom:transcript') !== '0';
  };

  const [tab, setTab] = useState<CanvasTab>('arena');
  const [theme, setTheme] = useState<ThemeMode>(initialTheme);
  const [eventFilter, setEventFilter] = useState<'all' | QuestRoom>('all');
  const [selectedHypothesisId, setSelectedHypothesisId] = useState<string | null>(null);
  const [refinementDrafts, setRefinementDrafts] = useState<Record<string, string>>({});
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [leftPanelWidth, setLeftPanelWidth] = useState(initialLeftPanelWidth);
  const [rightPanelWidth, setRightPanelWidth] = useState(initialRightPanelWidth);
  const [topSectionHeight, setTopSectionHeight] = useState(initialTopSectionHeight);
  const [transcriptOpen, setTranscriptOpen] = useState(initialTranscriptOpen);
  const [showArxivFetch, setShowArxivFetch] = useState(false);
  const [arxivDraft, setArxivDraft] = useState('');
  const [commandDraft, setCommandDraft] = useState('');
  const [lastRefinements, setLastRefinements] = useState<Record<string, string>>({});
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  const { events: polledEvents } = useQuestEvents(activeConversationId, {
    enabled: !!activeConversationId,
    pollMs: 2500,
    limit: 140,
  });

  useEffect(() => {
    window.localStorage.setItem('warroom:theme', theme);
  }, [theme]);

  useEffect(() => {
    window.localStorage.setItem('warroom:leftWidth', String(leftPanelWidth));
  }, [leftPanelWidth]);

  useEffect(() => {
    window.localStorage.setItem('warroom:rightWidth', String(rightPanelWidth));
  }, [rightPanelWidth]);

  useEffect(() => {
    window.localStorage.setItem('warroom:topHeight', String(topSectionHeight));
  }, [topSectionHeight]);

  useEffect(() => {
    window.localStorage.setItem('warroom:transcript', transcriptOpen ? '1' : '0');
  }, [transcriptOpen]);

  useEffect(() => {
    let cancelled = false;

    const loadConversations = async () => {
      try {
        const response = await fetch('/api/conversations', { cache: 'no-store' });
        if (!response.ok) return;
        const data = (await response.json()) as Conversation[];
        if (!cancelled) setConversations(Array.isArray(data) ? data : []);
      } catch {
        if (!cancelled) setConversations([]);
      }
    };

    void loadConversations();
    return () => {
      cancelled = true;
    };
  }, [activeConversationId]);

  const snapshot = useMemo(() => deriveWarRoomSnapshot(messages, polledEvents), [messages, polledEvents]);
  const selectedConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeConversationId) ?? null,
    [conversations, activeConversationId]
  );
  const selectedDomain = (selectedConversation?.domain || 'ai_ml') as QuestDomain;
  const activeCommandChips = domainCommandChips[selectedDomain] || commandChips;

  const resolvedSelectedHypothesisId = useMemo(() => {
    if (snapshot.hypotheses.length === 0) return null;
    if (selectedHypothesisId && snapshot.hypotheses.some((hypothesis) => hypothesis.id === selectedHypothesisId)) {
      return selectedHypothesisId;
    }
    return snapshot.hypotheses[0].id;
  }, [snapshot.hypotheses, selectedHypothesisId]);

  const selectedHypothesis = useMemo(
    () => snapshot.hypotheses.find((hypothesis) => hypothesis.id === resolvedSelectedHypothesisId) ?? null,
    [snapshot.hypotheses, resolvedSelectedHypothesisId]
  );

  const activeEvents = useMemo(
    () => snapshot.events.filter((event) => (eventFilter === 'all' ? true : event.room === eventFilter)),
    [snapshot.events, eventFilter]
  );

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

  const applyRefinement = (hypothesisId: string) => {
    const draft = refinementDrafts[hypothesisId]?.trim();
    if (!draft) return;
    const hypothesis = snapshot.hypotheses.find((item) => item.id === hypothesisId);
    const label = hypothesis ? `Refine hypothesis "${hypothesis.title}": ${draft}` : draft;
    onRefineHypotheses(label, hypothesisEngine);
    setLastRefinements((prev) => ({ ...prev, [hypothesisId]: draft }));
    setRefinementDrafts((prev) => ({ ...prev, [hypothesisId]: '' }));
  };

  const triggerUpload = () => {
    uploadInputRef.current?.click();
  };

  const onUploadSelect = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      onUploadFile(file);
    }
    event.target.value = '';
  };

  const runFetchArxiv = () => {
    if (!onFetchArxiv) return;
    const value = arxivDraft.trim();
    if (!value) return;
    onFetchArxiv(value);
    setArxivDraft('');
    setShowArxivFetch(false);
  };

  const runCommand = () => {
    const value = commandDraft.trim();
    if (!value) return;
    onSendMessage(value);
    setCommandDraft('');
  };

  const onCommandKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      runCommand();
    }
  };

  return (
    <div className={`${styles.root} ${theme === 'dark' ? styles.themeDark : styles.themeLight}`}>
      <header className={styles.topBar}>
        <div className={styles.brandBlock}>
          <div className={styles.brandMark}>
            <Orbit size={18} />
          </div>
          <div>
            <p className={styles.brandTitle}>VREDA Mission Control</p>
            <p className={styles.brandSub}>Production War Room</p>
          </div>
        </div>

        <div className={styles.roomChipBar}>
          {roomTracks.map((room) => (
            <div
              key={room.id}
              className={`${styles.roomChip} ${
                snapshot.roomStates[room.id] === 'active'
                  ? styles.roomChipActive
                  : snapshot.roomStates[room.id] === 'done'
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
            <p className={styles.sectionLabel}>Quest Controls</p>
            <button className={styles.newQuestButton} onClick={onNewConversation}>
              <FlaskConical size={14} /> New Research Quest
            </button>

            <p className={styles.sectionLabel}>User History</p>
            <div className={styles.historyList}>
              {conversations.map((conversation) => {
                const domain = (conversation.domain || 'ai_ml') as QuestDomain;
                const rowState = roomStateFromConversation(conversation, activeConversationId);

                return (
                  <button
                    key={conversation.id}
                    className={`${styles.historyItem} ${conversation.id === activeConversationId ? styles.historyItemActive : ''}`}
                    onClick={() => onSelectConversation(conversation.id)}
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
                      <p>{conversation.title}</p>
                    </div>
                    <div className={styles.historyMeta}>
                      <span className={`${styles.domainBadge} ${domainClassMap[domain]}`}>{getDomainLabel(domain)}</span>
                      <span>{formatRelativeTime(conversation.created_at)}</span>
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
            aria-label="Resize history and events sections"
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
                    <span>{event.timestamp}</span>
                    <span>{roomTracks.find((room) => room.id === event.room)?.label}</span>
                  </div>
                  <p>{event.message}</p>
                  <span
                    className={`${styles.eventLevelBadge} ${
                      event.level === 'success'
                        ? styles.eventSuccess
                        : event.level === 'warn'
                          ? styles.eventWarn
                          : event.level === 'error'
                            ? styles.eventError
                            : styles.eventInfo
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
            <button className={styles.transcriptToggle} onClick={() => setTranscriptOpen((value) => !value)}>
              {transcriptOpen ? <PanelBottomClose size={14} /> : <PanelBottomOpen size={14} />}
              {transcriptOpen ? 'Hide Log' : 'Show Log'}
            </button>
          </nav>

          {tab === 'arena' && (
            <section className={styles.arenaView}>
              <div className={styles.arenaHeader}>
                <div>
                  <p className={styles.arenaEyebrow}>
                    {activeConversationId
                      ? `${getDomainLabel(selectedDomain)} · ${selectedConversation?.title || 'Research Quest'}`
                      : 'No Active Quest'}
                  </p>
                  <h1>Hypothesis Arena</h1>
                  <p>Cards stay concise. Detailed decision intelligence stays in Inspector.</p>
                </div>
                <button
                  className={styles.primaryAction}
                  onClick={() => {
                    if (selectedHypothesis) onSelectHypothesis(selectedHypothesis.id);
                  }}
                  disabled={!selectedHypothesis || strategistLoading}
                >
                  Continue to Budget <ChevronRight size={14} />
                </button>
              </div>

              <div className={styles.hypothesisGrid}>
                {snapshot.hypotheses.map((hypothesis) => (
                  <article
                    key={hypothesis.id}
                    className={`${styles.hypothesisCard} ${hypothesis.id === resolvedSelectedHypothesisId ? styles.hypothesisSelected : ''}`}
                    onClick={() => setSelectedHypothesisId(hypothesis.id)}
                  >
                    <div className={styles.hypothesisTop}>
                      <h3>{hypothesis.title}</h3>
                      <span className={styles.costPill}>{hypothesis.cost}</span>
                    </div>
                    <p className={styles.hypothesisSummary}>{hypothesis.oneLiner}</p>
                    <div className={styles.metricRow}>
                      <span>confidence {hypothesis.confidence}</span>
                      <span>risk {hypothesis.risk}</span>
                    </div>

                    <div className={styles.refineInline} onClick={(ev) => ev.stopPropagation()}>
                      <input
                        value={refinementDrafts[hypothesis.id] ?? ''}
                        onChange={(event) => setRefinementDrafts((prev) => ({ ...prev, [hypothesis.id]: event.target.value }))}
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
                    {snapshot.paperSet.map((paper) => (
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
              <p>Execution room wiring lands in next phase. Current strategist flow remains intact.</p>
            </section>
          )}

          {tab === 'manifest' && (
            <section className={styles.placeholderPanel}>
              <h2>Manifest Studio</h2>
              <p>Manifest content appears after budget approval from existing strategist routes.</p>
            </section>
          )}

          {transcriptOpen && (
            <section className={styles.transcriptDrawer}>
              <div className={styles.transcriptHeader}>Conversation Log</div>
              <div className={styles.transcriptBody}>
                {messages.map((message) => {
                  const typeLabel = getMessageTypeLabel(message);
                  const normalizedContent = normalizeMessageContent(message.content);
                  const pipelineEvents = message.metadata?.type === 'pipeline_progress' ? message.metadata.pipeline_events ?? [] : [];

                  return (
                    <article
                      key={message.id}
                      className={`${styles.transcriptMessage} ${
                        message.role === 'user' ? styles.transcriptUser : styles.transcriptAssistant
                      }`}
                    >
                      <div className={styles.transcriptMetaRow}>
                        <span className={styles.transcriptRole}>{message.role === 'user' ? 'You' : 'VREDA'}</span>
                        <span className={styles.transcriptTime}>{formatClockTime(message.created_at)}</span>
                      </div>

                      {typeLabel && (
                        <div className={styles.transcriptTagRow}>
                          <span className={styles.transcriptTag}>{typeLabel}</span>
                        </div>
                      )}

                      <p className={styles.transcriptContent}>{normalizedContent}</p>

                      {pipelineEvents.length > 0 && (
                        <ul className={styles.pipelineMiniList}>
                          {pipelineEvents.slice(-4).map((event, index) => (
                            <li key={`${message.id}-pipeline-mini-${index}`}>
                              {event.message}
                            </li>
                          ))}
                        </ul>
                      )}

                      {message.metadata?.type === 'paper_analysis' && (
                        <div className={styles.transcriptActionRow}>
                          <button
                            onClick={() => onSendMessage('Brainstorm 4 novel hypotheses from this paper')}
                            disabled={isProcessing || strategistLoading}
                          >
                            Generate Hypotheses
                          </button>
                        </div>
                      )}

                      {message.metadata?.type === 'budget_quote' && (
                        <div className={styles.transcriptActionRow}>
                          <button onClick={onApproveBudget} disabled={isProcessing || strategistLoading}>
                            Approve Budget
                          </button>
                        </div>
                      )}
                    </article>
                  );
                })}

                {streamingText && (
                  <article className={`${styles.transcriptMessage} ${styles.transcriptAssistant}`}>
                    <div className={styles.transcriptMetaRow}>
                      <span className={styles.transcriptRole}>VREDA</span>
                      <span className={styles.transcriptTime}>live</span>
                    </div>
                    <p className={styles.transcriptContent}>{streamingText}</p>
                  </article>
                )}

                {isLoading && !streamingText && (
                  <div className={styles.loadingRow}>Loading response...</div>
                )}
              </div>
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

          {selectedHypothesis ? (
            <>
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
                {lastRefinements[selectedHypothesis.id] && (
                  <p className={styles.lastRefinement}>
                    <strong>Last refinement:</strong> {lastRefinements[selectedHypothesis.id]}
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
            </>
          ) : (
            <div className={styles.inspectCard}>
              <p className={styles.inspectTitle}>Selected Hypothesis</p>
              <p>No hypothesis selected yet. Upload or fetch a paper, then generate hypotheses.</p>
            </div>
          )}

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
              <Bot size={12} /> {snapshot.events.length} events tracked
            </p>
            <p className={styles.provenanceRow}>
              <Lightbulb size={12} /> 5 room states derived automatically
            </p>
          </div>
        </aside>
      </div>

      <footer className={styles.commandDock}>
        <div className={styles.chipRow}>
          {activeCommandChips.map((chip) => (
            <button key={chip} className={styles.commandChip} onClick={() => onSendMessage(chip)}>
              {chip}
            </button>
          ))}
        </div>

        <div className={styles.intakeRow}>
          <input ref={uploadInputRef} type="file" accept=".pdf" className={styles.hiddenUploadInput} onChange={onUploadSelect} />
          <button className={styles.intakeButton} onClick={triggerUpload}>
            <Upload size={13} /> Upload PDF
          </button>
          {onFetchArxiv && (
            <button className={styles.intakeButton} onClick={() => setShowArxivFetch((value) => !value)}>
              <FileText size={13} /> Fetch arXiv
            </button>
          )}
          {showArxivFetch && onFetchArxiv && (
            <div className={styles.arxivInline}>
              <input
                value={arxivDraft}
                onChange={(event) => setArxivDraft(event.target.value)}
                placeholder="e.g. 2602.23318"
                aria-label="arXiv id"
              />
              <button onClick={runFetchArxiv}>Run</button>
            </div>
          )}
        </div>

        <div className={styles.engineRow}>
          <span className={styles.engineLabel}>Hypothesis engine</span>
          <button
            className={`${styles.engineButton} ${hypothesisEngine === 'gpt' ? styles.engineButtonActive : ''}`}
            onClick={() => onHypothesisEngineChange('gpt')}
            type="button"
          >
            GPT
          </button>
          <button
            className={`${styles.engineButton} ${hypothesisEngine === 'claude' ? styles.engineButtonActive : ''}`}
            onClick={() => onHypothesisEngineChange('claude')}
            type="button"
          >
            Claude
          </button>
          <span className={styles.engineHint}>
            {hypothesisEngine === 'claude' ? 'Claude backend is pending.' : 'GPT is active.'}
          </span>
        </div>

        <div className={styles.commandInputRow}>
          <input
            value={commandDraft}
            onChange={(event) => setCommandDraft(event.target.value)}
            onKeyDown={onCommandKeyDown}
            aria-label="Command input"
            placeholder="Ask VREDA to compare hypotheses, search evidence, or prep final manifest..."
            disabled={inputDisabled || isProcessing || strategistLoading}
          />
          <button
            onClick={runCommand}
            disabled={inputDisabled || isProcessing || strategistLoading || commandDraft.trim().length === 0}
          >
            Run Command
          </button>
        </div>
      </footer>
    </div>
  );
}
