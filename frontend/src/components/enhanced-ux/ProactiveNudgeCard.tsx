'use client';

import React from 'react';
import { ProactiveNudge } from '@/types/enhanced-ux';
import { Sparkles, MapPin, DollarSign, CheckCircle, Clock, AlertCircle, Calendar, Phone } from '@/components/icons';

interface ProactiveNudgeCardProps {
    nudge: ProactiveNudge;
    onAction?: (action: string) => void;
    onDismiss?: () => void;
    className?: string;
}

export function ProactiveNudgeCard({ nudge, onAction, onDismiss, className = '' }: ProactiveNudgeCardProps) {
    const getIcon = () => {
        switch (nudge.type) {
            case 'repeat_views':
                return <Sparkles className="w-5 h-5" />;
            case 'location_focus':
                return <MapPin className="w-5 h-5" />;
            case 'budget_concern':
                return <DollarSign className="w-5 h-5" />;
            case 'decision_ready':
                return <CheckCircle className="w-5 h-5" />;
            case 'long_session':
                return <Clock className="w-5 h-5" />;
            case 'abandoned_interest':
                return <AlertCircle className="w-5 h-5" />;
            default:
                return <Sparkles className="w-5 h-5" />;
        }
    };

    const getColorScheme = () => {
        switch (nudge.priority) {
            case 'high':
                return {
                    bg: 'bg-red-50 border-red-200',
                    icon: 'bg-red-100 text-red-600',
                    badge: 'bg-red-100 text-red-800',
                };
            case 'medium':
                return {
                    bg: 'bg-orange-50 border-orange-200',
                    icon: 'bg-orange-100 text-orange-600',
                    badge: 'bg-orange-100 text-orange-800',
                };
            case 'low':
                return {
                    bg: 'bg-blue-50 border-blue-200',
                    icon: 'bg-blue-100 text-blue-600',
                    badge: 'bg-blue-100 text-blue-800',
                };
            default:
                return {
                    bg: 'bg-gray-50 border-gray-200',
                    icon: 'bg-gray-100 text-gray-600',
                    badge: 'bg-gray-100 text-gray-800',
                };
        }
    };

    const getActionButton = () => {
        if (!nudge.action || !onAction) return null;

        const actions = {
            schedule_visit: { label: 'Schedule Visit', icon: Calendar },
            show_alternatives: { label: 'Show Alternatives', icon: Sparkles },
            take_break: { label: 'Take a Break', icon: Clock },
            contact_rm: { label: 'Contact RM', icon: Phone },
        };

        const actionConfig = actions[nudge.action as keyof typeof actions];
        if (!actionConfig) return null;

        const Icon = actionConfig.icon;

        return (
            <button
                onClick={() => onAction(nudge.action!)}
                className="mt-3 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2 text-sm font-medium text-gray-700"
            >
                <Icon className="w-4 h-4" />
                {actionConfig.label}
            </button>
        );
    };

    const colors = getColorScheme();

    return (
        <div className={`${colors.bg} border rounded-lg p-4 mb-3 ${className}`}>
            <div className="flex items-start gap-3">
                <div className={`${colors.icon} rounded-full p-2 flex-shrink-0`}>
                    {getIcon()}
                </div>
                
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors.badge}`}>
                            {nudge.priority.toUpperCase()} PRIORITY
                        </span>
                        <span className="text-xs text-gray-500">
                            Smart Suggestion
                        </span>
                    </div>
                    
                    <p className="text-sm text-gray-900 font-medium mb-1">
                        {nudge.message}
                    </p>
                    
                    {getActionButton()}
                </div>
                
                {onDismiss && (
                    <button
                        onClick={onDismiss}
                        className="text-gray-400 hover:text-gray-600 transition-colors ml-2 flex-shrink-0"
                        aria-label="Dismiss"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                )}
            </div>
        </div>
    );
}
