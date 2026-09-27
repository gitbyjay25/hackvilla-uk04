/**
 * useRealtimeStream — React hook for Pathway live stream
 *
 * Maintains a persistent WebSocket connection to the Nexarch stream endpoint.
 * Provides live metric updates and issue alerts to components.
 *
 * Usage:
 *   const { metrics, issues, connected, error } = useRealtimeStream(tenantId);
 */
'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

const PROD_WS_URL = 'wss://api.modelix.world';

function buildWsBaseUrl() {
    const explicit = (process.env.NEXT_PUBLIC_WS_URL || '').trim();
    if (explicit) return explicit.replace(/\/+$/, '');

    const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').trim();
    if (apiBase) {
        if (apiBase.startsWith('https://')) return apiBase.replace(/^https:\/\//, 'wss://').replace(/\/+$/, '');
        if (apiBase.startsWith('http://')) return apiBase.replace(/^http:\/\//, 'ws://').replace(/\/+$/, '');
        if (apiBase.startsWith('wss://') || apiBase.startsWith('ws://')) return apiBase.replace(/\/+$/, '');
    }

    return PROD_WS_URL;
}

function shouldEnableRealtime() {
    return true;
}

const WS_URL = `${buildWsBaseUrl()}/api/v1/stream/live`;

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;
const HEARTBEAT_INTERVAL_MS = 30_000;

/**
 * @param {string|null} tenantId   — tenant to subscribe to (null disables hook)
 * @param {object}      options
 * @param {number}      options.maxMetricHistory  — how many metric snapshots to keep per service (default 50)
 * @param {number}      options.maxIssueHistory   — how many issues to keep (default 100)
 */
export function useRealtimeStream(tenantId, options = {}) {
    const { maxMetricHistory = 50, maxIssueHistory = 100 } = options;

    const [connected, setConnected] = useState(false);
    const [error, setError] = useState(null);

    // metrics: Map<serviceName, MetricRow[]>  (newest first, bounded by maxMetricHistory)
    const [metrics, setMetrics] = useState({});
    // issues: array of latest issue events, newest first
    const [issues, setIssues] = useState([]);
    // raw events for consumers that want full history
    const [lastEvent, setLastEvent] = useState(null);

    const wsRef = useRef(null);
    const reconnectAttempts = useRef(0);
    const reconnectTimer = useRef(null);
    const heartbeatTimer = useRef(null);
    const isMounted = useRef(true);

    const cleanup = useCallback(() => {
        if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
        if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
        if (wsRef.current) {
            wsRef.current.onclose = null; // prevent reconnect loop on intentional close
            wsRef.current.close();
            wsRef.current = null;
        }
    }, []);

    const connect = useCallback(() => {
        if (!tenantId || !isMounted.current) return;
        if (!shouldEnableRealtime()) return;

        const url = `${WS_URL}?tenant_id=${encodeURIComponent(tenantId)}`;
        let ws;

        try {
            ws = new WebSocket(url);
        } catch (e) {
            setError('WebSocket not supported');
            return;
        }

        wsRef.current = ws;

        ws.onopen = () => {
            if (!isMounted.current) return;
            setConnected(true);
            setError(null);
            reconnectAttempts.current = 0;

            // Heartbeat to keep the connection alive through proxies
            heartbeatTimer.current = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send('ping');
                }
            }, HEARTBEAT_INTERVAL_MS);
        };

        ws.onmessage = (evt) => {
            if (!isMounted.current) return;
            try {
                const msg = JSON.parse(evt.data);
                setLastEvent(msg);

                if (msg.type === 'metrics_update') {
                    setMetrics((prev) => {
                        const history = prev[msg.service] || [];
                        const next = [msg.data, ...history];
                        return {
                            ...prev,
                            [msg.service]: next.slice(0, maxMetricHistory),
                        };
                    });
                } else if (msg.type === 'issue_detected') {
                    setIssues((prev) => {
                        const next = [msg.data, ...prev];
                        return next.slice(0, maxIssueHistory);
                    });
                }
            } catch (_) {
                // silently ignore malformed frames
            }
        };

        ws.onerror = () => {
            if (!isMounted.current) return;
            setError('WebSocket error');
        };

        ws.onclose = () => {
            if (!isMounted.current) return;
            setConnected(false);
            clearInterval(heartbeatTimer.current);

            if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts.current += 1;
                const delay = Math.min(RECONNECT_DELAY_MS * reconnectAttempts.current, 30_000);
                reconnectTimer.current = setTimeout(connect, delay);
            } else {
                setError('Stream unavailable — too many reconnect attempts.');
            }
        };
    }, [tenantId, maxIssueHistory, maxMetricHistory]);

    useEffect(() => {
        isMounted.current = true;
        connect();

        return () => {
            isMounted.current = false;
            cleanup();
        };
    }, [connect, cleanup]);

    const reconnect = useCallback(() => {
        cleanup();
        reconnectAttempts.current = 0;
        connect();
    }, [cleanup, connect]);

    return { connected, error, metrics, issues, lastEvent, reconnect };
}

export default useRealtimeStream;
