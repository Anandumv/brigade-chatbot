# Sales Coaching System - Troubleshooting Guide

## Current Issue: Backend Deployment Failed ❌

### Problem
The coaching system is fully implemented in the code, but the Railway backend deployment is returning:
```
{"status":"error","code":404,"message":"Application not found"}
```

This means:
1. ✅ **Code is correct** - All coaching features are implemented
2. ✅ **Frontend is deployed** - Vercel deployment successful
3. ❌ **Backend is not running** - Railway deployment failed

### Why You Don't See Coaching Prompts

The coaching prompts require the backend to be running because they are generated in [backend/main.py](backend/main.py:1187-1487). Since the backend is down, the frontend can't get coaching data.

---

## Solution 1: Test Locally First (Recommended)

### Step 1: Start Backend Locally

```bash
cd backend

# Make sure pixeltable is running
pixeltable --start

# Start the FastAPI server
uvicorn main:app --reload --port 8000
```

### Step 2: Start Frontend Locally

```bash
cd frontend

# Make sure API URL points to local backend
# Check frontend/.env.local has:
# NEXT_PUBLIC_API_URL=http://localhost:8000

npm run dev
```

### Step 3: Test Coaching Triggers

Visit `http://localhost:3000` and follow this conversation flow:

#### 🧪 Test Scenario 1: Site Visit Trigger
```
You (as salesman): "Show me 2BHK in Whitefield under 2 Cr"
AI: [Shows 3 projects]

You: "Tell me about Brigade Citrine"
AI: [Shows project details]

You: "What are the amenities?"
AI: [Shows amenities]

You: "Tell me about Prestige Lakeside Habitat"
AI: [Shows another project]

You: "When is the possession date?"
AI: [Shows possession info]

💡 EXPECTED COACHING PROMPT (after 5+ messages, 3+ projects viewed):
┌─────────────────────────────────────────────────────┐
│ ⚠️ 💡 Sales Coaching   [HIGH] [Action Suggestion]   │
│                                                     │
│ Customer viewed 3 projects + asking detailed       │
│ questions. TIME TO CLOSE - Suggest site visit NOW. │
│                                                     │
│ 📝 SUGGESTED SCRIPT:                                │
│ "I can see you're really interested in these       │
│  projects! How about we schedule a site visit      │
│  this weekend?"                                     │
└─────────────────────────────────────────────────────┘
```

#### 🧪 Test Scenario 2: Budget Objection
```
You: "Show me 3BHK in Sarjapur"
AI: [Shows projects]

You: "This seems too expensive"
AI: [Handles objection]

💡 EXPECTED COACHING PROMPT:
┌─────────────────────────────────────────────────────┐
│ ⚠️ 💡 Sales Coaching   [HIGH] [Objection Handling]  │
│                                                     │
│ BUDGET OBJECTION: Customer concerned about pricing.│
│ Emphasize value, market comparison, and flexible   │
│ payment plans.                                      │
│                                                     │
│ 📝 SUGGESTED SCRIPT:                                │
│ "I understand budget is important. This project is │
│  12% below market average. Plus, with flexible EMI │
│  plans, it's quite affordable."                    │
└─────────────────────────────────────────────────────┘
```

---

## Solution 2: Fix Railway Deployment

### Why Railway Failed

Possible reasons:
1. **Missing Environment Variables** - Pixeltable credentials not set
2. **Port Configuration** - Railway might need specific port binding
3. **Startup Command** - Wrong command in railway.json
4. **Dependencies** - Some packages failed to install

### Fix Steps

#### Check Railway Logs
1. Go to Railway dashboard: https://railway.app/
2. Find your backend project
3. Click "Deployments" → Latest deployment
4. Check logs for errors like:
   - `ModuleNotFoundError` (missing dependency)
   - `Connection refused` (database/pixeltable not accessible)
   - `Port binding error`

#### Common Fixes

**Fix 1: Environment Variables**
Railway needs these variables set:
```bash
# In Railway dashboard → Variables tab:
PIXELTABLE_API_KEY=your_api_key
PIXELTABLE_PROJECT=your_project
OPENAI_API_KEY=your_openai_key
PORT=8000
```

**Fix 2: Railway Configuration**
Check `railway.json` or `railway.toml`:
```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

**Fix 3: Procfile** (if using Procfile)
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

**Fix 4: Requirements**
Make sure `backend/requirements.txt` has all dependencies:
```
fastapi
uvicorn[standard]
pixeltable
openai
pydantic
python-multipart
```

---

## Solution 3: Use Alternative Hosting

If Railway continues to fail, try:

### Option A: Render.com
```bash
# In Render dashboard:
1. Create new "Web Service"
2. Connect GitHub repo
3. Root directory: "backend"
4. Build command: "pip install -r requirements.txt"
5. Start command: "uvicorn main:app --host 0.0.0.0 --port $PORT"
```

### Option B: Fly.io
```bash
cd backend
fly launch
# Follow prompts, will create fly.toml
fly deploy
```

### Option C: Local Ngrok (Quick Test)
```bash
# Terminal 1: Start backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2: Expose with ngrok
ngrok http 8000

# Copy ngrok URL (e.g., https://abc123.ngrok.io)
# Update frontend/.env.local:
# NEXT_PUBLIC_API_URL=https://abc123.ngrok.io

cd frontend
npm run dev
```

---

## Verification Checklist

Once backend is running, verify coaching works:

### ✅ Backend Health Check
```bash
# Should return: {"status": "ok", "version": "1.0"}
curl https://your-backend-url.com/health
```

### ✅ Coaching Endpoint Test
```bash
curl -X POST https://your-backend-url.com/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me 2BHK in Whitefield",
    "user_id": "test_salesman",
    "session_id": "test_session_001"
  }'

# Should include in response:
{
  "answer": "...",
  "coaching_prompt": {
    "type": "discovery_qualifier",
    "priority": "low",
    "message": "💡 DISCOVERY PHASE: Ask qualifying questions...",
    "suggested_script": "..."
  }
}
```

### ✅ Frontend Coaching Display
1. Open browser console (F12)
2. Send a query in the chat
3. Check network tab for `/api/chat/query` response
4. Verify `coaching_prompt` field exists
5. Look for CoachingPanel component rendering above assistant message

---

## Expected Behavior

### When Coaching Works Correctly

**Discovery Stage (First 1-3 messages):**
```
┌─────────────────────────────────────────────────────┐
│ ✨ 💡 Sales Coaching   [LOW] [Discovery Qualifier]  │
│                                                     │
│ DISCOVERY PHASE: Ask qualifying questions to       │
│ understand customer needs better.                  │
└─────────────────────────────────────────────────────┘
```

**Evaluation Stage (3-5 messages, 2+ projects viewed):**
```
┌─────────────────────────────────────────────────────┐
│ ✨ 💡 Sales Coaching   [MEDIUM] [Action Suggestion] │
│                                                     │
│ Customer comparing options. Offer side-by-side     │
│ comparison or focus on their top choice.           │
└─────────────────────────────────────────────────────┘
```

**Closing Stage (5+ messages, 3+ projects, detailed questions):**
```
┌─────────────────────────────────────────────────────┐
│ ⚠️ 💡 Sales Coaching   [HIGH] [Action Suggestion]   │
│                                                     │
│ Customer viewed 3 projects + asking detailed       │
│ questions. High engagement. TIME TO CLOSE.         │
│                                                     │
│ 📝 SUGGESTED SCRIPT:                                │
│ "Would you like to schedule a site visit this      │
│  weekend? I can arrange all 3 properties."         │
└─────────────────────────────────────────────────────┘
```

---

## Debug Commands

### Check Backend Logs
```bash
# Railway:
railway logs

# Local:
# Check terminal where uvicorn is running
# Look for lines like:
# 💡 COACHING: action_suggestion - Customer viewed 3 projects...
```

### Check Frontend Console
```javascript
// In browser console (F12):
// Look for coaching_prompt in network responses
// Filter by: /api/chat/query
// Check response payload for coaching_prompt field
```

### Test Coaching Rules Directly
```python
# backend/test_coaching.py
from services.conversation_director import get_conversation_director
from services.session_manager import get_session_manager

director = get_conversation_director()
session_manager = get_session_manager()

# Create test session
session_id = "test_001"
session_manager.create_session(session_id, "test_user")

# Simulate conversation
for i in range(6):
    session = session_manager.get_session(session_id)
    coaching = director.get_coaching_prompt(
        session=session.model_dump(),
        current_query=f"Test query {i}",
        context={"search_performed": True}
    )
    print(f"Message {i}: {coaching}")
```

---

## Still Not Working?

### Check These Files:

1. **[backend/main.py](backend/main.py:1187-1487)** - Coaching integration
2. **[backend/services/conversation_director.py](backend/services/conversation_director.py)** - Coaching logic
3. **[backend/models/coaching_rules.py](backend/models/coaching_rules.py)** - Rule definitions
4. **[frontend/src/components/CoachingPanel.tsx](frontend/src/components/CoachingPanel.tsx)** - UI component
5. **[frontend/src/components/ChatInterface.tsx](frontend/src/components/ChatInterface.tsx:467-471)** - Integration

### Contact Support

If none of these solutions work:
1. Share Railway deployment logs
2. Share frontend browser console errors
3. Share backend terminal output when running locally
4. Share example API request/response

---

## Quick Start (Recommended)

**Just want to see it working? Run locally:**

```bash
# Terminal 1: Backend
cd backend && uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Browser: http://localhost:3000
# Test conversation: Follow "Test Scenario 1" above
```

**Expected result:** After 5+ messages viewing 3+ projects, you'll see a HIGH priority coaching card suggesting a site visit.
