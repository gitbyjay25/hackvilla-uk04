'use client';

/**
 * Skeleton loaders for dashboard sections.
 * Provides smooth loading placeholders that match each section's layout.
 */

const pulse = {
    background: 'linear-gradient(90deg, var(--color-surface, #1a1a2e) 25%, var(--color-border, #2a2a3e) 50%, var(--color-surface, #1a1a2e) 75%)',
    backgroundSize: '200% 100%',
    animation: 'skeleton-pulse 1.5s ease-in-out infinite',
    borderRadius: '0.375rem',
    display: 'block',
};

export function SkeletonBlock({ width = '100%', height = '1rem', style = {} }) {
    return (
        <span
            style={{
                ...pulse,
                width,
                height,
                ...style,
            }}
            aria-hidden="true"
        />
    );
}

export function SkeletonCard({ rows = 3 }) {
    return (
        <div style={{ padding: '1.25rem', border: '1px solid var(--color-border, #2a2a3e)', borderRadius: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <SkeletonBlock height="1.25rem" width="60%" />
            {Array.from({ length: rows }).map((_, i) => (
                <SkeletonBlock key={i} height="0.875rem" width={`${70 + (i % 3) * 10}%`} />
            ))}
        </div>
    );
}

export function SkeletonMetricGrid({ count = 4 }) {
    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
            {Array.from({ length: count }).map((_, i) => (
                <SkeletonCard key={i} rows={2} />
            ))}
        </div>
    );
}

export function SkeletonTable({ rows = 5, cols = 4 }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {/* Header */}
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: '0.5rem', paddingBottom: '0.5rem', borderBottom: '1px solid var(--color-border, #2a2a3e)' }}>
                {Array.from({ length: cols }).map((_, i) => (
                    <SkeletonBlock key={i} height="0.875rem" width="70%" />
                ))}
            </div>
            {/* Rows */}
            {Array.from({ length: rows }).map((_, r) => (
                <div key={r} style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: '0.5rem', padding: '0.4rem 0' }}>
                    {Array.from({ length: cols }).map((_, c) => (
                        <SkeletonBlock key={c} height="0.875rem" width={c === 0 ? '80%' : '60%'} />
                    ))}
                </div>
            ))}
        </div>
    );
}

// Global CSS for the animation (injected once)
if (typeof document !== 'undefined') {
    const styleId = 'nexarch-skeleton-style';
    if (!document.getElementById(styleId)) {
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            @keyframes skeleton-pulse {
                0%   { background-position: 200% 0; }
                100% { background-position: -200% 0; }
            }
        `;
        document.head.appendChild(style);
    }
}
