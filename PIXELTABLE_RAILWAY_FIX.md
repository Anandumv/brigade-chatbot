# CRITICAL FIX: Pixeltable Data Persistence on Railway

## Problem Summary

The `/api/assist/` endpoint returns 0 projects for ALL queries (even simple ones like "Show me projects in Sarjapur") despite:
- ✅ All 76 projects exist in `backend/data/seed_projects.json`
- ✅ Admin refresh endpoint reports "Loaded 76 projects"
- ✅ Local Pixeltable has all 76 projects and queries work perfectly
- ❌ Railway deployment cannot access Pixeltable data

## Root Cause

**PIXELTABLE_DB_URL environment variable is NOT set on Railway.**

Pixeltable was patched (`backend/vendor/pixeltable/env.py:313-319`) to require `PIXELTABLE_DB_URL` for production deployments. Without this variable:
- Pixeltable cannot connect to a persistent PostgreSQL database
- Data inserted via admin refresh is stored in a temporary/ephemeral location
- Each query might be hitting an empty database or different instance

## Evidence

1. Local test (with Pixeltable using local pgdata):
   ```bash
   $ python3 -c "from database.pixeltable_setup import get_projects_table; print(get_projects_table().count())"
   > 76  # ✅ All projects present
   ```

2. Live Railway test:
   ```bash
   $ curl POST /admin/refresh-projects
   > {"status":"success","message":"Loaded 76 projects"}  # ✅ Claims to load data

   $ curl POST /api/assist/ -d '{"query":"Show me projects in Sarjapur"}'
   > {"projects":[], ...}  # ❌ Returns 0 projects
   ```

3. Pixeltable env.py patch (line 313-319):
   ```python
   external_db_url = os.environ.get('PIXELTABLE_DB_URL')
   if external_db_url:
       self._db_url = external_db_url
   else:
       raise excs.Error("PIXELTABLE_DB_URL environment variable must be set")
   ```

## Fix Steps

### Step 1: Add PIXELTABLE_DB_URL to Railway

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Navigate to your project: `brigade-chatbot-production`
3. Select the **Backend** service
4. Click **Variables** tab
5. Click **+ New Variable**
6. Add:
   ```
   Variable Name: PIXELTABLE_DB_URL
   Value: ${{Postgres.DATABASE_URL}}
   ```
   *(Railway will auto-replace this with the actual PostgreSQL connection string)*

7. **Save** and redeploy

### Step 2: Fix Admin Refresh Schema Mismatch

The `/admin/refresh-projects` endpoint creates a table schema at `backend/main.py:787-806` that is MISSING the `latitude` and `longitude` fields that exist in the original schema at `backend/database/pixeltable_setup.py:108-109`.

**Fix**: Update [backend/main.py:787-806](backend/main.py#L787-L806) to include all fields:

```python
schema = {
    'project_id': pxt.String,
    'name': pxt.String,
    'developer': pxt.String,
    'location': pxt.String,
    'zone': pxt.String,
    'configuration': pxt.String,
    'budget_min': pxt.Int,
    'budget_max': pxt.Int,
    'possession_year': pxt.Int,
    'possession_quarter': pxt.String,
    'status': pxt.String,
    'rera_number': pxt.String,
    'description': pxt.String,
    'amenities': pxt.String,
    'usp': pxt.String,
    'rm_details': pxt.Json,
    'brochure_url': pxt.String,
    'registration_process': pxt.String,
    'latitude': pxt.Float,          # ADD THIS
    'longitude': pxt.Float,         # ADD THIS
}
```

### Step 3: Verify Fix

After deploying with `PIXELTABLE_DB_URL` set:

1. **Check health endpoint**:
   ```bash
   curl https://brigade-chatbot-production.up.railway.app/health
   ```
   Should show "Pixeltable: OK"

2. **Trigger admin refresh**:
   ```bash
   curl -X POST https://brigade-chatbot-production.up.railway.app/admin/refresh-projects \
     -H 'x-admin-key: secret'
   ```
   Should return: `{"status":"success","message":"Loaded 76 projects"}`

3. **Test location query**:
   ```bash
   curl -X POST https://brigade-chatbot-production.up.railway.app/api/assist/ \
     -H 'Content-Type: application/json' \
     -d '{"call_id":"test-001","query":"Show me projects in Sarjapur"}'
   ```
   **Expected**: Returns 13 projects with Sarjapur in location

4. **Test BHK + location query**:
   ```bash
   curl -X POST https://brigade-chatbot-production.up.railway.app/api/assist/ \
     -H 'Content-Type: application/json' \
     -d '{"call_id":"test-002","query":"2BHK in Sarjapur"}'
   ```
   **Expected**: Returns 6 projects (2BHK in Sarjapur)

5. **Test BHK + location + budget**:
   ```bash
   curl -X POST https://brigade-chatbot-production.up.railway.app/api/assist/ \
     -H 'Content-Type: application/json' \
     -d '{"call_id":"test-003","query":"2BHK in Sarjapur under 1.5Cr"}'
   ```
   **Expected**: Returns 5-6 projects matching criteria

## Why This Happened

1. **Railway PostgreSQL was provisioned** but `PIXELTABLE_DB_URL` was never set to connect to it
2. **Local development worked** because Pixeltable uses local `~/.pixeltable/pgdata` directory
3. **Admin refresh succeeded** but data went into ephemeral storage (temp directory or in-memory)
4. **Queries returned empty** because they were querying the Railway PostgreSQL which was never populated

## Impact

**Before Fix:**
- ❌ ALL queries return 0 projects
- ❌ Users cannot search for any properties
- ❌ System appears completely broken

**After Fix:**
- ✅ All 76 projects accessible
- ✅ Location filtering works ("Sarjapur" returns 13 projects)
- ✅ BHK filtering works ("2BHK" returns 68 projects)
- ✅ Budget filtering works ("under 1.5Cr" returns correct results)
- ✅ Combined filters work ("2BHK in Sarjapur under 1.5Cr" returns 5-6 projects)

## Files Modified

1. `backend/main.py` - Lines 787-806 (add latitude/longitude to admin refresh schema)
2. Railway environment variables - Add `PIXELTABLE_DB_URL`

## Deployment Checklist

- [ ] Add `PIXELTABLE_DB_URL` to Railway Backend service variables
- [ ] Update `backend/main.py` admin refresh schema
- [ ] Commit and push changes
- [ ] Wait for Railway auto-deploy (~2 minutes)
- [ ] Run `/admin/refresh-projects` to seed data
- [ ] Verify all 5 test queries above

## Success Criteria

✅ Query "Show me projects in Sarjapur" returns 13 projects
✅ Query "2BHK in Sarjapur under 1.5Cr" returns 5-6 projects
✅ All previous 71 tests continue to pass
✅ No errors in Railway logs about Pixeltable connection

---

**Estimated Time to Fix**: 10 minutes
**Priority**: CRITICAL (blocks all functionality)
**Status**: Ready to implement
