/**
 * Nexarch API Client — backward-compatible facade
 *
 * All domain logic is now in focused modules under src/lib/api/.
 * This file imports from those modules and re-exports as the `apiClient`
 * singleton so all existing pages continue to work unchanged.
 *
 * New code should import directly from the domain modules, e.g.:
 *   import { getDashboardOverview } from '@/lib/api/dashboard';
 */

import { tokenStorage, apiRequest } from './api/auth';
import * as authApi from './api/auth';
import * as dashboardApi from './api/dashboard';
import * as adminApi from './api/admin';
import * as systemArchitectureApi from './api/system-architecture';
import * as alphaCodeApi from './api/alpha-code';

class NexarchClient {
    // ── Token / session helpers ─────────────────────────────────────────
    getToken()            { return tokenStorage.get(); }
    setToken(token)       { tokenStorage.set(token); }
    removeToken()         { tokenStorage.remove(); }
    getUser()             { return tokenStorage.getUser(); }
    setUser(user)         { tokenStorage.setUser(user); }

    /** Low-level fetch wrapper (kept for any internal callers). */
    async request(endpoint, options = {}) { return apiRequest(endpoint, options); }

    // ── Auth ────────────────────────────────────────────────────────────
    signup(email, password, fullName = null) { return authApi.signup(email, password, fullName); }
    login(email, password)                  { return authApi.login(email, password); }
    getGoogleAuthUrl()                       { return authApi.getGoogleAuthUrl(); }
    googleSignIn(code, state = null)         { return authApi.googleSignIn(code, state); }
    getCurrentUser()                         { return authApi.getCurrentUser(); }
    updateProfile(profile)                   { return authApi.updateProfile(profile); }
    getGoogleStatus()                        { return authApi.getGoogleStatus(); }
    logout()                                 { return authApi.logout(); }

    // ── Health & System ─────────────────────────────────────────────────
    getHealth()           { return adminApi.getHealth(); }
    getHealthDetailed()   { return adminApi.getHealthDetailed(); }
    getSystemInfo()       { return adminApi.getSystemInfo(); }
    getSystemStats()      { return adminApi.getSystemStats(); }

    // ── Dashboard ───────────────────────────────────────────────────────
    getDashboardOverview()              { return dashboardApi.getDashboardOverview(); }
    getArchitectureMap()                { return dashboardApi.getArchitectureMap(); }
    getServices()                       { return dashboardApi.getServices(); }
    getServiceMetrics(name)             { return dashboardApi.getServiceMetrics(name); }
    getTrends(hours = 24)               { return dashboardApi.getTrends(hours); }
    getInsights()                       { return dashboardApi.getInsights(); }
    getDashboardHealth()                { return dashboardApi.getDashboardHealth(); }
    getBottlenecks()                    { return dashboardApi.getBottlenecks(); }
    getWorkflows(goal)                  { return dashboardApi.getWorkflows(goal); }
    getRecommendations()                { return dashboardApi.getRecommendations(); }
    getStreamStatus()                   { return dashboardApi.getStreamStatus(); }

    // ── Admin, Cache, API Keys ───────────────────────────────────────────
    createTenant(data)                  { return adminApi.createTenant(data); }
    getTenants()                        { return adminApi.getTenants(); }
    getTenant(id)                       { return adminApi.getTenant(id); }
    updateTenant(id, data)              { return adminApi.updateTenant(id, data); }
    deleteTenant(id)                    { return adminApi.deleteTenant(id); }
    getCacheStats()                     { return adminApi.getCacheStats(); }
    invalidateCache()                   { return adminApi.invalidateCache(); }
    invalidateCacheOperation(op)        { return adminApi.invalidateCacheOperation(op); }
    warmCache(op)                       { return adminApi.warmCache(op); }
    generateApiKey(name)                { return adminApi.generateApiKey(name); }
    listApiKeys()                       { return adminApi.listApiKeys(); }
    revokeApiKey(key)                   { return adminApi.revokeApiKey(key); }
    generateSampleData(count = 100)     { return adminApi.generateSampleData(count); }
    clearData()                         { return adminApi.clearData(); }
    clearDemoData()                     { return adminApi.clearData(); }

    // ── System-Architecture ─────────────────────────────────────────────
    getGithubInstallUrl()               { return systemArchitectureApi.getGithubInstallUrl(); }
    listGithubInstallations()           { return systemArchitectureApi.listGithubInstallations(); }
    upsertGithubInstallation(data)      { return systemArchitectureApi.upsertGithubInstallation(data); }
    autoLinkGithubInstallation(id)      { return systemArchitectureApi.autoLinkGithubInstallation(id); }
    listInstallationRepositories(id)    { return systemArchitectureApi.listInstallationRepositories(id); }
    connectRepository(data)             { return systemArchitectureApi.connectRepository(data); }
    listConnectedRepositories()         { return systemArchitectureApi.listConnectedRepositories(); }
    listSdkApps()                       { return systemArchitectureApi.listSdkApps(); }
    createRepositorySnapshot(id, data)  { return systemArchitectureApi.createRepositorySnapshot(id, data); }
    analyzeRepository(id, data)         { return systemArchitectureApi.analyzeRepository(id, data); }
    generateArchitectureVariants(data)  { return systemArchitectureApi.generateArchitectureVariants(data); }
    getVariantJob(jobId)                { return systemArchitectureApi.getVariantJob(jobId); }
    listArchitectureDocuments()         { return systemArchitectureApi.listArchitectureDocuments(); }
    getArchitectureGraphJson(docId)     { return systemArchitectureApi.getArchitectureGraphJson(docId); }
    listArchitectureVariants(docId)     { return systemArchitectureApi.listArchitectureVariants(docId); }
    createVariantWorkflowReport(variantId, data) { return systemArchitectureApi.createVariantWorkflowReport(variantId, data); }
    listVariantWorkflowReports(variantId) { return systemArchitectureApi.listVariantWorkflowReports(variantId); }
    getVariantWorkflowReport(reportId) { return systemArchitectureApi.getVariantWorkflowReport(reportId); }
    downloadVariantWorkflowReportPdf(reportId) { return systemArchitectureApi.downloadVariantWorkflowReportPdf(reportId); }

    // ── Alpha-Code ───────────────────────────────────────────────────────
    createDeepPlan(variantId)           { return alphaCodeApi.createDeepPlan(variantId); }
    startAlphaRun(variantId, planId)    { return alphaCodeApi.startAlphaRun(variantId, planId); }
    listAlphaRuns()                     { return alphaCodeApi.listAlphaRuns(); }
    getAlphaRun(runId)                  { return alphaCodeApi.getAlphaRun(runId); }
    downloadAlphaRunArtifact(runId)     { return alphaCodeApi.downloadAlphaRunArtifact(runId); }
    getAlphaRunDownloadUrl(runId)       { return alphaCodeApi.getAlphaRunDownloadUrl(runId); }
    createSandboxSession(alphaRunId)    { return alphaCodeApi.createSandboxSession(alphaRunId); }
    listSandboxSessions(alphaRunId = null) { return alphaCodeApi.listSandboxSessions(alphaRunId); }
    getSandboxSession(sessionId)         { return alphaCodeApi.getSandboxSession(sessionId); }
    startSandboxSession(sessionId)       { return alphaCodeApi.startSandboxSession(sessionId); }
    stopSandboxSession(sessionId)        { return alphaCodeApi.stopSandboxSession(sessionId); }
    runSandboxCommand(sessionId, command, timeoutSeconds = null) { return alphaCodeApi.runSandboxCommand(sessionId, command, timeoutSeconds); }
    uploadSandboxTests(sessionId, files, targetSubdir = 'uploaded_tests') { return alphaCodeApi.uploadSandboxTests(sessionId, files, targetSubdir); }
    runSandboxTests(sessionId, data)     { return alphaCodeApi.runSandboxTests(sessionId, data); }
    runSandboxAutofix(sessionId, data)   { return alphaCodeApi.runSandboxAutofix(sessionId, data); }
    runSandboxAutoValidation(sessionId, data) { return alphaCodeApi.runSandboxAutoValidation(sessionId, data); }
    listSandboxLogs(sessionId, limit = 50) { return alphaCodeApi.listSandboxLogs(sessionId, limit); }
}

// Export singleton instance (backward compatible)
export const apiClient = new NexarchClient();
export default apiClient;

// Re-export domain modules for new code that imports directly
export { tokenStorage, apiRequest } from './api/auth';
export * as authApi from './api/auth';
export * as dashboardApi from './api/dashboard';
export * as adminApi from './api/admin';
export * as systemArchitectureApi from './api/system-architecture';
export * as alphaCodeApi from './api/alpha-code';
