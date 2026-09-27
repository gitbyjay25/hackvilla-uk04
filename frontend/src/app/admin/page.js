'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { apiClient } from '@/lib/api-client';
import { isAdminUserEmail } from '@/lib/admin-access';
import Navbar from '@/components/Navbar';
import {
    Users,
    Building2,
    Plus,
    Edit,
    Trash2,
    RefreshCw,
    CheckCircle,
    XCircle,
    Key,
    AlertTriangle,
    Shield,
    Search,
    ChevronDown,
    ChevronUp,
    Mail,
    Calendar,
    Activity,
    Settings
} from 'lucide-react';

export default function AdminPage() {
    const { isAuthenticated, loading: authLoading, user } = useAuth();
    const isAdminUser = isAdminUserEmail(user?.email);
    const [tenants, setTenants] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const [actionLoading, setActionLoading] = useState(null);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);
    const [selectedTenant, setSelectedTenant] = useState(null);
    const [expandedTenant, setExpandedTenant] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');

    // Create/Edit form state
    const [formData, setFormData] = useState({
        name: '',
        email: '',
        plan: 'free',
        status: 'active',
        settings: {
            max_services: 10,
            max_users: 5,
            data_retention_days: 30,
            features: []
        }
    });

    const plans = ['free', 'starter', 'professional', 'enterprise'];
    const statuses = ['active', 'inactive', 'suspended', 'pending'];
    const featureOptions = [
        'ai_design',
        'workflow_generation',
        'real_time_monitoring',
        'advanced_analytics',
        'custom_integrations',
        'priority_support',
        'sso',
        'audit_logs'
    ];

    useEffect(() => {
        if (!authLoading && isAuthenticated && isAdminUser) {
            fetchTenants();
        }
    }, [authLoading, isAuthenticated, isAdminUser]);

    const fetchTenants = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await apiClient.getTenants();
            setTenants(data.tenants || data || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateTenant = async (e) => {
        e.preventDefault();
        setActionLoading('create');
        setError(null);
        setSuccess(null);
        try {
            await apiClient.createTenant(formData);
            setSuccess('Tenant created successfully');
            setShowCreateModal(false);
            resetForm();
            fetchTenants();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    };

    const handleUpdateTenant = async (e) => {
        e.preventDefault();
        if (!selectedTenant) return;
        setActionLoading('update');
        setError(null);
        setSuccess(null);
        try {
            await apiClient.updateTenant(selectedTenant.id, formData);
            setSuccess('Tenant updated successfully');
            setShowEditModal(false);
            setSelectedTenant(null);
            resetForm();
            fetchTenants();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    };

    const handleDeleteTenant = async (tenant) => {
        if (!confirm(`Are you sure you want to delete tenant "${tenant.name}"? This action cannot be undone.`)) {
            return;
        }
        setActionLoading(`delete-${tenant.id}`);
        setError(null);
        setSuccess(null);
        try {
            await apiClient.deleteTenant(tenant.id);
            setSuccess(`Tenant "${tenant.name}" deleted successfully`);
            fetchTenants();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    };

    const openEditModal = (tenant) => {
        setSelectedTenant(tenant);
        setFormData({
            name: tenant.name || '',
            email: tenant.email || '',
            plan: tenant.plan || 'free',
            status: tenant.status || 'active',
            settings: {
                max_services: tenant.settings?.max_services || 10,
                max_users: tenant.settings?.max_users || 5,
                data_retention_days: tenant.settings?.data_retention_days || 30,
                features: tenant.settings?.features || []
            }
        });
        setShowEditModal(true);
    };

    const resetForm = () => {
        setFormData({
            name: '',
            email: '',
            plan: 'free',
            status: 'active',
            settings: {
                max_services: 10,
                max_users: 5,
                data_retention_days: 30,
                features: []
            }
        });
    };

    const toggleFeature = (feature) => {
        setFormData(prev => ({
            ...prev,
            settings: {
                ...prev.settings,
                features: prev.settings.features.includes(feature)
                    ? prev.settings.features.filter(f => f !== feature)
                    : [...prev.settings.features, feature]
            }
        }));
    };

    const getStatusIcon = (status) => {
        switch (status) {
            case 'active':
                return <CheckCircle size={14} className="status-icon--active" />;
            case 'inactive':
                return <XCircle size={14} className="status-icon--inactive" />;
            case 'suspended':
                return <AlertTriangle size={14} className="status-icon--suspended" />;
            default:
                return <Activity size={14} className="status-icon--pending" />;
        }
    };

    const getPlanBadge = (plan) => {
        const colors = {
            free: 'plan-badge--free',
            starter: 'plan-badge--starter',
            professional: 'plan-badge--pro',
            enterprise: 'plan-badge--enterprise'
        };
        return <span className={`plan-badge ${colors[plan] || ''}`}>{plan}</span>;
    };

    const filteredTenants = tenants.filter(tenant =>
        tenant.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tenant.email?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    if (authLoading) {
        return (
            <div className="page-loading">
                <div className="spinner"></div>
                <p>Loading...</p>
            </div>
        );
    }

    if (!isAuthenticated) {
        return (
            <div className="auth-required">
                <h2 className="display-title display-md">ACCESS REQUIRED</h2>
                <p>Please sign in to access admin panel.</p>
                <Link href="/login" className="btn btn-primary">Sign In</Link>
            </div>
        );
    }

    if (!isAdminUser) {
        return (
            <div className="auth-required">
                <h2 className="display-title display-md">ADMIN ONLY</h2>
                <p>You do not have permission to access the admin panel.</p>
                <Link href="/dashboard" className="btn btn-primary">Go to Dashboard</Link>
            </div>
        );
    }

    return (
        <>
            <Navbar />
            <div className="dashboard-page">
                <div className="dashboard-content">
                    <div className="dashboard-header">
                        <div>
                            <span className="tape-label">
                                <Shield size={12} /> Admin Panel
                            </span>
                            <h1 className="display-title display-md" style={{ marginTop: '0.5rem' }}>
                                TENANT MANAGEMENT
                            </h1>
                        </div>
                        <div className="dashboard-header__actions">
                            <button onClick={() => setShowCreateModal(true)} className="btn btn-primary">
                                <Plus size={16} />
                                New Tenant
                            </button>
                            <button onClick={fetchTenants} className="btn btn-secondary" disabled={loading}>
                                <RefreshCw size={16} className={loading ? 'spinning' : ''} />
                                Refresh
                            </button>
                        </div>
                    </div>

                {error && (
                    <div className="dashboard-error">
                        {error}
                    </div>
                )}

                {success && (
                    <div className="dashboard-success">
                        <CheckCircle size={16} />
                        {success}
                    </div>
                )}

                {/* Stats Summary */}
                <div className="admin-stats">
                    <div className="admin-stat">
                        <Building2 size={20} />
                        <span className="admin-stat__value">{tenants.length}</span>
                        <span className="admin-stat__label">Total Tenants</span>
                    </div>
                    <div className="admin-stat">
                        <CheckCircle size={20} />
                        <span className="admin-stat__value">{tenants.filter(t => t.status === 'active').length}</span>
                        <span className="admin-stat__label">Active</span>
                    </div>
                    <div className="admin-stat">
                        <Users size={20} />
                        <span className="admin-stat__value">{tenants.reduce((acc, t) => acc + (t.user_count || 0), 0)}</span>
                        <span className="admin-stat__label">Total Users</span>
                    </div>
                    <div className="admin-stat">
                        <Activity size={20} />
                        <span className="admin-stat__value">{tenants.reduce((acc, t) => acc + (t.service_count || 0), 0)}</span>
                        <span className="admin-stat__label">Services</span>
                    </div>
                </div>

                {/* Search */}
                <div className="admin-search">
                    <Search size={18} />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search tenants by name or email..."
                    />
                </div>

                {/* Tenants List */}
                {loading ? (
                    <div className="loading-state">
                        <div className="spinner"></div>
                        <p>Loading tenants...</p>
                    </div>
                ) : filteredTenants.length > 0 ? (
                    <div className="tenants-list">
                        {filteredTenants.map(tenant => (
                            <div key={tenant.id} className="tenant-card">
                                <div
                                    className="tenant-card__header"
                                    onClick={() => setExpandedTenant(
                                        expandedTenant === tenant.id ? null : tenant.id
                                    )}
                                >
                                    <div className="tenant-card__info">
                                        <Building2 size={20} />
                                        <div>
                                            <h3>{tenant.name}</h3>
                                            <span className="tenant-email">{tenant.email}</span>
                                        </div>
                                    </div>
                                    <div className="tenant-card__meta">
                                        {getPlanBadge(tenant.plan)}
                                        <span className={`status-badge status-badge--${tenant.status}`}>
                                            {getStatusIcon(tenant.status)}
                                            {tenant.status}
                                        </span>
                                        {expandedTenant === tenant.id ? (
                                            <ChevronUp size={18} />
                                        ) : (
                                            <ChevronDown size={18} />
                                        )}
                                    </div>
                                </div>

                                {expandedTenant === tenant.id && (
                                    <div className="tenant-card__details">
                                        <div className="tenant-details-grid">
                                            <div className="tenant-detail">
                                                <span className="detail-label">Tenant ID</span>
                                                <code className="detail-value">{tenant.id}</code>
                                            </div>
                                            <div className="tenant-detail">
                                                <span className="detail-label">Created</span>
                                                <span className="detail-value">
                                                    {tenant.created_at ? new Date(tenant.created_at).toLocaleDateString() : 'N/A'}
                                                </span>
                                            </div>
                                            <div className="tenant-detail">
                                                <span className="detail-label">Users</span>
                                                <span className="detail-value">{tenant.user_count || 0} / {tenant.settings?.max_users || 5}</span>
                                            </div>
                                            <div className="tenant-detail">
                                                <span className="detail-label">Services</span>
                                                <span className="detail-value">{tenant.service_count || 0} / {tenant.settings?.max_services || 10}</span>
                                            </div>
                                            <div className="tenant-detail">
                                                <span className="detail-label">Data Retention</span>
                                                <span className="detail-value">{tenant.settings?.data_retention_days || 30} days</span>
                                            </div>
                                            <div className="tenant-detail">
                                                <span className="detail-label">Last Active</span>
                                                <span className="detail-value">
                                                    {tenant.last_active_at ? new Date(tenant.last_active_at).toLocaleString() : 'Never'}
                                                </span>
                                            </div>
                                        </div>

                                        {tenant.settings?.features?.length > 0 && (
                                            <div className="tenant-features">
                                                <span className="detail-label">Enabled Features</span>
                                                <div className="features-tags">
                                                    {tenant.settings.features.map((feature, idx) => (
                                                        <span key={idx} className="feature-tag">{feature.replace(/_/g, ' ')}</span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        <div className="tenant-card__actions">
                                            <button
                                                onClick={() => openEditModal(tenant)}
                                                className="btn btn-secondary"
                                            >
                                                <Edit size={14} />
                                                Edit
                                            </button>
                                            <button
                                                onClick={() => handleDeleteTenant(tenant)}
                                                className="btn btn-danger"
                                                disabled={actionLoading === `delete-${tenant.id}`}
                                            >
                                                <Trash2 size={14} />
                                                {actionLoading === `delete-${tenant.id}` ? 'Deleting...' : 'Delete'}
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="empty-state">
                        <Building2 size={48} />
                        <h3>No Tenants Found</h3>
                        <p>{searchQuery ? 'Try a different search term.' : 'Create your first tenant to get started.'}</p>
                        <button onClick={() => setShowCreateModal(true)} className="btn btn-primary">
                            <Plus size={16} />
                            Create Tenant
                        </button>
                    </div>
                )}
            </div>

            {/* Create Modal */}
            {showCreateModal && (
                <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <div className="modal__header">
                            <h2>Create New Tenant</h2>
                            <button onClick={() => setShowCreateModal(false)} className="modal__close">×</button>
                        </div>
                        <form onSubmit={handleCreateTenant} className="modal__body">
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Tenant Name *</label>
                                    <input
                                        type="text"
                                        value={formData.name}
                                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                        placeholder="Company or Organization Name"
                                        required
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Email *</label>
                                    <input
                                        type="email"
                                        value={formData.email}
                                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                        placeholder="admin@example.com"
                                        required
                                    />
                                </div>
                            </div>

                            <div className="form-row">
                                <div className="form-group">
                                    <label>Plan</label>
                                    <select
                                        value={formData.plan}
                                        onChange={(e) => setFormData({ ...formData, plan: e.target.value })}
                                    >
                                        {plans.map(plan => (
                                            <option key={plan} value={plan}>{plan.charAt(0).toUpperCase() + plan.slice(1)}</option>
                                        ))}
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Status</label>
                                    <select
                                        value={formData.status}
                                        onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                                    >
                                        {statuses.map(status => (
                                            <option key={status} value={status}>{status.charAt(0).toUpperCase() + status.slice(1)}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            <div className="form-section">
                                <h4>Limits</h4>
                                <div className="form-row form-row--thirds">
                                    <div className="form-group">
                                        <label>Max Services</label>
                                        <input
                                            type="number"
                                            value={formData.settings.max_services}
                                            onChange={(e) => setFormData({
                                                ...formData,
                                                settings: { ...formData.settings, max_services: parseInt(e.target.value) }
                                            })}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Max Users</label>
                                        <input
                                            type="number"
                                            value={formData.settings.max_users}
                                            onChange={(e) => setFormData({
                                                ...formData,
                                                settings: { ...formData.settings, max_users: parseInt(e.target.value) }
                                            })}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Data Retention (days)</label>
                                        <input
                                            type="number"
                                            value={formData.settings.data_retention_days}
                                            onChange={(e) => setFormData({
                                                ...formData,
                                                settings: { ...formData.settings, data_retention_days: parseInt(e.target.value) }
                                            })}
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="form-section">
                                <h4>Features</h4>
                                <div className="features-checkbox-grid">
                                    {featureOptions.map(feature => (
                                        <label key={feature} className="checkbox-label">
                                            <input
                                                type="checkbox"
                                                checked={formData.settings.features.includes(feature)}
                                                onChange={() => toggleFeature(feature)}
                                            />
                                            <span>{feature.replace(/_/g, ' ')}</span>
                                        </label>
                                    ))}
                                </div>
                            </div>

                            <div className="modal__footer">
                                <button type="button" onClick={() => setShowCreateModal(false)} className="btn btn-secondary">
                                    Cancel
                                </button>
                                <button type="submit" className="btn btn-primary" disabled={actionLoading === 'create'}>
                                    <Plus size={16} />
                                    {actionLoading === 'create' ? 'Creating...' : 'Create Tenant'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Edit Modal */}
            {showEditModal && selectedTenant && (
                <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <div className="modal__header">
                            <h2>Edit Tenant</h2>
                            <button onClick={() => setShowEditModal(false)} className="modal__close">×</button>
                        </div>
                        <form onSubmit={handleUpdateTenant} className="modal__body">
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Tenant Name *</label>
                                    <input
                                        type="text"
                                        value={formData.name}
                                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                        required
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Email *</label>
                                    <input
                                        type="email"
                                        value={formData.email}
                                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                        required
                                    />
                                </div>
                            </div>

                            <div className="form-row">
                                <div className="form-group">
                                    <label>Plan</label>
                                    <select
                                        value={formData.plan}
                                        onChange={(e) => setFormData({ ...formData, plan: e.target.value })}
                                    >
                                        {plans.map(plan => (
                                            <option key={plan} value={plan}>{plan.charAt(0).toUpperCase() + plan.slice(1)}</option>
                                        ))}
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Status</label>
                                    <select
                                        value={formData.status}
                                        onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                                    >
                                        {statuses.map(status => (
                                            <option key={status} value={status}>{status.charAt(0).toUpperCase() + status.slice(1)}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            <div className="form-section">
                                <h4>Limits</h4>
                                <div className="form-row form-row--thirds">
                                    <div className="form-group">
                                        <label>Max Services</label>
                                        <input
                                            type="number"
                                            value={formData.settings.max_services}
                                            onChange={(e) => setFormData({
                                                ...formData,
                                                settings: { ...formData.settings, max_services: parseInt(e.target.value) }
                                            })}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Max Users</label>
                                        <input
                                            type="number"
                                            value={formData.settings.max_users}
                                            onChange={(e) => setFormData({
                                                ...formData,
                                                settings: { ...formData.settings, max_users: parseInt(e.target.value) }
                                            })}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Data Retention (days)</label>
                                        <input
                                            type="number"
                                            value={formData.settings.data_retention_days}
                                            onChange={(e) => setFormData({
                                                ...formData,
                                                settings: { ...formData.settings, data_retention_days: parseInt(e.target.value) }
                                            })}
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="form-section">
                                <h4>Features</h4>
                                <div className="features-checkbox-grid">
                                    {featureOptions.map(feature => (
                                        <label key={feature} className="checkbox-label">
                                            <input
                                                type="checkbox"
                                                checked={formData.settings.features.includes(feature)}
                                                onChange={() => toggleFeature(feature)}
                                            />
                                            <span>{feature.replace(/_/g, ' ')}</span>
                                        </label>
                                    ))}
                                </div>
                            </div>

                            <div className="modal__footer">
                                <button type="button" onClick={() => setShowEditModal(false)} className="btn btn-secondary">
                                    Cancel
                                </button>
                                <button type="submit" className="btn btn-primary" disabled={actionLoading === 'update'}>
                                    <Edit size={16} />
                                    {actionLoading === 'update' ? 'Saving...' : 'Save Changes'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
        </>
    );
}
