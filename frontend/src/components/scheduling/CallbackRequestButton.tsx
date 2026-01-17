'use client';

import React, { useState } from 'react';
import { Phone } from '@/components/icons';
import { CallbackRequestModal } from './CallbackRequestModal';

interface CallbackRequestButtonProps {
    userId: string;
    sessionId?: string;
    className?: string;
}

export function CallbackRequestButton({ userId, sessionId, className = '' }: CallbackRequestButtonProps) {
    const [showModal, setShowModal] = useState(false);

    return (
        <>
            {/* Floating Button */}
            <button
                onClick={() => setShowModal(true)}
                className={`fixed bottom-24 right-6 bg-green-600 text-white p-4 rounded-full shadow-lg hover:bg-green-700 hover:scale-110 transition-all z-40 flex items-center gap-2 ${className}`}
                title="Request a callback"
            >
                <Phone className="w-6 h-6" />
                <span className="hidden md:block font-medium">Request Callback</span>
            </button>

            {/* Modal */}
            <CallbackRequestModal
                userId={userId}
                sessionId={sessionId}
                isOpen={showModal}
                onClose={() => setShowModal(false)}
                onSuccess={(callbackId) => {
                    console.log('Callback requested:', callbackId);
                    // Could show a toast notification here
                }}
            />
        </>
    );
}
