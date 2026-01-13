import 'server-only';
import { ProjectInfo, PersonaInfo } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function getProjectsServer(): Promise<ProjectInfo[]> {
    try {
        const res = await fetch(`${API_BASE}/api/projects`, {
            next: { revalidate: 3600 }, // Cache for 1 hour
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!res.ok) {
            throw new Error(`Failed to fetch projects: ${res.status}`);
        }

        return res.json();
    } catch (error) {
        console.warn('Server fetch failed, using fallback data:', error);
        // Return fallback data if API fails
        return [
            {
                id: 'brigade-citrine',
                name: 'Brigade Citrine',
                developer: 'Brigade Group',
                location: 'Bangalore',
                status: 'Active',
            },
            {
                id: 'brigade-avalon',
                name: 'Brigade Avalon',
                developer: 'Brigade Group',
                location: 'Bangalore',
                status: 'Active',
            },
        ];
    }
}

export async function getPersonasServer(): Promise<PersonaInfo[]> {
    try {
        const res = await fetch(`${API_BASE}/api/personas`, {
            next: { revalidate: 3600 }, // Cache for 1 hour
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!res.ok) {
            throw new Error(`Failed to fetch personas: ${res.status}`);
        }

        return res.json();
    } catch (error) {
        console.warn('Server fetch failed, using fallback data:', error);
        // Return fallback data if API fails
        return [
            {
                id: 'first_time_buyer',
                name: 'First-Time Homebuyer',
                description: 'Focuses on affordability, financing options, and move-in readiness',
                priorities: ['Affordability', 'Payment plans', 'Loan assistance'],
                concerns: ['Hidden costs', 'Legal clarity'],
            },
            {
                id: 'investor',
                name: 'Investor',
                description: 'Focuses on ROI, rental yield, and appreciation potential',
                priorities: ['Rental yield', 'Appreciation', 'Location growth'],
                concerns: ['Market risks', 'Vacancy rates'],
            },
            {
                id: 'senior_citizen',
                name: 'Senior Citizen',
                description: 'Focuses on accessibility, healthcare, and peaceful environment',
                priorities: ['Accessibility', 'Healthcare nearby', 'Peaceful environment'],
                concerns: ['Maintenance', 'Emergency services'],
            },
            {
                id: 'family',
                name: 'Family',
                description: 'Focuses on schools, amenities, and family-friendly features',
                priorities: ['Schools nearby', 'Parks', 'Safety', 'Spacious units'],
                concerns: ['Community quality', 'Traffic'],
            },
        ];
    }
}
