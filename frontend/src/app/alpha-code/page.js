'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { apiClient } from '@/lib/api-client';
import Navbar from '@/components/Navbar';

export default function AlphaCodePage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const [presetVariant, setPresetVariant] = useState('');

    const [variantId, setVariantId] = useState(presetVariant);
    const [deepPlanId, setDeepPlanId] = useState('');
    const [runs, setRuns] = useState([]);
    const [loading, setLoading] = useState(false);
    const [downloadingRunId, setDownloadingRunId] = useState('');

    const [sandboxBusy, setSandboxBusy] = useState(false);
    const [sandboxModalOpen, setSandboxModalOpen] = useState(false);
    const [sandboxRunId, setSandboxRunId] = useState('');
    const [sandboxSessionId, setSandboxSessionId] = useState('');
    const [sandboxSession, setSandboxSession] = useState(null);
    const [sandboxLogs, setSandboxLogs] = useState([]);
    const [sandboxAutomation, setSandboxAutomation] = useState(null);
    const [autoValidationRunning, setAutoValidationRunning] = useState(false);

    const [error, setError] = useState('');
    const [message, setMessage] = useState('');

    const statusColor = useMemo(() => ({
        pending: '#b08900',
        in_progress: '#0056d6',
        completed: '#1a7f37',
        failed: '#cf222e',
    }), []);

    const sandboxStatusColor = useMemo(() => ({
        created: '#b08900',
        starting: '#0056d6',
        running: '#1a7f37',
        stopped: '#6b7280',
        failed: '#cf222e',
    }), []);

    const fetchRuns = async () => {
        try {
            const data = await apiClient.listAlphaRuns();
            setRuns(data || []);
        } catch (err) {
            setError(err.message || 'Failed to load alpha runs');
        }
    };

    useEffect(() => {
        if (typeof window !== 'undefined') {
            const params = new URLSearchParams(window.location.search);
            const v = params.get('variant') || '';
            setPresetVariant(v);
            if (v) {
                setVariantId(v);
            }
        }
    }, []);

    useEffect(() => {
        if (!authLoading && isAuthenticated) {
            fetchRuns();
        }
    }, [authLoading, isAuthenticated]);

    useEffect(() => {
        if (!sandboxModalOpen || !sandboxSessionId) {
            return;
        }

        const timer = setInterval(async () => {
            try {
                const [sessionData, logsData] = await Promise.all([
                    apiClient.getSandboxSession(sandboxSessionId),
                    apiClient.listSandboxLogs(sandboxSessionId, 100),
                ]);
                setSandboxSession(sessionData?.session || null);
                setSandboxLogs(logsData?.logs || sessionData?.logs || []);
            } catch {
                // Keep existing UI state during transient polling errors.
            }
        }, 5000);

        return () => clearInterval(timer);
    }, [sandboxModalOpen, sandboxSessionId]);

    const onPlanDeeply = async () => {
        if (!variantId) {
            setError('Provide architecture variant id first.');
            return;
        }
        setLoading(true);
        setError('');
        setMessage('');
        try {
            const result = await apiClient.createDeepPlan(variantId);
            setDeepPlanId(result.deep_plan_report_id);
            setMessage(`Deep plan generated: ${result.deep_plan_report_id}`);
        } catch (err) {
            setError(err.message || 'Plan Deeply failed');
        } finally {
            setLoading(false);
        }
    };

    const onMakeAlpha = async () => {
        if (!variantId || !deepPlanId) {
            setError('Need both variant id and deep plan id.');
            return;
        }
        setLoading(true);
        setError('');
        setMessage('');
        try {
            const result = await apiClient.startAlphaRun(variantId, deepPlanId);
            const modeText = result.execution_mode ? ` [${result.execution_mode}, ~${result.estimated_seconds || '?'}s]` : '';
            setMessage(`Alpha run started: ${result.run_id}${modeText}`);
            await fetchRuns();
        } catch (err) {
            setError(err.message || 'Failed to start alpha run');
        } finally {
            setLoading(false);
        }
    };

    const onDownloadZip = async (runId) => {
        setDownloadingRunId(runId);
        setError('');
        try {
            const token = window.localStorage.getItem('access_token');
            if (!token) {
                throw new Error('Missing auth token. Please sign in again.');
            }

            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/api/alpha-code/runs/${runId}/download`;
            form.style.display = 'none';

            const tokenInput = document.createElement('input');
            tokenInput.type = 'hidden';
            tokenInput.name = 'token';
            tokenInput.value = token;

            form.appendChild(tokenInput);
            document.body.appendChild(form);
            form.submit();
            form.remove();
        } catch (err) {
            setError(err.message || 'Failed to download zip artifact');
        } finally {
            setDownloadingRunId('');
        }
    };

    const refreshSandboxSession = async (sessionId) => {
        const [sessionData, logsData] = await Promise.all([
            apiClient.getSandboxSession(sessionId),
            apiClient.listSandboxLogs(sessionId, 100),
        ]);
        setSandboxSession(sessionData?.session || null);
        setSandboxLogs(logsData?.logs || sessionData?.logs || []);
    };

    const runAutoValidation = async (sessionId, opts = { silent: false }) => {
        if (!sessionId) return;

        if (!opts.silent) {
            setMessage('Automatic validation started. Loading execution logs now. We will email you when it completes.');
        }
        setSandboxBusy(true);
        setAutoValidationRunning(true);
        setError('');

        let active = true;
        const pollLogs = async () => {
            if (!active) return;
            try {
                await refreshSandboxSession(sessionId);
            } catch {
                // Ignore transient polling errors while a long validation run is active.
            }
        };

        await pollLogs();
        const pollTimer = window.setInterval(() => {
            void pollLogs();
        }, 2000);

        try {
            const result = await apiClient.runSandboxAutoValidation(sessionId, { max_attempts: 10 });
            const automation = result?.automation || null;
            setSandboxAutomation(automation);
            await refreshSandboxSession(sessionId);

            const emailState = result?.email_notification || {};
            const emailMsg = emailState?.attempted
                ? ' Completion email sent.'
                : ' Email will be sent when SMTP is configured.';

            if (automation?.passed) {
                setMessage(`Sandbox validation passed in ${automation.attempts?.length || 1} attempt(s).${emailMsg}`);
            } else {
                setError(`Sandbox validation did not pass after ${automation?.max_attempts || 10} attempt(s). Check logs for details.${emailMsg}`);
            }
        } catch (err) {
            setError(err.message || 'Failed to run automatic sandbox validation');
        } finally {
            active = false;
            window.clearInterval(pollTimer);
            setSandboxBusy(false);
            setAutoValidationRunning(false);
        }
    };

    const onOpenSandbox = async (run) => {
        if (!run || run.status !== 'completed') {
            setError('Sandbox is available only for completed alpha runs.');
            return;
        }

        setSandboxBusy(true);
        setError('');
        setMessage('Opening sandbox workspace...');

        try {
            const listed = await apiClient.listSandboxSessions(run.run_id);
            const sessions = listed?.sessions || [];
            let selected = sessions.find((item) => item.status === 'running') || sessions[0] || null;

            if (!selected) {
                const created = await apiClient.createSandboxSession(run.run_id);
                selected = created?.session || null;
            } else if (selected.status !== 'running') {
                const started = await apiClient.startSandboxSession(selected.session_id);
                selected = started?.session || selected;
            }

            if (!selected?.session_id) {
                throw new Error('Failed to initialize sandbox session.');
            }

            setSandboxRunId(run.run_id);
            setSandboxSessionId(selected.session_id);
            setSandboxModalOpen(true);
            setSandboxAutomation(null);
            await refreshSandboxSession(selected.session_id);
            await runAutoValidation(selected.session_id, { silent: true });
        } catch (err) {
            setError(err.message || 'Failed to open sandbox');
        } finally {
            setSandboxBusy(false);
        }
    };

    const onStartSandbox = async () => {
        if (!sandboxSessionId) return;
        setSandboxBusy(true);
        try {
            await apiClient.startSandboxSession(sandboxSessionId);
            await refreshSandboxSession(sandboxSessionId);
            setMessage('Sandbox started.');
        } catch (err) {
            setError(err.message || 'Failed to start sandbox');
        } finally {
            setSandboxBusy(false);
        }
    };

    const onStopSandbox = async () => {
        if (!sandboxSessionId) return;
        setSandboxBusy(true);
        try {
            await apiClient.stopSandboxSession(sandboxSessionId);
            await refreshSandboxSession(sandboxSessionId);
            setMessage('Sandbox stopped.');
        } catch (err) {
            setError(err.message || 'Failed to stop sandbox');
        } finally {
            setSandboxBusy(false);
        }
    };

    const closeSandboxModal = () => {
        setSandboxModalOpen(false);
        setSandboxRunId('');
        setSandboxSessionId('');
        setSandboxSession(null);
        setSandboxLogs([]);
        setSandboxAutomation(null);
        setAutoValidationRunning(false);
    };

    if (authLoading) {
        return (
            <>
                <Navbar />
                <div className="page-loading"><div className="spinner" /><p>Loading...</p></div>
            </>
        );
    }

    if (!isAuthenticated) {
        return (
            <>
                <Navbar />
                <div className="auth-required">
                    <h2 className="display-title display-md">ACCESS REQUIRED</h2>
                    <p>Please sign in to use Alpha-Code.</p>
                    <Link href="/login" className="btn btn-primary">Sign In</Link>
                </div>
            </>
        );
    }

    return (
        <>
            <Navbar />
            <div className="dashboard-page" style={{ padding: '2rem' }}>
                <h1 className="display-title display-md">Alpha-Code</h1>
                <p style={{ marginBottom: '1rem' }}>
                    Track runs and use automatic LangGraph-driven sandbox validation with retry + fix cycles.
                </p>

                {error && <div className="dashboard-error">{error}</div>}
                {message && <div className="dashboard-success">{message}</div>}

                <div style={{ border: '1px solid #ccc', padding: '1rem', marginBottom: '1rem' }}>
                    <h3>Run Controls</h3>
                    <label>Architecture Variant ID</label>
                    <input
                        type="text"
                        value={variantId}
                        onChange={(e) => setVariantId(e.target.value)}
                        placeholder="paste variant id"
                        style={{ width: '100%', padding: '0.5rem', marginBottom: '0.5rem' }}
                    />
                    <label>Deep Plan ID</label>
                    <input
                        type="text"
                        value={deepPlanId}
                        onChange={(e) => setDeepPlanId(e.target.value)}
                        placeholder="generated deep plan id"
                        style={{ width: '100%', padding: '0.5rem', marginBottom: '0.5rem' }}
                    />
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button className="btn btn-secondary" onClick={onPlanDeeply} disabled={loading}>Plan Deeply</button>
                        <button className="btn btn-primary" onClick={onMakeAlpha} disabled={loading}>Make Alpha Codebase</button>
                        <button className="btn btn-secondary" onClick={fetchRuns} disabled={loading}>Refresh</button>
                    </div>
                </div>

                <div style={{ border: '1px solid #ccc', padding: '1rem' }}>
                    <h3>Alpha Runs</h3>
                    {!runs.length ? <p>No runs yet.</p> : (
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr>
                                    <th style={{ textAlign: 'left', padding: '0.5rem' }}>Run ID</th>
                                    <th style={{ textAlign: 'left', padding: '0.5rem' }}>Variant</th>
                                    <th style={{ textAlign: 'left', padding: '0.5rem' }}>Status</th>
                                    <th style={{ textAlign: 'left', padding: '0.5rem' }}>Created</th>
                                    <th style={{ textAlign: 'left', padding: '0.5rem' }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {runs.map((run) => (
                                    <tr key={run.run_id} style={{ borderTop: '1px solid #eee' }}>
                                        <td style={{ padding: '0.5rem' }}>{run.run_id}</td>
                                        <td style={{ padding: '0.5rem' }}>
                                            {run.architecture_variant_id ? (
                                                <Link href={`/system-architecture?variant=${encodeURIComponent(run.architecture_variant_id)}`}>Open Variant</Link>
                                            ) : '-'}
                                        </td>
                                        <td style={{ padding: '0.5rem', color: statusColor[run.status] || '#333' }}>{run.status}</td>
                                        <td style={{ padding: '0.5rem' }}>{run.created_at ? new Date(run.created_at).toLocaleString() : '-'}</td>
                                        <td style={{ padding: '0.5rem' }}>
                                            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                                <button
                                                    onClick={() => onDownloadZip(run.run_id)}
                                                    className="btn btn-primary"
                                                    disabled={downloadingRunId === run.run_id || run.status !== 'completed'}
                                                >
                                                    {downloadingRunId === run.run_id ? 'Downloading...' : 'Download Zip'}
                                                </button>
                                                <button
                                                    onClick={() => onOpenSandbox(run)}
                                                    className="btn btn-secondary"
                                                    disabled={sandboxBusy || run.status !== 'completed'}
                                                >
                                                    Sandbox
                                                </button>
                                            </div>
                                            {run.status === 'failed' ? (
                                                <div style={{ color: '#cf222e', maxWidth: '32rem' }}>
                                                    Failed: {run.error_message || 'Unknown error'}
                                                </div>
                                            ) : run.status === 'in_progress' ? (
                                                <span style={{ color: '#0056d6' }}>Running...</span>
                                            ) : (
                                                <span style={{ color: '#666' }}>Queued...</span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>

                {sandboxModalOpen && (
                    <div
                        style={{
                            position: 'fixed',
                            inset: 0,
                            background: 'rgba(15, 23, 42, 0.62)',
                            zIndex: 1200,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '1rem',
                        }}
                        onClick={closeSandboxModal}
                    >
                        <div
                            style={{
                                width: 'min(1240px, 96vw)',
                                maxHeight: '90vh',
                                overflow: 'hidden',
                                background: '#fff',
                                borderRadius: '12px',
                                border: '1px solid #d1d5db',
                                boxShadow: '0 26px 64px rgba(2, 6, 23, 0.35)',
                                display: 'flex',
                                flexDirection: 'column',
                            }}
                            onClick={(event) => event.stopPropagation()}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.85rem 1rem', borderBottom: '1px solid #e5e7eb', background: '#f8fafc' }}>
                                <div>
                                    <h3 style={{ margin: 0 }}>Sandbox</h3>
                                    <p style={{ margin: '0.2rem 0 0', fontSize: '0.86rem', color: '#475569' }}>
                                        Run ID: {sandboxRunId} | Session: {sandboxSessionId || 'initializing'}
                                    </p>
                                </div>
                                <button type="button" className="btn btn-secondary" onClick={closeSandboxModal}>X</button>
                            </div>

                            <div style={{ padding: '1rem', overflow: 'auto' }}>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                    <div style={{ border: '1px solid #d1d5db', padding: '0.9rem' }}>
                                        <h4 style={{ marginTop: 0 }}>Session Controls</h4>
                                        <p style={{ marginTop: 0, color: sandboxStatusColor[sandboxSession?.status] || '#334155' }}>
                                            Status: {sandboxSession?.status || 'unknown'}
                                        </p>
                                        <p style={{ marginTop: 0, color: '#475569', fontSize: '0.88rem' }}>
                                            Stack: {sandboxSession?.stack_type || 'unknown'}
                                        </p>
                                        <p style={{ marginTop: 0, color: '#475569', fontSize: '0.88rem' }}>
                                            Idle expiry: {sandboxSession?.expires_at ? new Date(sandboxSession.expires_at).toLocaleString() : '-'}
                                        </p>
                                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                            <button className="btn btn-secondary" onClick={onStartSandbox} disabled={sandboxBusy || !sandboxSessionId}>Start</button>
                                            <button className="btn btn-secondary" onClick={onStopSandbox} disabled={sandboxBusy || !sandboxSessionId}>Stop</button>
                                            <button className="btn btn-secondary" onClick={() => sandboxSessionId && refreshSandboxSession(sandboxSessionId)} disabled={sandboxBusy || !sandboxSessionId}>Refresh Session</button>
                                        </div>
                                        {sandboxSession?.error_message && (
                                            <p style={{ color: '#b91c1c', marginTop: '0.5rem', marginBottom: 0 }}>
                                                {sandboxSession.error_message}
                                            </p>
                                        )}
                                    </div>

                                    <div style={{ border: '1px solid #d1d5db', padding: '0.9rem' }}>
                                        <h4 style={{ marginTop: 0 }}>Automatic Validation</h4>
                                        <p style={{ marginTop: 0, color: '#475569', fontSize: '0.88rem' }}>
                                            Uses LangGraph planning context from alpha run artifacts and executes up to 10 fix/retry cycles.
                                        </p>
                                        {autoValidationRunning && (
                                            <p style={{ marginTop: 0, color: '#0f766e', fontSize: '0.84rem', fontWeight: 600 }}>
                                                Validation in progress. Logs are loading and an email will be sent on completion.
                                            </p>
                                        )}
                                        <button
                                            className="btn btn-primary"
                                            onClick={() => runAutoValidation(sandboxSessionId)}
                                            disabled={sandboxBusy || !sandboxSessionId}
                                        >
                                            {autoValidationRunning ? 'Validation Running...' : (sandboxBusy ? 'Running...' : 'Run Automated Validation')}
                                        </button>
                                        {sandboxAutomation && (
                                            <div style={{ marginTop: '0.7rem', background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '8px', padding: '0.55rem' }}>
                                                <p style={{ margin: 0, fontWeight: 700, color: sandboxAutomation.passed ? '#166534' : '#b91c1c' }}>
                                                    Result: {sandboxAutomation.passed ? 'PASSED' : 'FAILED'}
                                                </p>
                                                <p style={{ margin: '0.2rem 0 0', color: '#475569', fontSize: '0.84rem' }}>
                                                    Engine: {sandboxAutomation.planning_engine || 'n/a'} | Attempts: {sandboxAutomation.attempts?.length || 0}/{sandboxAutomation.max_attempts || 10}
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div style={{ marginTop: '1rem', border: '1px solid #d1d5db', padding: '0.9rem' }}>
                                    <h4 style={{ marginTop: 0 }}>Execution Logs</h4>
                                    {!sandboxLogs.length ? (
                                        <p style={{ margin: 0 }}>{autoValidationRunning ? 'Loading logs...' : 'No logs yet.'}</p>
                                    ) : (
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.7rem' }}>
                                            {sandboxLogs.map((log) => (
                                                <div key={log.execution_id} style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '0.7rem', background: '#f8fafc' }}>
                                                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                                                        <strong>{log.action_type}</strong>
                                                        <span style={{ color: log.status === 'completed' ? '#166534' : '#b91c1c' }}>
                                                            {log.status} (exit {String(log.exit_code)})
                                                        </span>
                                                    </div>
                                                    <p style={{ margin: '0.25rem 0', fontSize: '0.82rem', color: '#475569' }}>
                                                        {log.created_at ? new Date(log.created_at).toLocaleString() : '-'}
                                                    </p>
                                                    {log.command_text && (
                                                        <pre style={{ margin: 0, background: '#0f172a', color: '#e2e8f0', padding: '0.5rem', borderRadius: '6px', overflow: 'auto', fontSize: '0.8rem' }}>{log.command_text}</pre>
                                                    )}
                                                    {Boolean(log.stdout) && (
                                                        <details style={{ marginTop: '0.4rem' }}>
                                                            <summary>stdout</summary>
                                                            <pre style={{ margin: 0, background: '#111827', color: '#d1fae5', padding: '0.5rem', borderRadius: '6px', overflow: 'auto', fontSize: '0.78rem' }}>{log.stdout}</pre>
                                                        </details>
                                                    )}
                                                    {Boolean(log.stderr) && (
                                                        <details style={{ marginTop: '0.4rem' }}>
                                                            <summary>stderr</summary>
                                                            <pre style={{ margin: 0, background: '#111827', color: '#fecaca', padding: '0.5rem', borderRadius: '6px', overflow: 'auto', fontSize: '0.78rem' }}>{log.stderr}</pre>
                                                        </details>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </>
    );
}
