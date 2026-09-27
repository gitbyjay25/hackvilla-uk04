/**
 * Auth API methods
 * All authentication-related calls: email/password, Google OAuth, session.
 */

const PROD_API_URL = 'https://api.modelix.world';
const API_URL = (process.env.NEXT_PUBLIC_API_URL || PROD_API_URL).replace(/\/+$/, '');

// Token helpers (shared across modules via localStorage)
export const tokenStorage = {
    get: () => (typeof window !== 'undefined' ? localStorage.getItem('access_token') : null),
    set: (token) => typeof window !== 'undefined' && localStorage.setItem('access_token', token),
    remove: () => {
        if (typeof window !== 'undefined') {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user');
        }
    },
    setUser: (user) =>
        typeof window !== 'undefined' && localStorage.setItem('user', JSON.stringify(user)),
    getUser: () => {
        if (typeof window === 'undefined') return null;
        try {
            return JSON.parse(localStorage.getItem('user'));
        } catch {
            return null;
        }
    },
};

/**
 * Core fetch wrapper — used by all api modules.
 * Handles auth headers, 401 redirect, and JSON error parsing.
 */
export async function apiRequest(endpoint, options = {}) {
    const token = tokenStorage.get();
    const hasBody = options.body !== undefined && options.body !== null;

    const headers = {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
    };

    // Only set JSON content type when sending a body and caller didn't set one.
    if (hasBody && !headers['Content-Type'] && !headers['content-type']) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        mode: 'cors',
        headers,
    });

    if (response.status === 401 && token) {
        tokenStorage.remove();
        if (
            typeof window !== 'undefined' &&
            !window.location.pathname.startsWith('/login') &&
            !window.location.pathname.startsWith('/signup') &&
            !window.location.pathname.startsWith('/auth')
        ) {
            window.location.href = '/login';
        }
        throw new Error('Unauthorized');
    }

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || response.statusText);
    }

    return response.json();
}

// ── Auth endpoints ──────────────────────────────────────────────────────────

export async function signup(email, password, fullName = null) {
    const result = await apiRequest('/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ email, password, full_name: fullName }),
    });
    if (result.access_token) tokenStorage.set(result.access_token);
    return result;
}

export async function login(email, password) {
    const result = await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
    });
    if (result.access_token) tokenStorage.set(result.access_token);
    return result;
}

export async function getGoogleAuthUrl() {
    return apiRequest('/auth/google');
}

export async function googleSignIn(code, state = null) {
    const result = await apiRequest('/auth/google/signin', {
        method: 'POST',
        body: JSON.stringify({ code, state }),
    });
    if (result.access_token) {
        tokenStorage.set(result.access_token);
        if (result.user) tokenStorage.setUser(result.user);
    }
    return result;
}

export async function getCurrentUser() {
    return apiRequest('/auth/me');
}

export async function updateProfile(profile) {
    return apiRequest('/auth/profile', {
        method: 'PUT',
        body: JSON.stringify(profile),
    });
}

export async function getGoogleStatus() {
    return apiRequest('/auth/google/status');
}

export async function logout() {
    try {
        await apiRequest('/auth/logout', { method: 'POST' });
    } finally {
        tokenStorage.remove();
    }
}
