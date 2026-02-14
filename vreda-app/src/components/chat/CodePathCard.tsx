'use client';

import type { CodePathAssessment } from '@/types/strategist';
import {
    GitBranch,
    ExternalLink,
    AlertTriangle,
    Code2,
    Package,
    Clock,
    CheckCircle,
    Star,
    GitFork,
    Activity,
    Search,
} from 'lucide-react';

interface CodePathCardProps {
    codePath: CodePathAssessment;
}

export default function CodePathCard({ codePath }: CodePathCardProps) {
    if (codePath.path === 'A' && codePath.code_found) {
        return <PathACard codeFound={codePath.code_found} />;
    }

    if (codePath.path === 'B' && codePath.formula_to_code_gap) {
        return <PathBCard gap={codePath.formula_to_code_gap} />;
    }

    return null;
}

function PathACard({ codeFound }: { codeFound: NonNullable<CodePathAssessment['code_found']> }) {
    const reuseConfig: Record<string, { color: string; bg: string; label: string; icon: typeof CheckCircle }> = {
        reuse: { color: 'var(--accent-green)', bg: 'rgba(16,185,129,0.08)', label: 'Reuse As-Is', icon: CheckCircle },
        partial_reuse: { color: 'var(--accent-amber)', bg: 'rgba(245,158,11,0.08)', label: 'Partial Reuse', icon: AlertTriangle },
        rewrite: { color: 'var(--accent-red)', bg: 'rgba(239,68,68,0.08)', label: 'Full Rewrite', icon: AlertTriangle },
    };

    const cfg = reuseConfig[codeFound.reuse_recommendation] || reuseConfig.partial_reuse;
    const RecIcon = cfg.icon;

    return (
        <div className="codepath-card">
            {/* Header */}
            <div className="codepath-header">
                <div className="codepath-header-left">
                    <GitBranch size={14} />
                    <span className="codepath-label">Code Available</span>
                </div>
                <span className="codepath-path-badge path-a">PATH A</span>
            </div>

            {/* Repo + Language inline */}
            <div className="codepath-repo-row">
                <a
                    href={codeFound.primary_repo}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="codepath-repo-link"
                >
                    <ExternalLink size={11} />
                    {codeFound.primary_repo}
                </a>
                <span className="codepath-lang-badge">{codeFound.language}</span>
                {codeFound.source && codeFound.source !== 'paper_text' && (
                    <span className="codepath-source-badge">
                        <Search size={9} />
                        {codeFound.source === 'papers_with_code' ? 'Papers With Code' : 'References'}
                    </span>
                )}
            </div>

            {/* Repo Metrics (from GitHub) */}
            {codeFound.repo_metrics && (
                <div className="codepath-stats-row">
                    <div className="codepath-stat">
                        <span className="codepath-stat-value">
                            <Star size={12} style={{ verticalAlign: 'middle', marginRight: 2 }} />
                            {codeFound.repo_metrics.stars.toLocaleString()}
                        </span>
                        <span className="codepath-stat-label">Stars</span>
                    </div>
                    <div className="codepath-stat">
                        <span className="codepath-stat-value">
                            <GitFork size={12} style={{ verticalAlign: 'middle', marginRight: 2 }} />
                            {codeFound.repo_metrics.forks.toLocaleString()}
                        </span>
                        <span className="codepath-stat-label">Forks</span>
                    </div>
                    <div className="codepath-stat">
                        <span className="codepath-stat-value">
                            <Activity size={12} style={{ verticalAlign: 'middle', marginRight: 2 }} />
                            {codeFound.repo_metrics.health_score}/100
                        </span>
                        <span className="codepath-stat-label">Health</span>
                    </div>
                    {codeFound.repo_metrics.framework && (
                        <div className="codepath-stat">
                            <span className="codepath-stat-value">{codeFound.repo_metrics.framework}</span>
                            <span className="codepath-stat-label">Framework</span>
                        </div>
                    )}
                </div>
            )}

            {/* Dependencies + Tech Debt in compact row */}
            <div className="codepath-details-row">
                {codeFound.dependencies.length > 0 && (
                    <div className="codepath-detail-block">
                        <div className="codepath-detail-label">
                            <Package size={10} /> Dependencies
                        </div>
                        <div className="paper-card-chip-row">
                            {codeFound.dependencies.map((dep, i) => (
                                <span key={i} className="paper-card-chip chip-cyan">{dep}</span>
                            ))}
                        </div>
                    </div>
                )}

                {codeFound.technical_debt.length > 0 && (
                    <div className="codepath-detail-block">
                        <div className="codepath-detail-label">
                            <AlertTriangle size={10} /> Tech Debt
                        </div>
                        <ul className="codepath-debt-list">
                            {codeFound.technical_debt.map((debt, i) => (
                                <li key={i}>{debt}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>

            {/* Recommendation Footer */}
            <div className="codepath-recommendation" style={{ color: cfg.color, background: cfg.bg }}>
                <RecIcon size={12} />
                <span>Recommendation: <strong>{cfg.label}</strong></span>
            </div>
            {codeFound.reuse_reasoning && (
                <div className="codepath-reasoning">{codeFound.reuse_reasoning}</div>
            )}
        </div>
    );
}

function PathBCard({ gap }: { gap: NonNullable<CodePathAssessment['formula_to_code_gap']> }) {
    const complexityConfig: Record<string, { color: string; bg: string }> = {
        low: { color: 'var(--accent-green)', bg: 'rgba(16,185,129,0.1)' },
        medium: { color: 'var(--accent-amber)', bg: 'rgba(245,158,11,0.1)' },
        high: { color: 'var(--accent-red)', bg: 'rgba(239,68,68,0.1)' },
    };

    const totalLoc = gap.algorithms_to_implement.reduce((sum, a) => sum + a.estimated_loc, 0);

    return (
        <div className="codepath-card">
            {/* Header */}
            <div className="codepath-header">
                <div className="codepath-header-left">
                    <Code2 size={14} />
                    <span className="codepath-label">Code Gap Analysis</span>
                </div>
                <span className="codepath-path-badge path-b">PATH B</span>
            </div>

            {/* Stats row */}
            <div className="codepath-stats-row">
                <div className="codepath-stat">
                    <span className="codepath-stat-value">{gap.algorithms_to_implement.length}</span>
                    <span className="codepath-stat-label">Algorithms</span>
                </div>
                <div className="codepath-stat">
                    <span className="codepath-stat-value">~{totalLoc}</span>
                    <span className="codepath-stat-label">Lines of Code</span>
                </div>
                <div className="codepath-stat">
                    <span className="codepath-stat-value">
                        <Clock size={12} style={{ verticalAlign: 'middle', marginRight: 2 }} />
                        {gap.total_estimated_effort_hours}h
                    </span>
                    <span className="codepath-stat-label">Est. Effort</span>
                </div>
            </div>

            {/* Algorithms */}
            <div className="codepath-algos">
                {gap.algorithms_to_implement.map((algo, i) => {
                    const cc = complexityConfig[algo.complexity] || complexityConfig.medium;
                    return (
                        <div key={i} className="codepath-algo-row">
                            <div className="codepath-algo-info">
                                <span className="codepath-algo-name">{algo.name}</span>
                                <span className="codepath-algo-meta">
                                    {algo.suggested_library} &middot; ~{algo.estimated_loc} LOC
                                </span>
                            </div>
                            <span
                                className="codepath-complexity-badge"
                                style={{ color: cc.color, background: cc.bg }}
                            >
                                {algo.complexity}
                            </span>
                        </div>
                    );
                })}
            </div>

            {/* Required Libraries */}
            {gap.required_libraries.length > 0 && (
                <div className="codepath-detail-block" style={{ marginTop: 8 }}>
                    <div className="codepath-detail-label">
                        <Package size={10} /> Required Libraries
                    </div>
                    <div className="paper-card-chip-row">
                        {gap.required_libraries.map((lib, i) => (
                            <span key={i} className="paper-card-chip chip-cyan">{lib}</span>
                        ))}
                    </div>
                </div>
            )}

            {/* Adaptable Repos (from Research Intelligence) */}
            {gap.adaptable_repos && gap.adaptable_repos.length > 0 && (
                <div className="codepath-detail-block" style={{ marginTop: 10 }}>
                    <div className="codepath-detail-label">
                        <Search size={10} /> Adaptable Repositories
                    </div>
                    <div className="codepath-adaptable-repos">
                        {gap.adaptable_repos.map((repo, i) => (
                            <div key={i} className="codepath-adaptable-repo">
                                <div className="codepath-adaptable-repo-header">
                                    <a
                                        href={repo.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="codepath-repo-link"
                                        style={{ fontSize: 12 }}
                                    >
                                        <ExternalLink size={10} />
                                        {repo.url.replace('https://github.com/', '')}
                                    </a>
                                    <span className="codepath-adaptable-repo-stars">
                                        <Star size={10} /> {repo.stars.toLocaleString()}
                                    </span>
                                    {repo.framework && (
                                        <span className="paper-card-chip chip-indigo" style={{ fontSize: 9, padding: '1px 5px' }}>
                                            {repo.framework}
                                        </span>
                                    )}
                                </div>
                                <div className="codepath-adaptable-repo-relevance">{repo.relevance}</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
