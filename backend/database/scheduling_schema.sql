-- Scheduling Schema
-- Tracks site visit and callback requests from users

-- Create scheduled_visits table
CREATE TABLE IF NOT EXISTS scheduled_visits (
    id SERIAL PRIMARY KEY,
    
    -- User Information
    user_id TEXT NOT NULL,
    session_id TEXT,
    
    -- Visit Details
    visit_type TEXT NOT NULL,  -- 'site_visit' or 'callback'
    project_id TEXT,
    project_name TEXT,
    
    -- Scheduling
    requested_date DATE,
    requested_time_slot TEXT,  -- 'morning' (9-12), 'afternoon' (12-3), 'evening' (3-6)
    preferred_date DATE,
    preferred_time TIME,
    status TEXT DEFAULT 'pending',  -- 'pending', 'confirmed', 'completed', 'cancelled', 'no_show'
    
    -- Contact Details
    contact_name TEXT,
    contact_phone TEXT NOT NULL,
    contact_email TEXT,
    
    -- Assignment
    assigned_rm TEXT,  -- Relationship Manager assigned
    assigned_rm_phone TEXT,
    
    -- Notes
    user_notes TEXT,  -- User's specific requests/questions
    rm_notes TEXT,    -- RM's notes after contact
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    confirmed_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    
    -- Metadata
    source TEXT,  -- 'proactive_nudge', 'coaching_prompt', 'user_request'
    lead_score_at_request FLOAT,  -- User's lead score when requested
    conversion_probability FLOAT,  -- Predicted conversion likelihood
    
    -- Reminders
    reminder_sent BOOLEAN DEFAULT FALSE,
    reminder_sent_at TIMESTAMP,
    
    -- Feedback
    user_feedback_rating INTEGER,  -- 1-5 stars
    user_feedback_text TEXT
);

-- Create callbacks table (for general callbacks, not tied to specific project)
CREATE TABLE IF NOT EXISTS callbacks (
    id SERIAL PRIMARY KEY,
    
    -- User Information
    user_id TEXT NOT NULL,
    session_id TEXT,
    
    -- Contact Details
    contact_name TEXT,
    contact_phone TEXT NOT NULL,
    contact_email TEXT,
    
    -- Scheduling
    requested_time TEXT,  -- 'asap', 'morning', 'afternoon', 'evening', 'specific_time'
    preferred_date DATE,
    preferred_time TIME,
    status TEXT DEFAULT 'pending',  -- 'pending', 'contacted', 'completed', 'no_answer', 'cancelled'
    
    -- Purpose
    callback_reason TEXT,  -- 'general_inquiry', 'budget_discussion', 'project_details', 'documentation', 'other'
    user_notes TEXT,
    
    -- Assignment
    assigned_agent TEXT,
    assigned_agent_phone TEXT,
    
    -- Call Details
    call_attempts INTEGER DEFAULT 0,
    last_call_attempt TIMESTAMP,
    contacted_at TIMESTAMP,
    call_duration_seconds INTEGER,
    call_outcome TEXT,  -- 'successful', 'no_answer', 'busy', 'wrong_number'
    
    -- Notes
    agent_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    
    -- Metadata
    source TEXT,
    lead_score_at_request FLOAT,
    urgency_level TEXT DEFAULT 'medium'  -- 'low', 'medium', 'high', 'urgent'
);

-- Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_scheduled_visits_user_id ON scheduled_visits(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_visits_status ON scheduled_visits(status);
CREATE INDEX IF NOT EXISTS idx_scheduled_visits_requested_date ON scheduled_visits(requested_date);
CREATE INDEX IF NOT EXISTS idx_scheduled_visits_assigned_rm ON scheduled_visits(assigned_rm);
CREATE INDEX IF NOT EXISTS idx_scheduled_visits_created_at ON scheduled_visits(created_at);
CREATE INDEX IF NOT EXISTS idx_scheduled_visits_project_id ON scheduled_visits(project_id);

CREATE INDEX IF NOT EXISTS idx_callbacks_user_id ON callbacks(user_id);
CREATE INDEX IF NOT EXISTS idx_callbacks_status ON callbacks(status);
CREATE INDEX IF NOT EXISTS idx_callbacks_urgency ON callbacks(urgency_level);
CREATE INDEX IF NOT EXISTS idx_callbacks_assigned_agent ON callbacks(assigned_agent);
CREATE INDEX IF NOT EXISTS idx_callbacks_created_at ON callbacks(created_at);

-- Create trigger for auto-updating updated_at
CREATE OR REPLACE FUNCTION update_scheduling_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_scheduled_visits_updated_at ON scheduled_visits;
CREATE TRIGGER trigger_update_scheduled_visits_updated_at
    BEFORE UPDATE ON scheduled_visits
    FOR EACH ROW
    EXECUTE FUNCTION update_scheduling_updated_at();

DROP TRIGGER IF EXISTS trigger_update_callbacks_updated_at ON callbacks;
CREATE TRIGGER trigger_update_callbacks_updated_at
    BEFORE UPDATE ON callbacks
    FOR EACH ROW
    EXECUTE FUNCTION update_scheduling_updated_at();

-- Example queries for sales team

-- Get today's scheduled visits
-- SELECT * FROM scheduled_visits 
-- WHERE requested_date = CURRENT_DATE 
-- AND status IN ('pending', 'confirmed')
-- ORDER BY requested_time_slot;

-- Get pending callbacks (urgent first)
-- SELECT * FROM callbacks 
-- WHERE status = 'pending'
-- ORDER BY 
--   CASE urgency_level 
--     WHEN 'urgent' THEN 1 
--     WHEN 'high' THEN 2 
--     WHEN 'medium' THEN 3 
--     ELSE 4 
--   END,
--   created_at;

-- Get RM workload
-- SELECT assigned_rm, COUNT(*) as visit_count
-- FROM scheduled_visits
-- WHERE status IN ('pending', 'confirmed')
-- AND requested_date >= CURRENT_DATE
-- GROUP BY assigned_rm
-- ORDER BY visit_count DESC;

-- Get conversion rate by source
-- SELECT source, 
--        COUNT(*) as total,
--        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
--        ROUND(100.0 * SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) as completion_rate
-- FROM scheduled_visits
-- GROUP BY source;
