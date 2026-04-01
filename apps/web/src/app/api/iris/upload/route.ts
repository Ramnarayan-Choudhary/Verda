import { NextRequest, NextResponse } from 'next/server';
import { irisProxy } from '@/lib/iris-proxy';

export async function POST(req: NextRequest) {
    const formData = await req.formData();
    const res = await irisProxy('/api/upload', {
        method: 'POST',
        body: formData,
        timeout: 60_000,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
}
