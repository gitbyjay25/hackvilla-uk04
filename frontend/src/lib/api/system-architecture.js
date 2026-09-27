/**
 * System-Architecture API methods
 */
import { apiRequest, tokenStorage } from './auth';

const PROD_API_URL = 'https://api.modelix.world';
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || PROD_API_URL).replace(/\/+$/, '');

export const getGithubInstallUrl = () =>
    apiRequest('/api/v1/system-architecture/github/install-url');

export const listGithubInstallations = () =>
    apiRequest('/api/v1/system-architecture/github/installations');

export const upsertGithubInstallation = (data) =>
    apiRequest('/api/v1/system-architecture/github/installations', {
        method: 'POST',
        body: JSON.stringify(data),
    });

export const autoLinkGithubInstallation = (installationId) =>
    apiRequest(`/api/v1/system-architecture/github/installations/auto-link?installation_id=${encodeURIComponent(installationId)}`, {
        method: 'POST',
    });

export const listInstallationRepositories = (installationId) =>
    apiRequest(`/api/v1/system-architecture/github/installations/${installationId}/repositories`);

export const connectRepository = (data) =>
    apiRequest('/api/v1/system-architecture/repositories/connect', {
        method: 'POST',
        body: JSON.stringify(data),
    });

export const listConnectedRepositories = () =>
    apiRequest('/api/v1/system-architecture/repositories');

export const listSdkApps = () =>
    apiRequest('/api/v1/system-architecture/sdk-apps');

export const createRepositorySnapshot = (repositoryId, data) =>
    apiRequest(`/api/v1/system-architecture/repositories/${repositoryId}/snapshot`, {
        method: 'POST',
        body: JSON.stringify(data),
    });

export const analyzeRepository = (repositoryId, data) =>
    apiRequest(`/api/v1/system-architecture/repositories/${repositoryId}/analyze`, {
        method: 'POST',
        body: JSON.stringify(data),
    });

export const generateArchitectureVariants = (data) =>
    apiRequest('/api/v1/system-architecture/generate-variants', {
        method: 'POST',
        body: JSON.stringify(data),
    });

export const getVariantJob = (jobId) =>
    apiRequest(`/api/v1/system-architecture/jobs/${jobId}`);

export const listArchitectureDocuments = () =>
    apiRequest('/api/v1/system-architecture/documents');

export const getArchitectureGraphJson = (documentId) => {
    const query = new URLSearchParams();
    query.set('strict_deep', 'true');
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return apiRequest(`/api/v1/system-architecture/documents/${encodeURIComponent(documentId)}/graph-json${suffix}`);
};

export const listArchitectureVariants = (architectureDocumentId = null) => {
    const query = architectureDocumentId
        ? `?architecture_document_id=${encodeURIComponent(architectureDocumentId)}`
        : '';
    return apiRequest(`/api/v1/system-architecture/variants${query}`);
};

export const createVariantWorkflowReport = (variantId, data = {}) =>
    apiRequest(`/api/v1/system-architecture/variants/${encodeURIComponent(variantId)}/reports`, {
        method: 'POST',
        body: JSON.stringify(data),
    });

export const listVariantWorkflowReports = (variantId) =>
    apiRequest(`/api/v1/system-architecture/variants/${encodeURIComponent(variantId)}/reports`);

export const getVariantWorkflowReport = (reportId) =>
    apiRequest(`/api/v1/system-architecture/reports/${encodeURIComponent(reportId)}`);

export const downloadVariantWorkflowReportPdf = async (reportId) => {
    const token = tokenStorage.get();
    const response = await fetch(`${API_BASE_URL}/api/v1/system-architecture/reports/${encodeURIComponent(reportId)}/download`, {
        method: 'GET',
        mode: 'cors',
        headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
    });

    if (!response.ok) {
        let detail = response.statusText;
        try {
            const err = await response.json();
            detail = err?.detail || detail;
        } catch {
            // Keep status text when payload is not JSON.
        }
        throw new Error(detail || 'Failed to download workflow report');
    }

    const blob = await response.blob();
    const disposition = response.headers.get('content-disposition') || '';
    const fileNameMatch = disposition.match(/filename="?([^\"]+)"?/i);
    return {
        blob,
        filename: fileNameMatch?.[1] || `workflow_report_${reportId}.pdf`,
    };
};
