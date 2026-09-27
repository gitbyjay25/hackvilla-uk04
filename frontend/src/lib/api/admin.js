/**
 * Admin, Cache, Health, System, and API Key management methods
 */
import { apiRequest } from './auth';

// System & Health
export const getHealth = () => apiRequest('/api/v1/health');
export const getHealthDetailed = () => apiRequest('/api/v1/health/detailed');
export const getSystemInfo = () => apiRequest('/api/v1/system/info');
export const getSystemStats = () => apiRequest('/api/v1/system/stats');

// Tenant Admin
export const createTenant = (data) =>
    apiRequest('/api/v1/admin/tenants', { method: 'POST', body: JSON.stringify(data) });
export const getTenants = () => apiRequest('/api/v1/admin/tenants');
export const getTenant = (id) => apiRequest(`/api/v1/admin/tenants/${id}`);
export const updateTenant = (id, data) =>
    apiRequest(`/api/v1/admin/tenants/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
export const deleteTenant = (id) =>
    apiRequest(`/api/v1/admin/tenants/${id}`, { method: 'DELETE' });

// Cache
export const getCacheStats = () => apiRequest('/api/v1/cache/stats');
export const invalidateCache = () =>
    apiRequest('/api/v1/cache/invalidate', { method: 'DELETE' });
export const invalidateCacheOperation = (op) =>
    apiRequest(`/api/v1/cache/invalidate/${op}`, { method: 'DELETE' });
export const warmCache = (op) =>
    apiRequest(`/api/v1/cache/warm/${op}`, { method: 'POST' });

// API Keys
export const generateApiKey = (name) =>
    apiRequest('/api/v1/api-keys/', { method: 'POST', body: JSON.stringify({ name }) });
export const listApiKeys = () => apiRequest('/api/v1/api-keys/');
export const revokeApiKey = (keyPreview) =>
    apiRequest(`/api/v1/api-keys/${keyPreview.split('...')[0]}`, { method: 'DELETE' });

// Demo / Dev
export const generateSampleData = (count = 100) =>
    apiRequest(`/api/v1/demo/generate-sample-data?count=${count}`, { method: 'POST' });
export const clearData = () => apiRequest('/api/v1/demo/clear-data', { method: 'DELETE' });
