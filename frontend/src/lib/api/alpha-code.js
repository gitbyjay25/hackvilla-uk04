/**
 * Alpha-Code API methods
 */
import { apiRequest, tokenStorage } from './auth';

const PROD_API_URL = 'https://api.modelix.world';
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || PROD_API_URL).replace(/\/+$/, '');

export const createDeepPlan = (architectureVariantId) =>
    apiRequest('/api/v1/alpha-code/plan-deeply', {
        method: 'POST',
        body: JSON.stringify({ architecture_variant_id: architectureVariantId }),
    });

export const startAlphaRun = (architectureVariantId, deepPlanReportId) =>
    apiRequest('/api/v1/alpha-code/runs', {
        method: 'POST',
        body: JSON.stringify({
            architecture_variant_id: architectureVariantId,
            deep_plan_report_id: deepPlanReportId,
        }),
    });

export const listAlphaRuns = () =>
    apiRequest('/api/v1/alpha-code/runs');

export const getAlphaRun = (runId) =>
    apiRequest(`/api/v1/alpha-code/runs/${runId}`);

export const downloadAlphaRunArtifact = async (runId) => {
    const token = tokenStorage.get();
    let response = await fetch(`/api/alpha-code/runs/${runId}/download`, {
        method: 'GET',
        headers: {
            ...(token ? { 'x-nexarch-token': token } : {}),
        },
    });

    // If local API proxy route is unavailable (e.g., stale dev server),
    // fallback to direct backend download with bearer auth.
    if (response.status === 404) {
        response = await fetch(`${API_BASE_URL}/api/v1/alpha-code/runs/${runId}/download`, {
            method: 'GET',
            headers: {
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
        });
    }

    if (!response.ok) {
        let detail = response.statusText;
        try {
            const err = await response.json();
            detail = err?.detail || detail;
        } catch {
            // Keep default status text when response is not JSON.
        }
        throw new Error(detail || 'Failed to download artifact');
    }

    const blob = await response.blob();
    const disposition = response.headers.get('content-disposition') || '';
    const fileNameMatch = disposition.match(/filename="?([^\"]+)"?/i);
    return {
        blob,
        filename: fileNameMatch?.[1] || `alpha_code_${runId}.zip`,
    };
};

export const getAlphaRunDownloadUrl = (runId) =>
    `${API_BASE_URL}/api/v1/alpha-code/runs/${runId}/download`;

export const createSandboxSession = (alphaRunId) =>
    apiRequest('/api/v1/alpha-code/sandbox/sessions', {
        method: 'POST',
        body: JSON.stringify({ alpha_run_id: alphaRunId }),
    });

export const listSandboxSessions = (alphaRunId = null) => {
    const suffix = alphaRunId ? `?alpha_run_id=${encodeURIComponent(alphaRunId)}` : '';
    return apiRequest(`/api/v1/alpha-code/sandbox/sessions${suffix}`);
};

export const getSandboxSession = (sessionId) =>
    apiRequest(`/api/v1/alpha-code/sandbox/sessions/${sessionId}`);

export const startSandboxSession = (sessionId) =>
    apiRequest(`/api/v1/alpha-code/sandbox/sessions/${sessionId}/start`, {
        method: 'POST',
    });

export const stopSandboxSession = (sessionId) =>
    apiRequest(`/api/v1/alpha-code/sandbox/sessions/${sessionId}/stop`, {
        method: 'POST',
    });

export const runSandboxCommand = (sessionId, command, timeoutSeconds = null) =>
    apiRequest(`/api/v1/alpha-code/sandbox/sessions/${sessionId}/commands`, {
        method: 'POST',
        body: JSON.stringify({
            command,
            timeout_seconds: timeoutSeconds,
        }),
    });

export const runSandboxTests = (sessionId, data) =>
    apiRequest(`/api/v1/alpha-code/sandbox/sessions/${sessionId}/tests/run`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
    });

export const runSandboxAutofix = (sessionId, data) =>
    apiRequest(`/api/v1/alpha-code/sandbox/sessions/${sessionId}/autofix`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
    });

export const runSandboxAutoValidation = (sessionId, data) =>
    apiRequest(`/api/v1/alpha-code/sandbox/sessions/${sessionId}/validate-auto`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
    });

export const listSandboxLogs = (sessionId, limit = 50) =>
    apiRequest(`/api/v1/alpha-code/sandbox/sessions/${sessionId}/logs?limit=${encodeURIComponent(String(limit))}`);

export const uploadSandboxTests = async (sessionId, files, targetSubdir = 'uploaded_tests') => {
    const token = tokenStorage.get();
    const form = new FormData();
    form.append('target_subdir', targetSubdir);
    (files || []).forEach((file) => form.append('files', file));

    const response = await fetch(`${API_BASE_URL}/api/v1/alpha-code/sandbox/sessions/${sessionId}/tests/upload`, {
        method: 'POST',
        headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: form,
    });

    if (!response.ok) {
        let detail = response.statusText;
        try {
            const err = await response.json();
            detail = err?.detail || detail;
        } catch {
            // Keep fallback detail.
        }
        throw new Error(detail || 'Failed to upload tests');
    }

    return response.json();
};
