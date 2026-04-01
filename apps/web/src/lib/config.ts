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

function optionalIntEnv(name: string, fallback: number): number {
    const raw = process.env[name];
    if (!raw) return fallback;
    const parsed = Number.parseInt(raw, 10);
    return Number.isFinite(parsed) ? parsed : fallback;
}

export const config = {
    supabase: {
        url: requireEnv('NEXT_PUBLIC_SUPABASE_URL'),
        anonKey: requireEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY'),
        serviceRoleKey: requireEnv('SUPABASE_SERVICE_ROLE_KEY'),
        paperBucket: optionalEnv('SUPABASE_PAPER_BUCKET', 'Research-Paper'),
    },
    gemini: {
        apiKey: requireEnv('GEMINI_API_KEY'),
        chatModel: optionalEnv('GEMINI_CHAT_MODEL', 'gemini-2.5-flash'),
    },
    openrouter: {
        apiKey: optionalEnv('OPENROUTER_API_KEY', ''),
        model: optionalEnv('OPENROUTER_MODEL', 'google/gemini-2.0-flash-001'),
    },
    deepseek: {
        apiKey: optionalEnv('DEEPSEEK_API_KEY', ''),
        model: optionalEnv('DEEPSEEK_MODEL', 'deepseek-reasoner'),
        baseUrl: optionalEnv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
    },
    openai: {
        apiKey: optionalEnv('OPENAI_API_KEY', ''),
        model: optionalEnv('OPENAI_MODEL', 'gpt-4o'),
        embeddingModel: optionalEnv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large'),
    },
    k2think: {
        apiKey: optionalEnv('K2THINK_API_KEY', ''),
        model: optionalEnv('K2THINK_MODEL', 'MBZUAI-IFM/K2-Think-v2'),
        baseUrl: 'https://api.k2think.ai/v1',
    },
    github: {
        token: optionalEnv('GITHUB_TOKEN', ''),
    },
    hypothesisService: {
        url: optionalEnv('HYPOTHESIS_SERVICE_URL', 'http://127.0.0.1:8000'),
        groundingTimeoutSeconds: optionalIntEnv('HYPOTHESIS_GROUNDING_TIMEOUT_SECONDS', 240),
    },
    hypothesisGptService: {
        url: optionalEnv('HYPOTHESIS_GPT_SERVICE_URL', 'http://127.0.0.1:8100'),
    },
    hypothesisClaudeService: {
        url: optionalEnv('HYPOTHESIS_CLAUDE_SERVICE_URL', 'http://127.0.0.1:8001'),
    },
    irisService: {
        url: optionalEnv('IRIS_SERVICE_URL', 'http://127.0.0.1:5001'),
    },
    app: {
        url: optionalEnv('NEXT_PUBLIC_APP_URL', 'http://localhost:3000'),
    },
} as const;
