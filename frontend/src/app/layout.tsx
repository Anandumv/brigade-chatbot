import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

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
            <body className={inter.className}>
                <main className="min-h-screen">
                    {children}
                </main>
            </body>
        </html>
    );
}
