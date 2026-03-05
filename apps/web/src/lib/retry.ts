import { logger } from './logger';

interface RetryOptions {
    maxRetries: number;
    baseDelayMs: number;
    maxDelayMs: number;
}

const DEFAULT_OPTIONS: RetryOptions = {
    maxRetries: 3,
    baseDelayMs: 1000,
    maxDelayMs: 8000,
};

export async function withRetry<T>(
    fn: () => Promise<T>,
    label: string,
    options: Partial<RetryOptions> = {}
): Promise<T> {
    const opts = { ...DEFAULT_OPTIONS, ...options };
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= opts.maxRetries; attempt++) {
        try {
            return await fn();
        } catch (error) {
            lastError = error instanceof Error ? error : new Error(String(error));

            if (attempt === opts.maxRetries) {
                logger.error(`${label}: All ${opts.maxRetries} attempts failed`, lastError);
                throw lastError;
            }

            const delay = Math.min(
                opts.baseDelayMs * Math.pow(2, attempt - 1),
                opts.maxDelayMs
            );
            logger.warn(`${label}: Attempt ${attempt}/${opts.maxRetries} failed, retrying in ${delay}ms`, {
                error: lastError.message,
            });
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }

    throw lastError;
}
