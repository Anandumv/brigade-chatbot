import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { PerformanceMonitor } from '@/components/PerformanceMonitor';

const inter = Inter({
    subsets: ['latin'],
    display: 'swap',
    preload: true,
    variable: '--font-inter',
});

export const metadata: Metadata = {
    title: 'Pin Click Sales Assist | Your AI Sales Copilot',
    description: 'Pin Click Sales Assist - Your AI Sales Copilot for property information.',
    keywords: ['Pinclick', 'real estate', 'property', 'sales assist', 'AI chatbot', 'Bangalore'],
    authors: [{ name: 'Pinclick' }],
    openGraph: {
        title: 'Pin Click Sales Assist',
        description: 'Your AI Sales Copilot. Ask about projects, prices, or anything related to your client requirement',
        type: 'website',
    },
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <head>
                <link rel="icon" href="/logo.png" type="image/png" />
                <link rel="preconnect" href={process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'} />
                <link rel="dns-prefetch" href={process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'} />
            </head>
            <body className={inter.className}>
                <PerformanceMonitor />
                <main className="min-h-screen">
                    {children}
                </main>
            </body>
        </html>
    );
}
