'use client';

import { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '@/lib/api-client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [isAuthenticated, setIsAuthenticated] = useState(false);

    // Check authentication status on mount
    useEffect(() => {
        checkAuth();
    }, []);

    const checkAuth = async () => {
        setLoading(true);
        try {
            const token = apiClient.getToken();
            if (token) {
                try {
                    const userData = await apiClient.getCurrentUser();
                    setUser(userData);
                    setIsAuthenticated(true);
                    // Persist user so we can restore on network-error paths below
                    apiClient.setUser(userData);
                } catch (apiError) {
                    // 401 → token invalid, clear everything
                    if (apiError.message === 'Unauthorized') {
                        console.error('Token invalid, clearing auth');
                        apiClient.removeToken();
                        setUser(null);
                        setIsAuthenticated(false);
                    } else {
                        // Network error or other transient issue — try to restore from
                        // persisted user data so we never leave isAuthenticated=true with user=null
                        console.warn('Auth check had non-fatal error:', apiError.message);
                        const cachedUser = apiClient.getUser();
                        if (cachedUser) {
                            setUser(cachedUser);
                            setIsAuthenticated(true);
                        } else {
                            // No cached user — stay unauthenticated to avoid broken UI state
                            setUser(null);
                            setIsAuthenticated(false);
                        }
                    }
                }
            } else {
                // No token, not authenticated
                setUser(null);
                setIsAuthenticated(false);
            }
        } catch (error) {
            console.error('Auth check failed:', error);
        } finally {
            setLoading(false);
        }
    };

    const loginWithGoogle = async () => {
        try {
            const { auth_url } = await apiClient.getGoogleAuthUrl();
            window.location.href = auth_url;
        } catch (error) {
            console.error('Failed to get Google auth URL:', error);
            throw error;
        }
    };

    const loginWithEmail = async (email, password) => {
        try {
            await apiClient.login(email, password);
            // Fetch user first so isAuthenticated is never true while user is null
            try {
                const userData = await apiClient.getCurrentUser();
                setUser(userData);
                apiClient.setUser(userData);
            } catch (userError) {
                console.error('Failed to fetch user data after login:', userError);
                // Set a minimal user object so components don\'t crash
                setUser({ email });
            }
            setIsAuthenticated(true);
        } catch (error) {
            console.error('Email login failed:', error);
            setIsAuthenticated(false);
            throw error;
        }
    };

    const signupWithEmail = async (email, password, fullName) => {
        try {
            await apiClient.signup(email, password, fullName);
            // Fetch user first so isAuthenticated is never true while user is null
            try {
                const userData = await apiClient.getCurrentUser();
                setUser(userData);
                apiClient.setUser(userData);
            } catch (userError) {
                console.error('Failed to fetch user data after signup:', userError);
                setUser({ email, full_name: fullName });
            }
            setIsAuthenticated(true);
        } catch (error) {
            console.error('Email signup failed:', error);
            setIsAuthenticated(false);
            throw error;
        }
    };

    const handleCallback = async (code) => {
        try {
            const result = await apiClient.googleSignIn(code);
            setUser(result.user);
            setIsAuthenticated(true);
            return result;
        } catch (error) {
            console.error('Google sign in failed:', error);
            throw error;
        }
    };

    const logout = async () => {
        try {
            await apiClient.logout();
        } finally {
            setUser(null);
            setIsAuthenticated(false);
        }
    };

    const updateProfile = async (profile) => {
        const updatedUser = await apiClient.updateProfile(profile);
        setUser(updatedUser);
        apiClient.setUser(updatedUser);
        return updatedUser;
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                loading,
                isAuthenticated,
                loginWithGoogle,
                loginWithEmail,
                signupWithEmail,
                handleCallback,
                logout,
                updateProfile,
                checkAuth,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
