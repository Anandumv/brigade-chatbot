import axios, { AxiosInstance } from 'axios';
import {
    ChatQueryRequest,
    ChatQueryResponse,
    ProjectInfo,
    PersonaInfo,
    QueryAnalytics,
    CompareProjectsRequest,
} from '@/types';

class ApiService {
    private client: AxiosInstance;

    constructor() {
        this.client = axios.create({
            baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
            headers: {
                'Content-Type': 'application/json',
            },
            timeout: 30000, // 30 second timeout
        });
    }

    // Chat endpoints
    async sendQuery(request: ChatQueryRequest): Promise<ChatQueryResponse> {
        const response = await this.client.post<ChatQueryResponse>('/api/chat/query', request);
        return response.data;
    }

    async compareProjects(request: CompareProjectsRequest): Promise<ChatQueryResponse> {
        const response = await this.client.post<ChatQueryResponse>('/api/chat/compare', request);
        return response.data;
    }

    // Project endpoints
    async getProjects(): Promise<ProjectInfo[]> {
        try {
            const response = await this.client.get<ProjectInfo[]>('/api/projects');
            return response.data;
        } catch (error) {
            // Return mock projects if API fails
            console.warn('Failed to fetch projects, using fallback data');
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

    // Persona endpoints
    async getPersonas(): Promise<PersonaInfo[]> {
        try {
            const response = await this.client.get<PersonaInfo[]>('/api/personas');
            return response.data;
        } catch (error) {
            // Return mock personas if API fails
            console.warn('Failed to fetch personas, using fallback data');
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

    // Analytics endpoints (Admin)
    async getAnalytics(userId: string, days: number = 7): Promise<QueryAnalytics> {
        const response = await this.client.get<QueryAnalytics>('/api/admin/analytics', {
            params: { user_id: userId, days },
        });
        return response.data;
    }

    // Health check
    async healthCheck(): Promise<{ status: string }> {
        const response = await this.client.get<{ status: string }>('/health');
        return response.data;
    }
}

export const apiService = new ApiService();
export default apiService;
