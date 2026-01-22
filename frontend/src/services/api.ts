import axios, { AxiosInstance } from 'axios';
import {
    ChatQueryRequest,
    ChatQueryResponse,
    ProjectInfo,
    PersonaInfo,
    QueryAnalytics,
    CompareProjectsRequest,
    AssistRequest,
    CopilotResponse,
    QuickFilters,
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

    // Copilot /assist endpoint (spec-compliant)
    async sendAssistQuery(request: AssistRequest): Promise<CopilotResponse> {
        const response = await this.client.post<CopilotResponse>('/api/assist/', request);
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
                { value: '2 BHK', label: '2 BHK' },
                { value: '2.5 BHK', label: '2.5 BHK' },
                { value: '3 BHK', label: '3 BHK' },
                { value: '3.5 BHK', label: '3.5 BHK' },
                { value: '4 BHK', label: '4 BHK' },
            ],
            locations: {
                east_bangalore: {
                    label: 'East Bangalore',
                    areas: [
                        { value: 'whitefield', label: 'Whitefield' },
                        { value: 'budigere', label: 'Budigere Cross' },
                        { value: 'varthur', label: 'Varthur' },
                        { value: 'gunjur', label: 'Gunjur' },
                        { value: 'sarjapur', label: 'Sarjapur Road' },
                        { value: 'panathur', label: 'Panathur Road' },
                        { value: 'marathahalli', label: 'Marathahalli' },
                        { value: 'bellandur', label: 'Bellandur' },
                        { value: 'hsr layout', label: 'HSR Layout' },
                    ],
                },
                north_bangalore: {
                    label: 'North Bangalore',
                    areas: [
                        { value: 'thanisandra', label: 'Thanisandra' },
                        { value: 'yelahanka', label: 'Yelahanka' },
                        { value: 'devanahalli', label: 'Devanahalli' },
                        { value: 'hebbal', label: 'Hebbal' },
                        { value: 'ivc road', label: 'IVC Road' },
                    ],
                },
            },
            budget_ranges: [
                { value: '50L-1.5CR', label: '₹50 Lac - ₹1.5 Cr', min: 50, max: 150 },
                { value: '1.5CR-2.0CR', label: '₹1.5 Cr - ₹2.0 Cr', min: 150, max: 200 },
                { value: '2.0CR-2.5CR', label: '₹2.0 Cr - ₹2.5 Cr', min: 200, max: 250 },
                { value: '2.5CR-3.0CR', label: '₹2.5 Cr - ₹3.0 Cr', min: 250, max: 300 },
                { value: '3.0CR-4.0CR', label: '₹3.0 Cr - ₹4.0 Cr', min: 300, max: 400 },
                { value: '4.0CR-5.0CR', label: '₹4.0 Cr - ₹5.0 Cr', min: 400, max: 500 },
                { value: 'ABOVE-5CR', label: 'Above ₹5 Cr', min: 500, max: null },
            ],
            possession_years: [
                { value: 'ready', label: 'Ready To Move In' },
                { value: '2025', label: '2025' },
                { value: '2026', label: '2026' },
                { value: '2027', label: '2027' },
                { value: '2028', label: '2028' },
                { value: '2029', label: '2029' },
                { value: '2030', label: '2030' },
            ],
        };
    }

    // Send query with filters (Updated to use structured payload)
    async sendQueryWithFilters(
        query: string,
        filters: SelectedFilters,
        userId?: string,
        sessionId?: string
    ): Promise<ChatQueryResponse> {
        return this.sendQuery({
            query: query.trim(),
            user_id: userId,
            session_id: sessionId,
            filters: filters,
        });
    }

    // Project endpoints
    async getProjects(userId: string = 'guest'): Promise<ProjectInfo[]> {
        try {
            const response = await this.client.get<ProjectInfo[]>('/api/projects', {
                params: { user_id: userId }
            });
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

