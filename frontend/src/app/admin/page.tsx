import dynamic from 'next/dynamic';
import { Suspense } from 'react';
import { Sparkles, ArrowLeft, Loader2 } from '@/components/icons';
import Link from 'next/link';

// Lazy load the AdminDashboard component
const AdminDashboard = dynamic(
    () => import('@/components/AdminDashboard').then((mod) => ({ default: mod.AdminDashboard })),
    {
        loading: () => (
            <div className="flex items-center justify-center p-12">
                <div className="text-center">
                    <Loader2 className="w-12 h-12 animate-spin text-brigade-gold mx-auto mb-4" />
                    <p className="text-gray-600">Loading dashboard...</p>
                </div>
            </div>
        ),
        ssr: false, // Skip SSR for admin dashboard (heavy client component)
    }
);

export default function AdminPage() {
    return (
        <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
            {/* Header */}
            <header className="bg-white border-b border-gray-200 shadow-sm">
                <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Link
                            href="/"
                            className="flex items-center gap-2 text-gray-600 hover:text-brigade-dark transition-colors"
                        >
                            <ArrowLeft className="w-5 h-5" />
                            <span className="text-sm font-medium">Back to Chat</span>
                        </Link>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brigade-gold to-yellow-600 flex items-center justify-center shadow-lg">
                            <Sparkles className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h1 className="text-lg font-bold text-brigade-dark">Admin Dashboard</h1>
                            <p className="text-xs text-gray-500">Brigade Sales Assistant</p>
                        </div>
                    </div>
                </div>
            </header>

            {/* Dashboard Content - Lazy Loaded */}
            <Suspense
                fallback={
                    <div className="flex items-center justify-center p-12">
                        <div className="text-center">
                            <Loader2 className="w-12 h-12 animate-spin text-brigade-gold mx-auto mb-4" />
                            <p className="text-gray-600">Loading dashboard...</p>
                        </div>
                    </div>
                }
            >
                <AdminDashboard />
            </Suspense>
        </div>
    );
}

export const metadata = {
    title: 'Admin Dashboard - Pinclick Genie',
    description: 'Analytics and management for Pinclick Genie',
};
