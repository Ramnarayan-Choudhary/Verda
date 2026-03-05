import { logger } from '@/lib/logger';
import type { SupabaseClient } from '@supabase/supabase-js';

/**
 * Pipeline checkpoint utilities.
 * Saves progress after each major pipeline step to enable debugging and status tracking.
 *
 * Uses the documents.status field to encode progress:
 * - 'processing:step_name' during pipeline execution
 * - 'ready' on success
 * - 'error:step_name' on failure
 *
 * All operations are fire-and-forget (non-blocking) to avoid slowing the pipeline.
 */

export type PipelineStep =
    | 'upload'
    | 'extract_text'
    | 'chunk'
    | 'embed'
    | 'store_chunks'
    | 'parse_analysis'
    | 'research_intelligence'
    | 'scout'
    | 'store_session';

/**
 * Save a checkpoint for a pipeline step. Fire-and-forget.
 */
export function saveCheckpoint(
    supabase: SupabaseClient,
    documentId: string,
    step: PipelineStep
): void {
    supabase
        .from('documents')
        .update({ status: `processing:${step}` })
        .eq('id', documentId)
        .then(({ error }) => {
            if (error) {
                logger.warn('Checkpoint save failed', { documentId, step, error: error.message });
            }
        });
}

/**
 * Mark a pipeline step as failed with context. Fire-and-forget.
 */
export function saveFailure(
    supabase: SupabaseClient,
    documentId: string,
    failedStep: PipelineStep,
    reason: string
): void {
    supabase
        .from('documents')
        .update({ status: `error:${failedStep}` })
        .eq('id', documentId)
        .then(({ error }) => {
            if (error) {
                logger.warn('Failure checkpoint save failed', { documentId, failedStep, error: error.message });
            }
        });

    logger.error('Pipeline failed', new Error(reason), { documentId, failedStep });
}

/**
 * Mark pipeline as complete. Fire-and-forget.
 */
export function markComplete(
    supabase: SupabaseClient,
    documentId: string
): void {
    supabase
        .from('documents')
        .update({ status: 'ready' })
        .eq('id', documentId)
        .then(({ error }) => {
            if (error) {
                logger.warn('Complete checkpoint save failed', { documentId, error: error.message });
            }
        });
}
