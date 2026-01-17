import { Suspense } from 'react';
import { ChatInterface } from '@/components/ChatInterface';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { getProjectsServer, getPersonasServer } from '@/services/server-api';

// This is now a Server Component - no 'use client' directive
export default async function Home() {
    // Parallel server-side data fetching
    const [projects, personas] = await Promise.all([
        getProjectsServer(),
        getPersonasServer(),
    ]);

    return (
        <div className="h-screen flex flex-col">
            <Suspense fallback={<LoadingSkeleton />}>
                <ChatInterface projects={projects} personas={personas} />
            </Suspense>
        </div>
    );
}

// Metadata for the page
export const metadata = {
    title: 'Pin Click Sales Assist - Chat',
    description: 'Your AI Sales Copilot. Ask about projects, prices, or anything related to your client requirement',
};
