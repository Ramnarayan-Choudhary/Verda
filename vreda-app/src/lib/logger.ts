type LogContext = Record<string, unknown>;

const isDev = process.env.NODE_ENV !== 'production';

function formatMessage(level: string, message: string, context?: LogContext, error?: Error): string {
    if (isDev) {
        const ctx = context ? ` ${JSON.stringify(context)}` : '';
        const err = error ? `\n  ${error.stack || error.message}` : '';
        return `[VREDA:${level}] ${message}${ctx}${err}`;
    }
    return JSON.stringify({
        level,
        message,
        ...context,
        ...(error && { error: { name: error.name, message: error.message, stack: error.stack } }),
        timestamp: new Date().toISOString(),
    });
}

export const logger = {
    info(message: string, context?: LogContext): void {
        console.log(formatMessage('INFO', message, context));
    },

    warn(message: string, context?: LogContext): void {
        console.warn(formatMessage('WARN', message, context));
    },

    error(message: string, error?: Error, context?: LogContext): void {
        console.error(formatMessage('ERROR', message, context, error));
    },

    debug(message: string, context?: LogContext): void {
        if (isDev) {
            console.debug(formatMessage('DEBUG', message, context));
        }
    },
};
