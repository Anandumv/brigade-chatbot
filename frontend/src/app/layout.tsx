import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
    title: 'Brigade Sales Assistant | AI-Powered Property Information',
    description: 'Get accurate, source-backed information about Brigade Group properties. Ask about amenities, pricing, configurations, and more.',
    keywords: ['Brigade Group', 'real estate', 'property', 'sales assistant', 'AI chatbot', 'Bangalore', 'Brigade Citrine', 'Brigade Avalon'],
    authors: [{ name: 'Brigade Group' }],
    openGraph: {
        title: 'Brigade Sales Assistant',
        description: 'AI-powered property information for Brigade Group projects',
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
            <body className={inter.className}>
                <main className="min-h-screen">
                    {children}
                </main>
            </body>
        </html>
    );
}
