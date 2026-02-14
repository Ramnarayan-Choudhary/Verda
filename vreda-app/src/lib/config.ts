// Centralized configuration — validates all env vars at import time

function requireEnv(name: string): string {
    const value = process.env[name];
    if (!value) {
        throw new Error(`Missing required environment variable: ${name}`);
    }
    return value;
}

function optionalEnv(name: string, fallback: string): string {
    return process.env[name] || fallback;
}

export const config = {
    supabase: {
        url: requireEnv('NEXT_PUBLIC_SUPABASE_URL'),
        anonKey: requireEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY'),
        serviceRoleKey: requireEnv('SUPABASE_SERVICE_ROLE_KEY'),
    },
    gemini: {
        apiKey: requireEnv('GEMINI_API_KEY'),
    },
    openrouter: {
        apiKey: requireEnv('OPENROUTER_API_KEY'),
        model: optionalEnv('OPENROUTER_MODEL', 'google/gemini-2.0-flash-001'),
    },
    k2think: {
        apiKey: optionalEnv('K2THINK_API_KEY', ''),
        model: optionalEnv('K2THINK_MODEL', 'MBZUAI-IFM/K2-Think-v2'),
        baseUrl: 'https://api.k2think.ai/v1',
    },
    github: {
        token: optionalEnv('GITHUB_TOKEN', ''),
    },
    app: {
        url: optionalEnv('NEXT_PUBLIC_APP_URL', 'http://localhost:3000'),
    },
} as const;
