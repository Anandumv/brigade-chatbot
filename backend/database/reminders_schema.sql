-- Reminders Schema
-- Stores scheduled reminders for site visits and callbacks

-- Create reminders table
CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    
    -- Type and channel
    reminder_type TEXT NOT NULL,  -- 'visit_24h_before', 'visit_1h_before', 'callback_pending', 'followup'
    channel TEXT NOT NULL,  -- 'email', 'sms', 'whatsapp', 'push_notification'
    
    -- Target user
    user_id TEXT NOT NULL,
    user_name TEXT,
    user_contact TEXT NOT NULL,  -- email or phone
    
    -- Related entity
    related_type TEXT,  -- 'visit' or 'callback'
    related_id TEXT,  -- visit_id or callback_id
    
    -- Scheduling
    scheduled_time TIMESTAMP NOT NULL,
    sent_at TIMESTAMP,
    status TEXT DEFAULT 'scheduled',  -- 'scheduled', 'sent', 'failed', 'cancelled'
    
    -- Content
    subject TEXT,
    message TEXT NOT NULL,
    
    -- Tracking
    created_at TIMESTAMP DEFAULT NOW(),
    attempts INTEGER DEFAULT 0,
    last_error TEXT
);

-- Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);
CREATE INDEX IF NOT EXISTS idx_reminders_scheduled_time ON reminders(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_reminders_related ON reminders(related_type, related_id);
CREATE INDEX IF NOT EXISTS idx_reminders_type ON reminders(reminder_type);

-- Query examples:

-- Get pending reminders that are due
-- SELECT * FROM reminders 
-- WHERE status = 'scheduled' 
-- AND scheduled_time <= NOW()
-- ORDER BY scheduled_time;

-- Get reminders for a specific visit
-- SELECT * FROM reminders
-- WHERE related_type = 'visit'
-- AND related_id = 'visit_000001';

-- Get all reminders for a user
-- SELECT * FROM reminders
-- WHERE user_id = 'user_123'
-- ORDER BY scheduled_time DESC;
