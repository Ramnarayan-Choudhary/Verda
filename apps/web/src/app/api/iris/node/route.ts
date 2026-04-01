import { NextRequest, NextResponse } from 'next/server';
import { irisProxy } from '@/lib/iris-proxy';

export async function POST(req: NextRequest) {
    const body = await req.json();
    const res = await irisProxy('/api/node', { method: 'POST', body });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
}
