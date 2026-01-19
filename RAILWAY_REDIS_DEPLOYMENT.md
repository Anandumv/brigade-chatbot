# Railway Redis Deployment Guide

This guide walks you through deploying Redis on Railway and connecting it to your FastAPI backend.

## Step 1: Deploy Redis on Railway

### Option A: Using Railway Dashboard (Recommended)

1. **Log in to Railway**: Go to [railway.app](https://railway.app) and sign in

2. **Create New Project** (or use existing project):
   - Click **"New Project"**
   - Select **"Deploy from Railway"** or add to existing project

3. **Add Redis Service**:
   - Click **"+ New"** in your project
   - Select **"Database"**
   - Choose **"Redis"**
   - Railway will automatically provision a Redis instance

4. **Copy Redis URL**:
   - Click on the Redis service
   - Go to **"Variables"** tab
   - Copy the `REDIS_URL` or `REDIS_PRIVATE_URL` (private URL is recommended for security)
   - Format: `redis://default:PASSWORD@redis.railway.internal:6379`

### Option B: Using Railway CLI

```bash
# Install Railway CLI (if not already installed)
npm i -g @railway/cli

# Login to Railway
railway login

# Link to your project
railway link

# Add Redis service
railway add --database redis

# Get Redis connection URL
railway variables
```

## Step 2: Configure Backend Environment Variables

### On Railway (Backend Service)

1. Go to your **Backend service** (FastAPI)
2. Click **"Variables"** tab
3. Add the following environment variable:

```bash
# Redis Configuration
REDIS_URL=redis://default:PASSWORD@redis.railway.internal:6379
```

**Important**: Replace the URL with the actual Redis URL from Step 1. Use the **private URL** (`redis.railway.internal`) for internal communication between services.

### Other Required Environment Variables

Make sure these are also set:

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
GPT_MODEL=gpt-4-turbo

# Redis (90 minutes TTL)
REDIS_URL=redis://default:PASSWORD@redis.railway.internal:6379
REDIS_TTL_SECONDS=5400

# Database (if using Railway Postgres)
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

## Step 3: Verify Deployment

### Check Redis Connection

Once deployed, your backend will automatically connect to Redis on startup. Check the logs:

```bash
# Using Railway CLI
railway logs --service backend

# Or check in Railway dashboard
# Go to Backend service → Deployments → Select latest → View logs
```

Look for these log messages:

```
✅ Redis connected successfully: redis://default:***@redis.railway.internal:6379
Redis status: healthy
```

If Redis fails, you'll see:

```
⚠️ Redis connection failed: ...
⚠️ Context will use in-memory fallback
```

### Test the /assist Endpoint

```bash
# Get your Railway backend URL
BACKEND_URL=https://your-app.up.railway.app

# Test health check
curl $BACKEND_URL/api/assist/health

# Expected response:
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

### Test Context Persistence

```bash
# Send first query
curl -X POST $BACKEND_URL/api/assist \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-12345",
    "query": "Show me 2BHK under 1.3Cr in Sarjapur"
  }'

# Send follow-up query (should use context)
curl -X POST $BACKEND_URL/api/assist \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-12345",
    "query": "What about 3BHK?"
  }'
```

## Step 4: Monitor Redis

### Railway Dashboard Monitoring

1. Go to Redis service in Railway
2. Check **"Metrics"** tab for:
   - Memory usage
   - Connection count
   - Command statistics

### Redis CLI Access (if needed)

```bash
# Using Railway CLI
railway connect redis

# This opens a Redis CLI session
# Test commands:
> PING
PONG

> INFO memory
# Shows memory usage

> KEYS call:*
# Lists all conversation keys

> TTL call:test-12345
# Shows remaining TTL for a key

> GET call:test-12345
# Shows context JSON for a call_id
```

## Step 5: Scaling Considerations

### Redis Memory Limits

- Railway Free Plan: ~512 MB Redis
- Paid Plans: Up to 32 GB+

**Estimate storage needs**:
- Average context size: ~2-5 KB per conversation
- 90-minute TTL means contexts auto-expire
- 512 MB can handle ~100,000 active conversations

### Eviction Policy

Railway Redis uses `allkeys-lru` eviction policy by default:
- When memory limit is reached, least recently used keys are evicted
- Your 90-minute TTL ensures old contexts are removed

### Connection Pooling

The backend uses `redis-py` which handles connection pooling automatically:
- Default: 50 max connections per instance
- Railway Redis supports 10,000+ concurrent connections

## Troubleshooting

### Issue: "Connection refused"

**Cause**: Redis URL is incorrect or service isn't running

**Solution**:
1. Verify Redis service is running in Railway dashboard
2. Check `REDIS_URL` environment variable
3. Use **private URL** (`redis.railway.internal`) not public URL
4. Ensure backend and Redis are in the same Railway project

### Issue: "Context not persisting"

**Cause**: Redis fallback to in-memory mode

**Solution**:
1. Check backend logs for Redis connection errors
2. Verify `REDIS_URL` is set correctly
3. Test Redis connection:
   ```bash
   railway connect redis
   > PING
   ```

### Issue: "Out of memory"

**Cause**: Too many contexts stored

**Solution**:
1. Reduce `REDIS_TTL_SECONDS` (current: 5400s = 90 min)
2. Upgrade Railway plan for more Redis memory
3. Implement manual cleanup for abandoned contexts

### Issue: "Slow response times"

**Cause**: Redis latency or connection issues

**Solution**:
1. Check Redis metrics in Railway dashboard
2. Ensure backend and Redis are in same Railway region
3. Monitor connection pool exhaustion in logs

## Best Practices

### 1. Use Private URLs
Always use `redis.railway.internal` (private URL) instead of public URL for:
- Better security (no public exposure)
- Lower latency (internal network)
- No egress charges

### 2. Monitor TTL
- Current TTL: 90 minutes (5400 seconds)
- Adjust based on conversation patterns
- Shorter TTL = less memory usage

### 3. Implement Cleanup
Add a scheduled job to clean up abandoned contexts:

```python
# backend/services/redis_cleanup.py (optional)
import redis
from config import settings

def cleanup_expired_contexts():
    client = redis.from_url(settings.redis_url)
    # Get all context keys
    keys = client.keys("call:*")
    # Redis automatically removes expired keys, but this forces cleanup
    for key in keys:
        if client.ttl(key) < 0:  # Expired
            client.delete(key)
```

### 4. Add Observability

Monitor these metrics:
- Redis memory usage (Railway dashboard)
- Context hit rate (log in application)
- Average context size (log in application)
- Failed Redis operations (error logs)

## Cost Estimation

### Railway Pricing (as of 2024)

- **Free Plan**: $0/month
  - 512 MB Redis
  - Suitable for development and testing

- **Pro Plan**: $20/month
  - First $20 of usage included
  - Redis: ~$0.50/GB/month
  - 2 GB Redis = ~$1/month

### Example Costs

| Conversations/day | Avg Context Size | Storage Needed | Monthly Cost |
|-------------------|------------------|----------------|--------------|
| 1,000             | 3 KB             | ~50 MB         | Free         |
| 10,000            | 3 KB             | ~500 MB        | Free         |
| 100,000           | 3 KB             | ~5 GB          | ~$3/month    |

*Note: With 90-minute TTL, storage is much lower than these estimates*

## Next Steps

1. ✅ Deploy Redis on Railway
2. ✅ Set `REDIS_URL` environment variable in backend
3. ✅ Redeploy backend to pick up new environment variable
4. ✅ Test `/api/assist/health` endpoint
5. ✅ Test context persistence with sample queries
6. ✅ Monitor Redis metrics in Railway dashboard
7. 📋 Update frontend to use `/api/assist` endpoint (optional)

## Support

- Railway Docs: https://docs.railway.app/databases/redis
- Railway Discord: https://discord.gg/railway
- Redis Docs: https://redis.io/docs/

---

**Status**: Ready for production deployment ✅
