import { NextResponse } from 'next/server';
import { irisProxy } from '@/lib/iris-proxy';

export async function POST() {
    const res = await irisProxy('/api/reset', { method: 'POST' });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
}
