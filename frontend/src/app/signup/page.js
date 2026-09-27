'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { Globe, Zap, Shield, Cpu } from 'lucide-react';

export default function SignupPage() {
    const router = useRouter();
    const { loginWithGoogle, signupWithEmail, isAuthenticated, loading } = useAuth();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');

    useEffect(() => {
        if (!loading && isAuthenticated) {
            router.push('/dashboard');
        }
    }, [isAuthenticated, loading, router]);

    const handleEmailSignup = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);
        console.log('Starting signup process...');
        try {
            console.log('Calling signupWithEmail...');
            await signupWithEmail(email, password, fullName);
            console.log('Signup successful, redirecting to dashboard...');
            // Only redirect if successful
            router.push('/dashboard');
        } catch (err) {
            console.error('Signup error:', err);
            setError(err.message || 'Signup failed. Please try again.');
            setIsLoading(false);
        }
    };

    const handleGoogleSignup = async () => {
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
                        <span className="tape-label">JOIN NOW</span>
                    </div>

                    {/* Title */}
                    <h1 className="auth-title display-title display-md">
                        CREATE ACCOUNT
                    </h1>

                    <p className="auth-subtitle">
                        Start observing your production architecture and get AI-powered optimization recommendations. Free forever.
                    </p>

                    {/* Features */}
                    <div className="auth-features">
                        <div className="auth-feature">
                            <Cpu size={18} />
                            <span>Production Observability</span>
                        </div>
                        <div className="auth-feature">
                            <Zap size={18} />
                            <span>AI-Powered Architecture Insights</span>
                        </div>
                        <div className="auth-feature">
                            <Shield size={18} />
                            <span>Lightweight SDK Integration</span>
                        </div>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="auth-error">
                            {error}
                        </div>
                    )}

                    {/* Email/Password Form */}
                    <form onSubmit={handleEmailSignup} className="auth-form">
                        <div className="form-group">
                            <label htmlFor="fullName">Full Name</label>
                            <input
                                type="text"
                                id="fullName"
                                value={fullName}
                                onChange={(e) => setFullName(e.target.value)}
                                disabled={isLoading}
                                placeholder="John Doe"
                                required
                            />
                        </div>
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
                                minLength="8"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="btn-primary"
                        >
                            {isLoading ? 'Creating account...' : 'Create Account'}
                        </button>
                    </form>

                    {/* Divider */}
                    <div className="auth-divider">
                            <Globe size={20} />
                    </div>

                    {/* Google Sign Up Button */}
                    <button
                        onClick={handleGoogleSignup}
                        disabled={isLoading}
                        className="btn-google"
                    >
                        <Globe size={20} />
                        <span>{isLoading ? 'Connecting...' : 'Sign up with Google'}</span>
                    </button>

                    {/* Divider */}
                    <div className="auth-divider">
                        <span>NO CREDIT CARD REQUIRED</span>
                    </div>

                    {/* Info */}
                    <div className="auth-info">
                        <p>By creating an account, you agree to our Terms of Service and Privacy Policy.</p>
                    </div>

                    {/* Footer */}
                    <div className="auth-footer">
                        <p>Already have an account?</p>
                        <Link href="/login" className="auth-link">
                            Sign In
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
                        <span className="display-title">OBSERVE</span>
                        <span className="display-title">ANALYZE</span>
                        <span className="display-title">OPTIMIZE</span>
                        <span className="display-title">EVOLVE</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
