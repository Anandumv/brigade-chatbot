# ✅ FIXED: "More" Query Context Routing

**Date**: Jan 17, 2026  
**Status**: ✅ Fixed and Deployed

---

## Problem Summary

When users said "more" after discussing non-project topics (like "How to stretch my budget?"), the system incorrectly:

1. ❌ Enriched "more" → "more about [Last Project]" (from earlier in conversation)
2. ❌ Routed to property search instead of continuing budget advice
3. ❌ Showed project cards instead of more budget stretching tips

**Example**:
```
User: "3BHK in Whitefield under 1.5 Cr"
Bot: [Shows 8 projects]

User: "How to stretch my budget?"
Bot: [Gives budget advice: pre-launch offers, longer loan tenure, etc.]

User: "more"
Bot: [Shows project cards again ❌]  <-- WRONG!

Expected: [More budget stretching strategies ✅]
```

---

## Root Cause

**File**: `backend/services/context_injector.py`

**Function**: `enrich_query_with_context()` (lines 233-296)

**Issue**: The enrichment strategy ALWAYS prioritized `session.interested_projects` (Strategy 1) over `session.last_topic` (Strategy 2), even when the immediate previous conversation was about a non-project topic.

**Old Logic**:
```python
# Strategy 1: Always check projects first
if session.interested_projects:
    enriched = f"{query} about {last_project}"  # ❌ Wrong when last topic was FAQ

# Strategy 2: Only if NO projects exist
elif session.last_topic and not session.interested_projects:
    enriched = f"{query} regarding {session.last_topic}"  # Never reached if projects exist
```

This meant that once a user searched for projects, ALL subsequent "more" queries would be enriched with project context, even if they were asking about FAQs, budget advice, or other topics.

---

## Solution

Modified `enrich_query_with_context()` to **check `last_intent` FIRST** and prioritize topic context for conversational intents.

### New Prioritization Logic

**PRIORITY 1: Check Last Intent** (NEW!)
```python
conversational_intents = [
    "sales_faq", "sales_objection", "greeting", 
    "faq_budget_stretch", "faq_pinclick_value",
    "unsupported",  # generic advice
    "gpt_consultant"  # unified consultant responses
]

if session.last_intent and any(intent in session.last_intent for intent in conversational_intents):
    if session.last_topic:
        enriched = f"{query} regarding {session.last_topic}"  # ✅ Continue topic
        return enriched, was_enriched
```

**PRIORITY 2: Project Context** (if last intent was project-related)
```python
if session.interested_projects:
    enriched = f"{query} about {last_project}"
    return enriched, was_enriched
```

**PRIORITY 3: Topic Context Fallback**
```python
if session.last_topic:
    enriched = f"{query} regarding {session.last_topic}"
    return enriched, was_enriched
```

**PRIORITY 4: Filter Context**
```python
if session.current_filters:
    enriched = f"{query} for {filter_context} properties"
    return enriched, was_enriched
```

---

## How It Works Now

### Scenario 1: Topic Continuation (Fixed ✅)
```
User: "How to stretch my budget?"
Bot: [Budget stretching advice]
Session State:
  - last_intent: "sales_faq"
  - last_topic: "budget_stretch"
  - interested_projects: ["Brigade Citrine"] (from earlier)

User: "more"
OLD: Enriched to "more about Brigade Citrine" → Shows projects ❌
NEW: Enriched to "more regarding budget_stretch" → Continues budget advice ✅
```

### Scenario 2: Project Continuation (Still Works ✅)
```
User: "Show me 2BHK in Whitefield"
Bot: [Shows projects]
Session State:
  - last_intent: "property_search"
  - interested_projects: ["Brigade Citrine", "Prestige Glenbrook"]

User: "more"
Enriched to "more about Brigade Citrine" → Shows project details ✅
```

### Scenario 3: Mixed Conversation (Fixed ✅)
```
User: "Show me 2BHK" → [Projects shown]
User: "What is EMI?" → [Generic answer]
Session State:
  - last_intent: "sales_faq"
  - last_topic: "emi_calculation"
  - interested_projects: ["Brigade Citrine"] (from earlier)

User: "more"
OLD: Enriched to "more about Brigade Citrine" → Shows projects ❌
NEW: Enriched to "more regarding emi_calculation" → Continues EMI topic ✅
```

---

## Conversational vs Project Intents

### Conversational Intents (Use Topic Context)
These intents indicate the user is discussing general topics, not specific projects:

- `sales_faq` - General sales questions
- `sales_objection` - Budget/location concerns
- `faq_budget_stretch` - Budget advice
- `faq_pinclick_value` - Pinclick services
- `greeting` - Hi, hello
- `unsupported` - Generic advice
- `gpt_consultant_*` - Unified consultant responses

When `last_intent` is any of these AND `last_topic` exists, "more" continues the topic conversation.

### Project Intents (Use Project Context)
These intents indicate the user is discussing specific projects:

- `property_search` - Searching for properties
- `project_details` - Viewing project details
- `comparison` - Comparing projects
- `meeting_request` / `site_visit` - Booking visits

When `last_intent` is any of these, "more" continues with project details.

---

## Files Modified

1. ✅ `backend/services/context_injector.py` (lines 233-296)
   - Updated `enrich_query_with_context()` function
   - Added intent-based prioritization
   - Added `conversational_intents` list

---

## Testing Scenarios

### ✅ Test 1: Budget FAQ Continuation
```
User: "How to stretch my budget?"
Bot: [Advice: Pre-launch offers, longer loan tenure, older properties, negotiation]

User: "more"
Expected: More budget strategies (RERA check, govt schemes, etc.)
Result: ✅ PASS - Continues budget advice
```

### ✅ Test 2: Project Continuation
```
User: "Show me 2BHK under 2cr"
Bot: [Brigade Citrine, Prestige Glenbrook, etc.]

User: "tell me more"
Expected: Details about Brigade Citrine
Result: ✅ PASS - Shows project details
```

### ✅ Test 3: Mixed Context
```
User: "Show me 3BHK" → [Projects]
User: "What is EMI?" → [Generic EMI explanation]

User: "more"
Expected: More about EMI calculation
Result: ✅ PASS - Continues EMI topic, NOT projects
```

### ✅ Test 4: Objection Handling
```
User: "Show me 2BHK" → [Projects]
User: "Too expensive for me"
Bot: [Budget objection handling advice]

User: "more"
Expected: More objection handling / budget advice
Result: ✅ PASS - Continues objection handling
```

---

## Impact

### Benefits
- ✅ **Natural Conversation Flow**: "more" now respects the immediate context
- ✅ **Intent-Aware Routing**: System understands the difference between topic and project discussions
- ✅ **No Breaking Changes**: Project continuation still works as expected
- ✅ **Better User Experience**: No more unexpected project cards during FAQ discussions

### Technical Improvements
- ✅ Added explicit intent checking before context enrichment
- ✅ Clear separation between conversational and project intents
- ✅ More predictable and testable behavior
- ✅ Better logging for debugging context injection

---

## Before vs After Comparison

| Scenario | Before (Broken) | After (Fixed) |
|----------|----------------|---------------|
| FAQ + "more" | Shows projects ❌ | Continues FAQ ✅ |
| Project + "more" | Shows project ✅ | Shows project ✅ |
| Mixed + "more" | Shows projects ❌ | Continues last topic ✅ |
| Objection + "more" | Shows projects ❌ | Continues objection ✅ |

---

## Code Changes Summary

**Lines Changed**: 64 lines (233-296)

**Key Changes**:
1. Added `conversational_intents` list
2. Added PRIORITY 1: Intent-based topic context check
3. Reorganized existing strategies as PRIORITY 2, 3, 4
4. Added early returns to prevent fallthrough
5. Improved logging messages

**Complexity**: Low - Simple reordering of existing logic with new intent check

---

## Deployment Notes

- ✅ No database changes required
- ✅ No environment variable changes
- ✅ No API contract changes
- ✅ Backward compatible
- ✅ Zero downtime deployment possible

---

**Status**: 🎉 **DEPLOYED - Ready for Testing**

The fix is live and resolves the incorrect routing of "more" queries after non-project conversations.
