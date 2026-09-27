import Link from 'next/link';
import { BookOpen, Key, Server, Activity, Rocket, ArrowRight } from 'lucide-react';
import Navbar from '@/components/Navbar';

export const metadata = {
    title: 'Nexarch SDK Docs',
    description: 'Integration guide for the Nexarch SDK with FastAPI services and telemetry best practices.',
};

export default function SdkDocsPage() {
    return (
        <>
            <Navbar />
            <div className="dashboard-page sdk-docs-page">
                <div className="dashboard-content">
                <div className="dashboard-header">
                    <div>
                        <span className="tape-label">Integration Guide</span>
                        <h1 className="display-title display-md" style={{ marginTop: '0.5rem' }}>
                            NEXARCH SDK DOCS
                        </h1>
                        <p className="dashboard-welcome" style={{ maxWidth: 860 }}>
                            Deep guide for integrating Nexarch SDK into your FastAPI server. The SDK captures runtime telemetry,
                            ships spans to Nexarch, and powers the dashboard with real production signals.
                        </p>
                    </div>
                </div>

                <section className="dashboard-panel sdk-docs-hero">
                    <div className="panel-header">
                        <h2 className="section-title">
                            <BookOpen size={18} />
                            How The SDK Works
                        </h2>
                    </div>
                    <div className="sdk-flow-grid">
                        <div className="sdk-flow-step">
                            <Server size={18} />
                            <h3>1. Instrument FastAPI</h3>
                            <p>Initialize SDK in your app startup. It wraps request lifecycle and captures service-level spans.</p>
                        </div>
                        <div className="sdk-flow-step">
                            <Activity size={18} />
                            <h3>2. Capture Runtime Signals</h3>
                            <p>Each request records latency, status code, errors, and upstream/downstream service relationship data.</p>
                        </div>
                        <div className="sdk-flow-step">
                            <Rocket size={18} />
                            <h3>3. Send To Nexarch</h3>
                            <p>Spans are batched and sent securely to ingest endpoints. Dashboard analytics are computed from this telemetry.</p>
                        </div>
                    </div>
                </section>

                <section className="dashboard-panel">
                    <div className="panel-header">
                        <h2 className="section-title">FastAPI Quick Start</h2>
                    </div>

                    <div className="sdk-docs-block">
                        <h3>Step 1: Install package</h3>
                        <pre className="sdk-code-block">pip install nexarch-sdk</pre>
                    </div>

                    <div className="sdk-docs-block">
                        <h3>Step 2: Create API key in Nexarch</h3>
                        <p>Open API Keys and generate a key for your environment (production, staging, or development).</p>
                    </div>

                    <div className="sdk-docs-block">
                        <h3>Step 3: Integrate with your FastAPI app</h3>
                        <pre className="sdk-code-block">{`from fastapi import FastAPI\nfrom nexarch import NexarchSDK\n\napp = FastAPI()\n\nsdk = NexarchSDK(\n    api_key="nx_...",\n    service_name="orders-service",\n    backend_url="https://your-nexarch-server"\n)\n\nsdk.init(app)\n\n@app.get("/health")\ndef health():\n    return {"status": "ok"}`}</pre>
                    </div>

                    <div className="sdk-docs-block">
                        <h3>Step 4: Generate traffic and verify</h3>
                        <p>
                            Hit your API endpoints and then open Dashboard. You should see services, request volume, latency trends,
                            error rates, and deep window analysis.
                        </p>
                    </div>
                </section>

                <section className="dashboard-panel">
                    <div className="panel-header">
                        <h2 className="section-title">What Telemetry Is Captured</h2>
                    </div>
                    <ul className="sdk-docs-list">
                        <li>Request volume by time bucket</li>
                        <li>Average and p95 latency</li>
                        <li>Error rate and reliability trends</li>
                        <li>Service dependency relationships</li>
                        <li>Per-service health and bottleneck indicators</li>
                    </ul>
                </section>

                <section className="dashboard-panel sdk-support-panel">
                    <div className="panel-header">
                        <h2 className="section-title">Support Status And Roadmap</h2>
                    </div>
                    <p>
                        <strong>Current support:</strong> Nexarch SDK officially supports <strong>FastAPI</strong> right now.
                    </p>
                    <p>
                        <strong>Coming soon:</strong> Django, Flask, Node.js packages on npm (including Express and NestJS), and other
                        popular ecosystems.
                    </p>
                    <p>
                        We are expanding framework adapters while preserving the same telemetry model so teams can migrate without losing
                        comparability in dashboard analytics.
                    </p>
                </section>

                <div className="sdk-docs-actions">
                    <Link href="/api-keys" className="btn btn-primary">
                        <Key size={16} />
                        Create API Key
                    </Link>
                    <Link href="/dashboard" className="btn btn-secondary">
                        Open Telemetry Dashboard
                        <ArrowRight size={14} />
                    </Link>
                </div>
            </div>
            </div>
        </>
    );
}
