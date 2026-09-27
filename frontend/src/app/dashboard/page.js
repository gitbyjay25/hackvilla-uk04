'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { apiClient } from '@/lib/api-client';
import Navbar from '@/components/Navbar';
import {
    Activity,
    AlertCircle,
    AlertTriangle,
    BarChart3,
    BookOpen,
    CheckCircle2,
    Clock3,
    Heart,
    Key,
    RefreshCw,
    Server,
    TrendingDown,
    TrendingUp,
    XCircle,
} from 'lucide-react';

const TREND_WINDOWS = [6, 24, 72, 168];

const EMPTY_TRENDS = {
    data_points: [],
    summary: {
        latency_change: 0,
        error_change: 0,
        volume_change: 0,
        max_requests: 0,
        total_requests: 0,
        avg_latency_ms: 0,
        avg_error_rate: 0,
    },
    deep_analysis: {
        windows: {},
        anomalies: [],
    },
};

function safePercentChange(first, last) {
    if (first === 0) {
        return 0;
    }
    return ((last - first) / first) * 100;
}

function buildSummaryFromDataPoints(dataPoints) {
    if (!dataPoints.length) {
        return { ...EMPTY_TRENDS.summary };
    }

    const first = dataPoints[0];
    const last = dataPoints[dataPoints.length - 1];
    const totalRequests = dataPoints.reduce((sum, p) => sum + (p.request_count || 0), 0);
    const weightedLatency = totalRequests
        ? dataPoints.reduce((sum, p) => sum + ((p.avg_latency_ms || 0) * (p.request_count || 0)), 0) / totalRequests
        : 0;
    const totalErrors = dataPoints.reduce(
        (sum, p) => sum + Math.round((p.error_rate || 0) * (p.request_count || 0)),
        0
    );

    return {
        latency_change: safePercentChange(first.avg_latency_ms || 0, last.avg_latency_ms || 0),
        error_change: safePercentChange(first.error_rate || 0, last.error_rate || 0),
        volume_change: safePercentChange(first.request_count || 0, last.request_count || 0),
        max_requests: Math.max(...dataPoints.map((p) => p.request_count || 0), 0),
        total_requests: totalRequests,
        avg_latency_ms: weightedLatency,
        avg_error_rate: totalRequests ? totalErrors / totalRequests : 0,
    };
}

function normalizeTrends(raw) {
    if (!raw) {
        return { ...EMPTY_TRENDS };
    }

    let dataPoints = Array.isArray(raw.data_points)
        ? raw.data_points.map((p) => ({
              timestamp: p.timestamp,
              request_count: Number(p.request_count || 0),
              avg_latency_ms: Number(p.avg_latency_ms || 0),
              error_rate: Number(p.error_rate || 0),
          }))
        : [];

    if (!dataPoints.length && Array.isArray(raw.volume)) {
        const bucketByTimestamp = new Map();

        for (const item of raw.volume || []) {
            bucketByTimestamp.set(item.timestamp, {
                timestamp: item.timestamp,
                request_count: Number(item.value || 0),
                avg_latency_ms: 0,
                error_rate: 0,
            });
        }

        for (const item of raw.latency || []) {
            const bucket = bucketByTimestamp.get(item.timestamp) || {
                timestamp: item.timestamp,
                request_count: 0,
                avg_latency_ms: 0,
                error_rate: 0,
            };
            bucket.avg_latency_ms = Number(item.value || 0);
            bucketByTimestamp.set(item.timestamp, bucket);
        }

        for (const item of raw.error_rate || []) {
            const bucket = bucketByTimestamp.get(item.timestamp) || {
                timestamp: item.timestamp,
                request_count: 0,
                avg_latency_ms: 0,
                error_rate: 0,
            };
            bucket.error_rate = Number(item.value || 0);
            bucketByTimestamp.set(item.timestamp, bucket);
        }

        dataPoints = [...bucketByTimestamp.values()];
    }

    dataPoints.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    return {
        ...EMPTY_TRENDS,
        ...raw,
        data_points: dataPoints,
        summary: raw.summary || buildSummaryFromDataPoints(dataPoints),
        deep_analysis: {
            windows: raw.deep_analysis?.windows || {},
            anomalies: raw.deep_analysis?.anomalies || [],
        },
    };
}

function toUiStatus(status) {
    if (['healthy', 'good'].includes(status)) {
        return 'healthy';
    }
    if (['warning', 'degraded'].includes(status)) {
        return 'warning';
    }
    if (['critical', 'unhealthy'].includes(status)) {
        return 'critical';
    }
    return 'neutral';
}

function metricDirection(metric, value) {
    if (metric === 'error' || metric === 'latency') {
        return value <= 0 ? 'good' : 'bad';
    }
    return value >= 0 ? 'good' : 'bad';
}

function formatSignedPercent(value) {
    const abs = Math.abs(value || 0).toFixed(1);
    return `${abs}%`;
}

export default function DashboardPage() {
    const { isAuthenticated, loading: authLoading, user } = useAuth();

    const [overview, setOverview] = useState(null);
    const [health, setHealth] = useState(null);
    const [services, setServices] = useState([]);
    const [trends, setTrends] = useState(EMPTY_TRENDS);

    const [loading, setLoading] = useState(true);
    const [trendLoading, setTrendLoading] = useState(false);
    const [error, setError] = useState(null);
    const [trendHours, setTrendHours] = useState(24);
    const [initialized, setInitialized] = useState(false);

    const hasTelemetryData = useMemo(() => {
        return (
            (overview?.total_requests || 0) > 0 ||
            (services?.length || 0) > 0 ||
            (trends?.data_points?.length || 0) > 0
        );
    }, [overview, services, trends]);

    useEffect(() => {
        if (!authLoading && isAuthenticated) {
            fetchDashboard();
        }
    }, [authLoading, isAuthenticated]);

    useEffect(() => {
        if (initialized && isAuthenticated) {
            fetchTrendsOnly();
        }
    }, [trendHours, initialized, isAuthenticated]);

    const fetchDashboard = async () => {
        setLoading(true);
        setError(null);

        try {
            const [overviewData, healthData, servicesData, trendsData] = await Promise.all([
                apiClient.getDashboardOverview(),
                apiClient.getDashboardHealth(),
                apiClient.getServices(),
                apiClient.getTrends(trendHours),
            ]);

            setOverview(overviewData);
            setHealth(healthData);
            setServices(Array.isArray(servicesData) ? servicesData : []);
            setTrends(normalizeTrends(trendsData));
            setInitialized(true);
        } catch (err) {
            setError(err.message || 'Failed to load dashboard telemetry.');
        } finally {
            setLoading(false);
        }
    };

    const fetchTrendsOnly = async () => {
        setTrendLoading(true);
        try {
            const trendsData = await apiClient.getTrends(trendHours);
            setTrends(normalizeTrends(trendsData));
        } catch (err) {
            console.error('Failed to refresh trends:', err);
        } finally {
            setTrendLoading(false);
        }
    };

    const getHealthIcon = (status) => {
        const uiStatus = toUiStatus(status);
        if (uiStatus === 'healthy') {
            return <CheckCircle2 size={16} className="health-icon health-icon--healthy" />;
        }
        if (uiStatus === 'warning') {
            return <AlertCircle size={16} className="health-icon health-icon--warning" />;
        }
        if (uiStatus === 'critical') {
            return <XCircle size={16} className="health-icon health-icon--critical" />;
        }
        return <AlertCircle size={16} className="health-icon" />;
    };

    const getScoreColor = (score) => {
        if (score >= 80) return 'var(--color-success, #4caf50)';
        if (score >= 60) return 'var(--color-warning, #ff9800)';
        return 'var(--color-error, #c62828)';
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
                <p>Please sign in to view telemetry.</p>
                <Link href="/login" className="btn btn-primary">Sign In</Link>
            </div>
        );
    }

    const dataPoints = trends?.data_points || [];
    const trendSummary = trends?.summary || EMPTY_TRENDS.summary;
    const deepWindows = Object.entries(trends?.deep_analysis?.windows || {});
    const anomalies = trends?.deep_analysis?.anomalies || [];
    const trendBars = dataPoints.slice(-12);
    const maxRequests = Math.max(trendSummary.max_requests || 0, 1);
    const healthCategories = Object.entries(health?.categories || {});

    return (
        <>
            <Navbar />
            <div className="dashboard-page">
                <div className="dashboard-content">
                <div className="dashboard-header">
                    <div>
                        <span className="tape-label">SDK Runtime Telemetry</span>
                        <h1 className="display-title display-md" style={{ marginTop: '0.5rem' }}>
                            DASHBOARD
                        </h1>
                        {user && <p className="dashboard-welcome">Welcome back, {user.full_name || user.email}</p>}
                    </div>
                    <div className="dashboard-header__actions">
                        <button onClick={fetchDashboard} className="btn btn-secondary" disabled={loading}>
                            <RefreshCw size={16} className={loading ? 'spinning' : ''} />
                            Refresh
                        </button>
                    </div>
                </div>

                {error && <div className="dashboard-error">{error}</div>}

                {loading ? (
                    <div className="loading-state">
                        <div className="spinner"></div>
                        <p>Loading telemetry dashboard...</p>
                    </div>
                ) : !hasTelemetryData ? (
                    <div className="dashboard-panel telemetry-onboarding">
                        <div className="panel-header">
                            <h2 className="section-title">
                                <Server size={18} />
                                No SDK Telemetry Yet
                            </h2>
                        </div>

                        <p>
                            We do not have runtime spans yet for this tenant. Connect the SDK to your FastAPI service,
                            generate traffic, then refresh this page.
                        </p>

                        <ol className="telemetry-onboarding__steps">
                            <li>Create an API key for SDK authentication.</li>
                            <li>Install and initialize Nexarch SDK in your FastAPI app.</li>
                            <li>Send test requests to produce traces and service interactions.</li>
                        </ol>

                        <div className="telemetry-onboarding__actions">
                            <Link href="/sdk-docs" className="btn btn-primary">
                                <BookOpen size={16} />
                                Open SDK Docs
                            </Link>
                            <Link href="/api-keys" className="btn btn-secondary">
                                <Key size={16} />
                                Manage API Keys
                            </Link>
                            <button className="btn btn-secondary" onClick={fetchDashboard}>
                                <RefreshCw size={16} />
                                Recheck Telemetry
                            </button>
                        </div>
                    </div>
                ) : (
                    <>
                        <div className="stats-grid stats-grid--large">
                            <div className="stat-card stat-card--featured">
                                <div
                                    className="stat-card__icon"
                                    style={{ backgroundColor: getScoreColor(overview?.health_score || 0) }}
                                >
                                    <Heart size={24} />
                                </div>
                                <div className="stat-card__content">
                                    <span className="stat-card__label">Health Score</span>
                                    <span className="stat-card__value">{overview?.health_score || 0}</span>
                                </div>
                                <div className="stat-card__indicator" style={{ '--score-color': getScoreColor(overview?.health_score || 0) }}>
                                    <div className="score-bar" style={{ width: `${overview?.health_score || 0}%` }}></div>
                                </div>
                            </div>

                            <div className="stat-card">
                                <div className="stat-card__icon"><Server size={24} /></div>
                                <div className="stat-card__content">
                                    <span className="stat-card__label">Services</span>
                                    <span className="stat-card__value">{overview?.total_services || 0}</span>
                                </div>
                            </div>

                            <div className="stat-card">
                                <div className="stat-card__icon"><BarChart3 size={24} /></div>
                                <div className="stat-card__content">
                                    <span className="stat-card__label">Total Requests</span>
                                    <span className="stat-card__value">{(overview?.total_requests || 0).toLocaleString()}</span>
                                </div>
                            </div>

                            <div className="stat-card">
                                <div className="stat-card__icon"><Clock3 size={24} /></div>
                                <div className="stat-card__content">
                                    <span className="stat-card__label">Avg Latency</span>
                                    <span className="stat-card__value">{(overview?.avg_latency_ms || 0).toFixed(1)}ms</span>
                                </div>
                            </div>

                            <div className="stat-card">
                                <div className="stat-card__icon"><AlertCircle size={24} /></div>
                                <div className="stat-card__content">
                                    <span className="stat-card__label">Error Rate</span>
                                    <span className="stat-card__value">{((overview?.error_rate || 0) * 100).toFixed(2)}%</span>
                                </div>
                            </div>
                        </div>

                        {(overview?.critical_issues > 0 || overview?.warnings > 0 || overview?.active_incidents > 0) && (
                            <div className="alerts-row">
                                {(overview?.critical_issues || 0) > 0 && (
                                    <div className="alert-badge alert-badge--critical">
                                        <AlertTriangle size={16} />
                                        <span>{overview.critical_issues} Critical Issue{overview.critical_issues > 1 ? 's' : ''}</span>
                                    </div>
                                )}
                                {(overview?.warnings || 0) > 0 && (
                                    <div className="alert-badge alert-badge--warning">
                                        <AlertCircle size={16} />
                                        <span>{overview.warnings} Warning{overview.warnings > 1 ? 's' : ''}</span>
                                    </div>
                                )}
                                {(overview?.active_incidents || 0) > 0 && (
                                    <div className="alert-badge alert-badge--incident">
                                        <Activity size={16} />
                                        <span>{overview.active_incidents} Active Incident{overview.active_incidents > 1 ? 's' : ''}</span>
                                    </div>
                                )}
                            </div>
                        )}

                        <div className="dashboard-grid">
                            <div className="dashboard-panel trends-panel">
                                <div className="panel-header">
                                    <h2 className="section-title">Trends</h2>
                                    <div className="trend-selector">
                                        {TREND_WINDOWS.map((hours) => (
                                            <button
                                                key={hours}
                                                className={`trend-btn ${trendHours === hours ? 'trend-btn--active' : ''}`}
                                                onClick={() => setTrendHours(hours)}
                                                disabled={trendLoading}
                                            >
                                                {hours}h
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="trend-summary">
                                    {[
                                        { key: 'latency', label: 'Latency', value: trendSummary.latency_change || 0 },
                                        { key: 'error', label: 'Errors', value: trendSummary.error_change || 0 },
                                        { key: 'volume', label: 'Volume', value: trendSummary.volume_change || 0 },
                                    ].map((item) => {
                                        const direction = metricDirection(item.key, item.value);
                                        const good = direction === 'good';
                                        const isPositive = (item.value || 0) >= 0;
                                        const TrendIcon = isPositive ? TrendingUp : TrendingDown;
                                        return (
                                            <div key={item.key} className="trend-item">
                                                <div className="trend-item__header">
                                                    <span>{item.label} Change</span>
                                                </div>
                                                <div className="trend-item__value">
                                                    <TrendIcon size={16} className={good ? 'trend-good' : 'trend-bad'} />
                                                    {formatSignedPercent(item.value)}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>

                                {trendBars.length > 0 ? (
                                    <div className="trend-chart">
                                        <div className="trend-chart__bars">
                                            {trendBars.map((point) => (
                                                <div
                                                    key={point.timestamp}
                                                    className="trend-bar"
                                                    style={{
                                                        height: `${Math.min(100, ((point.request_count || 0) / maxRequests) * 100)}%`,
                                                        backgroundColor: (point.error_rate || 0) > 0.05 ? 'var(--color-error, #c62828)' : 'var(--color-yellow)',
                                                    }}
                                                    title={`${point.request_count} requests | ${(point.error_rate * 100).toFixed(2)}% errors | ${point.avg_latency_ms.toFixed(1)}ms`}
                                                />
                                            ))}
                                        </div>
                                        <div className="trend-chart__labels">
                                            <span>Last {trendHours}h request-volume profile</span>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="empty-state empty-state--small">
                                        <BarChart3 size={32} />
                                        <p>No trend data available</p>
                                    </div>
                                )}
                            </div>

                            <div className="dashboard-panel deep-analysis-panel">
                                <div className="panel-header">
                                    <h2 className="section-title">Deep Window Analysis</h2>
                                </div>

                                {deepWindows.length > 0 ? (
                                    <div className="window-analysis-grid">
                                        {deepWindows.map(([windowKey, metrics]) => {
                                            const uiStatus = toUiStatus(metrics.status);
                                            return (
                                                <div
                                                    key={windowKey}
                                                    className={`window-card window-card--${uiStatus} ${windowKey === `${trendHours}h` ? 'window-card--active' : ''}`}
                                                >
                                                    <div className="window-card__header">
                                                        <span>{windowKey}</span>
                                                        <span className={`health-item__status health-item__status--${uiStatus}`}>{metrics.status}</span>
                                                    </div>
                                                    <div className="window-card__metrics">
                                                        <p><strong>{metrics.request_count || 0}</strong> requests</p>
                                                        <p><strong>{(metrics.avg_latency_ms || 0).toFixed(1)}ms</strong> avg latency</p>
                                                        <p><strong>{(metrics.p95_latency_ms || 0).toFixed(1)}ms</strong> p95 latency</p>
                                                        <p><strong>{((metrics.error_rate || 0) * 100).toFixed(2)}%</strong> error rate</p>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                ) : (
                                    <div className="empty-state empty-state--small">
                                        <Clock3 size={32} />
                                        <p>No deep analysis available</p>
                                    </div>
                                )}

                                {anomalies.length > 0 && (
                                    <div className="trend-anomalies">
                                        <h4>Detected Anomalies</h4>
                                        {anomalies.slice(0, 3).map((item) => (
                                            <div key={`${item.type}-${item.timestamp}`} className="anomaly-item">
                                                <AlertTriangle size={14} />
                                                <span>{item.message}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="dashboard-panel services-panel">
                                <div className="panel-header">
                                    <h2 className="section-title">Top Services</h2>
                                    <Link href="/system-architecture" className="panel-link">View All →</Link>
                                </div>

                                {services.length > 0 ? (
                                    <div className="services-list">
                                        {services.slice(0, 8).map((service) => (
                                            <div key={service.name} className="service-item">
                                                <div className="service-item__info">
                                                    {getHealthIcon(service.health_status)}
                                                    <span className="service-item__name">{service.name}</span>
                                                </div>
                                                <div className="service-item__stats">
                                                    <span>{(service.request_count || 0).toLocaleString()} calls</span>
                                                    <span>{(service.avg_latency_ms || 0).toFixed(0)}ms</span>
                                                    <span>{((service.error_rate || 0) * 100).toFixed(2)}%</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="empty-state empty-state--small">
                                        <Server size={32} />
                                        <p>No services discovered</p>
                                    </div>
                                )}
                            </div>

                            <div className="dashboard-panel health-panel">
                                <div className="panel-header">
                                    <h2 className="section-title">System Health</h2>
                                </div>

                                {healthCategories.length > 0 ? (
                                    <div className="health-grid">
                                        {healthCategories.map(([name, category]) => {
                                            const uiStatus = toUiStatus(category.status);
                                            return (
                                                <div key={name} className="health-item">
                                                    {getHealthIcon(category.status)}
                                                    <span className="health-item__name">{name.replace(/_/g, ' ')}</span>
                                                    <span className={`health-item__status health-item__status--${uiStatus}`}>
                                                        {category.score}/100
                                                    </span>
                                                </div>
                                            );
                                        })}
                                    </div>
                                ) : (
                                    <div className="empty-state empty-state--small">
                                        <Activity size={32} />
                                        <p>No health data available</p>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="dashboard-footer">
                            <Clock3 size={14} />
                            <span>Last updated: {new Date(overview?.last_updated || Date.now()).toLocaleString()}</span>
                        </div>
                    </>
                )}
                </div>
            </div>
        </>
    );
}