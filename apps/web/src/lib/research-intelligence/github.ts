import { withRetry } from '@/lib/retry';
import { logger } from '@/lib/logger';
import { config } from '@/lib/config';
import { githubLimiter } from '@/lib/literature/rate-limiter';
import type { RepoMetrics } from '@/types/research-intelligence';

const GITHUB_API_BASE = 'https://api.github.com';

function getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'VREDA-AI-Research',
    };
    if (config.github.token) {
        headers['Authorization'] = `Bearer ${config.github.token}`;
    }
    return headers;
}

/**
 * Parse a GitHub URL into owner/repo.
 */
export function parseGitHubUrl(url: string): { owner: string; repo: string } | null {
    const patterns = [
        /github\.com\/([^/]+)\/([^/\s#?.]+)/,
        /^([^/]+)\/([^/\s#?.]+)$/,
    ];

    for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match) {
            return {
                owner: match[1],
                repo: match[2].replace(/\.git$/, ''),
            };
        }
    }
    return null;
}

/**
 * Compute a health score (0-100) from repo metrics.
 * Weights: stars 25%, recency 30%, readme 15%, low issues 15%, activity 15%
 */
function computeHealthScore(
    stars: number,
    daysSinceLastPush: number,
    hasReadme: boolean,
    openIssues: number,
    forks: number
): number {
    // Stars: 0-25 (log scale, 100+ stars = max)
    const starScore = Math.min(25, (Math.log10(Math.max(stars, 1)) / 2) * 25);

    // Recency: 0-30 (< 30 days = 30, > 365 days = 0)
    const recencyScore = daysSinceLastPush < 30 ? 30
        : daysSinceLastPush < 90 ? 22
        : daysSinceLastPush < 180 ? 15
        : daysSinceLastPush < 365 ? 8
        : 0;

    // README: 0-15
    const readmeScore = hasReadme ? 15 : 0;

    // Issues ratio: 0-15 (fewer open issues relative to stars = healthier)
    const issueRatio = stars > 0 ? openIssues / stars : openIssues;
    const issueScore = issueRatio < 0.1 ? 15 : issueRatio < 0.3 ? 10 : issueRatio < 0.5 ? 5 : 0;

    // Forks (community interest): 0-15
    const forkScore = Math.min(15, (Math.log10(Math.max(forks, 1)) / 2) * 15);

    return Math.round(starScore + recencyScore + readmeScore + issueScore + forkScore);
}

/**
 * Get comprehensive metrics for a GitHub repository.
 */
export async function getRepoMetrics(repoUrl: string): Promise<RepoMetrics | null> {
    const parsed = parseGitHubUrl(repoUrl);
    if (!parsed) {
        logger.warn('Could not parse GitHub URL', { repoUrl });
        return null;
    }

    const { owner, repo } = parsed;
    await githubLimiter.acquire();

    return withRetry(
        async () => {
            logger.info('GitHub repo metrics', { owner, repo });
            const headers = getHeaders();

            // Fetch repo info, README, and languages in parallel
            const [repoRes, readmeRes, langRes] = await Promise.allSettled([
                fetch(`${GITHUB_API_BASE}/repos/${owner}/${repo}`, { headers }),
                fetch(`${GITHUB_API_BASE}/repos/${owner}/${repo}/readme`, { headers }),
                fetch(`${GITHUB_API_BASE}/repos/${owner}/${repo}/languages`, { headers }),
            ]);

            // Repo info (required)
            if (repoRes.status !== 'fulfilled' || !repoRes.value.ok) {
                const status = repoRes.status === 'fulfilled' ? repoRes.value.status : 'network_error';
                if (status === 404) {
                    logger.warn('GitHub repo not found', { owner, repo });
                    return null;
                }
                if (status === 403) {
                    throw new Error('GitHub API rate limit exceeded');
                }
                throw new Error(`GitHub API error: ${status}`);
            }

            const repoData = await repoRes.value.json();

            // README (optional)
            let hasReadme = false;
            let readmePreview = '';
            if (readmeRes.status === 'fulfilled' && readmeRes.value.ok) {
                hasReadme = true;
                try {
                    const readmeData = await readmeRes.value.json();
                    if (readmeData.content) {
                        const decoded = Buffer.from(readmeData.content, 'base64').toString('utf-8');
                        readmePreview = decoded.substring(0, 500);
                    }
                } catch {
                    // README parsing is non-critical
                }
            }

            // Languages (optional)
            const languages: Record<string, number> = langRes.status === 'fulfilled' && langRes.value.ok
                ? await langRes.value.json()
                : {};

            const lastPushed = repoData.pushed_at || repoData.updated_at || '';
            const daysSinceLastPush = lastPushed
                ? Math.floor((Date.now() - new Date(lastPushed).getTime()) / (1000 * 60 * 60 * 24))
                : 999;

            // Detect framework from languages + README
            let framework: string | null = null;
            const readmeLower = readmePreview.toLowerCase();
            const langKeys = Object.keys(languages).map(k => k.toLowerCase());
            if (readmeLower.includes('pytorch') || readmeLower.includes('torch')) framework = 'PyTorch';
            else if (readmeLower.includes('tensorflow') || readmeLower.includes('tf.')) framework = 'TensorFlow';
            else if (readmeLower.includes('jax') || readmeLower.includes('flax')) framework = 'JAX';
            else if (readmeLower.includes('keras')) framework = 'Keras';
            else if (langKeys.includes('jupyter notebook') && langKeys.includes('python')) framework = 'Python/Jupyter';

            const stars = repoData.stargazers_count || 0;
            const forks = repoData.forks_count || 0;
            const openIssues = repoData.open_issues_count || 0;

            return {
                url: repoData.html_url || repoUrl,
                owner,
                name: repo,
                stars,
                forks,
                open_issues: openIssues,
                last_pushed: lastPushed,
                primary_language: repoData.language || 'Unknown',
                languages,
                framework,
                has_readme: hasReadme,
                readme_preview: readmePreview,
                days_since_last_push: daysSinceLastPush,
                health_score: computeHealthScore(stars, daysSinceLastPush, hasReadme, openIssues, forks),
            };
        },
        'githubRepoMetrics',
        { maxRetries: 2, baseDelayMs: 1000 }
    );
}
