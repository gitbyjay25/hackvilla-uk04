import { SkeletonMetricGrid, SkeletonCard } from '@/components/Skeleton';

export default function DashboardLoading() {
    return (
        <div className="dashboard-page">
            <div className="dashboard-content">
                <div className="dashboard-header">
                    <div style={{ height: 32, width: 260, background: '#e2e8f0', borderRadius: 4 }} />
                </div>
                <SkeletonMetricGrid cols={4} />
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginTop: 24 }}>
                    <SkeletonCard lines={6} />
                    <SkeletonCard lines={6} />
                </div>
            </div>
        </div>
    );
}
