import { NextResponse } from 'next/server';
import { irisProxy } from '@/lib/iris-proxy';

export async function GET() {
    const res = await irisProxy('/api/idea');
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
}
