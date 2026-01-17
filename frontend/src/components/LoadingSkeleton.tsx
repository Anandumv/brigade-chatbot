export function LoadingSkeleton() {
    return (
        <div className="flex items-center justify-center min-h-screen bg-gradient-to-b from-gray-50 to-white">
            <div className="text-center space-y-4">
                {/* Animated icon placeholder */}
                <div className="w-16 h-16 bg-gradient-to-br from-red-200 to-orange-200 rounded-2xl mx-auto animate-pulse" />

                {/* Title skeleton */}
                <div className="h-6 w-48 bg-gray-200 rounded mx-auto animate-pulse" />

                {/* Subtitle skeleton */}
                <div className="h-4 w-64 bg-gray-200 rounded mx-auto animate-pulse" />

                {/* Loading text */}
                <p className="text-sm text-gray-500 mt-4">Loading Pin Click Sales Assist...</p>
            </div>
        </div>
    );
}
