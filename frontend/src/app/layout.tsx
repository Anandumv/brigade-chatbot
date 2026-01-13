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
    title: 'Pinclick Genie | Your Real Estate Assistant',
    description: 'Pinclick Genie - Expert AI assistant for property information.',
    keywords: ['Pinclick', 'real estate', 'property', 'genie', 'AI chatbot', 'Bangalore'],
    authors: [{ name: 'Pinclick' }],
    openGraph: {
        title: 'Pinclick Genie',
        description: 'Your expert AI real estate assistant',
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
