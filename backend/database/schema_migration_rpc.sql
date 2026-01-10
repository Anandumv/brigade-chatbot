-- =====================================================
-- RPC FUNCTIONS FOR HYBRID RETRIEVAL
-- =====================================================
-- Purpose: Provide stored procedures for filtered searches
-- =====================================================

-- Function for executing filtered unit searches
-- This allows parameterized queries from the application layer
CREATE OR REPLACE FUNCTION execute_filtered_search(
    p_bedrooms INTEGER[] DEFAULT NULL,
    p_max_price NUMERIC DEFAULT NULL,
    p_min_price NUMERIC DEFAULT NULL,
    p_city TEXT DEFAULT NULL,
    p_locality TEXT DEFAULT NULL,
    p_possession_year INTEGER DEFAULT NULL,
    p_status TEXT[] DEFAULT NULL,
    p_developer_name TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 100
)
RETURNS TABLE (
    unit_id UUID,
    project_id UUID,
    project_name TEXT,
    project_location TEXT,
    city TEXT,
    locality TEXT,
    project_status TEXT,
    rera_number TEXT,
    developer_id UUID,
    developer_name TEXT,
    type_name TEXT,
    bedrooms INTEGER,
    toilets INTEGER,
    balconies INTEGER,
    base_price_inr NUMERIC,
    price_per_sqft NUMERIC,
    carpet_area_sqft NUMERIC,
    super_builtup_area_sqm NUMERIC,
    possession_year INTEGER,
    possession_quarter TEXT,
    available_units INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        pv.unit_id,
        pv.project_id,
        pv.project_name,
        pv.project_location,
        pv.city,
        pv.locality,
        pv.project_status,
        pv.rera_number,
        pv.developer_id,
        pv.developer_name,
        pv.type_name,
        pv.bedrooms,
        pv.toilets,
        pv.balconies,
        pv.base_price_inr,
        pv.price_per_sqft,
        pv.carpet_area_sqft,
        pv.super_builtup_area_sqm,
        pv.possession_year,
        pv.possession_quarter,
        pv.available_units
    FROM project_units_view pv
    WHERE
        (p_bedrooms IS NULL OR pv.bedrooms = ANY(p_bedrooms))
        AND (p_max_price IS NULL OR pv.base_price_inr <= p_max_price)
        AND (p_min_price IS NULL OR pv.base_price_inr >= p_min_price)
        AND (p_city IS NULL OR LOWER(pv.city) = LOWER(p_city))
        AND (p_locality IS NULL OR LOWER(pv.locality) = LOWER(p_locality))
        AND (p_possession_year IS NULL OR pv.possession_year = p_possession_year)
        AND (p_status IS NULL OR pv.project_status = ANY(p_status))
        AND (p_developer_name IS NULL OR LOWER(pv.developer_name) LIKE LOWER('%' || p_developer_name || '%'))
    ORDER BY pv.base_price_inr ASC
    LIMIT p_limit;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION execute_filtered_search TO anon, authenticated;

-- =====================================================
-- HELPER FUNCTION: Get project summary statistics
-- =====================================================
CREATE OR REPLACE FUNCTION get_project_summary(p_project_id UUID)
RETURNS TABLE (
    project_id UUID,
    project_name TEXT,
    developer_name TEXT,
    total_unit_types INTEGER,
    min_price_inr NUMERIC,
    max_price_inr NUMERIC,
    min_bedrooms INTEGER,
    max_bedrooms INTEGER,
    possession_years INTEGER[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        pv.project_id,
        pv.project_name,
        pv.developer_name,
        COUNT(DISTINCT pv.unit_id)::INTEGER AS total_unit_types,
        MIN(pv.base_price_inr) AS min_price_inr,
        MAX(pv.base_price_inr) AS max_price_inr,
        MIN(pv.bedrooms) AS min_bedrooms,
        MAX(pv.bedrooms) AS max_bedrooms,
        ARRAY_AGG(DISTINCT pv.possession_year ORDER BY pv.possession_year) AS possession_years
    FROM project_units_view pv
    WHERE pv.project_id = p_project_id
    GROUP BY pv.project_id, pv.project_name, pv.developer_name;
END;
$$;

GRANT EXECUTE ON FUNCTION get_project_summary TO anon, authenticated;

-- =====================================================
-- HELPER FUNCTION: Get available developers
-- =====================================================
CREATE OR REPLACE FUNCTION get_active_developers()
RETURNS TABLE (
    developer_id UUID,
    developer_name TEXT,
    total_projects INTEGER,
    min_price_inr NUMERIC,
    max_price_inr NUMERIC
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id AS developer_id,
        d.name AS developer_name,
        COUNT(DISTINCT p.id)::INTEGER AS total_projects,
        MIN(p.min_price_inr) AS min_price_inr,
        MAX(p.max_price_inr) AS max_price_inr
    FROM developers d
    JOIN projects p ON d.id = p.developer_id
    WHERE p.status != 'archived'
    GROUP BY d.id, d.name
    ORDER BY d.name;
END;
$$;

GRANT EXECUTE ON FUNCTION get_active_developers TO anon, authenticated;

-- =====================================================
-- Verification
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'RPC FUNCTIONS CREATED';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Available functions:';
    RAISE NOTICE '- execute_filtered_search(...)';
    RAISE NOTICE '- get_project_summary(project_id)';
    RAISE NOTICE '- get_active_developers()';
    RAISE NOTICE '========================================';
END $$;
