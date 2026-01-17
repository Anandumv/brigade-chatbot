# 🏗️ Sales AI Chatbot - System Architecture

**Version**: 2.0 (Phases 1, 2A, 2B Complete)  
**Date**: January 17, 2026

---

## 🎯 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│                         USER (Web/Mobile/API)                            │
│                                                                          │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  │ HTTP/S
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js/React)                         │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────────┐  │
│  │  Chat UI       │  │  Property      │  │  Sales Dashboard         │  │
│  │  • Messages    │  │  Cards         │  │  • Hot Leads            │  │
│  │  • Chips       │  │  • Expandable  │  │  • Analytics            │  │
│  │  • Typing      │  │  • Actions     │  │  • Heatmaps             │  │
│  └────────────────┘  └────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │ REST API
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    API LAYER (FastAPI/main.py)                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     /api/chat/query                               │  │
│  │  1. Load User Profile (user_profile_manager)                     │  │
│  │  2. Load Session (session_manager)                               │  │
│  │  3. Preprocess Query (query_preprocessor)                        │  │
│  │  4. Enrich with Context (context_injector)                       │  │
│  │  5. Classify Intent (intent_classifier)                          │  │
│  │  6. Analyze Sentiment (sentiment_analyzer)                       │  │
│  │  7. Generate Response (gpt_sales_consultant)                     │  │
│  │  8. Apply Coaching (conversation_director)                       │  │
│  │  9. Track Profile (user_profile_manager)                         │  │
│  │  10. Update Session (session_manager)                            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                  ┌───────────────┼───────────────┐
                  │               │               │
                  ▼               ▼               ▼
┌──────────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  CORE SERVICES       │ │  SUPPORT     │ │  DATA LAYER      │
│                      │ │  SERVICES    │ │                  │
│  • Session Mgr      │ │  • Market    │ │  • Pixeltable    │
│  • Profile Mgr      │ │    Intel     │ │    (Projects)    │
│  • Intent Class     │ │  • Urgency   │ │  • Supabase      │
│  • Sentiment        │ │    Engine    │ │    (Profiles)    │
│  • GPT Consultant   │ │              │ │  • Vector Store  │
│  • Hybrid Retrieval │ │              │ │    (Embeddings)  │
│  • Conversation Dir │ │              │ │                  │
└──────────────────────┘ └──────────────┘ └──────────────────┘
         │                       │                  │
         └───────────────────────┴──────────────────┘
                          │
                          ▼
         ┌────────────────────────────────────────┐
         │      EXTERNAL SERVICES                 │
         │  • OpenAI (GPT-4, Embeddings)         │
         │  • Supabase (PostgreSQL)              │
         │  • Pixeltable (Project Database)      │
         └────────────────────────────────────────┘
```

---

## 🔄 Request Flow (Detailed)

```
1. USER SENDS MESSAGE
   │
   ├─► "Show me 2BHK in Whitefield under 2 Cr"
   │
   └─► POST /api/chat/query
       {
         "query": "Show me 2BHK in Whitefield under 2 Cr",
         "session_id": "sess_123",
         "user_id": "user_abc"
       }

2. API HANDLER (main.py)
   │
   ├─► Step 0.5: Load User Profile
   │   ├─ user_profile_manager.get_or_create_profile("user_abc")
   │   ├─ Check total_sessions (2 = returning user)
   │   ├─ Generate welcome_back_message
   │   └─ Calculate lead_score (engagement + intent)
   │
   ├─► Step 0.55: Load Session
   │   ├─ session_manager.get_or_create_session("sess_123")
   │   └─ Load conversation_history (last 10 turns)
   │
   ├─► Step 1: Preprocess Query
   │   ├─ query_preprocessor.preprocess(query)
   │   └─ Normalize: "2bhk" → "2BHK", "whitfield" → "Whitefield"
   │
   ├─► Step 2: Enrich with Context
   │   ├─ context_injector.enrich_query_with_context(query, session)
   │   └─ Add: budget range, preferred locations from history
   │
   ├─► Step 3: Classify Intent
   │   ├─ intent_classifier.classify_intent_with_gpt(query, history)
   │   └─ Result: "property_search"
   │
   ├─► Step 4: Analyze Sentiment
   │   ├─ sentiment_analyzer.analyze_sentiment(query)
   │   └─ Result: {"sentiment": "neutral", "frustration_level": 0}
   │
   ├─► Step 5: Generate Response
   │   ├─ gpt_sales_consultant.generate_response(query, session, intent, sentiment)
   │   ├─ Call hybrid_retrieval.search_properties(filters)
   │   ├─ Get 3 best matches
   │   └─ Format response with GPT-4
   │
   ├─► Step 6: Apply Conversation Coaching
   │   ├─ conversation_director.analyze_conversation(session)
   │   ├─ Detect stage: "awareness"
   │   ├─ Calculate engagement: 3.5/10
   │   ├─ Check coaching_rules for triggers
   │   ├─ Add: "💡 Would you also like to know about schools nearby?"
   │   └─ Inject urgency: "⚡ Only 12 units left!"
   │
   ├─► Step 7: Add Welcome Back (if returning)
   │   └─ Prepend: "Welcome back! Last time you explored Brigade Citrine..."
   │
   ├─► Step 8: Track User Profile
   │   ├─ profile_manager.track_property_viewed("user_abc", "proj_001", "Brigade Citrine")
   │   ├─ profile_manager.track_sentiment("user_abc", "neutral", 0)
   │   └─ profile_manager.update_preferences("user_abc", budget_max=20000)
   │
   └─► Step 9: Update Session
       ├─ session.messages.append({"user": query, "assistant": response})
       ├─ session.last_intent = "property_search"
       └─ session_manager.save_session(session)

3. RETURN RESPONSE
   │
   └─► {
         "answer": "Welcome back! ...[response]... 💡 [coaching]... ⚡ [urgency]",
         "sources": [...],
         "confidence": "High",
         "session_id": "sess_123",
         "intent": "property_search",
         "suggested_actions": ["Schedule Site Visit", "Download Brochure"],
         "response_time_ms": 1850
       }
```

---

## 🧩 Component Details

### **1. Session Manager** (`session_manager.py`)
**Responsibility**: Maintain conversation state within a session

```
┌─────────────────────────────────────────┐
│         Session Manager                 │
│                                         │
│  ConversationSession {                 │
│    session_id: str                     │
│    messages: List[Message]             │
│    current_filters: Dict               │
│    interested_projects: List[str]      │
│    last_intent: str                    │
│    conversation_phase: str             │
│    objection_count: int                │
│    last_sentiment: str                 │
│    frustration_score: float            │
│  }                                      │
│                                         │
│  Methods:                               │
│  • get_or_create_session()             │
│  • add_message()                        │
│  • update_filters()                     │
│  • record_objection()                   │
│  • get_context_summary()                │
└─────────────────────────────────────────┘
```

**Storage**: In-memory dictionary (can be Redis/Supabase)

---

### **2. User Profile Manager** (`user_profile_manager.py`)
**Responsibility**: Persist user data across sessions

```
┌─────────────────────────────────────────┐
│       User Profile Manager              │
│                                         │
│  UserProfile {                          │
│    user_id: str                         │
│    preferences: {budget, config, loc}   │
│    properties_viewed: List[Dict]        │
│    interested_projects: List[Dict]      │
│    objections_history: List[Dict]       │
│    sentiment_history: List[Dict]        │
│    engagement_score: float (0-10)       │
│    intent_to_buy_score: float (0-10)    │
│    lead_temperature: str (hot/warm/cold)│
│    total_sessions: int                  │
│  }                                      │
│                                         │
│  Methods:                               │
│  • get_or_create_profile()             │
│  • track_property_viewed()             │
│  • mark_interested()                    │
│  • track_objection()                    │
│  • track_sentiment()                    │
│  • calculate_lead_score()               │
│  • get_welcome_back_message()           │
└─────────────────────────────────────────┘
```

**Storage**: PostgreSQL/Supabase (`user_profiles` table)

---

### **3. Conversation Director** (`conversation_director.py`)
**Responsibility**: Analyze conversation and trigger coaching

```
┌─────────────────────────────────────────┐
│       Conversation Director             │
│                                         │
│  Capabilities:                          │
│  • Detect conversation stage            │
│    (awareness → consideration → decision)│
│  • Calculate engagement score           │
│    (message count, timing, sentiment)   │
│  • Trigger coaching rules               │
│    (site visit, objection, qualification)│
│  • Inject market intelligence           │
│  • Generate urgency signals             │
│                                         │
│  Methods:                               │
│  • analyze_conversation()               │
│  • detect_stage()                       │
│  • calculate_engagement()               │
│  • get_coaching_prompt()                │
│  • track_objection()                    │
└─────────────────────────────────────────┘
```

**Logic**: Rule-based (COACHING_RULES from `coaching_rules.py`)

---

### **4. Sentiment Analyzer** (`sentiment_analyzer.py`)
**Responsibility**: Detect user sentiment and frustration

```
┌─────────────────────────────────────────┐
│        Sentiment Analyzer               │
│                                         │
│  Input: User query                      │
│  Output: {                              │
│    sentiment: str (positive/negative/   │
│               neutral/frustrated/excited)│
│    frustration_level: int (0-10)        │
│    reasoning: str                       │
│  }                                      │
│                                         │
│  Methods:                               │
│  • analyze_sentiment()                  │
│  • get_tone_adjustment()                │
│    (empathy for frustrated,             │
│     enthusiasm for excited)             │
│                                         │
│  Powered by: GPT-4 (structured output)  │
└─────────────────────────────────────────┘
```

---

### **5. GPT Sales Consultant** (`gpt_sales_consultant.py`)
**Responsibility**: Generate natural, context-aware responses

```
┌─────────────────────────────────────────┐
│        GPT Sales Consultant             │
│                                         │
│  Capabilities:                          │
│  • Natural language generation          │
│  • Context-aware responses              │
│  • Sentiment-adaptive tone              │
│  • Property data formatting             │
│  • Objection handling                   │
│                                         │
│  Process:                               │
│  1. Build context from session          │
│  2. Add retrieved properties            │
│  3. Apply sentiment tone adjustment     │
│  4. Generate response with GPT-4        │
│  5. Format with markdown                │
│                                         │
│  Powered by: GPT-4 Turbo                │
└─────────────────────────────────────────┘
```

---

### **6. Hybrid Retrieval** (`hybrid_retrieval.py`)
**Responsibility**: Fetch relevant properties from database

```
┌─────────────────────────────────────────┐
│         Hybrid Retrieval                │
│                                         │
│  Methods:                               │
│  • search_properties()                  │
│    - Filters: budget, config, location  │
│    - Semantic search (embeddings)       │
│    - Structured filters (SQL)           │
│    - Hybrid ranking                     │
│                                         │
│  • get_budget_alternatives()            │
│    - Cheaper (10-20% less)              │
│    - Better value (10-15% more)         │
│    - Emerging areas (similar budget)    │
│                                         │
│  • compare_localities()                 │
│    - Price comparison                   │
│    - Appreciation potential             │
│                                         │
│  Data Source: Pixeltable (brigade.projects)│
└─────────────────────────────────────────┘
```

---

## 🗄️ Data Models

### **ConversationSession** (Session Manager)
```python
class ConversationSession(BaseModel):
    session_id: str
    user_id: Optional[str]
    messages: List[Dict[str, Any]] = []
    current_filters: Dict[str, Any] = {}
    interested_projects: List[str] = []
    last_intent: Optional[str] = None
    last_topic: Optional[str] = None
    conversation_phase: str = "awareness"
    objection_count: int = 0
    coaching_prompts_shown: List[str] = []
    last_message_time: Optional[datetime] = None
    projects_viewed_count: int = 0
    last_sentiment: str = "neutral"
    frustration_score: float = 0.0
    sentiment_history: List[Dict[str, Any]] = []
    last_shown_projects: List[Dict] = []
```

---

### **UserProfile** (User Profile Manager)
```python
class UserProfile(BaseModel):
    user_id: str
    name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    
    # Preferences
    budget_min: Optional[int]
    budget_max: Optional[int]
    preferred_configurations: List[str] = []
    preferred_locations: List[str] = []
    must_have_amenities: List[str] = []
    
    # History
    total_sessions: int = 0
    properties_viewed: List[Dict] = []  # [{id, name, view_count, viewed_at}]
    interested_projects: List[Dict] = []  # [{id, name, interest_level}]
    objections_history: List[Dict] = []  # [{type, count, last_raised_at}]
    sentiment_history: List[Dict] = []  # [{sentiment, frustration, timestamp}]
    
    # Scoring
    engagement_score: float = 0.0  # 0-10
    intent_to_buy_score: float = 0.0  # 0-10
    lead_temperature: str = "cold"  # hot/warm/cold
    
    # Analytics
    site_visits_scheduled: int = 0
    callbacks_requested: int = 0
    brochures_downloaded: int = 0
    
    # Timestamps
    created_at: datetime
    last_active: datetime
```

---

## 🔐 Security & Privacy

### Authentication
- **Frontend**: Session tokens (JWT)
- **Backend**: API key validation
- **Admin**: Separate ADMIN_KEY for sensitive ops

### Data Protection
- **User Profiles**: Encrypted at rest (Supabase)
- **PII**: Name, phone, email stored securely
- **Conversations**: Session data expires after 30 days
- **GDPR**: User can request data deletion

### Rate Limiting
- 100 requests/minute per IP
- 1000 requests/hour per user
- Prevents abuse

---

## 📊 Monitoring & Logging

### Application Logs
```python
logger.info(f"👋 RETURNING USER: {user_id} (session #{total_sessions})")
logger.info(f"📊 LEAD SCORE: {lead_temperature} (engagement: {engagement}/10)")
logger.warning(f"🚨 HUMAN ESCALATION OFFERED (frustration: {frustration}/10)")
```

### Metrics to Track
- **Performance**: Response time, API latency
- **Usage**: Queries/day, users/day, sessions/user
- **Quality**: Sentiment distribution, frustration incidents
- **Business**: Conversion rate, hot leads, site visits

### Tools
- **Backend**: Python `logging` module
- **APM**: (Future) Datadog, New Relic
- **Analytics**: (Future) Mixpanel, Amplitude

---

## 🚀 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CLOUDFLARE CDN                         │
│                    (Frontend Static Files)                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    VERCEL (Frontend)                        │
│                  Next.js 14 App Router                      │
│                  • Server-side rendering                    │
│                  • API routes (proxy)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   RENDER (Backend)                          │
│                  FastAPI + Uvicorn                          │
│                  • Auto-scaling (2-10 instances)            │
│                  • Health checks                            │
│                  • SSL/TLS                                  │
└──────────┬───────────────┴───────────────┬──────────────────┘
           │                               │
           ▼                               ▼
┌──────────────────────┐       ┌────────────────────────────┐
│   SUPABASE           │       │   OPENAI                   │
│   (PostgreSQL)       │       │   • GPT-4 Turbo           │
│   • user_profiles    │       │   • text-embedding-3-small│
│   • sessions (future)│       │   • Structured outputs    │
└──────────────────────┘       └────────────────────────────┘
```

---

## 📈 Scalability Considerations

### Current Capacity
- **Concurrent Users**: 100-500
- **Requests/Second**: 10-50
- **Database**: 10K users, 100K sessions
- **Response Time**: 1.5-2.5s

### Bottlenecks
1. **OpenAI API**: 3500 TPM (tokens/min) limit
2. **Pixeltable**: No connection pooling
3. **Session Storage**: In-memory (not distributed)

### Scale Plan (10x traffic)
1. **OpenAI**: Upgrade to Tier 4 (90K TPM)
2. **Database**: Connection pooling (PgBouncer)
3. **Sessions**: Move to Redis (distributed cache)
4. **Backend**: Auto-scale 2 → 20 instances
5. **CDN**: Cloudflare for static assets

---

## 🎯 Next Steps

**Immediate** (Week 1):
- Deploy Phases 1, 2A, 2B to production
- Monitor metrics (conversion, engagement, sentiment)
- Gather user feedback

**Short-term** (Month 1):
- Implement Phase 2C (proactive nudges + dashboard)
- Optimize lead scoring thresholds
- Add more coaching rules based on real conversations

**Long-term** (Months 2-4):
- Phase 3: Multimodal, Calendar, Follow-ups
- Phase 4: Predictive ML, Voice, Multi-project

---

**Architecture is solid! Ready for production! 🚀**
