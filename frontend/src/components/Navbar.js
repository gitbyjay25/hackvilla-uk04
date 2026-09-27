'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { isAdminUserEmail } from '@/lib/admin-access';
import { User, LogOut, Key } from 'lucide-react';

export default function Navbar() {
    const router = useRouter();
    const pathname = usePathname();
    const { user, isAuthenticated, logout, loading } = useAuth();
    const isAdminUser = isAdminUserEmail(user?.email);

    const handleLogout = async () => {
        await logout();
        router.push('/');
    };

    return (
        <nav className="navbar">
            <Link href="/" className="navbar__logo">NEXARCH</Link>

            <div className="navbar__links">
                {pathname === '/' && (
                    <Link href="/#features" className="navbar__link">Features</Link>
                )}
                <Link href="/sdk-docs" className="navbar__link">SDK Docs</Link>
                {isAuthenticated && (
                    <Link href="/dashboard" className="navbar__link">Dashboard</Link>
                )}
                {isAuthenticated && (
                    <Link href="/system-architecture" className="navbar__link">System-Architecture</Link>
                )}
                {isAuthenticated && (
                    <Link href="/api-keys" className="navbar__link flex items-center gap-1">
                        <Key size={14} />
                        API Keys
                    </Link>
                )}
                {isAuthenticated && (
                    <Link href="/alpha-code" className="navbar__link">Alpha-Code</Link>
                )}
                {isAuthenticated && isAdminUser && (
                    <Link href="/settings" className="navbar__link">Settings</Link>
                )}
                {isAuthenticated && isAdminUser && (
                    <Link href="/admin" className="navbar__link">Admin</Link>
                )}
                {isAuthenticated && (
                    <Link href="/profile" className="navbar__link">Profile</Link>
                )}

                {loading ? (
                    <span className="navbar__loading">...</span>
                ) : isAuthenticated ? (
                    <div className="navbar__user">
                        <span className="navbar__user-name">
                            <User size={16} />
                            {user?.full_name || user?.email || 'User'}
                        </span>
                        <button onClick={handleLogout} className="btn btn-secondary navbar__logout">
                            <LogOut size={14} />
                            Logout
                        </button>
                    </div>
                ) : (
                    <>
                        <Link href="/login" className="navbar__link">Login</Link>
                        <Link href="/signup" className="btn btn-primary navbar__cta">
                            Get Started
                        </Link>
                    </>
                )}
            </div>
        </nav>
    );
}
