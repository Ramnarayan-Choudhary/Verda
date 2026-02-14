// Token bucket rate limiter for external API calls

interface RateLimiterConfig {
    maxTokens: number;
    refillRateMs: number; // ms between refills
}

class TokenBucketRateLimiter {
    private tokens: number;
    private lastRefill: number;
    private readonly maxTokens: number;
    private readonly refillRateMs: number;

    constructor(config: RateLimiterConfig) {
        this.maxTokens = config.maxTokens;
        this.refillRateMs = config.refillRateMs;
        this.tokens = config.maxTokens;
        this.lastRefill = Date.now();
    }

    private refill(): void {
        const now = Date.now();
        const elapsed = now - this.lastRefill;
        const tokensToAdd = Math.floor(elapsed / this.refillRateMs);

        if (tokensToAdd > 0) {
            this.tokens = Math.min(this.maxTokens, this.tokens + tokensToAdd);
            this.lastRefill = now;
        }
    }

    async acquire(): Promise<void> {
        this.refill();

        if (this.tokens > 0) {
            this.tokens--;
            return;
        }

        // Wait for next token
        const waitTime = this.refillRateMs - (Date.now() - this.lastRefill);
        await new Promise(resolve => setTimeout(resolve, Math.max(waitTime, 0)));
        this.refill();
        this.tokens--;
    }
}

// arXiv: 1 request per 3 seconds
export const arxivLimiter = new TokenBucketRateLimiter({
    maxTokens: 1,
    refillRateMs: 3000,
});

// Semantic Scholar: 10 requests per second (free tier, no API key)
export const semanticScholarLimiter = new TokenBucketRateLimiter({
    maxTokens: 10,
    refillRateMs: 1000,
});

// Papers With Code: ~5 requests per second (conservative)
export const pwcLimiter = new TokenBucketRateLimiter({
    maxTokens: 5,
    refillRateMs: 1000,
});

// GitHub: 60 req/hour unauthed (1/min), 5000 req/hour with token (~1.4/sec)
export const githubLimiter = new TokenBucketRateLimiter({
    maxTokens: process.env.GITHUB_TOKEN ? 5 : 1,
    refillRateMs: process.env.GITHUB_TOKEN ? 1000 : 60000,
});
