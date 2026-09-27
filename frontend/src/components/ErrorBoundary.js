'use client';

import React from 'react';

/**
 * ErrorBoundary
 * Wrap any section that might throw during render.
 * Shows a graceful fallback instead of a blank/crashed page.
 *
 * Usage:
 *   <ErrorBoundary fallback={<p>Failed to load this section.</p>}>
 *     <SomeComponent />
 *   </ErrorBoundary>
 */
export default class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, info) {
        console.error('[ErrorBoundary] Caught error:', error, info);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div style={{
                    padding: '1.5rem',
                    border: '1px solid var(--color-error, #ef4444)',
                    borderRadius: '0.5rem',
                    background: 'rgba(239,68,68,0.05)',
                    color: 'var(--color-error, #ef4444)',
                    fontSize: '0.875rem',
                }}>
                    <strong>Something went wrong in this section.</strong>
                    {this.props.showDetails && this.state.error && (
                        <pre style={{ marginTop: '0.5rem', fontSize: '0.75rem', opacity: 0.7, whiteSpace: 'pre-wrap' }}>
                            {this.state.error.message}
                        </pre>
                    )}
                    {this.props.allowRetry !== false && (
                        <button
                            onClick={this.handleReset}
                            style={{ marginTop: '0.75rem', textDecoration: 'underline', background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
                        >
                            Try again
                        </button>
                    )}
                </div>
            );
        }

        return this.props.children;
    }
}
