'use client';

import { useAuth } from '@/lib/auth-context';
import Navbar from '@/components/Navbar';
import Hero from '@/components/Hero';
import Features from '@/components/Features';
import CTASection from '@/components/CTASection';
import Footer from '@/components/Footer';
import Link from 'next/link';
import { BookOpen, Rocket } from 'lucide-react';

export default function Home() {
    const { isAuthenticated, loading: authLoading } = useAuth();

    return (
        <main>
            <Navbar />
            <Hero />
            <Features />
            {!authLoading && !isAuthenticated && (
                <section className="dashboard-page" style={{ paddingTop: '0', paddingBottom: '0' }}>
                    <div className="dashboard-content" style={{ paddingTop: '0' }}>
                        <div className="dashboard-panel sdk-home-panel">
                            <div className="panel-header">
                                <h2 className="section-title">
                                    <BookOpen size={18} />
                                    SDK Docs For FastAPI
                                </h2>
                            </div>
                            <p style={{ marginBottom: '0.75rem' }}>
                                Learn how Nexarch SDK captures runtime telemetry from your FastAPI service, how to install it,
                                and how to connect it to your first API key.
                            </p>
                            <p style={{ marginBottom: '1rem' }}>
                                The current SDK supports FastAPI only. Django, Flask, and Node.js packages are coming next,
                                along with popular frameworks like Express and NestJS.
                            </p>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
                                <Link href="/sdk-docs" className="btn btn-primary">
                                    <Rocket size={16} />
                                    Open SDK Docs
                                </Link>
                                <Link href="/api-keys" className="btn btn-secondary">
                                    Create API Key
                                </Link>
                            </div>
                        </div>
                    </div>
                </section>
            )}
            <CTASection />
            <Footer />
        </main>
    );
}
