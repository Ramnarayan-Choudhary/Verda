export class VredaError extends Error {
    constructor(
        message: string,
        public code: string,
        public statusCode: number = 500,
        public context?: Record<string, unknown>
    ) {
        super(message);
        this.name = 'VredaError';
    }
}

export class EmbeddingError extends VredaError {
    constructor(message: string, context?: Record<string, unknown>) {
        super(message, 'EMBEDDING_ERROR', 502, context);
        this.name = 'EmbeddingError';
    }
}

export class LLMError extends VredaError {
    constructor(message: string, context?: Record<string, unknown>) {
        super(message, 'LLM_ERROR', 502, context);
        this.name = 'LLMError';
    }
}

export class ValidationError extends VredaError {
    constructor(message: string, context?: Record<string, unknown>) {
        super(message, 'VALIDATION_ERROR', 400, context);
        this.name = 'ValidationError';
    }
}

export class StorageError extends VredaError {
    constructor(message: string, context?: Record<string, unknown>) {
        super(message, 'STORAGE_ERROR', 500, context);
        this.name = 'StorageError';
    }
}

export class AgentError extends VredaError {
    constructor(
        message: string,
        public agentName: string,
        context?: Record<string, unknown>
    ) {
        super(message, 'AGENT_ERROR', 502, { agentName, ...context });
        this.name = 'AgentError';
    }
}
