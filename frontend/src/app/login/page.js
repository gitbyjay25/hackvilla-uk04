'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { Globe } from 'lucide-react';

function LoginContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { loginWithGoogle, loginWithEmail, isAuthenticated, loading } = useAuth();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    useEffect(() => {
        if (!loading && isAuthenticated) {
            router.push('/dashboard');
        }
    }, [isAuthenticated, loading, router]);

    useEffect(() => {
        // Check for error in URL params
        const errorParam = searchParams.get('error');
        if (errorParam) {
            const errorMessages = {
                'server_error': 'Server error occurred. Please try again.',
                'auth_failed': 'Authentication failed. Please try again.',
                'no_code': 'No authorization code received from Google.',
                'no_email': 'No email address received from Google.',
                'http_error': 'HTTP error occurred during authentication.'
            };
            setError(errorMessages[errorParam] || 'An error occurred. Please try again.');
        }
    }, [searchParams]);

    const handleEmailLogin = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);
        try {
            await loginWithEmail(email, password);
            // Only redirect if successful
            router.push('/dashboard');
        } catch (err) {
            console.error('Login error:', err);
            setError(err.message || 'Login failed. Please check your credentials.');
            setIsLoading(false);
        }
    };

    const handleGoogleLogin = async () => {
        setIsLoading(true);
        setError(null);
        try {
            await loginWithGoogle();
        } catch (err) {
            setError('Failed to connect to authentication service. Please try again.');
            setIsLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="auth-page">
                <div className="auth-container">
                    <div className="auth-loading">Loading...</div>
                </div>
            </div>
        );
    }

    return (
        <div className="auth-page">
            {/* Halftone decorations */}
            <div className="halftone-corner halftone-corner--top-right" />
            <div className="halftone-corner halftone-corner--bottom-left" />

            <div className="auth-container">
                <div className="auth-card">
                    {/* Header */}
                    <div className="auth-header">
                        <Link href="/" className="auth-logo">NEXARCH</Link>
                        <span className="tape-label tape-label--rotated">WELCOME BACK</span>
                    </div>

                    {/* Title */}
                    <h1 className="auth-title display-title display-md">
                        SIGN IN
                    </h1>

                    <p className="auth-subtitle">
                        Access your production architecture observability dashboard and AI-powered optimization insights.
                    </p>

                    {/* Error Message */}
                    {error && (
                        <div className="auth-error">
                            {error}
                        </div>
                    )}

                    {/* Email/Password Form */}
                    <form onSubmit={handleEmailLogin} className="auth-form">
                        <div className="form-group">
                            <label htmlFor="email">Email</label>
                            <input
                                type="email"
                                id="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                disabled={isLoading}
                                placeholder="you@example.com"
                            />
                        </div>
                        <div className="form-group">
                            <label htmlFor="password">Password</label>
                            <input
                                type="password"
                                id="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                disabled={isLoading}
                                placeholder="••••••••"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="btn-primary"
                        >
                            {isLoading ? 'Signing in...' : 'Sign In'}
                        </button>
                    </form>

                    {/* Divider */}
                    <div className="auth-divider">
                        <span>OR</span>
                    </div>

                    {/* Google Sign In Button */}
                    <button
                        onClick={handleGoogleLogin}
                        disabled={isLoading}
                        className="btn-google"
                    >
                        <Globe size={20} />
                        <span>{isLoading ? 'Connecting...' : 'Continue with Google'}</span>
                    </button>

                    {/* Divider */}
                    <div className="auth-divider">
                        <span>SECURE AUTHENTICATION</span>
                    </div>

                    {/* Info */}
                    <div className="auth-info">
                        <p>By signing in, you agree to our Terms of Service and Privacy Policy.</p>
                    </div>

                    {/* Footer */}
                    <div className="auth-footer">
                        <p>Don't have an account?</p>
                        <Link href="/signup" className="auth-link">
                            Create Account
                        </Link>
                    </div>
                </div>

                {/* Side decoration */}
                <div className="auth-decoration">
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

export default function LoginPage() {
    return (
        <Suspense fallback={
            <div className="auth-page">
                <div className="auth-container">
                    <div className="auth-loading">Loading...</div>
                </div>
            </div>
        }>
            <LoginContent />
        </Suspense>
    );
}
