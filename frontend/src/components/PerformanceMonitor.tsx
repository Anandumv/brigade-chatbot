'use client';

import { useReportWebVitals } from 'next/web-vitals';

export function PerformanceMonitor() {
    useReportWebVitals((metric) => {
        // Log performance metrics in development
        if (process.env.NODE_ENV === 'development') {
            console.log({
                name: metric.name,
                value: Math.round(metric.name === 'CLS' ? metric.value * 1000 : metric.value),
                rating: metric.rating,
            });
        }
        // In production, you could send to analytics service
        // fetch('/api/analytics', { method: 'POST', body: JSON.stringify(metric) });
    });

    return null;
}
