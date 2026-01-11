-- FIXED: Cast project_status to text to avoid type mismatch
-- Run this in Supabase SQL Editor

DROP FUNCTION IF EXISTS execute_filtered_search;

CREATE OR REPLACE FUNCTION execute_filtered_search(
    p_bedrooms int[] DEFAULT NULL,
    p_min_price numeric DEFAULT NULL,
    p_max_price numeric DEFAULT NULL,
    p_city text DEFAULT NULL,
    p_locality text DEFAULT NULL,
    p_developer_name text DEFAULT NULL,
    p_status text[] DEFAULT NULL,
    p_possession_year int DEFAULT NULL,
    p_limit int DEFAULT 100
)
RETURNS TABLE (
    unit_id uuid, project_id uuid, project_name text, project_location text,
    city text, locality text, project_status text, developer_name text,
    type_name text, bedrooms int, base_price_inr numeric, carpet_area_sqft numeric,
    possession_year int, is_available boolean
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT puv.unit_id, puv.project_id, puv.project_name, puv.project_location,
        puv.city, puv.locality, puv.project_status::text, puv.developer_name,
        puv.type_name, puv.bedrooms, puv.base_price_inr, puv.carpet_area_sqft,
        puv.possession_year, puv.is_available
    FROM project_units_view puv
    WHERE (p_bedrooms IS NULL OR puv.bedrooms = ANY(p_bedrooms))
        AND (p_city IS NULL OR puv.city ILIKE '%' || p_city || '%')
        AND (p_locality IS NULL OR puv.locality ILIKE '%' || p_locality || '%')
        AND (p_developer_name IS NULL OR puv.developer_name ILIKE '%' || p_developer_name || '%')
        AND (p_min_price IS NULL OR puv.base_price_inr >= p_min_price)
        AND (p_max_price IS NULL OR puv.base_price_inr <= p_max_price)
    LIMIT p_limit;
END; $$;

GRANT EXECUTE ON FUNCTION execute_filtered_search TO anon, authenticated, service_role;
NOTIFY pgrst, 'reload schema';
