import axios, { AxiosInstance } from 'axios';
import {
    ScheduleVisitRequest,
    ScheduleVisitResponse,
    CallbackRequest,
    CallbackResponse,
    VisitInfo,
    CallbackInfo,
} from '@/types/scheduling';

class SchedulingApiService {
    private client: AxiosInstance;

    constructor() {
        this.client = axios.create({
            baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
            headers: {
                'Content-Type': 'application/json',
            },
            timeout: 30000,
        });
    }

    // Schedule a site visit
    async scheduleVisit(request: ScheduleVisitRequest): Promise<ScheduleVisitResponse> {
        try {
            const response = await this.client.post<ScheduleVisitResponse>('/api/schedule/site-visit', request);
            return response.data;
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Failed to schedule visit');
        }
    }

    // Request a callback
    async requestCallback(request: CallbackRequest): Promise<CallbackResponse> {
        try {
            const response = await this.client.post<CallbackResponse>('/api/schedule/callback', request);
            return response.data;
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Failed to request callback');
        }
    }

    // Get user's scheduled visits
    async getUserVisits(userId: string): Promise<VisitInfo[]> {
        try {
            const response = await this.client.get<any>(`/api/schedule/user/${userId}`);
            return response.data.site_visits || [];
        } catch (error) {
            console.warn('Failed to fetch user visits');
            return [];
        }
    }

    // Get user's callbacks
    async getUserCallbacks(userId: string): Promise<CallbackInfo[]> {
        try {
            const response = await this.client.get<any>(`/api/schedule/user/${userId}`);
            return response.data.callbacks || [];
        } catch (error) {
            console.warn('Failed to fetch user callbacks');
            return [];
        }
    }

    // Admin: Get all visits
    async getAllVisits(): Promise<VisitInfo[]> {
        try {
            const response = await this.client.get<any>('/api/admin/schedule/visits');
            return response.data.visits || [];
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Failed to fetch visits');
        }
    }

    // Admin: Get all callbacks
    async getAllCallbacks(): Promise<CallbackInfo[]> {
        try {
            const response = await this.client.get<any>('/api/admin/schedule/callbacks');
            return response.data.callbacks || [];
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Failed to fetch callbacks');
        }
    }

    // Admin: Update visit status
    async updateVisitStatus(visitId: string, status: string, notes?: string): Promise<void> {
        try {
            await this.client.put(`/api/admin/schedule/visit/${visitId}/status`, { status, notes });
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Failed to update visit status');
        }
    }

    // Admin: Update callback status
    async updateCallbackStatus(
        callbackId: string,
        status: string,
        notes?: string,
        callDuration?: number
    ): Promise<void> {
        try {
            await this.client.put(`/api/admin/schedule/callback/${callbackId}/status`, {
                status,
                notes,
                call_duration: callDuration,
            });
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Failed to update callback status');
        }
    }
}

export const schedulingApi = new SchedulingApiService();
export default schedulingApi;
