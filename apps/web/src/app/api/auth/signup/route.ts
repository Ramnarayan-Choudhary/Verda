import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

type SignupBody = {
    email?: string;
    password?: string;
};

export async function POST(request: Request) {
    try {
        const body = (await request.json()) as SignupBody;
        const email = body.email?.trim().toLowerCase();
        const password = body.password ?? '';

        if (!email || !password) {
            return NextResponse.json(
                { error: 'Email and password are required.' },
                { status: 400 }
            );
        }

        if (password.length < 6) {
            return NextResponse.json(
                { error: 'Password must be at least 6 characters.' },
                { status: 400 }
            );
        }

        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
        const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

        if (!supabaseUrl || !serviceRoleKey) {
            return NextResponse.json(
                { error: 'Server auth configuration is missing.' },
                { status: 500 }
            );
        }

        const adminClient = createClient(supabaseUrl, serviceRoleKey, {
            auth: {
                autoRefreshToken: false,
                persistSession: false,
            },
        });

        const { error } = await adminClient.auth.admin.createUser({
            email,
            password,
            email_confirm: true,
        });

        if (error) {
            const message = error.message.toLowerCase();
            if (
                message.includes('already been registered') ||
                message.includes('already registered') ||
                message.includes('user already exists')
            ) {
                return NextResponse.json(
                    { error: 'Account already exists. Please sign in.' },
                    { status: 409 }
                );
            }

            return NextResponse.json({ error: error.message }, { status: 400 });
        }

        return NextResponse.json({ ok: true }, { status: 201 });
    } catch {
        return NextResponse.json(
            { error: 'Invalid signup request payload.' },
            { status: 400 }
        );
    }
}
