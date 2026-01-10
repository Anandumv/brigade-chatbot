'use client';

import { useEffect, useState } from 'react';
import { ChatInterface } from '@/components/ChatInterface';
import { apiService } from '@/services/api';
import { ProjectInfo, PersonaInfo } from '@/types';
import { Loader2 } from 'lucide-react';

export default function Home() {
    const [projects, setProjects] = useState<ProjectInfo[]>([]);
    const [personas, setPersonas] = useState<PersonaInfo[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function loadData() {
            try {
                const [projectsData, personasData] = await Promise.all([
                    apiService.getProjects(),
                    apiService.getPersonas(),
                ]);
                setProjects(projectsData);
                setPersonas(personasData);
            } catch (err) {
                console.error('Failed to load initial data:', err);
                setError('Failed to connect to the server. Some features may be limited.');
                // Still load fallback data from API service
                const [projectsData, personasData] = await Promise.all([
                    apiService.getProjects(),
                    apiService.getPersonas(),
                ]);
                setProjects(projectsData);
                setPersonas(personasData);
            } finally {
                setIsLoading(false);
            }
        }

        loadData();
    }, []);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gradient-to-b from-gray-50 to-white">
                <div className="text-center">
                    <Loader2 className="w-12 h-12 animate-spin text-brigade-gold mx-auto mb-4" />
                    <p className="text-gray-600">Loading Brigade Sales Assistant...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="h-screen flex flex-col">
            {error && (
                <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-amber-700 text-sm text-center">
                    {error}
                </div>
            )}
            <div className="flex-1 overflow-hidden">
                <ChatInterface projects={projects} personas={personas} />
            </div>
        </div>
    );
}
