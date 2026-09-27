'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { apiClient } from '@/lib/api-client';

function toPercent(value) {
    const amount = Number(value || 0);
    return `${(amount * 100).toFixed(2)}%`;
}

export default function ProjectDetailPage() {
    const params = useParams();
    const projectId = params?.projectId;
    const { isAuthenticated, loading: authLoading } = useAuth();

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [detail, setDetail] = useState(null);
    const [regenerating, setRegenerating] = useState(false);

    const report = useMemo(() => detail?.latest_report || null, [detail]);

    const fetchDetail = async () => {
        if (!projectId) return;
        setLoading(true);
        setError('');
        try {
            const payload = await apiClient.getProjectDetail(projectId);
            setDetail(payload || null);
        } catch (err) {
            setError(err.message || 'Failed to load project details');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!authLoading && isAuthenticated && projectId) {
            fetchDetail();
        }
    }, [authLoading, isAuthenticated, projectId]);

    const regenerateReport = async () => {
        if (!projectId) return;
        setRegenerating(true);
        setError('');
        try {
            await apiClient.regenerateProjectAIReport(projectId);
            await fetchDetail();
        } catch (err) {
            setError(err.message || 'Failed to regenerate AI report');
        } finally {
            setRegenerating(false);
        }
    };

    if (authLoading || loading) {
        return (
            <div className="page-loading">
                <div className="spinner" />
                <p>Loading project details...</p>
            </div>
        );
    }

    if (!isAuthenticated) {
        return (
            <div className="auth-required">
                <h2 className="display-title display-md">ACCESS REQUIRED</h2>
                <p>Please sign in to view this project.</p>
                <Link href="/login" className="btn btn-primary">Sign In</Link>
            </div>
        );
    }

    const overview = detail?.overview?.summary || {};
    const project = detail?.overview?.project || {};
    const services = detail?.services || [];

    return (
        <div className="dashboard-page" style={{ padding: '2rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <div>
                    <Link href="/dashboard" className="btn btn-secondary">Back to Dashboard</Link>
                    <h1 className="display-title display-md" style={{ marginTop: '0.75rem' }}>{project.name || 'Project'}</h1>
                    <p style={{ margin: 0, color: '#64748b' }}>{project.description || 'Runtime analytics and AI insights'}</p>
                </div>
                <button className="btn btn-primary" onClick={regenerateReport} disabled={regenerating}>
                    {regenerating ? 'Regenerating...' : 'Regenerate AI Report'}
                </button>
            </div>

            {error && <div className="dashboard-error">{error}</div>}

            <div className="stats-grid" style={{ marginBottom: '1rem' }}>
                <div className="stat-card">
                    <span className="stat-card__label">Total Requests</span>
                    <span className="stat-card__value">{overview.total_requests || 0}</span>
                </div>
                <div className="stat-card">
                    <span className="stat-card__label">Avg Latency</span>
                    <span className="stat-card__value">{overview.avg_latency_ms || 0}ms</span>
                </div>
                <div className="stat-card">
                    <span className="stat-card__label">Error Rate</span>
                    <span className="stat-card__value">{toPercent(overview.error_rate || 0)}</span>
                </div>
                <div className="stat-card">
                    <span className="stat-card__label">Services</span>
                    <span className="stat-card__value">{overview.service_count || 0}</span>
                </div>
            </div>

            <div className="dashboard-grid" style={{ gap: '1rem' }}>
                <div className="dashboard-panel">
                    <h3>Service Analytics</h3>
                    {!services.length ? (
                        <p>No service analytics available yet.</p>
                    ) : (
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                <thead>
                                    <tr>
                                        <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: '0.5rem' }}>Service</th>
                                        <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: '0.5rem' }}>Requests</th>
                                        <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: '0.5rem' }}>Avg Latency</th>
                                        <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: '0.5rem' }}>Error Rate</th>
                                        <th style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: '0.5rem' }}>Last Seen</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {services.map((row) => (
                                        <tr key={row.service_name}>
                                            <td style={{ padding: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>{row.service_name}</td>
                                            <td style={{ padding: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>{row.request_count}</td>
                                            <td style={{ padding: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>{row.avg_latency_ms}ms</td>
                                            <td style={{ padding: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>{toPercent(row.error_rate)}</td>
                                            <td style={{ padding: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>{row.last_seen || 'N/A'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                <div className="dashboard-panel">
                    <h3>AI Report</h3>
                    {!report ? (
                        <p>No AI report generated yet.</p>
                    ) : (
                        <>
                            <p><strong>Generated:</strong> {report.generated_at || 'N/A'}</p>
                            <h4>Good Signals</h4>
                            <ul>
                                {(report.good_signals || []).map((item, idx) => <li key={`good-${idx}`}>{item}</li>)}
                            </ul>
                            <h4>Bad Signals</h4>
                            <ul>
                                {(report.bad_signals || []).map((item, idx) => <li key={`bad-${idx}`}>{item}</li>)}
                            </ul>
                            <h4>Actions</h4>
                            <ul>
                                {(report.actions || []).map((item, idx) => <li key={`act-${idx}`}>{item}</li>)}
                            </ul>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
