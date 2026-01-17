'use client';

import React from 'react';

interface QuickReply {
    label: string;
    icon?: string;
    value: string;
    variant?: 'primary' | 'secondary' | 'accent';
}

interface QuickRepliesProps {
    replies: QuickReply[];
    onSelect: (value: string) => void;
    disabled?: boolean;
}

export function QuickReplies({ replies, onSelect, disabled = false }: QuickRepliesProps) {
    if (!replies || replies.length === 0) return null;

    const getVariantStyles = (variant: string = 'secondary') => {
        switch (variant) {
            case 'primary':
                return 'bg-gradient-to-r from-green-500 to-emerald-500 text-white hover:from-green-600 hover:to-emerald-600 shadow-md';
            case 'accent':
                return 'bg-gradient-to-r from-orange-400 to-red-500 text-white hover:from-orange-500 hover:to-red-600 shadow-md';
            default:
                return 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-200';
        }
    };

    return (
        <div className="flex flex-wrap gap-2 mt-3 animate-fade-in">
            {replies.map((reply, index) => (
                <button
                    key={index}
                    onClick={() => onSelect(reply.value)}
                    disabled={disabled}
                    className={`
                        inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium
                        transition-all duration-200 transform hover:scale-105 active:scale-95
                        disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none
                        ${getVariantStyles(reply.variant)}
                    `}
                >
                    {reply.icon && <span className="text-lg">{reply.icon}</span>}
                    {reply.label}
                </button>
            ))}
        </div>
    );
}

// Pre-defined quick reply sets based on conversation context
export const QUICK_REPLY_SETS = {
    initial: [
        { label: 'Show 2BHK options', icon: '🏠', value: 'Show me 2BHK options', variant: 'secondary' as const },
        { label: 'Budget advice', icon: '💰', value: 'How to stretch my budget?', variant: 'secondary' as const },
    ],
    afterPropertySearch: [
        { label: 'More details', icon: '📋', value: 'Tell me more about this project', variant: 'secondary' as const },
        { label: 'Compare options', icon: '⚖️', value: 'Compare with other projects', variant: 'secondary' as const },
    ],
    afterFAQ: [
        { label: 'Yes, schedule meeting', icon: '✅', value: 'Yes, let\'s schedule a meeting', variant: 'primary' as const },
        { label: 'Show me options', icon: '🏠', value: 'Show me available options', variant: 'secondary' as const },
        { label: 'More questions', icon: '❓', value: 'I have more questions', variant: 'secondary' as const },
    ],
    afterObjection: [
        { label: 'I understand', icon: '👍', value: 'That makes sense, show me options', variant: 'secondary' as const },
        { label: 'Let\'s talk', icon: '📞', value: 'I\'d like to discuss further', variant: 'primary' as const },
        { label: 'Still concerned', icon: '🤔', value: 'I still have concerns', variant: 'secondary' as const },
    ],
    meetingCTA: [
        { label: 'Call me back', icon: '📱', value: 'Please call me back', variant: 'accent' as const },
        { label: 'Later', icon: '⏰', value: 'I\'ll think about it', variant: 'secondary' as const },
    ],
};

// Helper to determine which quick replies to show based on intent
export function getQuickRepliesForIntent(intent: string): QuickReply[] {
    const intentMap: Record<string, QuickReply[]> = {
        'property_search': QUICK_REPLY_SETS.afterPropertySearch,
        'intelligent_sales_faq': QUICK_REPLY_SETS.afterFAQ,
        'intelligent_sales_objection': QUICK_REPLY_SETS.afterObjection,
        'sales_faq': QUICK_REPLY_SETS.afterFAQ,
        'sales_objection': QUICK_REPLY_SETS.afterObjection,
        'greeting': QUICK_REPLY_SETS.initial,
    };

    // Check for partial matches
    for (const [key, replies] of Object.entries(intentMap)) {
        if (intent.includes(key)) {
            return replies;
        }
    }

    // Default to meeting CTA for other intents
    return QUICK_REPLY_SETS.meetingCTA;
}

export default QuickReplies;
