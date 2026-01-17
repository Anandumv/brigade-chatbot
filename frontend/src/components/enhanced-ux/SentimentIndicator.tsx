'use client';

import React, { useState } from 'react';
import { SentimentData } from '@/types/enhanced-ux';
import { Smile, Frown, Meh, AlertCircle, Phone } from '@/components/icons';

interface SentimentIndicatorProps {
    sentiment: SentimentData;
    onEscalate?: () => void;
    className?: string;
}

export function SentimentIndicator({ sentiment, onEscalate, className = '' }: SentimentIndicatorProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    const getSentimentIcon = () => {
        switch (sentiment.sentiment) {
            case 'excited':
                return <Smile className="w-5 h-5 text-green-600" />;
            case 'positive':
                return <Smile className="w-5 h-5 text-blue-600" />;
            case 'neutral':
                return <Meh className="w-5 h-5 text-gray-600" />;
            case 'negative':
                return <Frown className="w-5 h-5 text-orange-600" />;
            case 'frustrated':
                return <AlertCircle className="w-5 h-5 text-red-600" />;
            default:
                return <Meh className="w-5 h-5 text-gray-600" />;
        }
    };

    const getSentimentColor = () => {
        switch (sentiment.sentiment) {
            case 'excited':
                return 'bg-green-50 border-green-200 text-green-900';
            case 'positive':
                return 'bg-blue-50 border-blue-200 text-blue-900';
            case 'neutral':
                return 'bg-gray-50 border-gray-200 text-gray-900';
            case 'negative':
                return 'bg-orange-50 border-orange-200 text-orange-900';
            case 'frustrated':
                return 'bg-red-50 border-red-200 text-red-900';
            default:
                return 'bg-gray-50 border-gray-200 text-gray-900';
        }
    };

    const getFrustrationBar = () => {
        const percentage = (sentiment.frustration_score / 10) * 100;
        let color = 'bg-green-500';
        
        if (sentiment.frustration_score >= 7) {
            color = 'bg-red-500';
        } else if (sentiment.frustration_score >= 4) {
            color = 'bg-orange-500';
        } else if (sentiment.frustration_score >= 2) {
            color = 'bg-yellow-500';
        }

        return (
            <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                <div
                    className={`${color} h-2 rounded-full transition-all duration-300`}
                    style={{ width: `${percentage}%` }}
                />
            </div>
        );
    };

    const colors = getSentimentColor();

    return (
        <div className={`${colors} border rounded-lg p-3 ${className}`}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {getSentimentIcon()}
                    <div>
                        <p className="text-sm font-medium capitalize">
                            {sentiment.sentiment}
                        </p>
                        {sentiment.frustration_score > 0 && (
                            <div className="text-xs text-gray-600 mt-0.5">
                                Frustration: {sentiment.frustration_score.toFixed(1)}/10
                            </div>
                        )}
                    </div>
                </div>

                {sentiment.escalation_recommended && onEscalate && (
                    <button
                        onClick={onEscalate}
                        className="px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center gap-2 text-sm font-medium"
                    >
                        <Phone className="w-4 h-4" />
                        Talk to Human
                    </button>
                )}
            </div>

            {sentiment.frustration_score > 0 && (
                <div className="mt-2">
                    {getFrustrationBar()}
                </div>
            )}

            {isExpanded && sentiment.escalation_reason && (
                <div className="mt-2 pt-2 border-t border-gray-300">
                    <p className="text-xs text-gray-700">
                        <strong>Why:</strong> {sentiment.escalation_reason}
                    </p>
                </div>
            )}

            {sentiment.escalation_recommended && !onEscalate && (
                <div className="mt-2 pt-2 border-t border-gray-300">
                    <p className="text-xs text-gray-700">
                        💡 We recommend speaking with a human agent for better assistance.
                    </p>
                </div>
            )}
        </div>
    );
}
