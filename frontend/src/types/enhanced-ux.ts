// Phase 2 Enhanced UX Types

export interface ProactiveNudge {
    type: 'repeat_views' | 'location_focus' | 'budget_concern' | 'decision_ready' | 'long_session' | 'abandoned_interest';
    message: string;
    action?: 'schedule_visit' | 'show_alternatives' | 'take_break' | 'contact_rm';
    priority: 'high' | 'medium' | 'low';
}

export interface UrgencySignal {
    type: 'low_inventory' | 'price_increase' | 'high_demand' | 'time_limited_offer' | 'seasonal';
    message: string;
    priority_score: number;
    icon?: string;
}

export interface SentimentData {
    sentiment: 'excited' | 'positive' | 'neutral' | 'negative' | 'frustrated';
    frustration_score: number; // 0-10
    escalation_recommended: boolean;
    escalation_reason?: string;
    confidence: number; // 0-1
}

export interface UserProfileData {
    is_returning_user: boolean;
    last_visit_date?: string;
    viewed_projects_count?: number;
    interests?: string[];
    lead_score?: 'hot' | 'warm' | 'cold';
}
