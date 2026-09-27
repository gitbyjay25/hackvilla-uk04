'use client';

import { Eye, Zap, TrendingUp, BarChart3, Shield, GitBranch } from 'lucide-react';

export default function Features() {
    const features = [
        {
            icon: Eye,
            title: 'Production Observability',
            description: 'Understand your system from how it actually runs in production. Our lightweight SDK observes live request flows, service connections, and performance behavior without accessing source code or sensitive data.'
        },
        {
            icon: Zap,
            title: 'Automatic Architecture Rebuild',
            description: 'Automatically rebuild workflow and architectural design based on actual runtime behavior. Get clear visibility into your system\'s real structure and identify bottlenecks instantly.'
        },
        {
            icon: TrendingUp,
            title: 'AI-Powered Design Options',
            description: 'Generate multiple improved architecture designs with workflow options focused on performance, cost, or low-risk changes. Each option is optimized for your specific system needs.'
        },
        {
            icon: BarChart3,
            title: 'Metric-Based Comparison',
            description: 'Compare architecture options using clear metrics like speed, reliability, cost, and complexity. Make confident, data-backed decisions faster with actionable insights.'
        },
        {
            icon: Shield,
            title: 'Reduce Risk & Manual Analysis',
            description: 'Lower risk during architectural changes and eliminate manual analysis. Get continuous clarity as your applications evolve, ensuring your system stays production-ready.'
        },
        {
            icon: GitBranch,
            title: 'Workflow Pipeline Insights',
            description: 'Discover interesting information about your entire architecture and workflow pipelines. Keep your system organized and never get messed up with comprehensive visibility.'
        }
    ];

    return (
        <section className="features" id="features">
            <div className="features__header">
                <span className="tape-label">Core Capabilities</span>
                <h2 className="display-title display-md" style={{ marginTop: '1rem' }}>
                    UNDERSTAND YOUR ARCHITECTURE
                </h2>
                <p style={{ color: 'var(--color-gray)', marginTop: '1rem', maxWidth: '600px', margin: '1rem auto 0' }}>
                    Better system visibility platform that reduces manual analysis, lowers risk during changes, 
                    and provides continuous clarity as applications evolve.
                </p>
            </div>

            <div className="features__grid">
                {features.map((feature, index) => {
                    const IconComponent = feature.icon;
                    return (
                        <div key={index} className="feature-card">
                            <div className="feature-card__icon">
                                <IconComponent size={40} strokeWidth={1.5} />
                            </div>
                            <h3 className="feature-card__title">{feature.title}</h3>
                            <p className="feature-card__description">{feature.description}</p>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}
