'use client';

import React from 'react';
import { UrgencySignal } from '@/types/enhanced-ux';
import { AlertTriangle, TrendingUp, Users, Clock, Calendar } from '@/components/icons';

interface UrgencySignalsProps {
    signals: UrgencySignal[];
    projectName?: string;
    className?: string;
}

export function UrgencySignals({ signals, projectName, className = '' }: UrgencySignalsProps) {
    if (!signals || signals.length === 0) return null;

    const getIcon = (type: string) => {
        switch (type) {
            case 'low_inventory':
                return <AlertTriangle className="w-4 h-4" />;
            case 'price_increase':
                return <TrendingUp className="w-4 h-4" />;
            case 'high_demand':
                return <Users className="w-4 h-4" />;
            case 'time_limited_offer':
                return <Clock className="w-4 h-4" />;
            case 'seasonal':
                return <Calendar className="w-4 h-4" />;
            default:
                return <AlertTriangle className="w-4 h-4" />;
        }
    };

    const getColorScheme = (priorityScore: number) => {
        if (priorityScore >= 8) {
            return {
                bg: 'bg-red-50 border-red-300',
                text: 'text-red-900',
                icon: 'text-red-600',
                badge: 'bg-red-600 text-white',
            };
        } else if (priorityScore >= 5) {
            return {
                bg: 'bg-orange-50 border-orange-300',
                text: 'text-orange-900',
                icon: 'text-orange-600',
                badge: 'bg-orange-600 text-white',
            };
        } else {
            return {
                bg: 'bg-yellow-50 border-yellow-300',
                text: 'text-yellow-900',
                icon: 'text-yellow-600',
                badge: 'bg-yellow-600 text-white',
            };
        }
    };

    // Show only top 2 signals to avoid overwhelming
    const topSignals = signals.slice(0, 2);

    return (
        <div className={`space-y-2 ${className}`}>
            {topSignals.map((signal, index) => {
                const colors = getColorScheme(signal.priority_score);
                
                return (
                    <div
                        key={index}
                        className={`${colors.bg} border-l-4 rounded-r-lg p-3 flex items-start gap-3`}
                    >
                        <div className={`${colors.icon} flex-shrink-0 mt-0.5`}>
                            {getIcon(signal.type)}
                        </div>
                        
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                                <span className={`px-2 py-0.5 rounded text-xs font-bold ${colors.badge}`}>
                                    URGENT
                                </span>
                                {projectName && (
                                    <span className="text-xs text-gray-600">
                                        {projectName}
                                    </span>
                                )}
                            </div>
                            
                            <p className={`text-sm font-medium ${colors.text}`}>
                                {signal.message}
                            </p>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
