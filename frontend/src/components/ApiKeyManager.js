'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api-client';
import { Key, Copy, Trash2, Plus, CheckCircle, AlertCircle } from 'lucide-react';

export default function ApiKeyManager() {
    const [apiKeys, setApiKeys] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const [showNewKeyDialog, setShowNewKeyDialog] = useState(false);
    const [newKeyName, setNewKeyName] = useState('');
    const [newKey, setNewKey] = useState(null);
    const [copiedKey, setCopiedKey] = useState(null);

    useEffect(() => {
        fetchApiKeys();
    }, []);

    const fetchApiKeys = async () => {
        setLoading(true);
        setError(null);
        try {
            const keys = await apiClient.listApiKeys();
            setApiKeys(keys);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateKey = async (e) => {
        e.preventDefault();
        if (!newKeyName.trim()) {
            setError('Please enter a name for the API key');
            return;
        }

        setLoading(true);
        setError(null);
        try {
            const keyData = await apiClient.generateApiKey(newKeyName);
            setNewKey(keyData.key);
            setSuccess(`API key "${newKeyName}" created successfully`);
            setNewKeyName('');
            fetchApiKeys();
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleCopyKey = (key) => {
        navigator.clipboard.writeText(key);
        setCopiedKey(key);
        setTimeout(() => setCopiedKey(null), 2000);
    };

    const handleRevokeKey = async (keyPreview) => {
        if (!confirm('Are you sure you want to revoke this API key? This action cannot be undone.')) {
            return;
        }

        setLoading(true);
        setError(null);
        try {
            await apiClient.revokeApiKey(keyPreview);
            setSuccess('API key revoked successfully');
            fetchApiKeys();
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const closeNewKeyDialog = () => {
        setShowNewKeyDialog(false);
        setNewKey(null);
        setSuccess(null);
    };

    if (loading && apiKeys.length === 0) {
        return (
            <div className="loading-state">
                <div className="spinner"></div>
                <p>Loading API keys...</p>
            </div>
        );
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                    <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                        <Key size={20} />
                        Your API Keys
                    </h2>
                    <p style={{ color: 'var(--color-gray)', fontSize: '0.875rem' }}>
                        Create and manage API keys for SDK authentication
                    </p>
                </div>
                <button
                    onClick={() => setShowNewKeyDialog(true)}
                    className="btn btn-primary"
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                >
                    <Plus size={16} />
                    Generate New Key
                </button>
            </div>

            {/* Alerts */}
            {error && (
                <div className="dashboard-error" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <AlertCircle size={20} />
                    <span>{error}</span>
                </div>
            )}

            {success && !newKey && (
                <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '0.5rem', 
                    padding: '1rem',
                    backgroundColor: '#d4edda',
                    border: '2px solid #28a745',
                    color: '#155724'
                }}>
                    <CheckCircle size={20} />
                    <span>{success}</span>
                </div>
            )}

            {/* New Key Dialog */}
            {showNewKeyDialog && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0, 0, 0, 0.5)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 1000
                }}>
                    <div style={{
                        backgroundColor: 'var(--color-cream)',
                        padding: '2rem',
                        maxWidth: '500px',
                        width: '90%',
                        border: '2px solid var(--color-black)'
                    }}>
                        {!newKey ? (
                            <>
                                <h3 className="section-title" style={{ marginBottom: '1.5rem' }}>Generate API Key</h3>
                                <form onSubmit={handleCreateKey} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                                    <div>
                                        <label style={{ 
                                            display: 'block', 
                                            fontSize: '0.875rem', 
                                            fontWeight: 500, 
                                            marginBottom: '0.5rem'
                                        }}>
                                            Key Name
                                        </label>
                                        <input
                                            type="text"
                                            value={newKeyName}
                                            onChange={(e) => setNewKeyName(e.target.value)}
                                            placeholder="e.g., Production SDK, Development"
                                            style={{
                                                width: '100%',
                                                padding: '0.75rem',
                                                border: '2px solid var(--color-black)',
                                                backgroundColor: 'white',
                                                fontSize: '0.875rem'
                                            }}
                                            required
                                        />
                                    </div>
                                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                                        <button
                                            type="button"
                                            onClick={() => setShowNewKeyDialog(false)}
                                            className="btn btn-secondary"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            type="submit"
                                            disabled={loading}
                                            className="btn btn-primary"
                                        >
                                            {loading ? 'Generating...' : 'Generate'}
                                        </button>
                                    </div>
                                </form>
                            </>
                        ) : (
                            <>
                                <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
                                    <div style={{
                                        width: '60px',
                                        height: '60px',
                                        margin: '0 auto 1rem',
                                        backgroundColor: '#d4edda',
                                        borderRadius: '50%',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center'
                                    }}>
                                        <CheckCircle size={30} style={{ color: '#28a745' }} />
                                    </div>
                                    <h3 className="section-title" style={{ marginBottom: '0.5rem' }}>API Key Generated!</h3>
                                    <p style={{ color: 'var(--color-gray)', fontSize: '0.875rem' }}>
                                        Copy this key now - it won't be shown again
                                    </p>
                                </div>
                                <div style={{ position: 'relative', marginBottom: '1.5rem' }}>
                                    <input
                                        type="text"
                                        value={newKey}
                                        readOnly
                                        style={{
                                            width: '100%',
                                            padding: '0.75rem',
                                            paddingRight: '3rem',
                                            border: '2px solid var(--color-black)',
                                            backgroundColor: '#f8f9fa',
                                            fontFamily: 'monospace',
                                            fontSize: '0.8rem'
                                        }}
                                    />
                                    <button
                                        onClick={() => handleCopyKey(newKey)}
                                        style={{
                                            position: 'absolute',
                                            right: '0.5rem',
                                            top: '50%',
                                            transform: 'translateY(-50%)',
                                            padding: '0.5rem',
                                            border: 'none',
                                            background: 'transparent',
                                            cursor: 'pointer'
                                        }}
                                    >
                                        {copiedKey === newKey ? (
                                            <CheckCircle size={20} style={{ color: '#28a745' }} />
                                        ) : (
                                            <Copy size={20} style={{ color: 'var(--color-gray)' }} />
                                        )}
                                    </button>
                                </div>
                                <button
                                    onClick={closeNewKeyDialog}
                                    className="btn btn-primary"
                                    style={{ width: '100%' }}
                                >
                                    Done
                                </button>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* API Keys List */}
            <div style={{
                backgroundColor: 'white',
                border: '2px solid var(--color-black)',
                overflow: 'hidden'
            }}>
                {apiKeys.length === 0 ? (
                    <div style={{ 
                        padding: '3rem 2rem', 
                        textAlign: 'center',
                        color: 'var(--color-gray)'
                    }}>
                        <Key size={48} style={{ margin: '0 auto 1rem', opacity: 0.5 }} />
                        <p style={{ fontSize: '1.125rem', fontWeight: 500, marginBottom: '0.5rem' }}>No API keys yet</p>
                        <p style={{ fontSize: '0.875rem' }}>Generate your first API key to start using the SDK</p>
                    </div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '2px solid var(--color-black)' }}>
                                <th style={{ padding: '0.75rem 1.5rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                    Name
                                </th>
                                <th style={{ padding: '0.75rem 1.5rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                    Key
                                </th>
                                <th style={{ padding: '0.75rem 1.5rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                    Created
                                </th>
                                <th style={{ padding: '0.75rem 1.5rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                    Last Used
                                </th>
                                <th style={{ padding: '0.75rem 1.5rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                    Status
                                </th>
                                <th style={{ padding: '0.75rem 1.5rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                    Actions
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {apiKeys.map((key, index) => (
                                <tr 
                                    key={index} 
                                    style={{ 
                                        borderBottom: '1px solid #dee2e6',
                                        backgroundColor: !key.is_active ? '#f8f9fa' : 'white',
                                        opacity: !key.is_active ? 0.6 : 1
                                    }}
                                >
                                    <td style={{ padding: '1rem 1.5rem' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            <Key size={16} style={{ color: 'var(--color-gray)' }} />
                                            <span style={{ fontWeight: 500 }}>{key.name}</span>
                                        </div>
                                    </td>
                                    <td style={{ padding: '1rem 1.5rem' }}>
                                        <code style={{ 
                                            fontFamily: 'monospace', 
                                            fontSize: '0.8rem',
                                            backgroundColor: '#f8f9fa',
                                            padding: '0.25rem 0.5rem',
                                            border: '1px solid #dee2e6'
                                        }}>
                                            {key.key_preview}
                                        </code>
                                    </td>
                                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem', color: 'var(--color-gray)' }}>
                                        {new Date(key.created_at).toLocaleDateString()}
                                    </td>
                                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem', color: 'var(--color-gray)' }}>
                                        {key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never'}
                                    </td>
                                    <td style={{ padding: '1rem 1.5rem' }}>
                                        <span style={{
                                            padding: '0.25rem 0.75rem',
                                            fontSize: '0.75rem',
                                            fontWeight: 600,
                                            backgroundColor: key.is_active ? '#d4edda' : '#f8d7da',
                                            color: key.is_active ? '#155724' : '#721c24',
                                            textTransform: 'uppercase',
                                            letterSpacing: '0.05em'
                                        }}>
                                            {key.is_active ? 'Active' : 'Revoked'}
                                        </span>
                                    </td>
                                    <td style={{ padding: '1rem 1.5rem' }}>
                                        {key.is_active && (
                                            <button
                                                onClick={() => handleRevokeKey(key.key_preview)}
                                                className="btn btn-secondary"
                                                style={{ 
                                                    display: 'flex', 
                                                    alignItems: 'center', 
                                                    gap: '0.5rem',
                                                    fontSize: '0.75rem',
                                                    padding: '0.375rem 0.75rem'
                                                }}
                                                title="Revoke this API key"
                                            >
                                                <Trash2 size={14} />
                                                Revoke
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Usage Instructions */}
            <div style={{
                backgroundColor: '#f8f9fa',
                border: '2px solid var(--color-black)',
                padding: '1.5rem'
            }}>
                <h3 className="section-title" style={{ marginBottom: '1rem', fontSize: '1rem' }}>
                    How to use your API key
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '0.875rem' }}>
                    <div>
                        <strong>1. Install the Nexarch SDK:</strong>
                        <pre style={{
                            backgroundColor: 'var(--color-black)',
                            color: 'var(--color-cream)',
                            padding: '0.75rem',
                            marginTop: '0.5rem',
                            overflow: 'auto',
                            fontFamily: 'monospace',
                            fontSize: '0.8rem'
                        }}>pip install nexarch-sdk</pre>
                    </div>
                    <div>
                        <strong>2. Initialize the client with your API key:</strong>
                        <pre style={{
                            backgroundColor: 'var(--color-black)',
                            color: 'var(--color-cream)',
                            padding: '0.75rem',
                            marginTop: '0.5rem',
                            overflow: 'auto',
                            fontFamily: 'monospace',
                            fontSize: '0.8rem'
                        }}>from nexarch import NexarchClient{'\n\n'}client = NexarchClient(api_key="your_api_key_here")</pre>
                    </div>
                    <div>
                        <strong>Security Best Practices:</strong>
                        <ul style={{ marginTop: '0.5rem', paddingLeft: '1.5rem' }}>
                            <li>Never commit API keys to version control</li>
                            <li>Use environment variables to store keys</li>
                            <li>Rotate keys regularly</li>
                            <li>Revoke compromised keys immediately</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    );
}
