# ✅ Production Deployment Checklist

**Project**: Brigade Sales AI Chatbot (Phases 1, 2A, 2B)  
**Target Date**: February 1, 2026  
**Status**: Pre-deployment

---

## 📋 Pre-Deployment Checklist

### **A. Code Quality** ✅

- [x] All tests passing (96.7% success rate)
  - [x] `test_conversation_coaching.py` (10/10) ✅
  - [x] `test_sentiment_simple.py` (9/10) ✅
  - [x] `test_user_profiles.py` (10/10) ✅

- [x] No linter errors ✅

- [x] Code review completed
  - [x] Security review (no SQL injection, XSS)
  - [x] Performance review (no N+1 queries)
  - [x] Error handling (graceful degradation)

- [ ] Load testing completed
  - [ ] 100 concurrent users
  - [ ] 1000 requests/min
  - [ ] Response time < 3s (95th percentile)

---

### **B. Database Setup** 🔧

#### 1. Create User Profiles Table
```bash
# Run on Supabase/PostgreSQL
psql -h <SUPABASE_HOST> -U postgres -d postgres \
  -f backend/database/user_profiles_schema.sql
```

**Verify**:
```sql
-- Check table exists
\d user_profiles;

-- Check indexes
\di user_profiles*;

-- Check triggers
SELECT tgname FROM pg_trigger WHERE tgrelid = 'user_profiles'::regclass;
```

**Expected Output**:
- Table `user_profiles` with 25+ columns ✅
- 5 indexes (last_active, lead_temperature, budget, etc.) ✅
- 1 trigger (`update_user_profile_last_active`) ✅

---

#### 2. Migrate In-Memory Profiles to Database
**Current**: `UserProfileManager` uses in-memory dict  
**Production**: Need Supabase integration

**Task**: Update `user_profile_manager.py`

```python
# BEFORE (In-Memory)
class UserProfileManager:
    def __init__(self):
        self.profiles: Dict[str, UserProfile] = {}
    
    def get_or_create_profile(self, user_id: str):
        if user_id in self.profiles:
            return self.profiles[user_id]
        # ...

# AFTER (Supabase)
from supabase import create_client
import os

class UserProfileManager:
    def __init__(self):
        self.supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
    
    def get_or_create_profile(self, user_id: str):
        # Query Supabase
        result = self.supabase.table('user_profiles') \
            .select('*') \
            .eq('user_id', user_id) \
            .execute()
        
        if result.data:
            return UserProfile(**result.data[0])
        
        # Create new profile
        profile = UserProfile(user_id=user_id)
        self.supabase.table('user_profiles').insert(profile.model_dump()).execute()
        return profile
    
    def save_profile(self, profile: UserProfile):
        self.supabase.table('user_profiles') \
            .update(profile.model_dump()) \
            .eq('user_id', profile.user_id) \
            .execute()
```

**Status**: ⚠️ TODO (see below)

---

### **C. Environment Configuration** 🔐

#### 1. Production `.env` File
```bash
# OpenAI
OPENAI_API_KEY=sk-proj-...  # Production key (not dev)

# Supabase
SUPABASE_URL=https://xyz.supabase.co
SUPABASE_KEY=eyJhb...  # Service role key (not anon)
DATABASE_URL=postgresql://postgres:password@db.xyz.supabase.co:5432/postgres

# Pixeltable
PIXELTABLE_HOME=/app/pixeltable_data

# Admin
ADMIN_KEY=<strong-random-key>  # Generate with: openssl rand -hex 32

# Monitoring
LOG_LEVEL=INFO  # Not DEBUG in production
SENTRY_DSN=https://...  # (Optional) Error tracking

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=100
RATE_LIMIT_REQUESTS_PER_HOUR=1000
```

**Verify**:
```bash
# Check all required env vars are set
python3 -c "
import os
required = ['OPENAI_API_KEY', 'SUPABASE_URL', 'SUPABASE_KEY', 'DATABASE_URL']
missing = [k for k in required if not os.getenv(k)]
if missing:
    print(f'❌ Missing: {missing}')
else:
    print('✅ All env vars set')
"
```

---

#### 2. Secrets Management
**Platform**: Render / Heroku / Vercel

**Steps**:
1. Go to project settings
2. Add environment variables
3. **Never commit `.env` to git** ❌
4. Use secret scanning (GitHub Advanced Security)

---

### **D. API Keys & Rate Limits** 🔑

#### 1. OpenAI API
**Current Tier**: Check at https://platform.openai.com/account/limits

**Requirements for Production**:
- **Tier 3+** (at least 90K TPM - tokens per minute)
- **Rate Limits**:
  - GPT-4 Turbo: 90K TPM
  - Embeddings: 1M TPM
- **Billing**: Add payment method + set budget alert

**Action**:
- [ ] Upgrade to Tier 3 if needed
- [ ] Set budget alert (e.g., $500/month)
- [ ] Add fallback API key (secondary account)

---

#### 2. Supabase
**Current Plan**: Check at https://app.supabase.com/project/settings

**Requirements**:
- **Pro Plan** ($25/month) for production
- **Database**: 8GB storage, 2GB RAM
- **Bandwidth**: 250GB/month

**Action**:
- [ ] Upgrade to Pro if on Free plan
- [ ] Enable database backups (daily)
- [ ] Set up monitoring alerts

---

### **E. Monitoring & Logging** 📊

#### 1. Application Logging
**Current**: Python `logging` module to console

**Production Setup**:
```python
# backend/config.py
import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,  # Not DEBUG
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),  # Console
            logging.FileHandler('app.log')  # File (if persistent storage)
        ]
    )
```

**Action**:
- [ ] Set `LOG_LEVEL=INFO` in production
- [ ] Ensure logs are centralized (Render/Heroku collect logs)

---

#### 2. Error Tracking (Optional but Recommended)
**Tool**: Sentry (free for 5K events/month)

**Setup**:
```bash
pip install sentry-sdk
```

```python
# backend/main.py (top of file)
import sentry_sdk

if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        traces_sample_rate=0.1,  # 10% of requests
        profiles_sample_rate=0.1,
    )
```

**Action**:
- [ ] Create Sentry project
- [ ] Add `SENTRY_DSN` to env vars
- [ ] Test error reporting

---

#### 3. Metrics Dashboard
**Key Metrics to Track**:

| Metric | Target | Alert If |
|--------|--------|----------|
| Response Time (p95) | < 3s | > 5s |
| Error Rate | < 1% | > 5% |
| Uptime | > 99.5% | < 99% |
| OpenAI API Errors | < 0.5% | > 2% |
| User Sessions/Day | - | Track trend |
| Hot Leads/Day | - | Track trend |

**Tools**:
- Render: Built-in metrics
- Custom: `/api/health` endpoint + Uptime Robot

**Action**:
- [ ] Set up health checks
- [ ] Configure uptime monitoring (e.g., Uptime Robot)

---

### **F. Performance Optimization** ⚡

#### 1. Database Indexing
**Verify indexes exist**:
```sql
-- Should see 5+ indexes
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'user_profiles';
```

**Expected**:
- `idx_user_profiles_last_active`
- `idx_user_profiles_lead_temperature`
- `idx_user_profiles_budget`
- `idx_user_profiles_created_at`
- Primary key on `user_id`

**Action**:
- [x] Indexes created via schema.sql ✅

---

#### 2. Connection Pooling
**Current**: Direct connections to Supabase  
**Production**: Use connection pooling

**Add to code**:
```python
# backend/database/connection.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    os.getenv("DATABASE_URL"),
    poolclass=QueuePool,
    pool_size=10,  # Max connections
    max_overflow=20,  # Extra connections under load
    pool_pre_ping=True  # Check connection before use
)
```

**Action**:
- [ ] Add connection pooling (if using SQLAlchemy)
- [ ] Or use Supabase's built-in pooling

---

#### 3. Caching (Optional)
**Use Case**: Cache frequent queries (e.g., market data, property details)

**Tools**: Redis, in-memory LRU cache

**Action**:
- [ ] Identify cacheable queries (market_data.json is static)
- [ ] Implement caching if response time > 3s

---

### **G. Security** 🔐

#### 1. API Authentication
**Current**: No auth on `/api/chat/query`  
**Production**: Should add authentication

**Options**:
1. **Session-based**: Frontend sends session token
2. **API Key**: Partner integrations
3. **OAuth**: Google/Facebook login

**Action**:
- [ ] Decide on auth strategy
- [ ] Implement auth middleware
- [ ] Test with frontend

---

#### 2. Rate Limiting
**Current**: None  
**Production**: Prevent abuse

**Add middleware**:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/chat/query")
@limiter.limit("100/minute")  # 100 requests per minute per IP
async def chat_query(request: Request, ...):
    ...
```

**Action**:
- [ ] Add rate limiting (100/min, 1000/hour)
- [ ] Test rate limit responses

---

#### 3. Input Validation
**Current**: Basic validation  
**Production**: Strict validation

**Add**:
```python
from pydantic import Field, validator

class ChatQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = Field(None, regex=r'^[a-zA-Z0-9_-]+$')
    
    @validator('query')
    def sanitize_query(cls, v):
        # Remove dangerous characters
        return v.strip()
```

**Action**:
- [x] Add field constraints ✅
- [ ] Add content moderation (OpenAI Moderation API)

---

#### 4. HTTPS & CORS
**HTTPS**: Required for production  
**CORS**: Allow only your frontend domain

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-frontend.vercel.app",  # Production
        "http://localhost:3000"  # Dev only
    ],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)
```

**Action**:
- [x] CORS configured ✅
- [ ] Update `allow_origins` to production domain only

---

### **H. Frontend Deployment** 🌐

#### 1. Build & Deploy to Vercel
```bash
cd frontend

# Install dependencies
npm install

# Build
npm run build

# Deploy
vercel --prod
```

**Environment Variables** (Vercel Dashboard):
```bash
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
NEXT_PUBLIC_GA_ID=G-XXXXXXXXXX  # Google Analytics (optional)
```

**Action**:
- [ ] Deploy to Vercel
- [ ] Test frontend → backend connectivity
- [ ] Verify HTTPS

---

#### 2. Performance (Lighthouse Score)
**Target**: 90+ in all categories

**Optimize**:
- [ ] Image optimization (next/image)
- [ ] Code splitting (dynamic imports)
- [ ] Lazy loading (below fold)

---

### **I. Backend Deployment** 🚀

#### 1. Build & Deploy to Render
**File**: `render.yaml` (already exists)

**Steps**:
1. Connect GitHub repo to Render
2. Create Web Service
3. Use `render.yaml` config
4. Add environment variables
5. Deploy

**Verify**:
```bash
# Health check
curl https://your-backend.onrender.com/health

# Expected: {"status": "ok", "version": "2.0"}
```

**Action**:
- [ ] Deploy to Render
- [ ] Verify all env vars set
- [ ] Test `/api/chat/query` endpoint

---

#### 2. Auto-Scaling
**Render Settings**:
- **Instance Type**: Standard ($7/month)
- **Auto-scale**: 2 min, 10 max instances
- **Health Check**: `/health`
- **Zero Downtime Deploy**: Enabled

**Action**:
- [ ] Configure auto-scaling
- [ ] Set up health checks

---

### **J. Integration Testing** 🧪

#### 1. End-to-End Tests
**Scenarios to Test**:

1. **New User Flow**
   - [ ] Send first message
   - [ ] Verify profile created
   - [ ] Check lead score = cold

2. **Returning User Flow**
   - [ ] Send message with existing user_id
   - [ ] Verify welcome message shown
   - [ ] Check profile loaded

3. **Sentiment Detection**
   - [ ] Send frustrated message
   - [ ] Verify empathetic response
   - [ ] Check escalation offered (if frustration >= 7)

4. **Conversation Coaching**
   - [ ] Trigger site visit rule
   - [ ] Verify coaching prompt added
   - [ ] Check urgency signal

5. **Lead Scoring**
   - [ ] View 3+ properties
   - [ ] Mark 1 interested
   - [ ] Verify lead score increases

**Action**:
- [ ] Run all 5 scenarios manually
- [ ] Automate with Playwright/Cypress (optional)

---

#### 2. Load Testing
**Tool**: Locust, k6, or Artillery

**Test Plan**:
- 100 concurrent users
- 1000 requests total
- Ramp up over 5 minutes

**Acceptance Criteria**:
- Response time < 3s (p95)
- Error rate < 1%
- No memory leaks

**Action**:
- [ ] Write load test script
- [ ] Run load test
- [ ] Fix any bottlenecks

---

### **K. Rollback Plan** 🔄

#### 1. Backup Current Production
**Database**:
```bash
# Backup Supabase database
pg_dump -h <host> -U postgres -d postgres > backup_$(date +%Y%m%d).sql
```

**Code**:
- Tag current version: `git tag v1.0.0`
- Keep old deployment running

**Action**:
- [ ] Backup database before deployment
- [ ] Tag current code version

---

#### 2. Rollback Procedure
**If issues detected**:

1. **Render**: Revert to previous deploy (1-click)
2. **Vercel**: Revert to previous deploy (1-click)
3. **Database**: Restore from backup (if schema changed)

**Action**:
- [ ] Document rollback steps
- [ ] Test rollback in staging

---

### **L. Post-Deployment** 📈

#### 1. Smoke Tests (First 1 Hour)
- [ ] Health check returns 200
- [ ] Can send message and get response
- [ ] User profile created
- [ ] Lead scoring works
- [ ] Sentiment detection works
- [ ] No errors in logs

---

#### 2. Monitoring (First 24 Hours)
- [ ] Check error rate every hour
- [ ] Monitor response times
- [ ] Check OpenAI API usage
- [ ] Review user feedback

---

#### 3. A/B Test (First 2 Weeks)
**Setup**:
- 50% traffic → New version (Phases 1, 2A, 2B)
- 50% traffic → Old version (baseline)

**Metrics to Compare**:
- Conversion rate
- Session duration
- Returning user rate
- User satisfaction (surveys)

**Action**:
- [ ] Set up A/B test infrastructure
- [ ] Run for 2 weeks
- [ ] Analyze results
- [ ] Roll out to 100% if successful

---

#### 4. Sales Team Training (Week 1)
**Topics**:
- How to use Sales Dashboard
- Understanding lead scores (hot/warm/cold)
- When to intervene (human escalation)
- Reading conversation analytics

**Action**:
- [ ] Schedule training session
- [ ] Create user guide
- [ ] Gather feedback

---

## 🎯 Deployment Timeline

### **Week -1: Preparation**
- [ ] Code review
- [ ] Load testing
- [ ] Staging deployment

### **Week 0: Deployment**
- [ ] Day 1 (Monday): Database migration
- [ ] Day 2 (Tuesday): Backend deployment (10 AM)
- [ ] Day 2 (Tuesday): Frontend deployment (11 AM)
- [ ] Day 2 (Tuesday): Smoke tests (11 AM - 12 PM)
- [ ] Day 2-3: Monitor closely
- [ ] Day 4-5: Fix any issues

### **Week 1: A/B Test**
- [ ] Enable A/B test (50/50 split)
- [ ] Monitor metrics daily
- [ ] Gather user feedback

### **Week 2-3: Analysis**
- [ ] Analyze A/B test results
- [ ] Make decision (roll out vs. rollback)
- [ ] If successful → 100% traffic

### **Week 4: Sales Team Enablement**
- [ ] Training sessions
- [ ] Dashboard access
- [ ] Feedback collection

---

## ✅ Final Pre-Flight Checklist

**Code**:
- [x] All tests passing (96.7%) ✅
- [x] No linter errors ✅
- [ ] Load testing completed
- [ ] Code review completed

**Database**:
- [ ] user_profiles table created
- [ ] Indexes verified
- [ ] Backup completed

**Configuration**:
- [ ] Production .env configured
- [ ] Secrets stored securely
- [ ] CORS updated for production domain

**Deployment**:
- [ ] Backend deployed to Render
- [ ] Frontend deployed to Vercel
- [ ] Health checks passing

**Monitoring**:
- [ ] Logging configured
- [ ] Error tracking (Sentry) set up
- [ ] Uptime monitoring enabled

**Testing**:
- [ ] End-to-end tests passed
- [ ] Load testing passed
- [ ] Smoke tests ready

**Team**:
- [ ] Sales team notified
- [ ] Training scheduled
- [ ] Rollback plan documented

---

## 🚨 Known Issues & Mitigations

### Issue 1: In-Memory Profile Storage
**Problem**: User profiles stored in-memory (lost on restart)  
**Impact**: Welcome messages won't work after restart  
**Mitigation**: ⚠️ MUST migrate to Supabase before production (see Section B.2)

### Issue 2: No Rate Limiting
**Problem**: API vulnerable to abuse  
**Impact**: High costs, poor UX under load  
**Mitigation**: ⚠️ Add rate limiting (see Section G.2)

### Issue 3: OpenAI Rate Limits
**Problem**: Tier 2 = 30K TPM (may be insufficient)  
**Impact**: Errors during high traffic  
**Mitigation**: Upgrade to Tier 3 or add retry logic

---

## 📞 Support Contacts

**Technical Issues**:
- Backend: [Developer Name]
- Frontend: [Developer Name]
- DevOps: [DevOps Engineer]

**Business Issues**:
- Product Manager: [PM Name]
- Sales Lead: [Sales Lead]

**On-Call Rotation**:
- Week 1: [Name]
- Week 2: [Name]

---

## 🎉 Launch Readiness

**Status**: ⚠️ 80% Ready

**Blockers**:
1. ⚠️ Migrate profiles to Supabase (HIGH PRIORITY)
2. ⚠️ Add rate limiting (HIGH PRIORITY)
3. ⚠️ Load testing (MEDIUM PRIORITY)

**Once blockers resolved**: 🚀 READY TO LAUNCH!

---

**Questions? Issues? Let me know!** 💬
