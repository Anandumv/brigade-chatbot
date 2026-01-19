# 🚀 Deployment Checklist: Real Estate Sales Copilot

Complete checklist for deploying the enhanced Sales Copilot with Redis context persistence.

---

## Pre-Deployment Checklist

### ✅ Code Complete
- [x] Redis integration (backend/services/redis_context.py)
- [x] Budget relaxation service (backend/services/budget_relaxer.py)
- [x] Copilot formatter (backend/services/copilot_formatter.py)
- [x] System prompt with bullets (backend/prompts/sales_copilot_system.py)
- [x] Request/Response models (backend/models/copilot_*.py)
- [x] /assist endpoint router (backend/routes/assist.py)
- [x] Frontend TypeScript types (frontend/src/types/index.ts)
- [x] API service integration (frontend/src/services/api.ts)

### ✅ Configuration Files
- [x] backend/.env.example
- [x] backend/requirements.txt (Redis dependencies added)
- [x] railway.json
- [x] RAILWAY_REDIS_DEPLOYMENT.md

---

## Step 1: Local Testing (Optional but Recommended)

### 1.1 Start Local Redis

```bash
# Using Docker
docker run -d --name redis-local -p 6379:6379 redis:7-alpine

# Verify it's running
docker ps | grep redis
```

### 1.2 Update Local .env

```bash
cd backend
cp .env.example .env
# Edit .env and set:
# REDIS_URL=redis://localhost:6379/0
```

### 1.3 Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 1.4 Test Backend Locally

```bash
# Start backend
uvicorn main:app --reload

# In another terminal, run tests
python test_redis_assist.py
```

**Expected output**:
```
✅ Redis Connection: PASSED
✅ Redis Operations: PASSED
✅ /assist Endpoint: PASSED
✅ Context Persistence: PASSED
```

---

## Step 2: Deploy Redis on Railway

### 2.1 Add Redis Service

**Option A: Railway Dashboard**
1. Go to [railway.app](https://railway.app)
2. Open your project
3. Click **"+ New"** → **"Database"** → **"Redis"**
4. Wait for provisioning (~30 seconds)

**Option B: Railway CLI**
```bash
railway add --database redis
```

### 2.2 Get Redis URL

1. Click on Redis service
2. Go to **"Variables"** tab
3. Copy `REDIS_PRIVATE_URL` or `REDIS_URL`
4. Format: `redis://default:PASSWORD@redis.railway.internal:6379`

✅ **Checkpoint**: Redis service is running in Railway

---

## Step 3: Configure Backend Environment Variables

### 3.1 Set Redis URL in Backend

1. Go to **Backend service** in Railway
2. Click **"Variables"** tab
3. Add or update:

```
REDIS_URL=redis://default:PASSWORD@redis.railway.internal:6379
REDIS_TTL_SECONDS=5400
```

### 3.2 Verify All Required Variables

Ensure these are set:

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
GPT_MODEL=gpt-4-turbo

# Redis
REDIS_URL=redis://default:...@redis.railway.internal:6379
REDIS_TTL_SECONDS=5400

# Database (if using)
DATABASE_URL=postgresql://...

# Pixeltable
USE_PIXELTABLE=true
PIXELTABLE_MODE=exclusive

# Tavily (optional)
TAVILY_API_KEY=tvly-...

# App
ENVIRONMENT=production
API_HOST=0.0.0.0
API_PORT=8000
```

✅ **Checkpoint**: All environment variables are set

---

## Step 4: Deploy Backend

### 4.1 Push Code to Git

```bash
cd /Users/anandumv/Downloads/chatbot
git add .
git commit -m "feat: Add Redis context persistence and /assist endpoint"
git push origin main
```

### 4.2 Railway Auto-Deploy

Railway will automatically detect the push and redeploy the backend.

**Monitor deployment**:
1. Go to Backend service → **"Deployments"**
2. Click latest deployment
3. Watch **"Deploy Logs"**

**Look for these logs**:
```
✅ Redis context manager initialized
Redis status: healthy
✅ Database initialization successful
```

### 4.3 Verify Health Check

```bash
# Get your Railway backend URL
BACKEND_URL=https://your-app.up.railway.app

# Test health
curl $BACKEND_URL/health

# Test /assist health
curl $BACKEND_URL/api/assist/health
```

**Expected response**:
```json
{
  "status": "healthy",
  "endpoint": "/api/assist",
  "redis": {
    "redis_available": true,
    "fallback_mode": null,
    "status": "healthy"
  }
}
```

✅ **Checkpoint**: Backend deployed with Redis connection

---

## Step 5: Test /assist Endpoint

### 5.1 Test Basic Query

```bash
curl -X POST $BACKEND_URL/api/assist \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-12345",
    "query": "Show me 2BHK under 1.3Cr in Sarjapur"
  }'
```

**Expected response structure**:
```json
{
  "projects": [
    {
      "name": "Brigade Citrine",
      "location": "Sarjapur Road, Bangalore",
      "price_range": "85L - 1.25Cr",
      "bhk": "2BHK, 3BHK",
      "amenities": ["Pool", "Gym", "Clubhouse"],
      "status": "Ready-to-move"
    }
  ],
  "answer": [
    "**Brigade Citrine** matches your budget with **2BHK units under 1.3Cr**",
    "The project offers **ready-to-move** units with **immediate possession**",
    "Located on **Sarjapur Road** with **excellent connectivity** to IT parks"
  ],
  "pitch_help": "Brigade Citrine offers **immediate possession** with **zero waiting period**, perfect for urgent moves",
  "next_suggestion": "Schedule a **site visit** to see the **actual unit** and **amenities**"
}
```

### 5.2 Test Context Persistence

```bash
# Follow-up query (same call_id)
curl -X POST $BACKEND_URL/api/assist \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-12345",
    "query": "What about 3BHK?"
  }'
```

**Expected**: Response should reference previous context (Sarjapur, budget)

### 5.3 Test Budget Relaxation

```bash
# Query with tight budget (should trigger relaxation)
curl -X POST $BACKEND_URL/api/assist \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-67890",
    "query": "2BHK under 80L in Whitefield"
  }'
```

**Expected**: Response should include `relaxation_applied: true` and `relaxation_step: 1.1`

✅ **Checkpoint**: /assist endpoint working with context persistence

---

## Step 6: Deploy Frontend (Optional)

### 6.1 Update Vercel Environment Variable

If using Vercel:

1. Go to Vercel project settings
2. Add/update environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://your-app.up.railway.app
   ```
3. Redeploy frontend

### 6.2 Test from Frontend

Once frontend updates are complete (ChatInterface, ResponseCard, FilterPanel), test end-to-end:

1. Open frontend in browser
2. Send query: "Show me 2BHK under 1.3Cr"
3. Verify bullet-point response
4. Check pitch_help and next_suggestion display
5. Test follow-up: "What about 3BHK?"
6. Verify context is maintained

✅ **Checkpoint**: Frontend integrated with /assist endpoint

---

## Step 7: Monitor and Verify

### 7.1 Check Railway Logs

```bash
# Using Railway CLI
railway logs --service backend

# Look for:
# - Redis connection messages
# - /assist endpoint calls
# - Context save/load operations
# - Budget relaxation logs
```

### 7.2 Monitor Redis Metrics

1. Go to Redis service in Railway
2. Click **"Metrics"** tab
3. Monitor:
   - Memory usage (should be low with 90min TTL)
   - Connection count
   - Commands per second

### 7.3 Test Edge Cases

```bash
# Test with no budget (should not relax)
curl -X POST $BACKEND_URL/api/assist \
  -H "Content-Type: application/json" \
  -d '{"call_id": "test-1", "query": "Show me properties in Sarjapur"}'

# Test with filters
curl -X POST $BACKEND_URL/api/assist \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-2",
    "query": "Show me options",
    "filters": {
      "bhk": ["2BHK"],
      "status": ["Ready-to-move"],
      "price_range": [7000000, 13000000]
    }
  }'

# Test generic query (no projects)
curl -X POST $BACKEND_URL/api/assist \
  -H "Content-Type: application/json" \
  -d '{"call_id": "test-3", "query": "How far is Sarjapur from airport?"}'
```

✅ **Checkpoint**: All edge cases working correctly

---

## Step 8: Performance Verification

### 8.1 Response Time

Target: < 3 seconds average

```bash
# Test response time
time curl -X POST $BACKEND_URL/api/assist \
  -H "Content-Type: application/json" \
  -d '{"call_id": "perf-test", "query": "2BHK in Sarjapur"}'
```

### 8.2 Concurrent Requests

```bash
# Test 10 concurrent requests (requires siege or ab)
# Using Apache Bench:
ab -n 10 -c 5 -p test_payload.json -T application/json \
  $BACKEND_URL/api/assist
```

### 8.3 Redis Performance

Check Redis response time in Railway metrics:
- Target: < 10ms for GET/SET operations

✅ **Checkpoint**: Performance meets targets

---

## Step 9: Security Checklist

### 9.1 Verify Redis Security

- [ ] Using **private URL** (redis.railway.internal) not public
- [ ] No Redis password in frontend code
- [ ] Redis only accessible within Railway network

### 9.2 Verify API Security

- [ ] CORS configured correctly (not allow_origins=["*"] in production)
- [ ] Rate limiting enabled (if applicable)
- [ ] No sensitive data in logs
- [ ] Environment variables not exposed in responses

### 9.3 Verify Data Privacy

- [ ] Context data includes only necessary information
- [ ] No PII stored in Redis (if required, add encryption)
- [ ] TTL ensures data is auto-deleted after 90 minutes

✅ **Checkpoint**: Security best practices followed

---

## Step 10: Documentation and Handoff

### 10.1 Update Documentation

- [x] RAILWAY_REDIS_DEPLOYMENT.md
- [x] DEPLOYMENT_CHECKLIST.md (this file)
- [x] backend/.env.example
- [ ] Update main README.md with /assist endpoint info

### 10.2 Share Access

- [ ] Share Railway project with team
- [ ] Document environment variable values (securely)
- [ ] Share monitoring dashboard links

### 10.3 Create Runbook

Document:
- How to check Redis health
- How to restart services
- How to scale Redis if needed
- How to debug context issues
- How to monitor performance

✅ **Checkpoint**: Documentation complete

---

## Rollback Plan

If issues arise after deployment:

### Backend Issues

1. **Quick Fix**: Set `REDIS_URL` to invalid value to force in-memory fallback
2. **Rollback**: Revert to previous Railway deployment
3. **Disable**: Comment out Redis initialization in main.py

### Frontend Issues

1. **Feature Flag**: Keep using old `/api/chat/query` endpoint
2. **Gradual Rollout**: Test with 10% users first

---

## Success Criteria

✅ All items checked:

- [ ] Redis deployed on Railway
- [ ] Backend deployed with Redis connection
- [ ] `/api/assist/health` returns healthy status
- [ ] Context persists across requests
- [ ] Budget relaxation working (1.0x → 1.1x → 1.2x → 1.3x)
- [ ] Responses are JSON with 3-5 bullets
- [ ] pitch_help and next_suggestion always present
- [ ] Response time < 3 seconds
- [ ] No errors in Railway logs
- [ ] Redis memory usage reasonable
- [ ] Security best practices followed

---

## Support

**Railway Issues**: https://discord.gg/railway
**Redis Issues**: Check logs with `railway logs --service redis`
**Backend Issues**: Check logs with `railway logs --service backend`

---

## Next Steps After Deployment

1. **Monitor for 24 hours**: Watch logs, metrics, and error rates
2. **Test with real users**: Get feedback on response quality
3. **Optimize prompts**: Adjust system prompt based on outputs
4. **Fine-tune TTL**: Adjust based on conversation patterns
5. **Scale if needed**: Upgrade Redis plan if memory usage high

---

**Deployment Status**: ⏳ In Progress

**Last Updated**: 2025-01-19
