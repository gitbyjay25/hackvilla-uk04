/**
 * Dashboard API methods
 */
import { apiRequest } from './auth';

export const getDashboardOverview = () => apiRequest('/api/v1/dashboard/overview');
export const getDashboardHealth = () => apiRequest('/api/v1/dashboard/health');
export const getArchitectureMap = () => apiRequest('/api/v1/dashboard/architecture-map');
export const getServices = () => apiRequest('/api/v1/dashboard/services');
export const getServiceMetrics = (serviceName) =>
    apiRequest(`/api/v1/dashboard/services/${encodeURIComponent(serviceName)}/metrics`);
export const getTrends = (hours = 24) =>
    apiRequest(`/api/v1/dashboard/trends?hours=${hours}`);
export const getInsights = () => apiRequest('/api/v1/dashboard/insights');
export const getBottlenecks = () => apiRequest('/api/v1/dashboard/bottlenecks');
export const getWorkflows = (goal = 'optimize_performance') =>
    apiRequest(`/api/v1/dashboard/workflows?goal=${encodeURIComponent(goal)}`);
export const getRecommendations = () => apiRequest('/api/v1/dashboard/recommendations');
export const getStreamStatus = () => apiRequest('/api/v1/stream/status');
