const DEFAULT_ADMIN_EMAIL = 'kashifalikhan093@gmail.com';

function normalizeEmail(value) {
    return String(value || '').trim().toLowerCase();
}

export function getConfiguredAdminEmail() {
    return normalizeEmail(
        process.env.NEXT_PUBLIC_ENV_VAR_USER ||
        process.env.NEXT_PUBLIC_ADMIN_EMAIL ||
        process.env.ENV_VAR_USER ||
        process.env.ADMIN_EMAIL ||
        DEFAULT_ADMIN_EMAIL
    );
}

export function isAdminUserEmail(email) {
    const configured = getConfiguredAdminEmail();
    const candidate = normalizeEmail(email);
    return Boolean(configured && candidate && configured === candidate);
}
