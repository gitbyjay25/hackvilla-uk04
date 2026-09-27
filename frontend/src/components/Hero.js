'use client';

import Image from 'next/image';

export default function Hero() {
    return (
        <section className="hero">
            {/* Halftone decorations */}
            <div className="halftone-corner halftone-corner--top-right" />
            <div className="halftone-corner halftone-corner--bottom-left" />

            <div className="hero__content">
                {/* Text Content */}
                <div className="hero__text">
                    <div className="hero__badge">
                        <span className="tape-label">PRODUCTION INSIGHTS</span>
                        <span className="tape-label tape-label--rotated">v2.0</span>
                    </div>

                    <h1 className="hero__title display-title display-xl">
                        NEXARCH
                    </h1>

                    <p className="hero__subtitle">
                        Understand your production architecture automatically. Nexarch observes live request flows, 
                        service connections, and performance behavior without accessing source code. Get clear 
                        visibility into how your system actually works and make data-backed architectural decisions.
                    </p>

                    <div className="hero__meta">
                        <div className="hero__meta-item">
                            <span className="hero__meta-label">Systems Analyzed</span>
                            <span className="hero__meta-value">10,000+</span>
                        </div>
                        <div className="hero__meta-item">
                            <span className="hero__meta-label">Architecture Designs</span>
                            <span className="hero__meta-value">50K+</span>
                        </div>
                        <div className="hero__meta-item">
                            <span className="hero__meta-label">Performance Improvements</span>
                            <span className="hero__meta-value">85%</span>
                        </div>
                    </div>

                    <div className="hero__actions">
                        <button className="btn btn-primary">Start Observing</button>
                        <button className="btn btn-secondary">Learn More</button>
                    </div>
                </div>

                {/* Cryptex Image */}
                <div className="hero__image-container">
                    <div className="hero__image-decoration" />
                        <Image
                        src="/cryptex-wheel.png"
                        alt="Production architecture analysis and workflow visualization"
                        width={600}
                        height={450}
                        className="hero__image"
                        priority
                    />
                </div>
            </div>

            {/* Partners Bar */}
            <div className="partners-bar">
                <div className="partners-bar__item">
                    <span className="partners-bar__logo">◈ NEXARCH</span>
                </div>
                <div className="partners-bar__item">
                    <span className="partners-bar__text">Trusted by engineering teams at</span>
                    <span className="partners-bar__highlight">Scale Companies</span>
                </div>
                <div className="partners-bar__item">
                    <span className="partners-bar__text">Production systems analyzed</span>
                    <span className="partners-bar__highlight">Real-time</span>
                </div>
                <div className="partners-bar__item">
                    <button className="btn btn-primary">Get Started Free</button>
                </div>
            </div>
        </section>
    );
}
