'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { useAuth } from '@/lib/auth-context';
import { apiClient } from '@/lib/api-client';

export default function ProfilePage() {
    const router = useRouter();
    const { user, isAuthenticated, loading: authLoading, updateProfile } = useAuth();

    const [fullName, setFullName] = useState('');
    const [phoneNumber, setPhoneNumber] = useState('');
    const [linkedinUrl, setLinkedinUrl] = useState('');
    const [bio, setBio] = useState('');
    const [picture, setPicture] = useState('');

    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');

    const [installUrl, setInstallUrl] = useState('');
    const [githubInstallations, setGithubInstallations] = useState([]);
    const [githubLoading, setGithubLoading] = useState(false);

    const [installationIdInput, setInstallationIdInput] = useState('');
    const [accountLoginInput, setAccountLoginInput] = useState('');
    const [accountTypeInput, setAccountTypeInput] = useState('User');

    const hasGithubConnected = useMemo(() => githubInstallations.length > 0, [githubInstallations]);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push('/login');
            return;
        }

        if (isAuthenticated) {
            setFullName(user?.full_name || user?.name || '');
            setPhoneNumber(user?.phone_number || '');
            setLinkedinUrl(user?.linkedin_url || '');
            setBio(user?.bio || '');
            setPicture(user?.picture || '');
            refreshGithubData();
        }
    }, [authLoading, isAuthenticated, user, router]);

    useEffect(() => {
        if (typeof window === 'undefined' || authLoading || !isAuthenticated) {
            return;
        }

        const params = new URLSearchParams(window.location.search);
        const installationId = params.get('installation_id');
        const setupAction = params.get('setup_action');

        if (!installationId) {
            return;
        }

        if (setupAction && setupAction !== 'install' && setupAction !== 'update') {
            return;
        }

        const autoLink = async () => {
            setGithubLoading(true);
            setError('');
            try {
                await apiClient.autoLinkGithubInstallation(installationId);
                setMessage('GitHub installation linked successfully.');
                await refreshGithubData();
                router.replace('/profile');
            } catch (err) {
                setError(err.message || 'Failed to auto-link GitHub installation.');
            } finally {
                setGithubLoading(false);
            }
        };

        autoLink();
    }, [authLoading, isAuthenticated, router]);

    const refreshGithubData = async () => {
        setGithubLoading(true);
        try {
            const [installUrlData, installationsData] = await Promise.all([
                apiClient.getGithubInstallUrl(),
                apiClient.listGithubInstallations(),
            ]);
            setInstallUrl(installUrlData?.install_url || '');
            setGithubInstallations(installationsData || []);
        } catch (err) {
            setError(err.message || 'Failed to load GitHub connection status');
        } finally {
            setGithubLoading(false);
        }
    };

    const onPickImage = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;

        if (!file.type.startsWith('image/')) {
            setError('Please select a valid image file.');
            return;
        }

        if (file.size > 2 * 1024 * 1024) {
            setError('Profile picture must be under 2 MB.');
            return;
        }

        const reader = new FileReader();
        reader.onload = () => setPicture(String(reader.result || ''));
        reader.onerror = () => setError('Failed to read selected image file.');
        reader.readAsDataURL(file);
    };

    const onSaveProfile = async (event) => {
        event.preventDefault();
        setSaving(true);
        setError('');
        setMessage('');

        try {
            await updateProfile({
                full_name: fullName,
                phone_number: phoneNumber,
                linkedin_url: linkedinUrl,
                bio,
                picture,
            });
            setMessage('Profile updated successfully.');
        } catch (err) {
            setError(err.message || 'Failed to update profile.');
        } finally {
            setSaving(false);
        }
    };

    const onConnectGithub = () => {
        if (!installUrl) {
            setError('GitHub install URL is not available yet.');
            return;
        }
        window.open(installUrl, '_blank', 'noopener,noreferrer');
    };

    const onLinkInstallation = async () => {
        if (!installationIdInput.trim() || !accountLoginInput.trim()) {
            setError('Enter installation ID and account login first.');
            return;
        }

        setGithubLoading(true);
        setError('');
        setMessage('');
        try {
            await apiClient.upsertGithubInstallation({
                github_installation_id: installationIdInput.trim(),
                account_login: accountLoginInput.trim(),
                account_type: accountTypeInput.trim() || 'User',
            });
            setMessage('GitHub account linked successfully.');
            setInstallationIdInput('');
            setAccountLoginInput('');
            await refreshGithubData();
        } catch (err) {
            setError(err.message || 'Failed to link GitHub installation.');
        } finally {
            setGithubLoading(false);
        }
    };

    if (authLoading) {
        return (
            <>
                <Navbar />
                <div className="page-loading"><div className="spinner" /><p>Loading...</p></div>
            </>
        );
    }

    if (!isAuthenticated) {
        return (
            <>
                <Navbar />
                <div className="auth-required">
                    <h2 className="display-title display-md">ACCESS REQUIRED</h2>
                    <p>Please sign in to manage your profile.</p>
                    <Link href="/login" className="btn btn-primary">Sign In</Link>
                </div>
            </>
        );
    }

    return (
        <>
            <Navbar />
            <div className="dashboard-page" style={{ padding: '2rem' }}>
                <h1 className="display-title display-md">Profile</h1>
                <p style={{ marginBottom: '1rem' }}>
                    Manage account details and GitHub connection for System-Architecture features.
                </p>

                {error && <div className="dashboard-error">{error}</div>}
                {message && <div className="dashboard-success">{message}</div>}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                    <form onSubmit={onSaveProfile} style={{ border: '1px solid #ccc', padding: '1rem' }}>
                        <h3>Profile Details</h3>

                        <label>Full Name</label>
                        <input
                            type="text"
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                            placeholder="Your full name"
                            style={{ width: '100%', padding: '0.5rem', marginBottom: '0.5rem' }}
                        />

                        <label>Phone No. (optional)</label>
                        <input
                            type="text"
                            value={phoneNumber}
                            onChange={(e) => setPhoneNumber(e.target.value)}
                            placeholder="+1 555 123 4567"
                            style={{ width: '100%', padding: '0.5rem', marginBottom: '0.5rem' }}
                        />

                        <label>LinkedIn URL (optional)</label>
                        <input
                            type="url"
                            value={linkedinUrl}
                            onChange={(e) => setLinkedinUrl(e.target.value)}
                            placeholder="https://www.linkedin.com/in/your-profile"
                            style={{ width: '100%', padding: '0.5rem', marginBottom: '0.5rem' }}
                        />

                        <label>Bio (optional)</label>
                        <textarea
                            value={bio}
                            onChange={(e) => setBio(e.target.value)}
                            rows={4}
                            placeholder="Tell us about your role and focus"
                            style={{ width: '100%', padding: '0.5rem', marginBottom: '0.5rem' }}
                        />

                        <label>Profile Picture URL (optional)</label>
                        <input
                            type="url"
                            value={picture}
                            onChange={(e) => setPicture(e.target.value)}
                            placeholder="https://example.com/avatar.png"
                            style={{ width: '100%', padding: '0.5rem', marginBottom: '0.5rem' }}
                        />

                        <label>Or upload profile picture (optional)</label>
                        <input
                            type="file"
                            accept="image/*"
                            onChange={onPickImage}
                            style={{ width: '100%', marginBottom: '0.75rem' }}
                        />

                        {picture && (
                            <div style={{ marginBottom: '0.75rem' }}>
                                <img
                                    src={picture}
                                    alt="Profile preview"
                                    style={{ width: '72px', height: '72px', objectFit: 'cover', borderRadius: '999px', border: '1px solid #ddd' }}
                                />
                            </div>
                        )}

                        <button type="submit" className="btn btn-primary" disabled={saving}>
                            {saving ? 'Saving...' : 'Save Profile'}
                        </button>
                    </form>

                    <div style={{ border: '1px solid #ccc', padding: '1rem' }}>
                        <h3>GitHub Connection</h3>
                        <p style={{ marginBottom: '0.5rem' }}>
                            Status: {hasGithubConnected ? 'Connected' : 'Not connected'}
                        </p>

                        <button className="btn btn-secondary" onClick={onConnectGithub} disabled={githubLoading || !installUrl}>
                            Connect GitHub Account
                        </button>
                        <button className="btn btn-secondary" onClick={refreshGithubData} disabled={githubLoading} style={{ marginLeft: '0.5rem' }}>
                            Refresh
                        </button>

                        <div style={{ marginTop: '1rem', borderTop: '1px solid #eee', paddingTop: '1rem' }}>
                            <h4>Link Installation (manual)</h4>
                            <p style={{ color: '#555', marginBottom: '0.5rem' }}>
                                After app installation, paste installation details to link this account.
                            </p>
                            <input
                                type="text"
                                value={installationIdInput}
                                onChange={(e) => setInstallationIdInput(e.target.value)}
                                placeholder="GitHub installation ID"
                                style={{ width: '100%', padding: '0.5rem', marginBottom: '0.5rem' }}
                            />
                            <input
                                type="text"
                                value={accountLoginInput}
                                onChange={(e) => setAccountLoginInput(e.target.value)}
                                placeholder="GitHub account login (org/user)"
                                style={{ width: '100%', padding: '0.5rem', marginBottom: '0.5rem' }}
                            />
                            <input
                                type="text"
                                value={accountTypeInput}
                                onChange={(e) => setAccountTypeInput(e.target.value)}
                                placeholder="Account type (User/Organization)"
                                style={{ width: '100%', padding: '0.5rem', marginBottom: '0.5rem' }}
                            />
                            <button className="btn btn-primary" onClick={onLinkInstallation} disabled={githubLoading}>
                                Save GitHub Connection
                            </button>
                        </div>

                        <div style={{ marginTop: '1rem', borderTop: '1px solid #eee', paddingTop: '1rem' }}>
                            <h4>Connected Installations</h4>
                            {!githubInstallations.length ? (
                                <p style={{ color: '#a40000' }}>No GitHub account connected yet.</p>
                            ) : (
                                <div style={{ display: 'grid', gap: '0.5rem' }}>
                                    {githubInstallations.map((installation) => (
                                        <div key={installation.id} style={{ border: '1px solid #ddd', padding: '0.5rem' }}>
                                            <div><strong>{installation.account_login}</strong> ({installation.account_type || 'Unknown'})</div>
                                            <div style={{ color: '#555' }}>Installation ID: {installation.github_installation_id}</div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}
