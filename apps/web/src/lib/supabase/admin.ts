import { createClient } from '@supabase/supabase-js';
import { config } from '@/lib/config';

/**
 * Creates a Supabase admin client using the service role key.
 * This bypasses RLS and should ONLY be used for trusted server-side operations:
 * - Storage uploads (where RLS on storage.objects is tricky)
 * - Background jobs (saving assistant responses after stream completes)
 */
export function createAdminSupabaseClient() {
    return createClient(config.supabase.url, config.supabase.serviceRoleKey, {
        auth: {
            autoRefreshToken: false,
            persistSession: false,
        },
    });
}
