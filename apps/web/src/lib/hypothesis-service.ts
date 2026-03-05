import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { logger } from '@/lib/logger';

interface ServiceHealth {
    reachable: boolean;
    providerConfigured: boolean;
    detail?: string;
    runtimeModuleFile?: string;
    runtimePid?: number;
    runtimeStartedAtMs?: number;
    runtimeHealthProtocolVersion?: number;
    runtimeDefaultGroundingTimeoutSeconds?: number;
}

interface ServiceRuntime {
    process: ChildProcess | null;
    startupPromise: Promise<boolean> | null;
}

interface EnsureServiceReadyResult {
    ready: boolean;
    detail?: string;
}

declare global {
    var __vredaHypothesisServiceRuntime: ServiceRuntime | undefined;
}

function getRuntime(): ServiceRuntime {
    if (!globalThis.__vredaHypothesisServiceRuntime) {
        globalThis.__vredaHypothesisServiceRuntime = {
            process: null,
            startupPromise: null,
        };
    }
    return globalThis.__vredaHypothesisServiceRuntime;
}

function parseBool(value: string | undefined, fallback: boolean): boolean {
    if (value === undefined) return fallback;
    return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase());
}

function isAutostartEnabled(): boolean {
    return parseBool(process.env.HYPOTHESIS_SERVICE_AUTOSTART, process.env.NODE_ENV !== 'production');
}

function parseServiceUrl(serviceUrl: string): URL | null {
    try {
        return new URL(serviceUrl);
    } catch {
        return null;
    }
}

function isLocalhost(url: URL): boolean {
    return url.hostname === '127.0.0.1' || url.hostname === 'localhost';
}

function resolveServiceDir(): string | null {
    const candidates = [
        process.env.HYPOTHESIS_SERVICE_DIR,
        path.resolve(process.cwd(), 'services/hypothesis-room'),
        path.resolve(process.cwd(), '../services/hypothesis-room'),
        path.resolve(process.cwd(), '../../services/hypothesis-room'),
    ].filter(Boolean) as string[];

    for (const candidate of candidates) {
        const entrypoint = path.join(candidate, 'src', 'vreda_hypothesis', 'server.py');
        if (fs.existsSync(entrypoint)) {
            return candidate;
        }
    }

    return null;
}

function resolvePythonBin(serviceDir: string): string {
    const venvPython = path.join(serviceDir, '.venv', 'bin', 'python');
    if (fs.existsSync(venvPython)) {
        return venvPython;
    }

    return process.env.HYPOTHESIS_SERVICE_PYTHON || 'python3';
}

async function sleep(ms: number): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve, ms));
}

async function getServiceHealth(serviceUrl: string): Promise<ServiceHealth> {
    try {
        const response = await fetch(`${serviceUrl}/healthz`, {
            signal: AbortSignal.timeout(3000),
        });

        if (!response.ok) {
            return {
                reachable: false,
                providerConfigured: false,
                detail: `healthz returned ${response.status}`,
            };
        }

        const data = await response.json().catch(() => ({} as Record<string, unknown>));
        const providers = (data as { active_providers?: unknown }).active_providers;
        const runtime = (data as { runtime?: Record<string, unknown> }).runtime;
        const runtimeModuleFile =
            runtime && typeof runtime.module_file === 'string' ? runtime.module_file : undefined;
        const runtimePid =
            runtime && typeof runtime.pid === 'number' ? runtime.pid : undefined;
        const runtimeStartedAtMs =
            runtime && typeof runtime.started_at_epoch_s === 'number'
                ? Math.round(runtime.started_at_epoch_s * 1000)
                : undefined;
        const runtimeHealthProtocolVersion =
            runtime && typeof runtime.health_protocol_version === 'number'
                ? runtime.health_protocol_version
                : undefined;
        const runtimeTimeouts =
            runtime && typeof runtime.default_stage_timeouts_s === 'object'
                ? runtime.default_stage_timeouts_s as Record<string, unknown>
                : undefined;
        const runtimeDefaultGroundingTimeoutSeconds =
            runtimeTimeouts && typeof runtimeTimeouts.grounding === 'number'
                ? runtimeTimeouts.grounding
                : undefined;

        if (providers && typeof providers === 'object' && 'error' in (providers as Record<string, unknown>)) {
            return {
                reachable: true,
                providerConfigured: false,
                detail: String((providers as Record<string, unknown>).error || 'No LLM provider configured'),
                runtimeModuleFile,
                runtimePid,
                runtimeStartedAtMs,
                runtimeHealthProtocolVersion,
                runtimeDefaultGroundingTimeoutSeconds,
            };
        }

        return {
            reachable: true,
            providerConfigured: true,
            runtimeModuleFile,
            runtimePid,
            runtimeStartedAtMs,
            runtimeHealthProtocolVersion,
            runtimeDefaultGroundingTimeoutSeconds,
        };
    } catch {
        return {
            reachable: false,
            providerConfigured: false,
            detail: 'service did not respond on /healthz',
        };
    }
}

const EXPECTED_HEALTH_PROTOCOL_VERSION = 2;
const MIN_EXPECTED_DEFAULT_GROUNDING_TIMEOUT_SECONDS = 180;

function getLatestServiceSourceMtimeMs(serviceDir: string): number {
    const watchedFiles = [
        path.join(serviceDir, 'src', 'vreda_hypothesis', 'server.py'),
        path.join(serviceDir, 'src', 'vreda_hypothesis', 'main.py'),
        path.join(serviceDir, 'src', 'vreda_hypothesis', 'llm', 'provider.py'),
        path.join(serviceDir, 'src', 'vreda_hypothesis', 'stages', 'grounding.py'),
        path.join(serviceDir, 'src', 'vreda_hypothesis', 'stages', 'overgeneration.py'),
        path.join(serviceDir, 'src', 'vreda_hypothesis', 'stages', 'filtering.py'),
        path.join(serviceDir, 'src', 'vreda_hypothesis', 'stages', 'output.py'),
        path.join(serviceDir, 'src', 'vreda_hypothesis', 'models.py'),
    ];
    let latest = 0;
    for (const file of watchedFiles) {
        try {
            const stat = fs.statSync(file);
            if (stat.mtimeMs > latest) latest = stat.mtimeMs;
        } catch {
            // Ignore missing files; this is best-effort staleness detection.
        }
    }
    return latest;
}

function isServiceStale(health: ServiceHealth, serviceDir: string): boolean {
    if (!health.runtimeStartedAtMs) {
        return false;
    }
    const latestSourceMtimeMs = getLatestServiceSourceMtimeMs(serviceDir);
    return latestSourceMtimeMs > health.runtimeStartedAtMs + 1000;
}

async function restartLocalService(serviceUrl: string, health: ServiceHealth): Promise<boolean> {
    const runtime = getRuntime();
    if (runtime.process && !runtime.process.killed) {
        runtime.process.kill('SIGTERM');
        runtime.process = null;
        runtime.startupPromise = null;
    } else if (health.runtimePid && health.runtimePid !== process.pid) {
        try {
            process.kill(health.runtimePid, 'SIGTERM');
        } catch {
            // If process is already gone or inaccessible, continue with autostart attempt.
        }
    }
    await sleep(700);
    return autostartLocalService(serviceUrl);
}

async function waitUntilReady(serviceUrl: string, timeoutMs: number): Promise<ServiceHealth> {
    const start = Date.now();

    while (Date.now() - start < timeoutMs) {
        const health = await getServiceHealth(serviceUrl);
        if (health.reachable) {
            return health;
        }
        await sleep(700);
    }

    return {
        reachable: false,
        providerConfigured: false,
        detail: `service did not become reachable within ${Math.round(timeoutMs / 1000)}s`,
    };
}

async function autostartLocalService(serviceUrl: string): Promise<boolean> {
    const runtime = getRuntime();

    if (runtime.process && !runtime.process.killed) {
        const health = await waitUntilReady(serviceUrl, 10000);
        return health.reachable;
    }

    const serviceDir = resolveServiceDir();
    if (!serviceDir) {
        logger.error('Hypothesis service auto-start failed', new Error('Service directory not found'));
        return false;
    }

    const pythonBin = resolvePythonBin(serviceDir);
    const serviceSrcDir = path.join(serviceDir, 'src');
    const pythonPath = process.env.PYTHONPATH
        ? `${serviceSrcDir}${path.delimiter}${process.env.PYTHONPATH}`
        : serviceSrcDir;
    const parsedUrl = parseServiceUrl(serviceUrl);
    const port = parsedUrl?.port ? Number(parsedUrl.port) : 8000;
    const host = parsedUrl?.hostname || '127.0.0.1';

    logger.warn('Hypothesis service unavailable, attempting auto-start', {
        serviceUrl,
        serviceDir,
        serviceSrcDir,
        pythonBin,
        host,
        port,
    });

    const child = spawn(
        pythonBin,
        ['-m', 'vreda_hypothesis.server'],
        {
            cwd: serviceDir,
            env: {
                ...process.env,
                HOST: host,
                PORT: String(port),
                PYTHONPATH: pythonPath,
                VREDA_HYPOTHESIS_SRC: serviceSrcDir,
            },
            stdio: ['ignore', 'pipe', 'pipe'],
        }
    );

    runtime.process = child;

    child.stdout?.on('data', (chunk) => {
        const line = String(chunk).trim();
        if (line) {
            logger.info('hypothesis_service.stdout', { line: line.slice(0, 400) });
        }
    });

    child.stderr?.on('data', (chunk) => {
        const line = String(chunk).trim();
        if (line) {
            logger.warn('hypothesis_service.stderr', { line: line.slice(0, 400) });
        }
    });

    child.on('exit', (code, signal) => {
        logger.warn('Hypothesis service process exited', { code, signal });
        const current = getRuntime();
        current.process = null;
        current.startupPromise = null;
    });

    const health = await waitUntilReady(serviceUrl, 30000);
    return health.reachable;
}

export async function ensureHypothesisServiceReady(serviceUrl: string): Promise<EnsureServiceReadyResult> {
    let health = await getServiceHealth(serviceUrl);
    const parsedUrl = parseServiceUrl(serviceUrl);
    const serviceDir = resolveServiceDir();
    const canManageLocalService = Boolean(parsedUrl && isLocalhost(parsedUrl) && serviceDir);

    if (
        health.reachable &&
        health.providerConfigured &&
        canManageLocalService &&
        (!health.runtimeModuleFile || !health.runtimeStartedAtMs)
    ) {
        logger.warn('Hypothesis service missing runtime metadata; restarting', {
            runtimeModuleFile: health.runtimeModuleFile,
            runtimeStartedAtMs: health.runtimeStartedAtMs,
        });
        if (!isAutostartEnabled()) {
            return {
                ready: false,
                detail: 'Hypothesis service runtime metadata is missing and auto-start is disabled. Restart the service to apply updates.',
            };
        }
        const restarted = await restartLocalService(serviceUrl, health);
        if (!restarted) {
            return {
                ready: false,
                detail: 'Hypothesis service restart failed while reconciling runtime metadata.',
            };
        }
        const postRestartHealth = await getServiceHealth(serviceUrl);
        if (!postRestartHealth.reachable || !postRestartHealth.providerConfigured) {
            return {
                ready: false,
                detail: postRestartHealth.detail || 'Hypothesis service failed health checks after runtime metadata restart.',
            };
        }
        health = postRestartHealth;
    }

    const shouldVerifyRuntime =
        parsedUrl &&
        isLocalhost(parsedUrl) &&
        serviceDir &&
        health.runtimeModuleFile;

    if (
        health.reachable &&
        health.providerConfigured &&
        shouldVerifyRuntime &&
        (
            !health.runtimeHealthProtocolVersion ||
            health.runtimeHealthProtocolVersion < EXPECTED_HEALTH_PROTOCOL_VERSION ||
            (
                health.runtimeDefaultGroundingTimeoutSeconds !== undefined &&
                health.runtimeDefaultGroundingTimeoutSeconds < MIN_EXPECTED_DEFAULT_GROUNDING_TIMEOUT_SECONDS
            )
        )
    ) {
        logger.warn('Hypothesis service runtime contract mismatch; restarting', {
            runtimePid: health.runtimePid,
            runtimeHealthProtocolVersion: health.runtimeHealthProtocolVersion,
            runtimeDefaultGroundingTimeoutSeconds: health.runtimeDefaultGroundingTimeoutSeconds,
            expectedHealthProtocolVersion: EXPECTED_HEALTH_PROTOCOL_VERSION,
        });
        if (!isAutostartEnabled()) {
            return {
                ready: false,
                detail: 'Hypothesis service is running outdated runtime code and auto-start is disabled. Restart the service to apply updates.',
            };
        }
        const restarted = await restartLocalService(serviceUrl, health);
        if (!restarted) {
            return {
                ready: false,
                detail: 'Hypothesis service restart failed while applying runtime updates.',
            };
        }
        const postRestartHealth = await getServiceHealth(serviceUrl);
        if (!postRestartHealth.reachable || !postRestartHealth.providerConfigured) {
            return {
                ready: false,
                detail: postRestartHealth.detail || 'Hypothesis service failed health checks after runtime update restart.',
            };
        }
        health = postRestartHealth;
    }

    if (
        health.reachable &&
        health.providerConfigured &&
        parsedUrl &&
        isLocalhost(parsedUrl) &&
        serviceDir &&
        health.runtimeModuleFile
    ) {
        const expectedPrefix = path.join(serviceDir, 'src', 'vreda_hypothesis');
        if (!health.runtimeModuleFile.startsWith(expectedPrefix)) {
            return {
                ready: false,
                detail: `Hypothesis service is running from an unexpected module path (${health.runtimeModuleFile}). Restart it from ${serviceDir} so local source changes are applied.`,
            };
        }
    }

    if (
        health.reachable &&
        health.providerConfigured &&
        parsedUrl &&
        isLocalhost(parsedUrl) &&
        serviceDir &&
        isServiceStale(health, serviceDir)
    ) {
        logger.warn('Hypothesis service appears stale; restarting to load latest source', {
            runtimePid: health.runtimePid,
            runtimeStartedAtMs: health.runtimeStartedAtMs,
            latestSourceMtimeMs: getLatestServiceSourceMtimeMs(serviceDir),
        });
        if (!isAutostartEnabled()) {
            return {
                ready: false,
                detail: 'Hypothesis service is running outdated code and auto-start is disabled. Restart the service to apply latest source changes.',
            };
        }
        const restarted = await restartLocalService(serviceUrl, health);
        if (!restarted) {
            return {
                ready: false,
                detail: 'Hypothesis service restart failed while applying latest source updates.',
            };
        }
        const postRestart = await getServiceHealth(serviceUrl);
        if (!postRestart.reachable || !postRestart.providerConfigured) {
            return {
                ready: false,
                detail: postRestart.detail || 'Hypothesis service failed health checks after restart.',
            };
        }
        return { ready: true };
    }

    if (health.reachable && health.providerConfigured) {
        return { ready: true };
    }

    if (health.reachable && !health.providerConfigured) {
        return {
            ready: false,
            detail: health.detail || 'Hypothesis service is running but no LLM provider is configured.',
        };
    }

    if (!parsedUrl || !isLocalhost(parsedUrl)) {
        return {
            ready: false,
            detail: 'Hypothesis service is unreachable. Check HYPOTHESIS_SERVICE_URL and confirm the target service is running.',
        };
    }

    if (!isAutostartEnabled()) {
        return {
            ready: false,
            detail: 'Hypothesis service is not running and auto-start is disabled (HYPOTHESIS_SERVICE_AUTOSTART=0).',
        };
    }

    const runtime = getRuntime();
    if (!runtime.startupPromise) {
        runtime.startupPromise = autostartLocalService(serviceUrl);
    }

    const started = await runtime.startupPromise;

    // Reset startup promise so future failures can retry.
    runtime.startupPromise = null;

    if (!started) {
        return {
            ready: false,
            detail: 'Hypothesis service could not be started automatically. Ensure services/hypothesis-room/.venv exists and dependencies are installed.',
        };
    }

    const finalHealth = await getServiceHealth(serviceUrl);
    if (!finalHealth.reachable) {
        return {
            ready: false,
            detail: finalHealth.detail || 'Hypothesis service is still unreachable after auto-start attempt.',
        };
    }

    if (!finalHealth.providerConfigured) {
        return {
            ready: false,
            detail: finalHealth.detail || 'Hypothesis service started but no LLM provider is configured.',
        };
    }

    return { ready: true };
}

export function getHypothesisServiceStartCommand(): string {
    return './scripts/dev-up.sh (recommended) OR cd services/hypothesis-room && source .venv/bin/activate && python -m vreda_hypothesis.server';
}
