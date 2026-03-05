'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';

export default function ResetPasswordPage() {
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [loading, setLoading] = useState(false);
    const router = useRouter();
    const supabase = useMemo(() => createClient(), []);

    const handlePasswordUpdate = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setSuccess('');

        if (password !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }

        if (password.length < 6) {
            setError('Password must be at least 6 characters');
            return;
        }

        setLoading(true);

        const { error } = await supabase.auth.updateUser({ password });

        if (error) {
            if (error.message.toLowerCase().includes('auth session missing')) {
                setError('Reset link expired or invalid. Request a new reset link.');
            } else {
                setError(error.message);
            }
            setLoading(false);
            return;
        }

        setSuccess('Password updated. Redirecting to sign in...');
        setLoading(false);

        setTimeout(async () => {
            await supabase.auth.signOut();
            router.push('/auth/login');
            router.refresh();
        }, 1200);
    };

    return (
        <div className="auth-container">
            <div className="auth-card">
                <div className="auth-logo">
                    <h1>VREDA.ai</h1>
                    <p>Set a new password</p>
                </div>

                {error && <div className="auth-error">{error}</div>}
                {success && <div className="auth-success">{success}</div>}

                <form onSubmit={handlePasswordUpdate} className="auth-form" style={{ marginTop: '18px' }}>
                    <div className="auth-field">
                        <label htmlFor="password">New Password</label>
                        <input
                            id="password"
                            type="password"
                            placeholder="Min. 6 characters"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>

                    <div className="auth-field">
                        <label htmlFor="confirmPassword">Confirm New Password</label>
                        <input
                            id="confirmPassword"
                            type="password"
                            placeholder="••••••••"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            required
                        />
                    </div>

                    <button type="submit" className="auth-btn" disabled={loading}>
                        {loading ? 'Updating password...' : 'Update password'}
                    </button>
                </form>

                <p className="auth-link" style={{ marginTop: '12px' }}>
                    Link expired? <Link href="/auth/forgot-password">Request a new reset link</Link>
                </p>

                <p className="auth-link" style={{ marginTop: '16px' }}>
                    <Link href="/auth/login">Back to sign in</Link>
                </p>
            </div>
        </div>
    );
}
