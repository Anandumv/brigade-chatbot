'use client';

import { useEffect } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default function Error({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        // Log the error to an error reporting service
        console.error('Application Error:', error);
    }, [error]);

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 p-4">
            <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center space-y-6">
                <div className="w-16 h-16 bg-red-50 text-red-500 rounded-full flex items-center justify-center mx-auto">
                    <AlertCircle className="w-8 h-8" />
                </div>

                <div className="space-y-2">
                    <h2 className="text-2xl font-bold text-gray-900">Something went wrong!</h2>
                    <div className="bg-gray-100 rounded-lg p-3 overflow-auto max-h-32 text-left">
                        <p className="text-xs font-mono text-gray-600 break-words">
                            {error.message || 'An unexpected error occurred'}
                        </p>
                    </div>
                    <p className="text-gray-500 text-sm">
                        We apologize for the inconvenience. Please try refreshing the page.
                    </p>
                </div>

                <div className="flex gap-3 justify-center">
                    <button
                        onClick={() => window.location.reload()}
                        className="px-5 py-2.5 bg-gray-900 text-white rounded-xl hover:bg-gray-800 transition-colors font-medium text-sm flex items-center gap-2"
                    >
                        <RefreshCw className="w-4 h-4" />
                        Reload Page
                    </button>
                    <button
                        onClick={() => reset()}
                        className="px-5 py-2.5 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors font-medium text-sm"
                    >
                        Try Again
                    </button>
                </div>
            </div>
        </div>
    );
}
