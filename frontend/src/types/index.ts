// API Request/Response Types

export interface SourceInfo {
    document_name: string;
    chunk_id: string;
    source_type: 'brochure' | 'price_list' | 'spec_sheet' | 'website' | 'excel_metadata';
    page_number?: number;
    similarity_score: number;
    content_preview: string;
}

export interface RMDetails {
    name?: string;
    contact?: string;
}

export interface PriceRange {
    min?: number;
    max?: number;
    min_display?: string;
    max_display?: string;
}

export interface ProjectInfo {
    id: string;
    name: string;
    developer: string;
    location?: string;
    status?: string;
    project_id?: string;
    project_name?: string;
    developer_name?: string;
    zone?: string;
    city?: string;
    locality?: string;
    possession_year?: string | number;
    possession_quarter?: string;
    configuration?: string;
    config_summary?: string;
    price_range?: PriceRange | string;
    description?: string;
    amenities?: string;
    highlights?: string;
    usp?: string | string[];
    rera_number?: string;
    brochure_url?: string;
    brochure_link?: string;
    image_url?: string;
    rm_details?: RMDetails;
    rm_contact?: string;
    registration_process?: string;
    total_land_area?: string;
    towers?: string;
    floors?: string;
    location_link?: string;
    can_expand?: boolean;
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
    session_id?: string;
    persona?: string;
    filters?: any; // SelectedFilters type to be imported if needed, or loose coupling
}

export interface CoachingPrompt {
    type: string;
    priority: 'low' | 'medium' | 'high' | 'critical';
    message: string;
    suggested_script?: string;
}

export interface ChatQueryResponse {
    answer: string | string[];  // Can be string or array of bullets (CopilotResponse format)
    confidence: ConfidenceLevel;
    sources: SourceInfo[];
    intent: IntentType;
    is_refusal: boolean;
    refusal_reason?: string;
    response_time_ms: number;
    hallucination_risk?: boolean;
    suggested_actions?: string[];
    projects?: any[];
    // Phase 2: Enhanced UX data
    nudge?: import('./enhanced-ux').ProactiveNudge;
    urgency_signals?: import('./enhanced-ux').UrgencySignal[];
    sentiment?: import('./enhanced-ux').SentimentData;
    user_profile?: import('./enhanced-ux').UserProfileData;
    // Phase 3: Sales Coaching
    coaching_prompt?: CoachingPrompt;
    coaching_point?: string;  // CopilotResponse format
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
    // NEW: Answer bullets array (for CopilotResponse format)
    answer_bullets?: string[];
    // Phase 2: Enhanced UX data
    nudge?: import('./enhanced-ux').ProactiveNudge;
    urgency_signals?: import('./enhanced-ux').UrgencySignal[];
    sentiment?: import('./enhanced-ux').SentimentData;
    user_profile?: import('./enhanced-ux').UserProfileData;
    // Phase 3: Sales Coaching
    coaching_prompt?: CoachingPrompt;
    coaching_point?: string;
    // NEW: Live call structure
    live_call_structure?: LiveCallStructure;
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

// === Copilot Spec-Compliant Types ===

export interface QuickFilters {
    price_range?: [number, number];  // [min, max] in INR
    bhk?: string[];  // ["2BHK", "3BHK"]
    status?: string[];  // ["Ready-to-move", "Under Construction"]
    amenities?: string[];  // ["Pool", "Clubhouse", "Gym"]
    radius_km?: number;
    possession_window?: number;  // Year, e.g., 2027
}

export interface AssistRequest {
    call_id: string;
    query: string;
    filters?: QuickFilters;
}

export interface MatchingUnit {
    bhk: number;
    price_cr: number;
    price_lakhs: number;
    sqft_range?: string;
}

export interface CopilotProjectInfo {
    name: string;
    location: string;
    price_range: string;  // "70L - 1.3Cr"
    bhk: string;  // "2BHK, 3BHK"
    amenities: string[];
    status: string;  // "Ready-to-move" / "Under Construction"

    // NEW: Critical missing fields from backend
    brochure_url?: string;
    rm_details?: RMDetails;  // {name, contact}
    registration_process?: string;  // Markdown formatted
    zone?: string;  // "East Bangalore", "North Bangalore"
    rera_number?: string;
    developer?: string;
    possession_year?: number;
    possession_quarter?: string;  // "Q1", "Q2", "Q3", "Q4"

    // NEW: Configuration-level filtering transparency
    matching_units?: MatchingUnit[];  // Which configs match search
}

export interface LiveCallStructure {
    situation_reframe: string;
    consultant_questions: string[];
    recommended_next_step?: string;
    pushback_handling?: Record<string, string>;
    closing_summary: string;
    post_call_message: string;
}

export interface CopilotResponse {
    projects: CopilotProjectInfo[];
    answer: string[];  // 3-5 bullet points
    pitch_help: string;  // Single call-ready sentence
    next_suggestion: string;  // One-line action
    coaching_point: string;  // NEW: Real-time sales coaching (mandatory)
    live_call_structure?: LiveCallStructure;  // NEW: 6-part structure for live calls

    // Extended fields for budget relaxation
    relaxation_applied?: boolean;
    relaxation_step?: number;
    original_budget?: number;
    relaxed_budget?: number;
}
