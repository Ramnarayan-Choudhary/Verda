# Session Handoff — arXiv 429 Rate Limit Fix

> **Date**: 2026-03-01
> **Issue**: arXiv API returning `429 Too Many Requests` when fetching papers via `/api/literature/fetch`

---

## Problem

When a user tried to fetch an arXiv paper (e.g., `2602.23318`), the app hit a **429 rate limit error** from the arXiv API. The fetch failed after 2 retries and surfaced as a pipeline error.

**Error log**:```
[VREDA:WARN] fetchByArxivId: Attempt 1/2 failed, retrying in 3000ms {"error":"arXiv API error: 429 Unknown Error"}
[VREDA:ERROR] fetchByArxivId: All 2 attempts failed
  Error: arXiv API error: 429 Unknown Error
```

---

## Root Causes Found

Two bugs in `apps/web/src/lib/literature/arxiv.ts`:

### 1. Rate limiter called OUTSIDE the retry loop

```typescript
// BEFORE (broken) — rate limiter acquired once, retries fire immediately
await arxivLimiter.acquire();  // <-- only called once
return withRetry(async () => {
    const response = await fetch(url);  // retries hit arXiv without rate limiting
    ...
});
```

When the first request got 429'd and `withRetry` retried, it immediately fired another request without waiting for the rate limiter — causing another 429.

### 2. Insufficient retry budget

- Only **2 retries** with **3s base delay** (3s → 6s)
- Not enough time for arXiv to clear its rate limit window

---

## Fix Applied

**File changed**: `apps/web/src/lib/literature/arxiv.ts`

### Fix 1: Moved `arxivLimiter.acquire()` inside the retry loop

Both `searchArxiv()` and `fetchByArxivId()` now acquire the rate limiter token **inside** the retry callback, so every retry attempt respects the rate limit:

```typescript
// AFTER (fixed)
return withRetry(async () => {
    await arxivLimiter.acquire();  // <-- called on every retry
    const response = await fetch(url);
    ...
});
```

### Fix 2: Increased retry resilience

Changed retry config for both functions:

| Parameter | Before | After |
|-----------|--------|-------|
| `maxRetries` | 2 | 4 |
| `baseDelayMs` | 3000 | 5000 |

With exponential backoff, retry delays are now: **5s → 10s → 20s → 40s** — giving arXiv plenty of time to clear the rate limit.

---

## Files Modified

| File | What Changed |
|------|-------------|
| `apps/web/src/lib/literature/arxiv.ts` | Moved `arxivLimiter.acquire()` inside retry loop for both `searchArxiv()` and `fetchByArxivId()`; increased `maxRetries` to 4 and `baseDelayMs` to 5000 |

## Files NOT Modified (no changes needed)

| File | Why |
|------|-----|
| `apps/web/src/lib/literature/rate-limiter.ts` | Token bucket config (1 req / 3s) is fine |
| `apps/web/src/lib/retry.ts` | Generic retry utility works correctly |
| `apps/web/src/app/api/literature/fetch/route.ts` | API route logic is fine |

---

## Related Architecture Context

- **Rate limiter**: Token bucket in `apps/web/src/lib/literature/rate-limiter.ts` — arXiv is limited to 1 request per 3 seconds
- **Retry utility**: `withRetry()` in `apps/web/src/lib/retry.ts` — exponential backoff with formula `delay = baseDelayMs * 2^(attempt-1)`, capped at 8s by default (but the 5s base now gives 5s/10s/20s/40s)
- **arXiv client**: `apps/web/src/lib/literature/arxiv.ts` — uses `fast-xml-parser` to parse arXiv Atom API responses
- **Fetch pipeline**: `/api/literature/fetch` route downloads the paper PDF, processes it through the upload pipeline, then triggers the Strategist Room agents

---

## Status

Fix is applied and ready to test. The user should retry fetching arXiv paper `2602.23318` to verify the 429 is handled gracefully now.
