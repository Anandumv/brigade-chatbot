# Multi-Company Architecture Deployment Guide

Complete step-by-step guide for deploying the multi-project, multi-company real estate chatbot with hybrid filtering.

---

## Prerequisites

✅ Supabase project set up
✅ Backend environment configured (.env file)
✅ Python 3.9+ installed
✅ Virtual environment activated

---

## Step 1: Database Schema Migration

### 1.1 Run Primary Schema Migration

This adds support for multiple developers, pricing, location, and possession data.

```bash
cd /Users/anandumv/Downloads/chatbot/backend

# Connect to your Supabase database
# Replace with your actual DATABASE_URL from Supabase settings
psql "postgresql://postgres:[YOUR_PASSWORD]@db.[YOUR_PROJECT_REF].supabase.co:5432/postgres" \
  -f database/schema_migration.sql
```

**Expected Output:**
```
CREATE TABLE
CREATE INDEX
ALTER TABLE
...
NOTICE: ========================================
NOTICE: MIGRATION COMPLETE
NOTICE: ========================================
NOTICE: Developers in database: 1
NOTICE: Projects linked to developers: 0
```

### 1.2 Run RPC Functions Migration

This adds stored procedures for filtered searches.

```bash
psql "postgresql://postgres:[YOUR_PASSWORD]@db.[YOUR_PROJECT_REF].supabase.co:5432/postgres" \
  -f database/schema_migration_rpc.sql
```

**Expected Output:**
```
CREATE FUNCTION
GRANT
...
NOTICE: RPC FUNCTIONS CREATED
NOTICE: - execute_filtered_search(...)
NOTICE: - get_project_summary(project_id)
NOTICE: - get_active_developers()
```

### 1.3 Verify Migration Success

**Option A: Using psql**
```bash
psql "postgresql://..." -c "SELECT name FROM developers;"
psql "postgresql://..." -c "\d unit_types"  # Check if new columns exist
psql "postgresql://..." -c "SELECT * FROM project_units_view LIMIT 1;"
```

**Option B: Using Supabase Dashboard**
1. Go to https://app.supabase.com
2. Navigate to Table Editor
3. Verify `developers` table exists
4. Check `unit_types` table has new columns: `base_price_inr`, `possession_year`
5. Check `projects` table has: `developer_id`, `city`, `locality`

---

## Step 2: Populate Sample Data

### 2.1 Add Developers

```sql
-- Run in Supabase SQL Editor or psql

INSERT INTO developers (name, website, headquarters, description)
VALUES
    ('Brigade Group', 'https://brigade.co.in', 'Bangalore, Karnataka', 'Leading real estate developer in South India'),
    ('Prestige Group', 'https://prestigeconstructions.com', 'Bangalore, Karnataka', 'Premium real estate developer'),
    ('Sobha Limited', 'https://sobha.com', 'Bangalore, Karnataka', 'Quality construction and real estate')
ON CONFLICT (name) DO NOTHING;
```

### 2.2 Link Existing Projects to Developers

```sql
-- Update existing Brigade Citrine project (replace with your actual project ID)
UPDATE projects
SET
    developer_id = (SELECT id FROM developers WHERE name = 'Brigade Group'),
    city = 'Bangalore',
    locality = 'Old Madras Road',
    area = 'East Bangalore'
WHERE name ILIKE '%citrine%';
```

### 2.3 Add Sample Unit Types with Pricing

```sql
-- Example: Add unit types for Brigade Citrine (replace PROJECT_UUID with actual ID)
INSERT INTO unit_types (
    project_id,
    type_name,
    bedrooms,
    toilets,
    balconies,
    carpet_area_sqft,
    super_builtup_area_sqm,
    base_price_inr,
    price_per_sqft,
    possession_year,
    possession_quarter,
    available_units,
    is_available
)
VALUES
    (
        'YOUR_PROJECT_UUID_HERE',
        '2BED + 2TOILET - TYPE 3',
        2,
        2,
        1,
        1100,
        102.19,
        25000000,  -- ₹2.5 Cr
        22727,
        2027,
        'Q2',
        15,
        TRUE
    ),
    (
        'YOUR_PROJECT_UUID_HERE',
        '2BED + 2TOILET - TYPE 4',
        2,
        2,
        1,
        1200,
        111.48,
        28000000,  -- ₹2.8 Cr
        23333,
        2027,
        'Q3',
        20,
        TRUE
    ),
    (
        'YOUR_PROJECT_UUID_HERE',
        '3BED + 3TOILET - TYPE 7',
        3,
        3,
        2,
        1800,
        167.22,
        45000000,  -- ₹4.5 Cr
        25000,
        2027,
        'Q4',
        10,
        TRUE
    );
```

### 2.4 Refresh Materialized View

```sql
-- Refresh the project_units_view for fast searches
SELECT refresh_project_units_view();
```

---

## Step 3: Install New Dependencies

The new filtering services don't require additional packages beyond what's already in `requirements.txt`:

```bash
cd /Users/anandumv/Downloads/chatbot/backend
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Verify all packages are installed
pip install -r requirements.txt
```

---

## Step 4: Test the Implementation

### 4.1 Start the Backend Server

```bash
cd /Users/anandumv/Downloads/chatbot/backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Starting Real Estate Sales Intelligence Chatbot API...
INFO:     Environment: development
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 4.2 Test Filter Extraction

```bash
curl -X POST "http://localhost:8000/api/chat/filtered-search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "2bhk under 3cr in Bangalore",
    "user_id": "test-user"
  }'
```

**Expected Response:**
```json
{
  "query": "2bhk under 3cr in Bangalore",
  "filters": {
    "bedrooms": [2],
    "max_price_inr": 30000000,
    "city": "Bangalore"
  },
  "matching_projects": 1,
  "projects": [
    {
      "project_name": "Brigade Citrine",
      "developer_name": "Brigade Group",
      "location": "Old Madras Road, Bangalore",
      "matching_unit_count": 2,
      "price_range": {
        "min_display": "₹2.5 Cr",
        "max_display": "₹2.8 Cr"
      },
      "sample_units": [
        {
          "type_name": "2BED + 2TOILET - TYPE 3",
          "bedrooms": 2,
          "price_display": "₹2.5 Cr",
          "carpet_area_sqft": 1100,
          "possession": "2027 Q2"
        }
      ]
    }
  ],
  "search_method": "hybrid",
  "response_time_ms": 850
}
```

### 4.3 Test Edge Cases

**Test 1: No Matches (Should Fall Back to Web Search)**
```bash
curl -X POST "http://localhost:8000/api/chat/filtered-search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "1bhk under 50 lac in Mumbai",
    "user_id": "test-user"
  }'
```

**Expected:** `matching_projects: 0` with `web_fallback` content.

**Test 2: Multiple Filters**
```bash
curl -X POST "http://localhost:8000/api/chat/filtered-search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "3bhk ready to move whitefield under 5cr possession 2027",
    "user_id": "test-user"
  }'
```

**Expected:** Filters extracted: `bedrooms:[3], status:["completed"], locality:"Whitefield", max_price:50000000, possession_year:2027`

---

## Step 5: Extract Structured Data from Existing PDFs (Optional)

If you have existing PDF brochures, you can extract pricing and unit data using a script:

```bash
cd /Users/anandumv/Downloads/chatbot/backend

# Create the extraction script (manual for now, automation coming)
python scripts/extract_structured_data.py \
  --pdf "../Brigade Citrine E_Brochure 01-1.pdf" \
  --project-id "YOUR_PROJECT_UUID" \
  --extract-pricing
```

**What This Does:**
- Parses PDF for unit configurations (2BHK, 3BHK)
- Extracts pricing (₹2.5 Cr, etc.)
- Extracts carpet area, possession dates
- Inserts into `unit_types` table

**Note:** This script is a manual process for now. For production, consider:
1. Using OCR for better text extraction
2. Building a web interface for sales teams to input data
3. Integrating with existing CRM systems

---

## Step 6: Production Deployment Checklist

### 6.1 Environment Variables

Update `/Users/anandumv/Downloads/chatbot/backend/.env` for production:

```bash
# Production Configuration
ENVIRONMENT=production

# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_production_anon_key
SUPABASE_SERVICE_KEY=your_production_service_role_key

# OpenAI
OPENAI_API_KEY=your_openai_production_key

# Tavily (Web Search)
TAVILY_API_KEY=your_tavily_production_key

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Performance Tuning
SIMILARITY_THRESHOLD=0.70
TOP_K_RESULTS=10
```

### 6.2 Performance Optimization

**Enable Connection Pooling:**
```python
# In database/supabase_client.py
# Add connection pooling for production
```

**Add Caching:**
```python
# Cache filter extraction results for common queries
# Cache materialized view data (refresh every 5 minutes)
```

**Database Indexes:**
```sql
-- Already created in migration, but verify:
ANALYZE unit_types;
ANALYZE projects;
ANALYZE project_units_view;
```

### 6.3 Monitoring Setup

**Add Application Monitoring:**
- Response time tracking per endpoint
- Filter extraction accuracy metrics
- Cache hit rates
- Database query performance

**Database Monitoring:**
- Query execution times
- Index usage statistics
- Materialized view refresh times

### 6.4 Security

**Rate Limiting:**
```python
# Add to main.py
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.post("/api/chat/filtered-search", dependencies=[Depends(RateLimiter(times=100, seconds=60))])
```

**CORS Configuration:**
```python
# Update CORS for production domains only
allow_origins=[
    "https://yourdomain.com",
    "https://app.yourdomain.com"
]
```

---

## Step 7: Scaling for Hundreds of Companies

### 7.1 Add Multiple Developers

```sql
-- Production data population
INSERT INTO developers (name, website, headquarters, description)
VALUES
    ('Prestige Group', 'https://prestigeconstructions.com', 'Bangalore', 'Premium real estate'),
    ('Sobha Limited', 'https://sobha.com', 'Bangalore', 'Quality construction'),
    ('Godrej Properties', 'https://godrejproperties.com', 'Mumbai', 'Trusted developer'),
    ('Mahindra Lifespaces', 'https://mahindralifespaces.com', 'Mumbai', 'Sustainable communities'),
    ('DLF Limited', 'https://dlf.in', 'Delhi NCR', 'India\'s largest developer')
-- Add more as needed
;
```

### 7.2 Performance Testing

**Simulate 500 Projects:**
```bash
# Run load test
cd backend/tests
python load_test_filtered_search.py --projects 500 --queries 1000
```

**Target Metrics:**
- Response time: < 2 seconds (P95)
- Throughput: > 100 requests/second
- Memory usage: < 512MB per worker

---

## Step 8: Frontend Integration

### Sample Frontend Code (React/Next.js)

```typescript
// Example API call from frontend
const searchProperties = async (query: string) => {
  const response = await fetch('http://localhost:8000/api/chat/filtered-search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: query,
      user_id: currentUser.id
    })
  });

  const data = await response.json();

  // Display expandable project cards
  return data.projects.map(project => ({
    name: project.project_name,
    developer: project.developer_name,
    location: project.location,
    priceRange: project.price_range.min_display + ' - ' + project.price_range.max_display,
    units: project.sample_units,
    canExpand: project.can_expand
  }));
};
```

---

## Troubleshooting

### Issue: "relation 'developers' does not exist"

**Solution:**
```bash
# Re-run migration
psql "postgresql://..." -f database/schema_migration.sql
```

### Issue: "function execute_filtered_search does not exist"

**Solution:**
```bash
# Run RPC migration
psql "postgresql://..." -f database/schema_migration_rpc.sql
```

### Issue: "No units match structured filters"

**Check:**
1. Unit types table populated? `SELECT COUNT(*) FROM unit_types WHERE base_price_inr IS NOT NULL;`
2. Materialized view refreshed? `SELECT refresh_project_units_view();`
3. Filters extracted correctly? Check logs for "Extracted filters: {...}"

### Issue: Slow Response Times

**Optimize:**
1. Refresh materialized view: `SELECT refresh_project_units_view();`
2. Check index usage: `EXPLAIN ANALYZE SELECT * FROM project_units_view WHERE bedrooms = 2;`
3. Reduce similarity threshold for faster vector search

---

## Success Criteria

After deployment, verify:

- ✅ Database migration successful (developers, unit_types, projects tables updated)
- ✅ RPC functions created (execute_filtered_search)
- ✅ Sample data populated (at least 1 developer, 1 project, 3 unit types)
- ✅ Filtered search endpoint returns results for "2bhk under 3cr"
- ✅ Web fallback works for queries with no matches
- ✅ Response times < 2 seconds
- ✅ Filter extraction accuracy > 90% on test queries

---

## Next Steps

1. **Bulk Data Import**: Create scripts to import hundreds of projects from Excel/CSV
2. **Admin Dashboard**: Build UI for managing developers, projects, and unit types
3. **Analytics**: Monitor which filters are most common, optimize accordingly
4. **Advanced Filters**: Add amenity filtering, floor preferences, parking requirements
5. **Multi-Tenancy**: Add company-level isolation for SaaS deployment

---

**Questions or Issues?**
Check the API documentation at http://localhost:8000/docs
Review the testing guide in API_TESTING_GUIDE.md
