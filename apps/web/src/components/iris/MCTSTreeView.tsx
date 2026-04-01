'use client';

import { useEffect, useRef, useCallback } from 'react';
import type { IrisMCTSTreeNode } from '@/types/iris';
import { IRIS_ACTION_COLORS } from '@/types/iris';

interface MCTSTreeViewProps {
    treeData: IrisMCTSTreeNode | null;
    onNodeSelect: (nodeId: string) => void;
    currentNodeId?: string;
}

interface FlatNode {
    id: string;
    action: string;
    depth: number;
    x: number;
    y: number;
    reward: number;
    visits: number;
    isCurrentNode: boolean;
    parentId?: string;
    ideaPreview: string;
}

function flattenTree(node: IrisMCTSTreeNode, depth = 0, xOffset = 0, spread = 1, parentId?: string): FlatNode[] {
    const nodes: FlatNode[] = [];
    const flat: FlatNode = {
        id: node.id,
        action: node.action || 'research_goal',
        depth,
        x: xOffset,
        y: depth * 100 + 40,
        reward: node.reward || 0,
        visits: node.visits || 0,
        isCurrentNode: node.isCurrentNode || false,
        parentId,
        ideaPreview: (node.state?.current_idea || node.idea || '').slice(0, 60),
    };
    nodes.push(flat);

    const children = node.children || [];
    const childSpread = spread / Math.max(children.length, 1);
    const startX = xOffset - (spread / 2) + (childSpread / 2);

    children.forEach((child, i) => {
        nodes.push(...flattenTree(child, depth + 1, startX + i * childSpread, childSpread, node.id));
    });

    return nodes;
}

export default function MCTSTreeView({ treeData, onNodeSelect, currentNodeId }: MCTSTreeViewProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const nodesRef = useRef<FlatNode[]>([]);

    const draw = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas || !treeData) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;

        ctx.clearRect(0, 0, w, h);

        // Flatten tree
        const nodes = flattenTree(treeData, 0, w / 2, w * 0.8);
        nodesRef.current = nodes;

        const nodeMap = new Map<string, FlatNode>();
        for (const n of nodes) nodeMap.set(n.id, n);

        // Draw edges
        ctx.strokeStyle = 'rgba(99, 102, 241, 0.3)';
        ctx.lineWidth = 1.5;
        for (const n of nodes) {
            if (n.parentId) {
                const parent = nodeMap.get(n.parentId);
                if (parent) {
                    ctx.beginPath();
                    ctx.moveTo(parent.x, parent.y + 14);
                    const midY = (parent.y + 14 + n.y - 14) / 2;
                    ctx.bezierCurveTo(parent.x, midY, n.x, midY, n.x, n.y - 14);
                    ctx.stroke();
                }
            }
        }

        // Draw nodes
        for (const n of nodes) {
            const color = IRIS_ACTION_COLORS[n.action] || '#6366f1';
            const isSelected = n.id === currentNodeId || n.isCurrentNode;
            const radius = isSelected ? 16 : 12;

            // Glow for selected
            if (isSelected) {
                ctx.shadowColor = color;
                ctx.shadowBlur = 12;
            }

            // Node circle
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.globalAlpha = 0.9;
            ctx.fill();
            ctx.globalAlpha = 1;

            // Border
            ctx.strokeStyle = isSelected ? '#fff' : 'rgba(255,255,255,0.2)';
            ctx.lineWidth = isSelected ? 2 : 1;
            ctx.stroke();

            ctx.shadowColor = 'transparent';
            ctx.shadowBlur = 0;

            // Label
            ctx.fillStyle = '#e8eaf0';
            ctx.font = '10px Inter, sans-serif';
            ctx.textAlign = 'center';
            const label = n.action.replace(/_/g, ' ').replace('and ', '& ');
            ctx.fillText(label.length > 18 ? label.slice(0, 16) + '..' : label, n.x, n.y + radius + 14);

            // Visit count
            if (n.visits > 0) {
                ctx.fillStyle = 'rgba(255,255,255,0.5)';
                ctx.font = '9px Inter, sans-serif';
                ctx.fillText(`v:${n.visits}`, n.x, n.y + radius + 26);
            }
        }
    }, [treeData, currentNodeId]);

    useEffect(() => {
        draw();
        const handleResize = () => draw();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [draw]);

    const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        for (const n of nodesRef.current) {
            const dx = n.x - x;
            const dy = n.y - y;
            if (Math.sqrt(dx * dx + dy * dy) <= 18) {
                onNodeSelect(n.id);
                break;
            }
        }
    };

    if (!treeData) {
        return (
            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                height: 200, color: 'var(--text-secondary, #8b8fa3)', fontSize: 13,
            }}>
                No exploration tree yet. Start a research ideation to build the tree.
            </div>
        );
    }

    return (
        <div style={{
            background: 'var(--bg-elevated, #12121f)',
            border: '1px solid var(--border-subtle, #1e1e35)',
            borderRadius: 'var(--radius-lg, 12px)',
            overflow: 'hidden',
        }}>
            <div style={{
                padding: '10px 16px',
                borderBottom: '1px solid var(--border-subtle, #1e1e35)',
                fontSize: 13, fontWeight: 600,
                color: 'var(--text-primary, #e8eaf0)',
                display: 'flex', alignItems: 'center', gap: 8,
            }}>
                <span>Exploration Tree</span>
                <span style={{ fontSize: 10, color: 'var(--text-secondary)', fontWeight: 400 }}>
                    (click nodes to navigate)
                </span>
            </div>
            <canvas
                ref={canvasRef}
                onClick={handleClick}
                style={{ width: '100%', height: 350, cursor: 'pointer', display: 'block' }}
            />
            {/* Legend */}
            <div style={{
                display: 'flex', gap: 12, padding: '8px 16px', flexWrap: 'wrap',
                borderTop: '1px solid var(--border-subtle, #1e1e35)',
            }}>
                {Object.entries(IRIS_ACTION_COLORS).map(([action, color]) => (
                    <div key={action} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}>
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
                        <span style={{ color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                            {action.replace(/_/g, ' ')}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
