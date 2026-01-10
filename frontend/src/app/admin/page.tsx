'use client';

import { AdminDashboard } from '@/components/AdminDashboard';
import { Sparkles, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

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

            {/* Dashboard Content */}
            <AdminDashboard />
        </div>
    );
}
