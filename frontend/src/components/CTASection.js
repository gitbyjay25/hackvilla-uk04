'use client';

export default function CTASection() {
    return (
        <section className="cta-section halftone-bg">
            <div className="cta-section__content">
                <span className="tape-label">Free Forever Plan</span>

                <h2 className="cta-section__title display-title display-md" style={{ marginTop: '1.5rem' }}>
                    OBSERVE YOUR PRODUCTION<br />ARCHITECTURE TODAY
                </h2>

                <p className="cta-section__description">
                    Join engineering teams using Nexarch to understand their production systems and make 
                    data-backed architectural decisions. Start with our free plan — no credit card required. 
                    Upgrade when you're ready to scale your observability.
                </p>

                <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
                    <button className="btn btn-primary" style={{ padding: '1rem 2rem', fontSize: '1rem' }}>
                        Start Observing Free
                    </button>
                    <button className="btn btn-secondary" style={{ padding: '1rem 2rem', fontSize: '1rem' }}>
                        Book a Demo
                    </button>
                </div>

                <p style={{
                    marginTop: '2rem',
                    fontSize: '0.75rem',
                    color: 'var(--color-gray-light)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em'
                }}>
                    Real-time observability • AI-powered insights • Production-ready systems
                </p>
            </div>
        </section>
    );
}
