'use client';

import React from 'react';
import { CoachingPrompt } from '@/types';
import { Sparkles, Zap, AlertCircle, CheckCircle } from '@/components/icons';

interface CoachingPanelProps {
    coaching_prompt?: CoachingPrompt;
}

export function CoachingPanel({ coaching_prompt }: CoachingPanelProps) {
    if (!coaching_prompt) {
        return null;
    }

    // Determine icon and color based on priority
    const getPriorityConfig = (priority: string) => {
        switch (priority) {
            case 'critical':
                return {
                    icon: <Zap className="w-5 h-5" />,
                    bgColor: 'bg-red-50 border-red-300',
                    textColor: 'text-red-800',
                    iconColor: 'text-red-600',
                    badgeColor: 'bg-red-100 text-red-700'
                };
            case 'high':
                return {
                    icon: <AlertCircle className="w-5 h-5" />,
                    bgColor: 'bg-orange-50 border-orange-300',
                    textColor: 'text-orange-800',
                    iconColor: 'text-orange-600',
                    badgeColor: 'bg-orange-100 text-orange-700'
                };
            case 'medium':
                return {
                    icon: <Sparkles className="w-5 h-5" />,
                    bgColor: 'bg-blue-50 border-blue-300',
                    textColor: 'text-blue-800',
                    iconColor: 'text-blue-600',
                    badgeColor: 'bg-blue-100 text-blue-700'
                };
            default:
                return {
                    icon: <CheckCircle className="w-5 h-5" />,
                    bgColor: 'bg-gray-50 border-gray-300',
                    textColor: 'text-gray-800',
                    iconColor: 'text-gray-600',
                    badgeColor: 'bg-gray-100 text-gray-700'
                };
        }
    };

    const config = getPriorityConfig(coaching_prompt.priority);

    // Get type label
    const getTypeLabel = (type: string) => {
        return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    };

    return (
        <div className={`border-2 rounded-lg p-4 mb-4 ${config.bgColor} shadow-md`}>
            {/* Header */}
            <div className="flex items-start gap-3 mb-3">
                <div className={config.iconColor}>
                    {config.icon}
                </div>
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                        <h3 className={`font-semibold ${config.textColor}`}>
                            💡 Sales Coaching
                        </h3>
                        <span className={`text-xs px-2 py-1 rounded-full font-medium ${config.badgeColor}`}>
                            {coaching_prompt.priority.toUpperCase()}
                        </span>
                        <span className="text-xs px-2 py-1 rounded-full font-medium bg-gray-100 text-gray-600">
                            {getTypeLabel(coaching_prompt.type)}
                        </span>
                    </div>
                </div>
            </div>

            {/* Message */}
            <div className={`mb-3 ${config.textColor}`}>
                <p className="text-sm leading-relaxed">
                    {coaching_prompt.message}
                </p>
            </div>

            {/* Suggested Script (if available) */}
            {coaching_prompt.suggested_script && (
                <div className="mt-3 pt-3 border-t border-gray-300">
                    <p className="text-xs font-semibold text-gray-600 mb-2">
                        📝 SUGGESTED SCRIPT:
                    </p>
                    <div className="bg-white/50 rounded p-3 text-sm italic text-gray-700 leading-relaxed">
                        "{coaching_prompt.suggested_script}"
                    </div>
                </div>
            )}
        </div>
    );
}
