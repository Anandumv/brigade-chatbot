# 🎯 Conversation Coaching - Quick Reference Guide

## 🚀 Quick Start

### Run Tests
```bash
cd backend
python test_conversation_coaching.py
```

### Start Backend
```bash
cd backend
python main.py
```

---

## 📦 Services Overview

### 1. Conversation Director
```python
from services.conversation_director import get_conversation_director

director = get_conversation_director()

# Detect conversation stage
stage = director.detect_conversation_stage(session, query)
# Returns: "discovery", "evaluation", "negotiation", or "closing"

# Calculate engagement score
score = director.calculate_engagement_score(session)
# Returns: 0-10 score

# Get coaching prompt
prompt = director.get_coaching_prompt(session, query, context)
# Returns: {"type": "...", "priority": "...", "message": "...", "suggested_script": "..."}

# Track objection
objection = director.track_objection(session, query)
# Returns: "budget", "location", "construction_risk", or None
```

---

### 2. Market Intelligence
```python
from services.market_intelligence import get_market_intelligence

market = get_market_intelligence()

# Price comparison
comparison = market.get_price_comparison(project, locality="Whitefield")
# Returns: savings %, value proposition, price position

# Appreciation forecast
forecast = market.get_appreciation_forecast(project, locality="Whitefield")
# Returns: 3yr/5yr ROI, projected value, gain

# Locality insights
insights = market.get_locality_insights("Whitefield")
# Returns: avg price, appreciation, infrastructure, demographics

# Compare localities
comparison = market.compare_localities("Whitefield", "Sarjapur")
# Returns: side-by-side comparison with winners
```

---

### 3. Urgency Engine
```python
from services.urgency_engine import get_urgency_engine

urgency = get_urgency_engine()

# Get urgency signals
signals = urgency.get_urgency_signals(project, locality_data)
# Returns: List of urgency signals sorted by priority

# Signal types:
# - low_inventory: "Only 8 units left"
# - high_demand: "35 inquiries last week"
# - price_increase: "Prices increasing 10% in 15 days"
# - time_limited_offer: "Save ₹12 lakhs, offer ends in 10 days"
# - seasonal: "Financial year ending, claim tax benefits"
```

---

### 4. Budget Alternatives
```python
from services.hybrid_retrieval import hybrid_retrieval

# Get budget alternatives
alternatives = await hybrid_retrieval.get_budget_alternatives(
    original_filters=filters,
    budget_adjustment_percent=20.0,
    max_results=3
)

# Returns:
# {
#     "lower_budget": [...],      # 20% cheaper
#     "better_value": [...],      # 10-20% higher
#     "emerging_areas": [...],    # Same budget, better appreciation
#     "metadata": {...}
# }
```

---

### 5. Session Manager (Enhanced)
```python
from services.session_manager import SessionManager

session_manager = SessionManager()

# Track coaching prompt
session_manager.track_coaching_prompt(session_id, "site_visit_trigger")

# Check if prompt was shown
was_shown = session_manager.was_coaching_prompt_shown(
    session_id, 
    "site_visit_trigger", 
    within_minutes=30
)

# Update projects viewed
session_manager.update_projects_viewed(session_id, projects)

# Get engagement metrics
metrics = session_manager.get_engagement_metrics(session_id)
# Returns: message_count, projects_viewed, engagement_score, etc.
```

---

## 🎯 Coaching Rules Reference

### Conversion Triggers (HIGH Priority)

#### Site Visit Trigger
- **Conditions**: 3+ projects viewed, 5+ messages, evaluation/negotiation stage
- **Script**: "I can see you're really interested in {projects}! How about we schedule a site visit this weekend?"

#### Callback Trigger
- **Conditions**: 7+ messages, 2+ projects viewed, high engagement
- **Script**: "I'd love to connect you with our relationship manager. Would you prefer a call today evening or tomorrow morning?"

---

### Objection Handling (HIGH/MEDIUM Priority)

#### Budget Objection
- **Trigger**: User says "expensive", "too much", "cheaper", etc.
- **Framework**: LAER (Listen, Acknowledge, Explore, Respond)
- **Action**: Show budget alternatives + market intelligence + urgency

#### Location Objection
- **Trigger**: User says "too far", "far from", "location not good"
- **Response**: Emphasize connectivity, upcoming infrastructure, appreciation potential

#### Construction Risk Objection
- **Trigger**: User says "under construction", "delayed", "safe to buy"
- **Response**: Highlight RERA protection, builder track record, price advantage

---

### Qualification Opportunities (MEDIUM Priority)

#### Schools Query
- **Trigger**: User asks about "school", "education", "kids"
- **Action**: Ask "Do you have children? What grades are they in?"

#### Investment Query
- **Trigger**: User asks about "investment", "ROI", "appreciation"
- **Action**: Ask "Are you planning to stay here or is this an investment?"

---

### Upsell Opportunities (MEDIUM/LOW Priority)

#### Budget Upsell
- **Trigger**: Customer budget is X, show X+20% option
- **Script**: "For just ₹{difference} lakhs more, you get {benefits}. EMI difference is only ₹{emi}/month."

#### Configuration Upsell
- **Trigger**: Customer searching for 2BHK, has 3BHK options
- **Script**: "We also have 3BHK units for home office/future needs. Would you like to see those?"

---

## 📊 Market Data Available

### Localities Covered
1. **Whitefield** - IT corridor, high demand
2. **Sarjapur** - Emerging hotspot, high appreciation
3. **Electronic City** - Stable, IT campuses
4. **Hennur** - Growing, good connectivity
5. **Yelahanka** - Airport proximity
6. **Koramangala** - Premium, saturated
7. **HSR Layout** - High demand, young professionals
8. **Marathahalli** - Stable, IT corridor
9. **Bannerghatta Road** - Growing, nature lovers
10. **Devanahalli** - Emerging, highest appreciation

### Data Points
- Average price per sqft
- Price range (min/max)
- YoY appreciation rate
- 5-year historical appreciation
- Inventory trend
- Upcoming infrastructure
- Key attractions
- Demographics
- Rental yield
- Investment grade (A+, A, B+, B, C)

---

## 🎯 Conversation Stages

### Discovery
- **Goal**: Understand requirements (BHK, budget, location)
- **Triggers**: First 3 messages, property search performed
- **Actions**: Capture filters, show initial projects

### Evaluation
- **Goal**: Help customer compare and evaluate options
- **Triggers**: 3+ projects viewed, detailed questions
- **Actions**: Provide amenities, distances, market intelligence

### Negotiation
- **Goal**: Handle objections, overcome concerns
- **Triggers**: Objections raised, comparison queries
- **Actions**: LAER framework, budget alternatives, urgency signals

### Closing
- **Goal**: Schedule site visit, get commitment
- **Triggers**: "site visit", "schedule", "book", "token"
- **Actions**: Calendar integration, booking confirmation

---

## 🎓 Sales Frameworks Used

### LAER (Objection Handling)
1. **Listen**: Let customer express concern fully
2. **Acknowledge**: Show empathy, validate concern
3. **Explore**: Ask clarifying questions to uncover real objection
4. **Respond**: Provide 2-3 concrete solutions

### SPIN (Qualification)
1. **Situation**: "Are you currently renting?"
2. **Problem**: "What challenges are you facing?"
3. **Implication**: "How is the long commute affecting you?"
4. **Need-Payoff**: "How would living 10 mins from office improve your life?"

### BANT (Lead Scoring - Future)
1. **Budget**: Does customer have adequate budget?
2. **Authority**: Are they the decision maker?
3. **Need**: Do they have genuine need?
4. **Timeline**: When are they planning to buy?

---

## 💡 Best Practices

### 1. Coaching Prompt Frequency
- Don't show same prompt within 30 minutes
- Track with `session_manager.track_coaching_prompt()`
- Check with `session_manager.was_coaching_prompt_shown()`

### 2. Priority Handling
- CRITICAL/HIGH priority prompts override others
- Append high-priority scripts to response
- Log all coaching prompts for analysis

### 3. Budget Alternatives
- Only show when budget objection detected
- Limit to 2-3 alternatives per category
- Include emerging areas for better appreciation

### 4. Market Intelligence
- Show for top 3 projects only (avoid overwhelming)
- Combine with urgency signals for impact
- Use investment grade (A+, A) to build trust

### 5. Urgency Signals
- Maximum 3 signals per project
- Sort by priority score (highest first)
- Use authentic data (inventory, demand, offers)

---

## 🔍 Debugging

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Coaching Trigger
```python
logger.info(f"💡 COACHING: {coaching_prompt['type']} - {coaching_prompt['message']}")
```

### Verify Market Data
```python
insights = market_intel.get_locality_insights("Whitefield")
if not insights:
    logger.error("No market data for Whitefield")
```

### Test Objection Detection
```python
objection = director.track_objection(session, "It's too expensive")
logger.info(f"Detected objection: {objection}")  # Should be "budget"
```

---

## 📈 Monitoring

### Key Metrics to Track

**Coaching Effectiveness**:
- Coaching prompts triggered per session
- Site visit trigger → actual booking rate
- Budget objection → alternatives acceptance rate

**Engagement**:
- Average engagement score
- Stage progression (discovery → closing)
- Time spent in each stage

**Conversion**:
- Discovery → Evaluation rate
- Evaluation → Negotiation rate
- Negotiation → Closing rate
- Overall conversion rate

---

## 🚨 Common Issues

### Issue: Coaching prompt not triggering
**Solution**: Check conditions in `coaching_rules.py`, verify session state

### Issue: Market data not loading
**Solution**: Verify `market_data.json` path, check file permissions

### Issue: Budget alternatives empty
**Solution**: Check if filters have budget_max, verify database has projects

### Issue: Urgency signals not showing
**Solution**: Check if locality_data is passed, verify project has required fields

---

## 📞 Support

For questions or issues:
1. Check logs: `backend/uvicorn.log`
2. Run tests: `python test_conversation_coaching.py`
3. Review implementation: `CONVERSATION_COACHING_IMPLEMENTATION_COMPLETE.md`
4. Check gap analysis: `SALES_AI_GAP_ANALYSIS_ENHANCEMENT_PLAN.md`

---

**Happy Coaching! 🚀**
