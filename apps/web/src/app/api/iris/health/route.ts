import { NextResponse } from 'next/server';
import { isIrisHealthy } from '@/lib/iris-proxy';

export async function GET() {
    const healthy = await isIrisHealthy();
    return NextResponse.json({ healthy, service: 'iris-ideation' });
}
