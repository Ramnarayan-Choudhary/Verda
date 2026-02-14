'use client';

import { useState, useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';
import { Plus, LogOut, FlaskConical } from 'lucide-react';
import type { Conversation } from '@/types';

interface SidebarProps {
    activeConversationId: string | null;
    onSelect: (id: string) => void;
    onNewConversation: () => void;
}

async function loadConversations(): Promise<Conversation[]> {
    const res = await fetch('/api/conversations');
    if (res.ok) {
        return res.json();
    }
    return [];
}

export default function Sidebar({
    activeConversationId,
    onSelect,
    onNewConversation,
}: SidebarProps) {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const supabase = createClient();
    const router = useRouter();

    // Load on mount
    useEffect(() => {
        let cancelled = false;
        loadConversations().then(data => {
            if (!cancelled) setConversations(data);
        });
        return () => { cancelled = true; };
    }, []);

    // Re-fetch when active conversation changes (new conversation created)
    useEffect(() => {
        if (!activeConversationId) return;
        let cancelled = false;
        loadConversations().then(data => {
            if (!cancelled) setConversations(data);
        });
        return () => { cancelled = true; };
    }, [activeConversationId]);

    const handleLogout = async () => {
        await supabase.auth.signOut();
        router.push('/auth/login');
        router.refresh();
    };

    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <div className="sidebar-logo">VREDA.ai</div>
                <div className="sidebar-subtitle">Scientific Orchestrator</div>
                <button className="new-quest-btn" onClick={onNewConversation}>
                    <Plus size={16} />
                    New Research Quest
                </button>
            </div>

            <div className="sidebar-conversations">
                {conversations.length === 0 && (
                    <p style={{ fontSize: '13px', color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>
                        No quests yet. Start one!
                    </p>
                )}
                {conversations.map((conv) => (
                    <div
                        key={conv.id}
                        className={`conv-item ${conv.id === activeConversationId ? 'active' : ''}`}
                        onClick={() => onSelect(conv.id)}
                    >
                        <FlaskConical size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                        {conv.title}
                    </div>
                ))}
            </div>

            <div className="sidebar-footer">
                <button className="logout-btn" onClick={handleLogout}>
                    <LogOut size={14} />
                    Sign Out
                </button>
            </div>
        </aside>
    );
}
