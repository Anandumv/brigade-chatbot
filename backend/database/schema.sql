-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Create custom types
CREATE TYPE project_status AS ENUM ('upcoming', 'ongoing', 'completed');
CREATE TYPE document_type AS ENUM ('brochure', 'pricing', 'legal', 'faq', 'specification');
CREATE TYPE source_type AS ENUM ('internal', 'external');
CREATE TYPE query_intent AS ENUM ('project_fact', 'sales_pitch', 'comparison', 'unsupported');
CREATE TYPE user_role AS ENUM ('sales_rep', 'manager', 'admin');
CREATE TYPE source_category AS ENUM ('rera', 'govt', 'maps', 'third_party');

-- Projects table
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    status project_status NOT NULL DEFAULT 'ongoing',
    rera_number TEXT,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    type document_type NOT NULL,
    version TEXT DEFAULT '1.0',
    file_path TEXT NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    uploaded_by UUID REFERENCES auth.users(id)
);

-- Document chunks table (core table for RAG)
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI text-embedding-3-small dimensions
    section TEXT,  -- e.g., "Page 5: Amenities"
    source_type source_type NOT NULL DEFAULT 'internal',
    confidence_weight FLOAT NOT NULL DEFAULT 1.0,
    chunk_index INTEGER NOT NULL,
    metadata JSONB,  -- Additional metadata (page number, document section, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create vector index for similarity search (using IVFFlat for performance)
CREATE INDEX document_chunks_embedding_idx ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create standard indexes
CREATE INDEX idx_chunks_project ON document_chunks(project_id);
CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_source_type ON document_chunks(source_type);

-- Approved external sources table
CREATE TABLE approved_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    url TEXT,
    type source_category NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_verified TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Query logs table for analytics and audit trail
CREATE TABLE query_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    query TEXT NOT NULL,
    intent query_intent,
    answered BOOLEAN NOT NULL,
    refusal_reason TEXT,
    response_time_ms INTEGER,
    confidence_score TEXT,  -- 'High', 'Medium', 'Not Available'
    project_id UUID REFERENCES projects(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on query logs for analytics
CREATE INDEX idx_query_logs_user ON query_logs(user_id);
CREATE INDEX idx_query_logs_created_at ON query_logs(created_at DESC);
CREATE INDEX idx_query_logs_answered ON query_logs(answered);

-- User profiles table (extends Supabase auth.users)
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    role user_role NOT NULL DEFAULT 'sales_rep',
    project_access JSONB DEFAULT '[]'::jsonb,  -- Array of project UUIDs
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Unit types table for structured data (pricing, specifications)
CREATE TABLE unit_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type_name TEXT NOT NULL,  -- e.g., "3BED + 3TOILET - TYPE 5"
    bedrooms INTEGER,
    toilets INTEGER,
    has_study BOOLEAN DEFAULT FALSE,
    super_builtup_area_sqm NUMERIC(10,2),
    super_builtup_area_sqft NUMERIC(10,2),
    carpet_area_sqm NUMERIC(10,2),
    carpet_area_sqft NUMERIC(10,2),
    balcony_area_sqm NUMERIC(10,2),
    balcony_area_sqft NUMERIC(10,2),
    service_balcony_area_sqm NUMERIC(10,2),
    service_balcony_area_sqft NUMERIC(10,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_unit_types_project ON unit_types(project_id);

-- Row Level Security (RLS) Policies

-- Enable RLS on all tables
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE approved_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE unit_types ENABLE ROW LEVEL SECURITY;

-- Projects: Users can only see projects they have access to
CREATE POLICY "Users can view assigned projects"
ON projects FOR SELECT
USING (
    id IN (
        SELECT jsonb_array_elements_text(project_access)::uuid
        FROM user_profiles
        WHERE id = auth.uid()
    )
    OR
    EXISTS (
        SELECT 1 FROM user_profiles
        WHERE id = auth.uid() AND role = 'admin'
    )
);

-- Document chunks: Users can only query chunks from their assigned projects
CREATE POLICY "Users can query chunks from assigned projects"
ON document_chunks FOR SELECT
USING (
    project_id IN (
        SELECT jsonb_array_elements_text(project_access)::uuid
        FROM user_profiles
        WHERE id = auth.uid()
    )
    OR
    EXISTS (
        SELECT 1 FROM user_profiles
        WHERE id = auth.uid() AND role = 'admin'
    )
);

-- Documents: Users can view documents from their assigned projects
CREATE POLICY "Users can view documents from assigned projects"
ON documents FOR SELECT
USING (
    project_id IN (
        SELECT jsonb_array_elements_text(project_access)::uuid
        FROM user_profiles
        WHERE id = auth.uid()
    )
    OR
    EXISTS (
        SELECT 1 FROM user_profiles
        WHERE id = auth.uid() AND role = 'admin'
    )
);

-- Documents: Only admins can insert documents
CREATE POLICY "Only admins can insert documents"
ON documents FOR INSERT
WITH CHECK (
    EXISTS (
        SELECT 1 FROM user_profiles
        WHERE id = auth.uid() AND role = 'admin'
    )
);

-- Query logs: Users can only see their own logs, admins see all
CREATE POLICY "Users can view own query logs"
ON query_logs FOR SELECT
USING (
    user_id = auth.uid()
    OR
    EXISTS (
        SELECT 1 FROM user_profiles
        WHERE id = auth.uid() AND role = 'admin'
    )
);

-- Query logs: Users can insert their own logs
CREATE POLICY "Users can insert own query logs"
ON query_logs FOR INSERT
WITH CHECK (user_id = auth.uid());

-- User profiles: Users can view their own profile, admins view all
CREATE POLICY "Users can view own profile"
ON user_profiles FOR SELECT
USING (
    id = auth.uid()
    OR
    EXISTS (
        SELECT 1 FROM user_profiles
        WHERE id = auth.uid() AND role = 'admin'
    )
);

-- Approved sources: All authenticated users can view
CREATE POLICY "Authenticated users can view approved sources"
ON approved_sources FOR SELECT
TO authenticated
USING (is_active = TRUE);

-- Unit types: Users can view unit types from assigned projects
CREATE POLICY "Users can view unit types from assigned projects"
ON unit_types FOR SELECT
USING (
    project_id IN (
        SELECT jsonb_array_elements_text(project_access)::uuid
        FROM user_profiles
        WHERE id = auth.uid()
    )
    OR
    EXISTS (
        SELECT 1 FROM user_profiles
        WHERE id = auth.uid() AND role = 'admin'
    )
);

-- Functions

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for projects table
CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for user_profiles table
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function for vector similarity search
CREATE OR REPLACE FUNCTION search_similar_chunks(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.75,
    match_count int DEFAULT 5,
    filter_project_id uuid DEFAULT NULL,
    filter_source_type source_type DEFAULT NULL
)
RETURNS TABLE (
    chunk_id uuid,
    content text,
    section text,
    similarity float,
    project_name text,
    document_title text,
    metadata jsonb,
    confidence_weight float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id AS chunk_id,
        dc.content,
        dc.section,
        1 - (dc.embedding <=> query_embedding) AS similarity,
        p.name AS project_name,
        d.title AS document_title,
        dc.metadata,
        dc.confidence_weight
    FROM document_chunks dc
    JOIN projects p ON dc.project_id = p.id
    JOIN documents d ON dc.document_id = d.id
    WHERE
        (filter_project_id IS NULL OR dc.project_id = filter_project_id)
        AND (filter_source_type IS NULL OR dc.source_type = filter_source_type)
        AND (1 - (dc.embedding <=> query_embedding)) >= match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Insert sample approved sources
INSERT INTO approved_sources (name, url, type, is_active) VALUES
    ('Karnataka RERA', 'https://rera.karnataka.gov.in', 'rera', TRUE),
    ('Government of Karnataka', 'https://karnataka.gov.in', 'govt', TRUE);

COMMENT ON TABLE projects IS 'Real estate projects managed by Brigade Group';
COMMENT ON TABLE documents IS 'Project documents (brochures, specifications, etc.)';
COMMENT ON TABLE document_chunks IS 'Chunked document content with embeddings for RAG';
COMMENT ON TABLE approved_sources IS 'External sources approved for information retrieval';
COMMENT ON TABLE query_logs IS 'Audit trail of all user queries and system responses';
COMMENT ON TABLE user_profiles IS 'Extended user information beyond Supabase auth';
COMMENT ON TABLE unit_types IS 'Structured data for apartment unit specifications';
