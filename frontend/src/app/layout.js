import { Inter } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/lib/auth-context';

const inter = Inter({
    subsets: ['latin'],
    variable: '--font-inter',
    display: 'swap',
});

export const metadata = {
    title: 'NEXARCH | Production Architecture Observability',
    description: 'Understand your production architecture automatically. Observe live request flows, service connections, and get AI-powered architecture design recommendations based on runtime behavior.',
    keywords: ['architecture observability', 'production monitoring', 'system analysis', 'request flows', 'microservices', 'distributed systems', 'architecture optimization'],
    icons: {
        icon: '/favicon.ico',
    },
    openGraph: {
        title: 'NEXARCH | Production Architecture Observability',
        description: 'Understand your production architecture automatically. Observe live request flows and get data-backed architectural decisions.',
        type: 'website',
    },
};

export default function RootLayout({ children }) {
    return (
        <html lang="en">
            <head>
                <link rel="preconnect" href="https://fonts.googleapis.com" />
                <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
                <link
                    href="https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap"
                    rel="stylesheet"
                />
            </head>
            <body className={inter.variable}>
                <AuthProvider>
                    {children}
                </AuthProvider>
            </body>
        </html>
    );
}
