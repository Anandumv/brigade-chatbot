-- User Profiles Schema
-- Stores persistent user data across sessions for personalization and memory

-- Create user_profiles table
CREATE TABLE IF NOT EXISTS user_profiles (
    -- Identity
    user_id TEXT PRIMARY KEY,
    name TEXT,
    phone TEXT,
    email TEXT,
    
    -- Preferences (JSON for flexibility)
    budget_min INTEGER,  -- In lakhs
    budget_max INTEGER,  -- In lakhs
    preferred_configurations JSONB DEFAULT '[]',  -- ["2BHK", "3BHK"]
    preferred_locations JSONB DEFAULT '[]',       -- ["Whitefield", "Sarjapur"]
    must_have_amenities JSONB DEFAULT '[]',       -- ["gym", "pool", "clubhouse"]
    avoided_amenities JSONB DEFAULT '[]',         -- ["construction noise"]
    
    -- Interaction History
    total_sessions INTEGER DEFAULT 0,
    properties_viewed JSONB DEFAULT '[]',         -- [{id, name, viewed_at, view_count}]
    properties_rejected JSONB DEFAULT '[]',       -- [{id, name, reason, rejected_at}]
    interested_projects JSONB DEFAULT '[]',       -- [{id, name, interest_level, marked_at}]
    objections_history JSONB DEFAULT '[]',        -- [{type, count, last_raised_at}]
    
    -- Lead Scoring
    engagement_score FLOAT DEFAULT 0.0,      -- 0-10 scale
    intent_to_buy_score FLOAT DEFAULT 0.0,   -- 0-10 scale
    lead_temperature TEXT DEFAULT 'cold',     -- "hot", "warm", "cold"
    
    -- Sales Stage
    current_stage TEXT DEFAULT 'awareness',   -- awareness, consideration, decision, negotiation
    stage_history JSONB DEFAULT '[]',         -- [{stage, entered_at, exited_at}]
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW(),
    last_session_id TEXT,
    
    -- Analytics
    site_visits_scheduled INTEGER DEFAULT 0,
    site_visits_completed INTEGER DEFAULT 0,
    callbacks_requested INTEGER DEFAULT 0,
    callbacks_completed INTEGER DEFAULT 0,
    brochures_downloaded INTEGER DEFAULT 0,
    
    -- Sentiment Tracking
    sentiment_history JSONB DEFAULT '[]',     -- [{sentiment, frustration, timestamp}]
    avg_sentiment_score FLOAT DEFAULT 0.0,    -- -1 to 1
    
    -- Notes (for sales team)
    notes TEXT,
    tags JSONB DEFAULT '[]'                   -- ["serious_buyer", "price_sensitive", etc.]
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_user_profiles_last_active ON user_profiles(last_active);
CREATE INDEX IF NOT EXISTS idx_user_profiles_lead_temperature ON user_profiles(lead_temperature);
CREATE INDEX IF NOT EXISTS idx_user_profiles_current_stage ON user_profiles(current_stage);
CREATE INDEX IF NOT EXISTS idx_user_profiles_budget ON user_profiles(budget_min, budget_max);
CREATE INDEX IF NOT EXISTS idx_user_profiles_created_at ON user_profiles(created_at);

-- Create function to update last_active automatically
CREATE OR REPLACE FUNCTION update_user_profile_last_active()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_active = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto-updating last_active
DROP TRIGGER IF EXISTS trigger_update_user_profile_last_active ON user_profiles;
CREATE TRIGGER trigger_update_user_profile_last_active
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_user_profile_last_active();

-- Example queries for analytics

-- Get hot leads (high engagement, recent activity)
-- SELECT * FROM user_profiles 
-- WHERE lead_temperature = 'hot' 
-- AND last_active > NOW() - INTERVAL '7 days'
-- ORDER BY engagement_score DESC;

-- Get users stuck in consideration stage
-- SELECT * FROM user_profiles
-- WHERE current_stage = 'consideration'
-- AND last_active < NOW() - INTERVAL '3 days'
-- AND total_sessions >= 2;

-- Get users with high intent but no site visit
-- SELECT * FROM user_profiles
-- WHERE intent_to_buy_score > 7
-- AND site_visits_scheduled = 0
-- ORDER BY last_active DESC;
