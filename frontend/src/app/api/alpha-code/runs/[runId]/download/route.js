import { NextResponse } from 'next/server';

const PROD_API_URL = 'https://api.modelix.world';
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || PROD_API_URL).replace(/\/+$/, '');

async function handleDownload(request, params, explicitToken = null) {
    const { runId } = await params;
    const token = explicitToken || request.headers.get('x-nexarch-token') || request.nextUrl.searchParams.get('token');

    if (!token) {
        return NextResponse.json({ detail: 'Missing auth token' }, { status: 401 });
    }

    const upstream = await fetch(`${API_BASE}/api/v1/alpha-code/runs/${runId}/download`, {
        method: 'GET',
        headers: {
            Authorization: `Bearer ${token}`,
        },
        cache: 'no-store',
    });

    if (!upstream.ok) {
        const text = await upstream.text();
        let detail = text || upstream.statusText;
        try {
            const parsed = JSON.parse(text);
            detail = parsed?.detail || detail;
        } catch {
            // Keep plain text detail when body is not JSON.
        }
        return NextResponse.json({ detail }, { status: upstream.status });
    }

    const data = await upstream.arrayBuffer();
    const contentType = upstream.headers.get('content-type') || 'application/zip';
    const disposition = upstream.headers.get('content-disposition') || `attachment; filename="alpha_code_${runId}.zip"`;

    return new Response(data, {
        status: 200,
        headers: {
            'Content-Type': contentType,
            'Content-Disposition': disposition,
            'Content-Length': String(data.byteLength),
            'Cache-Control': 'no-store',
        },
    });
}

export async function GET(request, { params }) {
    return handleDownload(request, params);
}

export async function POST(request, { params }) {
    const formData = await request.formData();
    const bodyToken = formData.get('token');

    return handleDownload(request, params, bodyToken ? String(bodyToken) : null);
}
