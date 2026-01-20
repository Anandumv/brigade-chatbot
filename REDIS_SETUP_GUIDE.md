# Redis Setup Guide for Railway

**Quick guide to set up Redis context persistence in production**

---

## ✅ Current Status

- Backend code: ✅ Ready
- Redis integration: ✅ Implemented
- Deployment: ✅ Live
- Health check: ✅ Passing

**What's needed**: Set `REDIS_URL` environment variable in Railway

---

## 🚀 Setup Steps (5 minutes)

### Option 1: Railway Dashboard (Recommended)

1. **Add Redis Service**
   - Go to [railway.app](https://railway.app)
   - Open your project: **brigade-chatbot**
   - Click **"+ New"** button
   - Select **"Database"** → **"Redis"**
   - Wait 30 seconds for provisioning

2. **Get Redis URL**
   - Click on the newly created **Redis** service
   - Go to **"Variables"** tab
   - Find `REDIS_PRIVATE_URL` or `REDIS_URL`
   - Copy the URL (format: `redis://default:PASSWORD@redis.railway.internal:6379`)

3. **Configure Backend**
   - Go to **Backend** service (your main FastAPI service)
   - Click **"Variables"** tab
   - Click **"+ New Variable"**
   - Add:
     ```
     Variable: REDIS_URL
     Value: redis://default:PASSWORD@redis.railway.internal:6379
     ```
     (Paste the URL you copied)

   - Add second variable:
     ```
     Variable: REDIS_TTL_SECONDS
     Value: 5400
     ```

4. **Redeploy**
   - Click **"Redeploy"** button on backend service
   - Wait 1-2 minutes for deployment to complete

5. **Verify**
   ```bash
   curl https://brigade-chatbot-production.up.railway.app/api/assist/health
   ```

   Should return:
   ```json
   {
     "redis": {
       "redis_available": true,
       "status": "healthy"
     }
   }
   ```

---

### Option 2: Railway CLI

```bash
# Navigate to project directory
cd /Users/anandumv/Downloads/chatbot

# Login to Railway
railway login

# Link to your project
railway link

# Add Redis database
railway add --database redis

# Get Redis URL (note: this shows Redis variables)
railway variables --service redis

# Set Redis URL in backend
railway variables set REDIS_URL=redis://default:...@redis.railway.internal:6379 --service backend
railway variables set REDIS_TTL_SECONDS=5400 --service backend

# Redeploy
railway up
```

---

## 🔍 Troubleshooting

### Issue: "redis_available: false"

**Cause**: REDIS_URL not set or incorrect

**Fix**:
1. Go to Railway → Backend service → Variables
2. Check if `REDIS_URL` exists
3. If missing, add it following Step 3 above
4. If exists but wrong, copy correct URL from Redis service Variables tab
5. Redeploy backend

### Issue: "Connection refused"

**Cause**: Using public URL instead of private

**Fix**:
- ❌ Wrong: `redis://red-xxxxx.railway.app:6379`
- ✅ Correct: `redis://default:PASSWORD@redis.railway.internal:6379`

### Issue: Context not persisting after restart

**Cause**: Redis not connected, using in-memory fallback

**Fix**:
1. Check health endpoint shows `redis_available: true`
2. If false, follow "redis_available: false" fix above
3. Restart backend service in Railway

---

## 📊 Verify Redis is Working

### Test 1: Health Check
```bash
curl https://brigade-chatbot-production.up.railway.app/api/assist/health | jq .redis
```

Expected:
```json
{
  "redis_available": true,
  "fallback_mode": null,
  "status": "healthy"
}
```

### Test 2: Context Persistence
```bash
# First query
curl -X POST https://brigade-chatbot-production.up.railway.app/api/assist/ \
  -H 'Content-Type: application/json' \
  -d '{"call_id":"redis-test-123","query":"2BHK in Sarjapur"}'

# Wait 2 seconds
sleep 2

# Follow-up query (same call_id)
curl -X POST https://brigade-chatbot-production.up.railway.app/api/assist/ \
  -H 'Content-Type: application/json' \
  -d '{"call_id":"redis-test-123","query":"What about 3BHK?"}'
```

If Redis is working, the second response should reference "Sarjapur" from the first query.

---

## 🔒 Security Notes

- ✅ **Private URL Only**: Railway Redis uses internal network (`redis.railway.internal`)
- ✅ **No Public Exposure**: Redis is not accessible from internet
- ✅ **Automatic SSL/TLS**: Encrypted in production
- ✅ **90-Minute TTL**: Context auto-deleted after 90 minutes
- ⚠️ **No Encryption**: Context stored as plain JSON (add encryption if storing sensitive data)

---

## 📈 Monitor Redis

### Railway Dashboard
1. Go to Railway → Redis service
2. Click **"Metrics"** tab
3. Monitor:
   - Memory usage
   - Connection count
   - Commands per second

### Expected Values
- Memory: < 50 MB (low usage)
- Connections: 1-5 (backend connections)
- Commands/sec: ~10-100 (depending on traffic)

---

## 💰 Pricing

**Railway Redis (Hobby Plan)**:
- Free: Up to 512 MB memory
- Free: Up to 10k commands/sec
- Free: No bandwidth limits
- Cost: $0/month within free tier

**Estimated Usage**:
- Per context: ~1-5 KB
- With 90-min TTL: ~1000 concurrent sessions max
- Memory needed: ~5 MB for typical load
- **Verdict**: Free tier is sufficient ✅

---

## 🎯 Success Criteria

- ✅ `redis_available: true` in health check
- ✅ Context persists across requests
- ✅ No "fallback_mode" warnings in logs
- ✅ Backend logs show "Redis status: healthy"

---

## 📞 Need Help?

**Already Done**:
- ✅ Redis integration code written
- ✅ Fallback to in-memory if Redis unavailable
- ✅ Health check endpoint created
- ✅ Context save/load logic implemented

**Just Need To**:
1. Add Redis service in Railway (30 seconds)
2. Set REDIS_URL environment variable (1 minute)
3. Redeploy backend (2 minutes)
4. Verify health check (10 seconds)

**Total Time**: ~5 minutes

---

**Quick Reference**:
- Health Check: `https://brigade-chatbot-production.up.railway.app/api/assist/health`
- Railway Dashboard: https://railway.app/dashboard
- Redis Documentation: https://redis.io/docs/
- Support: https://discord.gg/railway
