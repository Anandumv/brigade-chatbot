-- =====================================================
-- REAL ESTATE CHATBOT - MULTI-COMPANY SCHEMA MIGRATION
-- =====================================================
-- Purpose: Add support for hundreds of real estate companies with structured filtering
-- Features: Pricing, location, possession, multi-developer support
-- Run: psql $DATABASE_URL -f schema_migration.sql
-- =====================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- 1. DEVELOPERS TABLE (Multi-Company Support)
-- =====================================================
-- Stores real estate companies (Brigade, Prestige, Sobha, etc.)

CREATE TABLE IF NOT EXISTS developers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    logo_url TEXT,
    website TEXT,
    headquarters TEXT,
    description TEXT,
    total_projects INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Sample data for Brigade Group
INSERT INTO developers (name, website, headquarters, description)
VALUES (
    'Brigade Group',
    'https://brigade.co.in',
    'Bangalore, Karnataka',
    'Leading real estate developer in South India with 300+ projects'
)
ON CONFLICT (name) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_developers_name ON developers(name);

-- =====================================================
-- 2. PROJECTS TABLE ENHANCEMENTS
-- =====================================================
-- Add developer relationship, location, and pricing metadata

-- Add developer_id column
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS developer_id UUID REFERENCES developers(id) ON DELETE CASCADE;

-- Add location columns
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS city TEXT,
ADD COLUMN IF NOT EXISTS locality TEXT,
ADD COLUMN IF NOT EXISTS area TEXT,
ADD COLUMN IF NOT EXISTS pincode TEXT;

-- Add pricing range columns (computed from unit_types)
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS min_price_inr NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS max_price_inr NUMERIC(15,2);

-- Add project metadata
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS total_units INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS available_units INTEGER,
ADD COLUMN IF NOT EXISTS launch_date DATE,
ADD COLUMN IF NOT EXISTS possession_start_year INTEGER,
ADD COLUMN IF NOT EXISTS possession_end_year INTEGER;

-- Create indexes for fast filtering
CREATE INDEX IF NOT EXISTS idx_projects_developer ON projects(developer_id);
CREATE INDEX IF NOT EXISTS idx_projects_city ON projects(city);
CREATE INDEX IF NOT EXISTS idx_projects_city_locality ON projects(city, locality);
CREATE INDEX IF NOT EXISTS idx_projects_price_range ON projects(min_price_inr, max_price_inr);
CREATE INDEX IF NOT EXISTS idx_projects_possession ON projects(possession_start_year);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- Update existing Brigade Citrine project with location data (if exists)
UPDATE projects
SET
    city = 'Bangalore',
    locality = 'Old Madras Road',
    area = 'East Bangalore',
    developer_id = (SELECT id FROM developers WHERE name = 'Brigade Group' LIMIT 1)
WHERE name ILIKE '%citrine%' AND developer_id IS NULL;

-- =====================================================
-- 3. UNIT_TYPES TABLE ENHANCEMENTS
-- =====================================================
-- Add pricing, possession, and configuration details

-- Add pricing columns
ALTER TABLE unit_types
ADD COLUMN IF NOT EXISTS base_price_inr NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS price_per_sqft NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS price_min_inr NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS price_max_inr NUMERIC(15,2);

-- Add possession columns
ALTER TABLE unit_types
ADD COLUMN IF NOT EXISTS possession_year INTEGER,
ADD COLUMN IF NOT EXISTS possession_quarter TEXT,
ADD COLUMN IF NOT EXISTS possession_month TEXT;

-- Add configuration metadata
ALTER TABLE unit_types
ADD COLUMN IF NOT EXISTS balconies INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS parking_slots INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS floor_range TEXT,
ADD COLUMN IF NOT EXISTS facing TEXT;

-- Add availability
ALTER TABLE unit_types
ADD COLUMN IF NOT EXISTS total_units INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS available_units INTEGER,
ADD COLUMN IF NOT EXISTS is_available BOOLEAN DEFAULT TRUE;

-- Create indexes for fast filtering
CREATE INDEX IF NOT EXISTS idx_unit_types_bedrooms ON unit_types(bedrooms);
CREATE INDEX IF NOT EXISTS idx_unit_types_price ON unit_types(base_price_inr);
CREATE INDEX IF NOT EXISTS idx_unit_types_price_range ON unit_types(price_min_inr, price_max_inr);
CREATE INDEX IF NOT EXISTS idx_unit_types_possession ON unit_types(possession_year);
CREATE INDEX IF NOT EXISTS idx_unit_types_project ON unit_types(project_id);
CREATE INDEX IF NOT EXISTS idx_unit_types_available ON unit_types(is_available);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_unit_types_bedrooms_price
ON unit_types(bedrooms, base_price_inr);

-- =====================================================
-- 4. AMENITIES TABLE
-- =====================================================
-- Store project amenities for filtering

CREATE TABLE IF NOT EXISTS amenities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_amenities_project ON amenities(project_id);
CREATE INDEX IF NOT EXISTS idx_amenities_category ON amenities(category);

-- =====================================================
-- 5. HELPER FUNCTIONS
-- =====================================================

-- Function to update project price range from unit_types
CREATE OR REPLACE FUNCTION update_project_price_range()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE projects
    SET
        min_price_inr = (
            SELECT MIN(base_price_inr)
            FROM unit_types
            WHERE project_id = NEW.project_id AND base_price_inr IS NOT NULL
        ),
        max_price_inr = (
            SELECT MAX(base_price_inr)
            FROM unit_types
            WHERE project_id = NEW.project_id AND base_price_inr IS NOT NULL
        ),
        updated_at = NOW()
    WHERE id = NEW.project_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update project price range when unit_types change
DROP TRIGGER IF EXISTS trigger_update_project_price_range ON unit_types;
CREATE TRIGGER trigger_update_project_price_range
AFTER INSERT OR UPDATE OF base_price_inr ON unit_types
FOR EACH ROW
EXECUTE FUNCTION update_project_price_range();

-- Function to update developer project count
CREATE OR REPLACE FUNCTION update_developer_project_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE developers
    SET
        total_projects = (
            SELECT COUNT(*)
            FROM projects
            WHERE developer_id = NEW.developer_id
        ),
        updated_at = NOW()
    WHERE id = NEW.developer_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update developer project count
DROP TRIGGER IF EXISTS trigger_update_developer_project_count ON projects;
CREATE TRIGGER trigger_update_developer_project_count
AFTER INSERT OR UPDATE OF developer_id ON projects
FOR EACH ROW
WHEN (NEW.developer_id IS NOT NULL)
EXECUTE FUNCTION update_developer_project_count();

-- =====================================================
-- 6. MATERIALIZED VIEW FOR FAST SEARCHES
-- =====================================================
-- Pre-joined view for common filtering queries

CREATE MATERIALIZED VIEW IF NOT EXISTS project_units_view AS
SELECT
    ut.id AS unit_id,
    ut.project_id,
    p.name AS project_name,
    p.location AS project_location,
    p.city,
    p.locality,
    p.area,
    p.status AS project_status,
    p.rera_number,
    d.id AS developer_id,
    d.name AS developer_name,
    ut.type_name,
    ut.bedrooms,
    ut.toilets,
    ut.balconies,
    ut.base_price_inr,
    ut.price_per_sqft,
    ut.carpet_area_sqft,
    ut.super_builtup_area_sqm,
    ut.possession_year,
    ut.possession_quarter,
    ut.is_available,
    ut.available_units
FROM unit_types ut
JOIN projects p ON ut.project_id = p.id
LEFT JOIN developers d ON p.developer_id = d.id
WHERE ut.is_available = TRUE;

-- Indexes on materialized view for ultra-fast filtering
CREATE INDEX IF NOT EXISTS idx_mv_bedrooms_price
ON project_units_view(bedrooms, base_price_inr);

CREATE INDEX IF NOT EXISTS idx_mv_city_locality
ON project_units_view(city, locality);

CREATE INDEX IF NOT EXISTS idx_mv_developer
ON project_units_view(developer_id);

CREATE INDEX IF NOT EXISTS idx_mv_possession
ON project_units_view(possession_year);

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_project_units_view()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY project_units_view;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 7. SAMPLE QUERY EXAMPLES
-- =====================================================

-- Example 1: Find 2BHK units under 3 crores in Bangalore
-- SELECT * FROM project_units_view
-- WHERE bedrooms = 2
--   AND base_price_inr <= 30000000
--   AND city = 'Bangalore'
-- ORDER BY base_price_inr ASC
-- LIMIT 50;

-- Example 2: Find 3BHK ready-to-move units in Whitefield under 5 crores
-- SELECT * FROM project_units_view
-- WHERE bedrooms = 3
--   AND base_price_inr <= 50000000
--   AND locality = 'Whitefield'
--   AND project_status = 'completed'
-- ORDER BY base_price_inr ASC;

-- Example 3: Find all units with possession in 2027
-- SELECT * FROM project_units_view
-- WHERE possession_year = 2027
-- GROUP BY project_id, project_name
-- ORDER BY developer_name, project_name;

-- =====================================================
-- 8. DATA VALIDATION CONSTRAINTS
-- =====================================================

-- Ensure price consistency
ALTER TABLE unit_types
ADD CONSTRAINT check_price_positive
CHECK (base_price_inr IS NULL OR base_price_inr > 0);

ALTER TABLE unit_types
ADD CONSTRAINT check_price_range
CHECK (
    (price_min_inr IS NULL AND price_max_inr IS NULL) OR
    (price_min_inr IS NOT NULL AND price_max_inr IS NOT NULL AND price_min_inr <= price_max_inr)
);

-- Ensure possession year is reasonable
ALTER TABLE unit_types
ADD CONSTRAINT check_possession_year
CHECK (possession_year IS NULL OR (possession_year >= 2020 AND possession_year <= 2050));

-- Ensure bedroom count is reasonable
ALTER TABLE unit_types
ADD CONSTRAINT check_bedrooms
CHECK (bedrooms IS NULL OR (bedrooms >= 0 AND bedrooms <= 10));

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================

-- Verify migration success
DO $$
DECLARE
    developer_count INTEGER;
    projects_with_developer INTEGER;
BEGIN
    SELECT COUNT(*) INTO developer_count FROM developers;
    SELECT COUNT(*) INTO projects_with_developer FROM projects WHERE developer_id IS NOT NULL;

    RAISE NOTICE '========================================';
    RAISE NOTICE 'MIGRATION COMPLETE';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Developers in database: %', developer_count;
    RAISE NOTICE 'Projects linked to developers: %', projects_with_developer;
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Next Steps:';
    RAISE NOTICE '1. Run: python backend/scripts/extract_structured_data.py';
    RAISE NOTICE '2. Refresh materialized view: SELECT refresh_project_units_view();';
    RAISE NOTICE '3. Test filtered search endpoint';
    RAISE NOTICE '========================================';
END $$;
