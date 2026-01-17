// Scheduling Types

export interface ScheduleVisitRequest {
    user_id: string;
    session_id?: string;
    project_id: string;
    project_name: string;
    contact_name: string;
    contact_phone: string;
    contact_email?: string;
    requested_date?: string; // ISO format: YYYY-MM-DD
    requested_time_slot?: 'morning' | 'afternoon' | 'evening';
    user_notes?: string;
}

export interface ScheduleVisitResponse {
    success: boolean;
    visit_id?: string;
    status?: string;
    message: string;
    details?: {
        date: string;
        time_slot: string;
        rm_name: string;
        rm_phone: string;
        confirmation_sent: boolean;
        calendar_invite_sent: boolean;
        reminders_scheduled: number;
    };
    alternative_slots?: string[];
    alternative_dates?: string[];
    reason?: string;
}

export interface CallbackRequest {
    user_id: string;
    session_id?: string;
    contact_name: string;
    contact_phone: string;
    contact_email?: string;
    callback_reason: string;
    user_notes?: string;
    urgency_level?: 'low' | 'medium' | 'high' | 'urgent';
}

export interface CallbackResponse {
    success: boolean;
    callback_id?: string;
    status?: string;
    message: string;
    details?: {
        agent_name: string;
        expected_callback: string;
        urgency: string;
        confirmation_sent: boolean;
    };
}

export interface VisitInfo {
    id: string;
    project_name: string;
    requested_date: string;
    requested_time_slot: string;
    status: 'pending' | 'confirmed' | 'completed' | 'cancelled';
    assigned_rm: string;
    assigned_rm_phone: string;
}

export interface CallbackInfo {
    id: string;
    callback_reason: string;
    status: 'pending' | 'contacted' | 'completed' | 'no_answer';
    assigned_agent: string;
    urgency_level: string;
    created_at: string;
}
