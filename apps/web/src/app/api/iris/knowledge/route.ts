import { NextRequest, NextResponse } from 'next/server';
import { irisProxy } from '@/lib/iris-proxy';

export async function GET() {
    const res = await irisProxy('/api/knowledge');
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
    const body = await req.json();
    const res = await irisProxy('/api/add_knowledge', { method: 'POST', body });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
}
