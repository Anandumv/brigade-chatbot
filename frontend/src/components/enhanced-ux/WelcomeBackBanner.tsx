'use client';

import React from 'react';
import { UserProfileData } from '@/types/enhanced-ux';
import { User, Calendar, TrendingUp, Sparkles } from '@/components/icons';

interface WelcomeBackBannerProps {
    userProfile?: UserProfileData;
    onDismiss?: () => void;
    className?: string;
}

export function WelcomeBackBanner({ userProfile, onDismiss, className = '' }: WelcomeBackBannerProps) {
    if (!userProfile?.is_returning_user) return null;

    const getWelcomeMessage = () => {
        if (userProfile.last_visit_date) {
            const daysSince = Math.floor(
                (Date.now() - new Date(userProfile.last_visit_date).getTime()) / (1000 * 60 * 60 * 24)
            );
            if (daysSince === 0) return "Welcome back! Continuing from where you left off?";
            if (daysSince === 1) return "Welcome back! We saved your preferences from yesterday.";
            if (daysSince < 7) return `Welcome back! It's been ${daysSince} days since your last visit.`;
            return "Welcome back! We've saved your preferences and interests.";
        }
        return "Welcome back! We've saved your preferences.";
    };

    const getLeadScoreBadge = () => {
        if (!userProfile.lead_score) return null;
        
        const colors = {
            hot: 'bg-red-100 text-red-800 border-red-300',
            warm: 'bg-orange-100 text-orange-800 border-orange-300',
            cold: 'bg-blue-100 text-blue-800 border-blue-300',
        };
        
        return (
            <span className={`px-2 py-1 rounded-full text-xs font-medium border ${colors[userProfile.lead_score]}`}>
                {userProfile.lead_score.toUpperCase()} Lead
            </span>
        );
    };

    return (
        <div className={`bg-gradient-to-r from-blue-50 to-indigo-50 border-l-4 border-blue-600 rounded-lg p-4 mb-4 ${className}`}>
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-3 flex-1">
                    <div className="bg-blue-100 rounded-full p-2 flex-shrink-0">
                        <User className="w-5 h-5 text-blue-600" />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-semibold text-gray-900">Welcome Back!</h3>
                            {getLeadScoreBadge()}
                        </div>
                        
                        <p className="text-sm text-gray-700 mb-2">
                            {getWelcomeMessage()}
                        </p>
                        
                        {userProfile.viewed_projects_count && userProfile.viewed_projects_count > 0 && (
                            <div className="flex items-center gap-4 text-xs text-gray-600">
                                <span className="flex items-center gap-1">
                                    <Calendar className="w-3 h-3" />
                                    {userProfile.viewed_projects_count} properties viewed
                                </span>
                                {userProfile.interests && userProfile.interests.length > 0 && (
                                    <span className="flex items-center gap-1">
                                        <Sparkles className="w-3 h-3" />
                                        {userProfile.interests.length} interests saved
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                </div>
                
                {onDismiss && (
                    <button
                        onClick={onDismiss}
                        className="text-gray-400 hover:text-gray-600 transition-colors ml-2 flex-shrink-0"
                        aria-label="Dismiss"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                )}
            </div>
        </div>
    );
}
