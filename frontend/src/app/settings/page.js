'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { apiClient } from '@/lib/api-client';
import { isAdminUserEmail } from '@/lib/admin-access';
import Navbar from '@/components/Navbar';
import {
    Settings,
    Database,
    RefreshCw,
    Trash2,
    Zap,
    AlertTriangle,
    CheckCircle,
    HardDrive,
    Key,
    Clock,
    Activity,
    BarChart3,
    Play,
    Server,
    Layers,
    Flame
} from 'lucide-react';

const PROD_API_URL = 'https://api.modelix.world';
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || PROD_API_URL).replace(/\/+$/, '');

export default function SettingsPage() {
    const { isAuthenticated, loading: authLoading, user } = useAuth();
    const isAdminUser = isAdminUserEmail(user?.email);
    const [cacheStats, setCacheStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const [actionLoading, setActionLoading] = useState(null);
    const [googleStatus, setGoogleStatus] = useState(null);

    // Available cache operations
    const cacheOperations = [
        { id: 'dashboard_overview', label: 'Dashboard Overview', icon: BarChart3 },
        { id: 'architecture_map', label: 'Architecture Map', icon: Layers },
        { id: 'services', label: 'Services', icon: Server },
        { id: 'trends', label: 'Trends', icon: Activity },
        { id: 'insights', label: 'Insights', icon: Zap },
        { id: 'recommendations', label: 'Recommendations', icon: Zap },
        { id: 'bottlenecks', label: 'Bottlenecks', icon: AlertTriangle },
        { id: 'health', label: 'Health', icon: Activity },
        { id: 'architecture_current', label: 'Current Architecture', icon: Database },
        { id: 'architecture_issues', label: 'Architecture Issues', icon: AlertTriangle }
    ];

    useEffect(() => {
        if (!authLoading && isAuthenticated && isAdminUser) {
            fetchCacheStats();
        }
    }, [authLoading, isAuthenticated, isAdminUser]);

    const fetchCacheStats = async () => {
        setLoading(true);
        setError(null);
        try {
            const [cacheData, oauthData] = await Promise.all([
                apiClient.getCacheStats(),
                apiClient.getGoogleStatus().catch(() => null),
            ]);
            setCacheStats(cacheData);
            setGoogleStatus(oauthData);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleInvalidateAll = async () => {
        if (!confirm('Are you sure you want to invalidate all cache? This may temporarily increase API response times.')) {
            return;
        }
        setActionLoading('invalidate-all');
        setError(null);
        setSuccess(null);
        try {
            await apiClient.invalidateCache();
            setSuccess('All cache invalidated successfully');
            fetchCacheStats();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    };

    const handleInvalidateOperation = async (operation) => {
        setActionLoading(`invalidate-${operation}`);
        setError(null);
        setSuccess(null);
        try {
            await apiClient.invalidateCacheOperation(operation);
            setSuccess(`Cache for "${operation}" invalidated successfully`);
            fetchCacheStats();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    };

    const handleWarmCache = async (operation) => {
        setActionLoading(`warm-${operation}`);
        setError(null);
        setSuccess(null);
        try {
            await apiClient.warmCache(operation);
            setSuccess(`Cache for "${operation}" warmed successfully`);
            fetchCacheStats();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    };

    const handleGenerateSampleData = async () => {
        if (!confirm('This will generate sample data for testing. Proceed?')) {
            return;
        }
        setActionLoading('generate-sample');
        setError(null);
        setSuccess(null);
        try {
            await apiClient.generateSampleData();
            setSuccess('Sample data generated successfully');
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    };

    const handleClearDemoData = async () => {
        if (!confirm('WARNING: This will delete all demo data. This action cannot be undone. Are you sure?')) {
            return;
        }
        setActionLoading('clear-demo');
        setError(null);
        setSuccess(null);
        try {
            await apiClient.clearDemoData();
            setSuccess('Demo data cleared successfully');
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    };

    const formatBytes = (bytes) => {
        if (!bytes) return '0 B';
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`;
    };

    if (authLoading) {
        return (
            <div className="page-loading">
                <div className="spinner"></div>
                <p>Loading...</p>
            </div>
        );
    }

    if (!isAuthenticated) {
        return (
            <div className="auth-required">
                <h2 className="display-title display-md">ACCESS REQUIRED</h2>
                <p>Please sign in to access settings.</p>
                <Link href="/login" className="btn btn-primary">Sign In</Link>
            </div>
        );
    }

    if (!isAdminUser) {
        return (
            <div className="auth-required">
                <h2 className="display-title display-md">ADMIN ONLY</h2>
                <p>You do not have permission to access settings.</p>
                <Link href="/dashboard" className="btn btn-primary">Go to Dashboard</Link>
            </div>
        );
    }

    return (
        <>
            <Navbar />
            <div className="dashboard-page">
                <div className="dashboard-content">
                <div className="dashboard-header">
                    <div>
                        <span className="tape-label">System Configuration</span>
                        <h1 className="display-title display-md" style={{ marginTop: '0.5rem' }}>
                            SETTINGS
                        </h1>
                    </div>
                    <div className="dashboard-header__actions">
                        <button onClick={fetchCacheStats} className="btn btn-secondary" disabled={loading}>
                            <RefreshCw size={16} className={loading ? 'spinning' : ''} />
                            Refresh
                        </button>
                    </div>
                </div>

                {error && (
                    <div className="dashboard-error">
                        {error}
                    </div>
                )}

                {success && (
                    <div className="dashboard-success">
                        <CheckCircle size={16} />
                        {success}
                    </div>
                )}

                <div className="settings-layout">
                    {/* Cache Statistics */}
                    <div className="settings-section">
                        <div className="settings-section__header">
                            <Database size={20} />
                            <h2>Cache Statistics</h2>
                        </div>

                        {loading ? (
                            <div className="loading-state">
                                <div className="spinner"></div>
                                <p>Loading cache stats...</p>
                            </div>
                        ) : cacheStats ? (
                            <div className="cache-stats-content">
                                {/* Overview Stats */}
                                <div className="cache-overview">
                                    <div className="cache-stat-card">
                                        <div className="cache-stat-card__icon">
                                            <HardDrive size={24} />
                                        </div>
                                        <div className="cache-stat-card__content">
                                            <span className="cache-stat-card__label">Total Keys</span>
                                            <span className="cache-stat-card__value">{cacheStats.total_keys || 0}</span>
                                        </div>
                                    </div>

                                    <div className="cache-stat-card">
                                        <div className="cache-stat-card__icon">
                                            <Database size={24} />
                                        </div>
                                        <div className="cache-stat-card__content">
                                            <span className="cache-stat-card__label">Memory Usage</span>
                                            <span className="cache-stat-card__value">{formatBytes(cacheStats.memory_usage)}</span>
                                        </div>
                                    </div>

                                    <div className="cache-stat-card">
                                        <div className="cache-stat-card__icon">
                                            <CheckCircle size={24} />
                                        </div>
                                        <div className="cache-stat-card__content">
                                            <span className="cache-stat-card__label">Hit Rate</span>
                                            <span className="cache-stat-card__value">
                                                {((cacheStats.hit_rate || 0) * 100).toFixed(1)}%
                                            </span>
                                        </div>
                                    </div>

                                    <div className="cache-stat-card">
                                        <div className="cache-stat-card__icon">
                                            <Clock size={24} />
                                        </div>
                                        <div className="cache-stat-card__content">
                                            <span className="cache-stat-card__label">Avg TTL</span>
                                            <span className="cache-stat-card__value">{cacheStats.avg_ttl_seconds || 0}s</span>
                                        </div>
                                    </div>
                                </div>

                                {/* Hit/Miss Stats */}
                                {(cacheStats.hits !== undefined || cacheStats.misses !== undefined) && (
                                    <div className="cache-hits-misses">
                                        <div className="hit-miss-bar">
                                            <div
                                                className="hit-bar"
                                                style={{
                                                    width: `${(cacheStats.hits / (cacheStats.hits + cacheStats.misses)) * 100 || 0}%`
                                                }}
                                            >
                                                <span>{cacheStats.hits?.toLocaleString() || 0} Hits</span>
                                            </div>
                                            <div
                                                className="miss-bar"
                                                style={{
                                                    width: `${(cacheStats.misses / (cacheStats.hits + cacheStats.misses)) * 100 || 0}%`
                                                }}
                                            >
                                                <span>{cacheStats.misses?.toLocaleString() || 0} Misses</span>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Operation-specific stats */}
                                {cacheStats.operations && Object.keys(cacheStats.operations).length > 0 && (
                                    <div className="cache-operations-stats">
                                        <h3>Operations Breakdown</h3>
                                        <div className="operations-table">
                                            <div className="operations-header">
                                                <span>Operation</span>
                                                <span>Keys</span>
                                                <span>Hits</span>
                                                <span>Hit Rate</span>
                                            </div>
                                            {Object.entries(cacheStats.operations).map(([op, stats]) => (
                                                <div key={op} className="operations-row">
                                                    <span className="op-name">{op.replace(/_/g, ' ')}</span>
                                                    <span>{stats.keys || 0}</span>
                                                    <span>{stats.hits?.toLocaleString() || 0}</span>
                                                    <span className={stats.hit_rate > 0.8 ? 'success' : stats.hit_rate > 0.5 ? 'warning' : 'error'}>
                                                        {((stats.hit_rate || 0) * 100).toFixed(1)}%
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Global Invalidate */}
                                <div className="cache-actions">
                                    <button
                                        onClick={handleInvalidateAll}
                                        className="btn btn-danger"
                                        disabled={actionLoading === 'invalidate-all'}
                                    >
                                        <Trash2 size={16} />
                                        {actionLoading === 'invalidate-all' ? 'Invalidating...' : 'Invalidate All Cache'}
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="empty-state empty-state--small">
                                <Database size={32} />
                                <p>No cache statistics available</p>
                            </div>
                        )}
                    </div>

                    {/* Cache Operations */}
                    <div className="settings-section">
                        <div className="settings-section__header">
                            <Zap size={20} />
                            <h2>Cache Operations</h2>
                        </div>
                        <p className="settings-section__description">
                            Manage cache for specific operations. Invalidate to refresh stale data or warm to pre-populate cache.
                        </p>

                        <div className="cache-operations-grid">
                            {cacheOperations.map(op => {
                                const Icon = op.icon;
                                return (
                                    <div key={op.id} className="cache-operation-card">
                                        <div className="cache-operation-card__header">
                                            <Icon size={16} />
                                            <span>{op.label}</span>
                                        </div>
                                        <div className="cache-operation-card__actions">
                                            <button
                                                onClick={() => handleWarmCache(op.id)}
                                                className="btn btn-secondary btn-small"
                                                disabled={actionLoading === `warm-${op.id}`}
                                                title="Warm cache"
                                            >
                                                <Flame size={14} />
                                                {actionLoading === `warm-${op.id}` ? '...' : 'Warm'}
                                            </button>
                                            <button
                                                onClick={() => handleInvalidateOperation(op.id)}
                                                className="btn btn-secondary btn-small"
                                                disabled={actionLoading === `invalidate-${op.id}`}
                                                title="Invalidate cache"
                                            >
                                                <Trash2 size={14} />
                                                {actionLoading === `invalidate-${op.id}` ? '...' : 'Clear'}
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Demo & Testing */}
                    <div className="settings-section settings-section--warning">
                        <div className="settings-section__header">
                            <AlertTriangle size={20} />
                            <h2>Demo & Testing</h2>
                        </div>
                        <p className="settings-section__description">
                            Generate sample data for testing or clear demo data from the system.
                        </p>

                        <div className="demo-actions">
                            <div className="demo-action-card">
                                <div className="demo-action-card__content">
                                    <Play size={24} />
                                    <div>
                                        <h3>Generate Sample Data</h3>
                                        <p>Create realistic sample data for testing the dashboard, architecture, and workflows.</p>
                                    </div>
                                </div>
                                <button
                                    onClick={handleGenerateSampleData}
                                    className="btn btn-primary"
                                    disabled={actionLoading === 'generate-sample'}
                                >
                                    <Play size={16} />
                                    {actionLoading === 'generate-sample' ? 'Generating...' : 'Generate Data'}
                                </button>
                            </div>

                            <div className="demo-action-card demo-action-card--danger">
                                <div className="demo-action-card__content">
                                    <Trash2 size={24} />
                                    <div>
                                        <h3>Clear Demo Data</h3>
                                        <p>Delete all demo and sample data from the system. This action cannot be undone.</p>
                                    </div>
                                </div>
                                <button
                                    onClick={handleClearDemoData}
                                    className="btn btn-danger"
                                    disabled={actionLoading === 'clear-demo'}
                                >
                                    <Trash2 size={16} />
                                    {actionLoading === 'clear-demo' ? 'Clearing...' : 'Clear All Data'}
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* API Information */}
                    <div className="settings-section">
                        <div className="settings-section__header">
                            <Server size={20} />
                            <h2>API Information</h2>
                        </div>

                        <div className="api-info">
                            <div className="api-info-item">
                                <span className="api-info-label">API Base URL</span>
                                <code className="api-info-value">{API_BASE_URL}</code>
                            </div>
                            <div className="api-info-item">
                                <span className="api-info-label">Authentication</span>
                                <span className="api-info-value">
                                    {googleStatus?.configured
                                        ? 'Google OAuth 2.0 (Configured)'
                                        : 'Google OAuth 2.0 (Not fully configured)'}
                                </span>
                            </div>
                            <div className="api-info-item">
                                <span className="api-info-label">OAuth Redirect URI</span>
                                <span className="api-info-value">{googleStatus?.redirect_uri || 'Not configured'}</span>
                            </div>
                            <div className="api-info-item">
                                <span className="api-info-label">Rate Limit</span>
                                <span className="api-info-value">Check response headers for X-RateLimit-*</span>
                            </div>
                        </div>
                    </div>
                </div>
                </div>
            </div>
        </>
    );
}
