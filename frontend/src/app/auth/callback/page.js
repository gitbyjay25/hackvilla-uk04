'use client';

import { useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { tokenStorage } from '@/lib/api-client';

function CallbackContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { handleCallback, checkAuth } = useAuth();

    useEffect(() => {
        const processCallback = async () => {
            const installationId = searchParams.get('installation_id');
            const setupAction = searchParams.get('setup_action');
            const state = searchParams.get('state');

            if (installationId) {
                const profileParams = new URLSearchParams();
                profileParams.set('installation_id', installationId);
                if (setupAction) profileParams.set('setup_action', setupAction);
                if (state) profileParams.set('state', state);
                router.push(`/profile?${profileParams.toString()}`);
                return;
            }

            // Check for code in URL params (from OAuth redirect)
            const code = searchParams.get('code');
            const oauthState = searchParams.get('state');

            // Check for token in URL hash (direct token)
            const hash = window.location.hash;
            const hashParams = new URLSearchParams(hash.substring(1));
            const accessToken = hashParams.get('access_token');

            if (accessToken) {
                // Token provided directly in hash — store via tokenStorage then refresh
                // AuthContext state so the user arrives at the dashboard fully authenticated.
                tokenStorage.set(accessToken);
                await checkAuth();
                router.push('/dashboard');
            } else if (code) {
                // Exchange code for token
                try {
                    await handleCallback(code, oauthState);
                    router.push('/dashboard');
                } catch (error) {
                    console.error('Callback error:', error);
                    router.push('/login?error=auth_failed');
                }
            } else {
                // No code or token, redirect to login
                router.push('/login');
            }
        };

        processCallback();
    }, [searchParams, handleCallback, checkAuth, router]);

    return (
        <div className="auth-page">
            <div className="halftone-corner halftone-corner--top-right" />
            <div className="halftone-corner halftone-corner--bottom-left" />

            <div className="auth-container">
                <div className="auth-card" style={{ textAlign: 'center' }}>
                    <div className="auth-logo">NEXARCH</div>
                    <h1 className="auth-title display-title display-md">
                        AUTHENTICATING
                    </h1>
                    <div className="auth-loading-spinner">
                        <div className="spinner"></div>
                    </div>
                    <p className="auth-subtitle">
                        Please wait while we complete your sign in...
                    </p>
                </div>

                <div className="auth-decoration" aria-hidden="true">
                    <div className="auth-decoration__grid">
                        {[...Array(16)].map((_, i) => (
                            <div key={i} className="auth-decoration__cell" />
                        ))}
                    </div>
                    <div className="auth-decoration__text">
                        <span className="display-title">PRODUCTION</span>
                        <span className="display-title">OBSERVABILITY</span>
                        <span className="display-title">ARCHITECTURE</span>
                        <span className="display-title">INSIGHTS</span>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default function AuthCallback() {
    return (
        <Suspense fallback={
            <div className="auth-page">
                <div className="halftone-corner halftone-corner--top-right" />
                <div className="halftone-corner halftone-corner--bottom-left" />
                <div className="auth-container">
                    <div className="auth-card" style={{ textAlign: 'center' }}>
                        <div className="auth-loading">Loading...</div>
                    </div>
                </div>
            </div>
        }>
            <CallbackContent />
        </Suspense>
    );
}
