# Sales AI Coaching System - Setup & Usage Guide

## 🎯 Overview

The Sales AI Coaching System transforms your chatbot into an intelligent sales assistant that provides **real-time coaching prompts** to salesmen during live customer calls. It guides them on when to suggest site visits, how to handle objections, and what actions to take based on conversation flow.

## ✅ What's Implemented

### Backend Services

1. **Conversation Director** ([backend/services/conversation_director.py](backend/services/conversation_director.py))
   - Detects conversation stage (discovery → evaluation → negotiation → closing)
   - Calculates customer engagement score (0-10)
   - Generates coaching prompts based on rule triggers
   - Tracks objections and conversation metrics

2. **Coaching Rules Engine** ([backend/models/coaching_rules.py](backend/models/coaching_rules.py))
   - 8 pre-built coaching rules with trigger conditions
   - Priority levels: critical, high, medium, low
   - Coaching types: conversion trigger, action suggestion, objection handling, etc.
   - Suggested scripts for each coaching moment

3. **Market Intelligence** ([backend/services/market_intelligence.py](backend/services/market_intelligence.py))
   - Price comparison vs market average for 10 Bangalore localities
   - ROI and appreciation forecasts (3-year and 5-year projections)
   - Investment grading (A+, A, B+, B, C)
   - Competitive positioning data

4. **Urgency Engine** ([backend/services/urgency_engine.py](backend/services/urgency_engine.py))
   - Inventory scarcity signals ("Only 5 units left")
   - Price increase alerts ("Prices increasing 5% in 7 days")
   - Time-limited offers (early bird, festival, FY-end)
   - Social proof messaging

5. **Enhanced Session Manager** ([backend/services/session_manager.py](backend/services/session_manager.py))
   - Tracks objection_count, coaching_prompts_shown, projects_viewed_count
   - Records last_message_time for silence detection
   - Prevents duplicate coaching prompts

### Frontend Components

1. **CoachingPanel** ([frontend/src/components/CoachingPanel.tsx](frontend/src/components/CoachingPanel.tsx))
   - Visual coaching prompt card with priority badges
   - Color-coded by priority (red=critical, orange=high, blue=medium, gray=low)
   - Displays suggested scripts for salesman to use
   - Shown only when coaching_prompt is present in response

2. **Type Definitions** ([frontend/src/types/index.ts](frontend/src/types/index.ts))
   - CoachingPrompt interface with type, priority, message, suggested_script
   - Added coaching_prompt to ChatQueryResponse and Message types

3. **ChatInterface Integration** ([frontend/src/components/ChatInterface.tsx](frontend/src/components/ChatInterface.tsx))
   - Extracts coaching_prompt from API response
   - Passes coaching data to message state
   - Renders CoachingPanel component in message flow

## 🚀 Quick Start

### 1. Backend Setup

The coaching system is **already integrated** into the main API endpoint. No additional setup needed!

**How it works:**
- Every API response at `POST /chat` now includes an optional `coaching_prompt` field
- Coaching triggers fire automatically based on conversation context
- Backend analyzes conversation stage, engagement, and context to generate prompts

**Example API Response:**
```json
{
  "answer": "Here are 3 projects in Whitefield...",
  "projects": [...],
  "coaching_prompt": {
    "type": "action_suggestion",
    "priority": "high",
    "message": "💡 Customer viewed 3 projects + asking detailed questions. High engagement detected. TIME TO CLOSE - Suggest site visit NOW.",
    "suggested_script": "I can see you're really interested in these projects! The best way to experience the amenities is in person. How about we schedule a site visit this weekend?"
  }
}
```

### 2. Frontend Setup

The CoachingPanel is **already integrated** into ChatInterface. It will automatically display when a coaching prompt is returned.

**What you'll see:**
- Coaching prompts appear as colored cards above the assistant's response
- Priority badge shows importance (CRITICAL, HIGH, MEDIUM, LOW)
- Type badge shows coaching category (e.g., "Action Suggestion")
- Suggested script provides exact words for salesman to use

### 3. Start the Application

```bash
# Terminal 1: Start Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2: Start Frontend
cd frontend
npm run dev

# Visit: http://localhost:3000
```

## 📋 Coaching Rules Reference

### 1. Site Visit Trigger
**When:** Customer viewed 3+ projects, 5+ messages, in evaluation/negotiation stage
**Priority:** HIGH
**Message:** "💡 CONVERSION TRIGGER: Customer has viewed 3 projects and asking detailed questions. TIME TO CLOSE - Suggest site visit NOW."
**Script:** "I can see you're really interested in these projects! The best way to experience the amenities is in person. How about we schedule a site visit this weekend?"

### 2. Budget Objection Handler
**When:** Customer mentions price concerns ("expensive", "cheaper", "discount")
**Priority:** HIGH
**Message:** "💡 BUDGET OBJECTION: Customer concerned about pricing. Emphasize value, market comparison, and flexible payment plans."
**Script:** "I understand budget is important. This project is actually 12% below market average. Plus, with our flexible EMI plans starting at ₹X/month, it's quite affordable. Would you like to see the payment breakdown?"

### 3. Location Objection Handler
**When:** Customer mentions location concerns ("too far", "far from")
**Priority:** MEDIUM
**Message:** "💡 LOCATION OBJECTION: Customer worried about distance/connectivity. Highlight upcoming infrastructure and connectivity improvements."
**Script:** "I understand location is key! The good news is [Project] has excellent connectivity - just 15 km to airport, and the new Metro station is opening 1.5km away next year. This area is rapidly developing!"

### 4. Multiple Projects Viewed
**When:** Customer viewed 2+ projects, in evaluation stage
**Priority:** MEDIUM
**Message:** "💡 Customer comparing options. Offer to create a side-by-side comparison or focus discussion on their top choice."
**Script:** "I see you're considering a few options! Would it help if I create a quick comparison of the top 2 projects based on your priorities? Or is there one that stands out to you?"

### 5. Discovery Phase Qualifier
**When:** Customer in discovery stage (first 3 messages)
**Priority:** LOW
**Message:** "💡 DISCOVERY PHASE: Ask qualifying questions to understand customer needs better."
**Script:** "To help you find the perfect home, may I ask - are you looking for immediate possession or under-construction? And do you prefer ready-to-move-in or pre-launch offers?"

### 6. Deep Query Engagement
**When:** Customer asking detailed questions (amenities, schools, distances)
**Priority:** MEDIUM
**Message:** "💡 HIGH ENGAGEMENT: Customer asking specific questions = strong interest. Time to personalize the pitch."
**Script:** "I can see you're doing thorough research! That's great. Based on what you've asked, it seems [feature] is important to you. Would you like me to find projects that excel in this area?"

### 7. Negotiation Stage Support
**When:** Customer in negotiation stage, objections raised
**Priority:** HIGH
**Message:** "💡 NEGOTIATION STAGE: Customer is negotiating = ready to buy. Address concerns, offer incentives, ask for commitment."
**Script:** "I understand your concerns about [objection]. Let me share some additional benefits that might help: [value proposition]. If we can address this, would you be ready to move forward with the booking?"

### 8. Silence Detection
**When:** No customer response for 120+ seconds
**Priority:** MEDIUM
**Message:** "💡 SILENCE DETECTED: Customer may be thinking or distracted. Re-engage with a question."
**Script:** "I hope I've answered your questions so far! Is there anything specific you'd like to know more about, or would you like to explore other options?"

## 🎨 Coaching Prompt UI Examples

### Critical Priority (Red)
```
┌─────────────────────────────────────────────────────┐
│ ⚡ 💡 Sales Coaching   [CRITICAL] [Conversion Trigger]│
│                                                     │
│ Customer ready to close! 3 projects viewed,        │
│ budget discussed, asking about possession dates.   │
│ ASK FOR SITE VISIT NOW.                            │
│                                                     │
│ 📝 SUGGESTED SCRIPT:                                │
│ "Would you like to schedule a site visit this      │
│  weekend? I can arrange visits to all 3 projects." │
└─────────────────────────────────────────────────────┘
```

### High Priority (Orange)
```
┌─────────────────────────────────────────────────────┐
│ ⚠️ 💡 Sales Coaching   [HIGH] [Objection Handling]   │
│                                                     │
│ Budget objection detected. Highlight market value, │
│ flexible EMI plans, and ROI potential.             │
│                                                     │
│ 📝 SUGGESTED SCRIPT:                                │
│ "This is 12% below market average! Plus, EMI is    │
│  just ₹45K/month. Great investment value."         │
└─────────────────────────────────────────────────────┘
```

### Medium Priority (Blue)
```
┌─────────────────────────────────────────────────────┐
│ ✨ 💡 Sales Coaching   [MEDIUM] [Action Suggestion]  │
│                                                     │
│ Customer viewed 2 projects. Offer comparison or    │
│ narrow down to their top choice.                   │
└─────────────────────────────────────────────────────┘
```

## 🧪 Testing Scenarios

### Test 1: Site Visit Trigger
**User Messages:**
1. "Show me 2BHK in Whitefield under 2 Cr"
2. "Tell me about Brigade Citrine"
3. "What amenities does it have?"
4. "Tell me more about Prestige Lakeside Habitat"
5. "What about the possession date?"

**Expected Coaching Prompt (after message 5):**
- Type: action_suggestion
- Priority: high
- Message: "Customer viewed 3 projects + asking detailed questions. TIME TO CLOSE - Suggest site visit NOW."

### Test 2: Budget Objection
**User Messages:**
1. "Show me 3BHK in Sarjapur"
2. "This seems too expensive"

**Expected Coaching Prompt (after message 2):**
- Type: objection_handling
- Priority: high
- Message: "BUDGET OBJECTION: Emphasize value, market comparison, and flexible payment plans."

### Test 3: Market Intelligence Integration
**Backend automatically includes:**
- Price comparison: "12% below Whitefield market average"
- ROI forecast: "Expected 15% appreciation in 3 years"
- Urgency signals: "Only 5 units left" or "Prices increasing 5% next month"

## 📊 Market Data Localities

The system includes real market data for these Bangalore localities:
1. Whitefield
2. Sarjapur
3. Electronic City
4. Hebbal
5. Marathahalli
6. Koramangala
7. HSR Layout
8. Yeshwanthpur
9. Kengeri
10. JP Nagar

**To add more localities:** Edit [backend/data/market_data.json](backend/data/market_data.json)

## 🔧 Customization

### Adding New Coaching Rules

Edit [backend/models/coaching_rules.py](backend/models/coaching_rules.py):

```python
COACHING_RULES["my_custom_rule"] = {
    "conditions": {
        "min_messages": 5,
        "conversation_stage": ["evaluation"],
        "query_contains": ["compare", "versus"]
    },
    "priority": CoachingPriority.HIGH,
    "type": CoachingType.ACTION_SUGGESTION,
    "message_template": "💡 Customer comparing projects. Suggest side-by-side comparison.",
    "suggested_script": "Would you like me to create a detailed comparison of these projects?"
}
```

### Adjusting Trigger Thresholds

In [backend/services/conversation_director.py](backend/services/conversation_director.py):

```python
# Change site visit trigger from 3 projects to 2 projects
def detect_conversation_stage(...):
    if projects_viewed >= 2:  # Was 3, now 2
        return "evaluation"
```

### Styling Coaching Prompts

Edit [frontend/src/components/CoachingPanel.tsx](frontend/src/components/CoachingPanel.tsx) to change colors, icons, or layout.

## 🎯 Best Practices

### For Salesmen
1. **Read coaching prompts before responding** - They provide context-aware suggestions
2. **Use suggested scripts as templates** - Personalize them to your style
3. **Pay attention to priority levels** - CRITICAL and HIGH need immediate action
4. **Track objections** - Coaching adapts based on customer concerns

### For Administrators
1. **Monitor coaching effectiveness** - Track conversion rates when coaching is shown
2. **Tune thresholds** - Adjust min_messages, min_projects_viewed based on your sales process
3. **Add custom rules** - Create coaching for your specific sales scenarios
4. **Update market data** - Keep [backend/data/market_data.json](backend/data/market_data.json) current

## 🐛 Troubleshooting

### Coaching prompts not appearing?
- Check backend logs for "💡 COACHING:" messages
- Verify session tracking is working (session_id present in requests)
- Test with scenarios that meet rule conditions (e.g., view 3+ projects)

### Frontend not displaying coaching panel?
- Check browser console for errors
- Verify CoachingPanel import in ChatInterface.tsx
- Check that message.coaching_prompt is populated

### Wrong coaching prompts triggering?
- Review rule conditions in [backend/models/coaching_rules.py](backend/models/coaching_rules.py)
- Check conversation stage detection logic
- Adjust thresholds (min_messages, min_projects_viewed)

## 📈 Next Steps

### Phase 2 Enhancements (Future)
1. **Google Maps Integration** - Real distance data for "How far is airport?" queries
2. **Proactive Budget Alternatives** - Automatically show ±15% budget options
3. **Cross-Sell Intelligence** - "Customers also viewed" recommendations
4. **CRM Integration** - Track coaching effectiveness and conversion rates

### Phase 3 Advanced Features
1. **ML-based Coaching** - Learn from successful conversations
2. **A/B Testing** - Test different coaching messages
3. **Voice Call Integration** - Real-time coaching during phone calls
4. **Team Analytics** - Compare salesman performance with/without AI coaching

## 📞 Support

For questions or issues:
1. Check this documentation
2. Review backend logs for debugging
3. Test with the provided scenarios
4. Check the plan document at [elegant-dazzling-avalanche.md](~/.claude/plans/elegant-dazzling-avalanche.md)

## 🎉 Success Metrics

Track these KPIs to measure coaching effectiveness:
- **Conversion Rate:** % of conversations that lead to site visits/bookings
- **Average Messages to Conversion:** How many messages before customer commits
- **Objection Resolution Rate:** % of objections successfully handled
- **Coaching Prompt Relevance:** Salesman feedback on coaching usefulness

---

**Built with:** Python FastAPI, Next.js, TypeScript, Pixeltable
**Version:** 1.0
**Last Updated:** January 18, 2026
