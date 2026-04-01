/**
 * IRIS Service Proxy — forwards requests from Next.js API routes
 * to the IRIS Flask backend running on IRIS_SERVICE_URL (default :5001).
 */

import { config } from '@/lib/config';
import { logger } from '@/lib/logger';

const IRIS_BASE = config.irisService.url;

interface IrisProxyOptions {
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
    timeout?: number;
}

/**
 * Forward a request to the IRIS Flask backend and return the response.
 * Always returns a Response whose body is valid JSON — if the upstream
 * returns HTML (e.g. Flask's default 500 page) the raw text is wrapped
 * so that route handlers can safely call `.json()` without throwing.
 */
export async function irisProxy(
    path: string,
    options: IrisProxyOptions = {}
): Promise<Response> {
    const { method = 'GET', body, headers = {}, timeout = 120_000 } = options;
    const url = `${IRIS_BASE}${path}`;

    const fetchHeaders: Record<string, string> = { ...headers };
    if (body && typeof body === 'object' && !(body instanceof FormData)) {
        fetchHeaders['Content-Type'] = 'application/json';
    }

    let raw: Response;
    try {
        raw = await fetch(url, {
            method,
            headers: fetchHeaders,
            body: body instanceof FormData
                ? body
                : body
                    ? JSON.stringify(body)
                    : undefined,
            signal: AbortSignal.timeout(timeout),
        });
    } catch (error) {
        logger.error('IRIS proxy error', error instanceof Error ? error : new Error(String(error)));
        return new Response(
            JSON.stringify({ error: 'IRIS service unavailable. Ensure the IRIS backend is running on ' + IRIS_BASE }),
            { status: 502, headers: { 'Content-Type': 'application/json' } }
        );
    }

    // Read the body once as text, then try to return a guaranteed-JSON response.
    // This prevents `res.json()` from throwing in route handlers when Flask
    // returns a plain-text or HTML error page (e.g. "Internal Server Error").
    const text = await raw.text();
    const contentType = raw.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');

    if (isJson) {
        // Already JSON — just pass through with same status
        return new Response(text, {
            status: raw.status,
            headers: { 'Content-Type': 'application/json' },
        });
    }

    // Try to parse as JSON anyway (some Flask responses omit content-type)
    try {
        JSON.parse(text);
        return new Response(text, {
            status: raw.status,
            headers: { 'Content-Type': 'application/json' },
        });
    } catch {
        // Non-JSON (HTML 500, plain text, etc.) — wrap in a JSON error object
        const snippet = text.slice(0, 300).replace(/</g, '&lt;');
        logger.error(`IRIS non-JSON response (${raw.status}) from ${path}`, new Error(snippet));
        return new Response(
            JSON.stringify({ error: `IRIS backend error (HTTP ${raw.status}): ${text.slice(0, 200)}` }),
            { status: raw.status >= 400 ? raw.status : 500, headers: { 'Content-Type': 'application/json' } }
        );
    }
}

/**
 * Forward a JSON POST to IRIS and return the parsed JSON response.
 */
export async function irisJsonPost<T = unknown>(
    path: string,
    body: unknown
): Promise<{ data: T | null; error: string | null; status: number }> {
    const res = await irisProxy(path, { method: 'POST', body });
    try {
        const data = await res.json();
        if (!res.ok) {
            return { data: null, error: data.error || `IRIS returned ${res.status}`, status: res.status };
        }
        return { data: data as T, error: null, status: res.status };
    } catch {
        return { data: null, error: 'Failed to parse IRIS response', status: res.status };
    }
}

/**
 * Check if the IRIS service is reachable.
 */
export async function isIrisHealthy(): Promise<boolean> {
    try {
        const res = await fetch(`${IRIS_BASE}/healthz`, {
            signal: AbortSignal.timeout(3000),
        });
        return res.ok;
    } catch {
        return false;
    }
}
