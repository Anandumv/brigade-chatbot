// API Request/Response Types

export interface SourceInfo {
    document_name: string;
    chunk_id: string;
    source_type: 'brochure' | 'price_list' | 'spec_sheet' | 'website' | 'excel_metadata';
    page_number?: number;
    similarity_score: number;
    content_preview: string;
}

export interface ProjectInfo {
    id: string;
    name: string;
    developer: string;
    location?: string;
    status?: string;
}

export interface PersonaInfo {
    id: string;
    name: string;
    description: string;
    priorities: string[];
    concerns: string[];
}

export type ConfidenceLevel = 'High' | 'Medium' | 'Not Available';

export type IntentType = 'project_fact' | 'sales_pitch' | 'comparison' | 'unsupported';

export interface ChatQueryRequest {
    query: string;
    project_id?: string;
    user_id?: string;
    persona?: string;
    filters?: any; // SelectedFilters type to be imported if needed, or loose coupling
}

export interface ChatQueryResponse {
    answer: string;
    confidence: ConfidenceLevel;
    sources: SourceInfo[];
    intent: IntentType;
    is_refusal: boolean;
    refusal_reason?: string;
    response_time_ms: number;
    hallucination_risk?: boolean;
    suggested_actions?: string[];
    projects?: any[];
}

export interface CompareProjectsRequest {
    query: string;
    project_ids: string[];
    user_id?: string;
}

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    confidence?: ConfidenceLevel;
    sources?: SourceInfo[];
    intent?: IntentType;
    isRefusal?: boolean;
    refusalReason?: string;
    suggested_actions?: string[];
    isLoading?: boolean;
    projects?: any[];
}

export interface QueryAnalytics {
    total_queries: number;
    answered_queries: number;
    refused_queries: number;
    refusal_rate: number;
    avg_response_time_ms: number;
    top_intents: Record<string, number>;
    recent_refusals: RecentRefusal[];
}

export interface RecentRefusal {
    query: string;
    reason: string;
    timestamp: string;
}

export interface ConversationState {
    messages: Message[];
    isLoading: boolean;
    selectedProject: ProjectInfo | null;
    selectedPersona: PersonaInfo | null;
    error: string | null;
}
