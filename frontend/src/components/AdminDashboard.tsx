'use client';

import React, { useEffect, useState } from 'react';
import { apiService } from '@/services/api';
import { QueryAnalytics } from '@/types';
import {
    BarChart3,
    MessageSquare,
    XCircle,
    Clock,
    TrendingUp,
    AlertTriangle,
    Loader2,
    RefreshCw
} from '@/components/icons';

interface StatCardProps {
    title: string;
    value: string | number;
    icon: React.ReactNode;
    subtitle?: string;
    trend?: 'up' | 'down' | 'neutral';
}

function StatCard({ title, value, icon, subtitle, trend }: StatCardProps) {
    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-sm font-medium text-gray-500">{title}</p>
                    <p className="text-2xl font-bold text-brigade-dark mt-1">{value}</p>
                    {subtitle && (
                        <p className={`text-xs mt-1 ${trend === 'up' ? 'text-green-600' :
                                trend === 'down' ? 'text-red-600' : 'text-gray-500'
                            }`}>
                            {subtitle}
                        </p>
                    )}
                </div>
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-brigade-gold/20 to-brigade-gold/5 flex items-center justify-center">
                    {icon}
                </div>
            </div>
        </div>
    );
}

export function AdminDashboard() {
    const [analytics, setAnalytics] = useState<QueryAnalytics | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [days, setDays] = useState(7);

    const fetchAnalytics = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await apiService.getAnalytics('admin', days);
            setAnalytics(data);
        } catch (err) {
            console.error('Failed to fetch analytics:', err);
            setError('Failed to load analytics. Please try again.');
            // Set mock data for demonstration
            setAnalytics({
                total_queries: 156,
                answered_queries: 142,
                refused_queries: 14,
                refusal_rate: 0.0897,
                avg_response_time_ms: 1847,
                top_intents: {
                    project_fact: 89,
                    sales_pitch: 42,
                    comparison: 18,
                    unsupported: 7
                },
                recent_refusals: [
                    { query: 'What is the crime rate in this area?', reason: 'Query outside scope', timestamp: new Date().toISOString() },
                    { query: 'Can you book a site visit?', reason: 'Action not supported', timestamp: new Date().toISOString() },
                ]
            });
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchAnalytics();
    }, [days]);

    if (isLoading && !analytics) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <Loader2 className="w-8 h-8 animate-spin text-brigade-gold" />
            </div>
        );
    }

    return (
        <div className="p-6 max-w-7xl mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-brigade-dark">Analytics Dashboard</h1>
                    <p className="text-gray-500 mt-1">Monitor chatbot performance and query patterns</p>
                </div>
                <div className="flex items-center gap-3">
                    <select
                        value={days}
                        onChange={(e) => setDays(Number(e.target.value))}
                        className="px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brigade-gold focus:border-transparent"
                    >
                        <option value={7}>Last 7 days</option>
                        <option value={14}>Last 14 days</option>
                        <option value={30}>Last 30 days</option>
                    </select>
                    <button
                        onClick={fetchAnalytics}
                        disabled={isLoading}
                        className="flex items-center gap-2 px-4 py-2 bg-brigade-gold text-white rounded-lg hover:bg-yellow-600 transition-colors disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                        Refresh
                    </button>
                </div>
            </div>

            {error && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 text-amber-700 text-sm">
                    {error}
                </div>
            )}

            {analytics && (
                <>
                    {/* Stats Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                        <StatCard
                            title="Total Queries"
                            value={analytics.total_queries}
                            icon={<MessageSquare className="w-6 h-6 text-brigade-gold" />}
                            subtitle={`Last ${days} days`}
                        />
                        <StatCard
                            title="Answered"
                            value={analytics.answered_queries}
                            icon={<BarChart3 className="w-6 h-6 text-green-600" />}
                            subtitle={`${((analytics.answered_queries / analytics.total_queries) * 100).toFixed(1)}% success rate`}
                            trend="up"
                        />
                        <StatCard
                            title="Refused"
                            value={analytics.refused_queries}
                            icon={<XCircle className="w-6 h-6 text-red-500" />}
                            subtitle={`${(analytics.refusal_rate * 100).toFixed(1)}% refusal rate`}
                            trend="neutral"
                        />
                        <StatCard
                            title="Avg Response Time"
                            value={`${(analytics.avg_response_time_ms / 1000).toFixed(2)}s`}
                            icon={<Clock className="w-6 h-6 text-blue-500" />}
                            subtitle="Target: < 3s"
                            trend={analytics.avg_response_time_ms < 3000 ? 'up' : 'down'}
                        />
                    </div>

                    {/* Intent Distribution and Recent Refusals */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Intent Distribution */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
                            <div className="flex items-center gap-2 mb-6">
                                <TrendingUp className="w-5 h-5 text-brigade-gold" />
                                <h2 className="text-lg font-semibold text-brigade-dark">Query Intents</h2>
                            </div>
                            <div className="space-y-4">
                                {Object.entries(analytics.top_intents).map(([intent, count]) => {
                                    const total = Object.values(analytics.top_intents).reduce((a, b) => a + b, 0);
                                    const percentage = (count / total) * 100;
                                    const colors: Record<string, string> = {
                                        project_fact: 'bg-blue-500',
                                        sales_pitch: 'bg-green-500',
                                        comparison: 'bg-purple-500',
                                        unsupported: 'bg-red-500',
                                    };

                                    return (
                                        <div key={intent}>
                                            <div className="flex items-center justify-between text-sm mb-1">
                                                <span className="font-medium capitalize">{intent.replace('_', ' ')}</span>
                                                <span className="text-gray-500">{count} ({percentage.toFixed(1)}%)</span>
                                            </div>
                                            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full ${colors[intent] || 'bg-gray-500'} transition-all duration-500`}
                                                    style={{ width: `${percentage}%` }}
                                                />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Recent Refusals */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
                            <div className="flex items-center gap-2 mb-6">
                                <AlertTriangle className="w-5 h-5 text-amber-500" />
                                <h2 className="text-lg font-semibold text-brigade-dark">Recent Refusals</h2>
                            </div>
                            <div className="space-y-4">
                                {analytics.recent_refusals.length > 0 ? (
                                    analytics.recent_refusals.slice(0, 5).map((refusal, index) => (
                                        <div
                                            key={index}
                                            className="p-3 bg-amber-50 rounded-lg border border-amber-100"
                                        >
                                            <p className="text-sm font-medium text-gray-800 truncate">
                                                &ldquo;{refusal.query}&rdquo;
                                            </p>
                                            <p className="text-xs text-amber-700 mt-1">
                                                Reason: {refusal.reason}
                                            </p>
                                            <p className="text-xs text-gray-400 mt-1">
                                                {new Date(refusal.timestamp).toLocaleString()}
                                            </p>
                                        </div>
                                    ))
                                ) : (
                                    <p className="text-gray-500 text-sm text-center py-8">
                                        No recent refusals
                                    </p>
                                )}
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

export default AdminDashboard;
