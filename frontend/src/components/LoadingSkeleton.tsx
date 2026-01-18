import { PinClickLogo } from './PinClickLogo';

export function LoadingSkeleton() {
    return (
        <div className="flex items-center justify-center min-h-screen bg-gradient-to-b from-gray-50 to-white">
            <div className="text-center space-y-4">
                {/* Logo with animation */}
                <div className="mx-auto animate-pulse">
                    <PinClickLogo size={64} showText={true} />
                </div>

                {/* Title skeleton */}
                <div className="h-6 w-48 bg-gray-200 rounded mx-auto animate-pulse" />

                {/* Subtitle skeleton */}
                <div className="h-4 w-64 bg-gray-200 rounded mx-auto animate-pulse" />

                {/* Loading text */}
                <p className="text-sm text-gray-500 mt-4">Loading...</p>
            </div>
        </div>
    );
}
