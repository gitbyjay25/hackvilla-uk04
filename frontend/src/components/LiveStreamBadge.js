'use client';

/**
 * LiveStreamBadge
 * Visual indicator that shows real-time Pathway stream connection status.
 * 
 * Usage:
 *   <LiveStreamBadge connected={connected} error={error} />
 */
export default function LiveStreamBadge({ connected, error }) {
    if (error) {
        return (
            <span style={{
                display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
                padding: '0.2rem 0.6rem', borderRadius: '999px',
                background: 'rgba(239,68,68,0.1)', color: '#ef4444',
                fontSize: '0.75rem', fontWeight: 500,
            }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ef4444' }} />
                Stream error
            </span>
        );
    }

    if (!connected) {
        return (
            <span style={{
                display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
                padding: '0.2rem 0.6rem', borderRadius: '999px',
                background: 'rgba(148,163,184,0.1)', color: '#94a3b8',
                fontSize: '0.75rem', fontWeight: 500,
            }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#94a3b8' }} />
                Connecting...
            </span>
        );
    }

    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
            padding: '0.2rem 0.6rem', borderRadius: '999px',
            background: 'rgba(34,197,94,0.1)', color: '#22c55e',
            fontSize: '0.75rem', fontWeight: 500,
        }}>
            <span style={{
                width: 6, height: 6, borderRadius: '50%', background: '#22c55e',
                boxShadow: '0 0 0 0 rgba(34,197,94,0.4)',
                animation: 'live-pulse 1.5s ease-out infinite',
            }} />
            Live
            <style>{`
                @keyframes live-pulse {
                    0%   { box-shadow: 0 0 0 0 rgba(34,197,94,0.4); }
                    70%  { box-shadow: 0 0 0 6px rgba(34,197,94,0); }
                    100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
                }
            `}</style>
        </span>
    );
}
