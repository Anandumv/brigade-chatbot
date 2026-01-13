import axios, { AxiosInstance } from 'axios';
import {
    ChatQueryRequest,
    ChatQueryResponse,
    ProjectInfo,
    PersonaInfo,
    QueryAnalytics,
    CompareProjectsRequest,
} from '@/types';
import { FilterOptions, SelectedFilters } from '@/types/filters';

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

    async sendSalesQuery(request: ChatQueryRequest): Promise<ChatQueryResponse> {
        const response = await this.client.post<ChatQueryResponse>('/api/chat/sales', request);
        return response.data;
    }

    async compareProjects(request: CompareProjectsRequest): Promise<ChatQueryResponse> {
        const response = await this.client.post<ChatQueryResponse>('/api/chat/compare', request);
        return response.data;
    }

    // Filter options endpoint
    async getFilterOptions(): Promise<FilterOptions> {
        try {
            const response = await this.client.get<FilterOptions>('/api/filters/options');
            return response.data;
        } catch (error) {
            console.warn('Failed to fetch filter options, using fallback data');
            return this.getFallbackFilterOptions();
        }
    }

    private getFallbackFilterOptions(): FilterOptions {
        return {
            configurations: [
                { value: '1', label: '1 BHK' },
                { value: '2', label: '2 BHK' },
                { value: '3', label: '3 BHK' },
                { value: '4', label: '4 BHK' },
                { value: '5', label: '5 BHK' },
                { value: '6', label: '6 BHK' },
            ],
            locations: {
                east_bangalore: {
                    label: 'East Bangalore',
                    areas: [
                        { value: 'whitefield', label: 'Whitefield' },
                        { value: 'budigere_cross', label: 'Budigere Cross' },
                        { value: 'harlur', label: 'Harlur' },
                        { value: 'banjara', label: 'Banjara' },
                        { value: 'helicopter_road', label: 'Helicopter Road' },
                        { value: 'khandike_road', label: 'Khandike Road' },
                        { value: 'sarjapur', label: 'Sarjapur' },
                        { value: 'thanisandra', label: 'Thanisandra' },
                    ],
                },
                north_bangalore: {
                    label: 'North Bangalore',
                    areas: [
                        { value: 'jakkur', label: 'Jakkur' },
                        { value: 'bagar', label: 'Bagar' },
                        { value: 'yelahanka', label: 'Yelahanka' },
                        { value: 'devanahalli', label: 'Devanahalli' },
                    ],
                },
            },
            budget_ranges: [
                { value: '50L-1CR', label: '₹50 Lac - ₹1 Cr', min: 5000000, max: 10000000 },
                { value: '1CR-1.5CR', label: '₹1 Cr - ₹1.5 Cr', min: 10000000, max: 15000000 },
                { value: '1.5CR-2CR', label: '₹1.5 Cr - ₹2 Cr', min: 15000000, max: 20000000 },
                { value: '2CR-2.5CR', label: '₹2 Cr - ₹2.5 Cr', min: 20000000, max: 25000000 },
                { value: '2.5CR-3CR', label: '₹2.5 Cr - ₹3 Cr', min: 25000000, max: 30000000 },
                { value: '3CR-4CR', label: '₹3 Cr - ₹4 Cr', min: 30000000, max: 40000000 },
                { value: '4CR-5CR', label: '₹4 Cr - ₹5 Cr', min: 40000000, max: 50000000 },
                { value: 'ABOVE-5CR', label: 'Above ₹5 Cr', min: 50000000, max: null },
            ],
            possession_years: [
                { value: 'READY', label: 'Ready to Move' },
                { value: '2024', label: '2024' },
                { value: '2025', label: '2025' },
                { value: '2026', label: '2026' },
                { value: '2027', label: '2027' },
                { value: '2028', label: '2028' },
                { value: '2029', label: '2029' },
                { value: '2030', label: '2030' },
            ],
        };
    }

    // Send query with filters
    async sendQueryWithFilters(
        query: string,
        filters: SelectedFilters,
        userId?: string
    ): Promise<ChatQueryResponse> {
        // Build enhanced query based on filters
        let enhancedQuery = query;

        if (filters.configuration) {
            enhancedQuery += ` ${filters.configuration}bhk`;
        }
        if (filters.location) {
            enhancedQuery += ` in ${filters.location}`;
        }
        if (filters.budgetMax) {
            const maxCr = filters.budgetMax / 10000000;
            enhancedQuery += ` under ${maxCr}cr`;
        }
        if (filters.possessionYear && filters.possessionYear !== 'READY') {
            enhancedQuery += ` possession ${filters.possessionYear}`;
        } else if (filters.possessionYear === 'READY') {
            enhancedQuery += ' ready to move';
        }

        return this.sendQuery({
            query: enhancedQuery.trim(),
            user_id: userId,
        });
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

