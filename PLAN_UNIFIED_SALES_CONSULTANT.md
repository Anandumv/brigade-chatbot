# Plan: Simplify to ChatGPT-Like Sales Consultant

## Goal
Transform the chatbot from a rigid multi-handler system into a ChatGPT-like unified sales consultant that maintains continuous conversation.

## Current vs Target

| Aspect | Current | Target |
|--------|---------|--------|
| **Intent Handlers** | 7+ separate handlers | 3 simple routes |
| **Conversation Flow** | Breaks between handlers | Continuous via unified GPT |
| **Objection Handling** | Scripted responses | Natural GPT responses |
| **FAQ Handling** | Scripted responses | Natural GPT responses |
| **Context Maintenance** | Lost between handlers | Always preserved in GPT |
| **User Experience** | Robotic/form-filling | Natural conversation |

## Implementation Plan

### Phase 1: Simplify Intent Routing (Main Change)

**File**: `backend/main.py`

**Current Flow** (7+ handlers):
```python
if intent == "greeting": → greeting_handler
elif intent == "sales_faq": → intelligent_sales_handler  
elif intent == "meeting_request": → gpt_meeting_handler
elif intent == "sales_objection": → intelligent_sales_handler
elif intent == "more_info_request": → gpt_content_generator
elif intent == "property_search": → database_search
elif intent == "comparison": → comparison_handler
elif intent == "unsupported": → contextual_fallback
```

**New Flow** (3 routes):
```python
# Route 1: Explicit property search
if intent == "property_search" and explicit_search_keywords_present:
    → database_search (Keep as-is)

# Route 2: Explicit project details
elif intent == "project_details" and project_name_extracted:
    → project_details_handler (Keep as-is)

# Route 3: EVERYTHING ELSE → Unified GPT Sales Consultant
else:
    → unified_sales_consultant_gpt(
        query=query,
        conversation_history=full_history,
        session_context=context,
        goal="Act as senior sales consultant maintaining continuous conversation"
    )
```

### Phase 2: Create Unified Sales Consultant Handler

**New File**: `backend/services/unified_sales_consultant.py`

```python
class UnifiedSalesConsultant:
    """
    Single GPT-4 powered sales consultant that handles ALL non-search queries.
    
    Capabilities:
    - Handles objections naturally
    - Answers FAQs conversationally
    - Provides investment advice
    - Discusses locations, appreciation, EMI
    - Maintains continuous conversation
    - Guides toward site visit
    - Never asks unnecessary clarifying questions
    - Uses context from previous messages
    """
    
    def handle_conversation(
        self,
        query: str,
        conversation_history: List[Dict],
        session_context: Dict,
        last_shown_projects: List[Dict] = None
    ) -> str:
        """
        Main handler for all conversational queries.
        
        Args:
            query: Current user query
            conversation_history: Last N messages
            session_context: Current session state
            last_shown_projects: Recently shown projects for reference
        
        Returns:
            Natural conversational response from sales consultant
        """
        
        system_prompt = """You are a senior sales consultant for Pinclick Real Estate in Bangalore.
        
        **YOUR ROLE:**
        - Act like a trusted advisor, not a form-filling bot
        - Maintain natural, continuous conversation
        - Use context from previous messages
        - Handle objections empathetically
        - Answer questions conversationally
        - Guide toward site visits naturally
        
        **CRITICAL RULES:**
        - NEVER ask "What are you looking for?" if context exists
        - NEVER give scripted/robotic responses
        - ALWAYS use conversation history to understand intent
        - ALWAYS reference previously discussed projects/topics
        - Continue conversations naturally like ChatGPT would
        
        **WHEN USER ASKS ABOUT:**
        - Objections (too expensive, far, etc.) → Handle empathetically, suggest alternatives
        - FAQs (EMI, appreciation, location) → Answer naturally with insights
        - Follow-ups ("give more points") → Continue previous topic seamlessly
        - Investment advice → Provide thoughtful analysis
        - General questions → Engage conversationally
        
        **YOUR GOAL:**
        Build trust → Provide value → Guide to site visit
        
        **CONTEXT:**
        - Last shown projects: {last_shown_projects}
        - User's filters: {current_filters}
        - Interested projects: {interested_projects}
        - Previous objections: {objections}
        - Conversation history: {conversation_history}
        """
        
        # Build full context message
        messages = [
            {"role": "system", "content": system_prompt.format(
                last_shown_projects=last_shown_projects,
                current_filters=session_context.get("current_filters"),
                interested_projects=session_context.get("interested_projects"),
                objections=session_context.get("objections"),
                conversation_history=conversation_history
            )}
        ]
        
        # Add conversation history
        messages.extend(conversation_history[-10:])
        
        # Add current query
        messages.append({"role": "user", "content": query})
        
        # Call GPT-4
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=800
        )
        
        return response.choices[0].message.content
```

### Phase 3: Simplify Intent Classifier

**File**: `backend/services/gpt_intent_classifier.py`

**Current**: 9+ intent types
**New**: 3 intent types only

```python
**Classify the intent into ONLY ONE of:**
- property_search: User explicitly asks to "show", "find", "list", "search" properties with requirements
- project_details: User asks to "show details of", "tell me about [Project]", "info about [Project]"
- sales_conversation: EVERYTHING ELSE (objections, FAQs, general questions, follow-ups, investment advice, location discussions, etc.)

**CRITICAL:**
- "it's too expensive" → sales_conversation (NOT sales_objection)
- "what is EMI" → sales_conversation (NOT sales_faq)
- "give more points" → sales_conversation (NOT more_info_request)
- "show me 2bhk" → property_search
- "details about Avalon" → project_details
```

### Phase 4: Update Main Endpoint

**File**: `backend/main.py`

**Changes**:

1. **Remove these handlers**:
   - `greeting` handler → Route to sales_conversation
   - `sales_faq` handler → Route to sales_conversation
   - `meeting_request` handler → Route to sales_conversation
   - `sales_objection` handler → Route to sales_conversation
   - `more_info_request` handler → Route to sales_conversation
   - `comparison` handler → Route to sales_conversation
   - `unsupported` handler → Route to sales_conversation

2. **Keep only 3 handlers**:
   - `property_search` → Database search (existing)
   - `project_details` → Project info (existing)
   - `sales_conversation` → Unified GPT consultant (NEW)

3. **New routing logic**:

```python
# After intent classification
if intent == "property_search":
    # Existing property search logic
    # ...

elif intent == "project_details":
    # Existing project details logic
    # ...

else:  # intent == "sales_conversation" (catch-all)
    # NEW: Unified sales consultant
    from services.unified_sales_consultant import UnifiedSalesConsultant
    
    consultant = UnifiedSalesConsultant()
    
    response_text = consultant.handle_conversation(
        query=original_query,
        conversation_history=conversation_history,
        session_context={
            "current_filters": session.current_filters,
            "interested_projects": session.interested_projects,
            "objections": session.objections_raised,
            "last_shown_projects": session.last_shown_projects,
            "conversation_phase": session.conversation_phase
        }
    )
    
    # Update session
    session_manager.add_message(request.session_id, "user", original_query)
    session_manager.add_message(request.session_id, "assistant", response_text[:500])
    session_manager.save_session(session)
    
    return ChatQueryResponse(
        answer=response_text,
        sources=[],
        confidence="High",
        intent="sales_conversation",
        response_time_ms=response_time_ms,
        suggested_actions=["Schedule site visit", "View properties", "Get more details"]
    )
```

## Migration Path

### Step 1: Create unified_sales_consultant.py ✅
- Implement UnifiedSalesConsultant class
- Test with sample conversations

### Step 2: Simplify intent classifier ✅
- Reduce to 3 intents only
- Update system prompt
- Update examples

### Step 3: Update main.py routing ✅
- Add sales_conversation route
- Remove old handlers (comment out first for safety)
- Test end-to-end

### Step 4: Clean up ✅
- Remove deprecated services
- Update documentation

## Expected Behavior After Changes

### Test Case 1: Objection Handling

**Query**: "It's too expensive for me"

**Before**: Routes to `sales_objection` → Scripted response
**After**: Routes to `sales_conversation` → Natural GPT response:

```
"I completely understand - budget is the most important factor. Let me help you with that. 

We have a few options:
1. I can show you similar properties in emerging areas like Sarjapur that offer 20-30% better value
2. We can explore extended payment plans or builder schemes that reduce upfront burden
3. Some projects offer early bird discounts if you book now

What would work best for your situation? Or would you like to see what's available in your current budget range?"
```

### Test Case 2: FAQ

**Query**: "What's the expected appreciation?"

**Before**: Routes to `sales_faq` → Scripted appreciation response
**After**: Routes to `sales_conversation` → Contextual response:

```
"Great question! For the Whitefield projects I showed you earlier, you're looking at:

- **Short-term (1-2 years)**: 8-10% appreciation
- **Medium-term (3-5 years)**: 15-20% appreciation  
- **Drivers**: Metro Phase 2, new tech parks, infrastructure upgrades

Brigade Citrine specifically is well-positioned because it's walkable to ITPL. Properties near major IT hubs historically appreciate faster.

The key is buying now before metro operational in 2026. Prices typically jump 15-20% post-metro.

Would you like to lock in one of these before prices rise?"
```

### Test Case 3: Follow-up

**Query**: [After showing projects] "give more points"

**Before**: May route to `more_info_request` → Disconnected response
**After**: Routes to `sales_conversation` → Seamless continuation:

```
"Absolutely! Beyond what I mentioned, here's why Brigade Citrine stands out:

**Financial Benefits:**
- 10% early bird discount if you book this month
- Flexible payment plan (20:80)
- Expected rental yield: 3-4% annually

**Lifestyle:**
- Walking distance to Phoenix Mall
- International schools within 2km
- Metro station 800m away

**Developer Track Record:**
- Brigade delivered 290+ projects
- 99% on-time possession record
- IGBC Gold certified

The combination of location + developer reliability + payment flexibility makes this a solid choice.

Want to see the actual unit layouts? Or should we schedule a site visit to experience the location firsthand?"
```

## Success Metrics

- ✅ Continuous conversation maintained across all query types
- ✅ No more "What are you looking for?" when context exists
- ✅ Natural objection handling (not scripted)
- ✅ Context-aware follow-ups
- ✅ Feels like talking to a real sales consultant
- ✅ Guides naturally toward site visit

## Files to Modify

1. **NEW**: `backend/services/unified_sales_consultant.py` - Main handler
2. `backend/services/gpt_intent_classifier.py` - Simplify to 3 intents
3. `backend/main.py` - Update routing logic
4. `backend/services/session_manager.py` - Ensure last_shown_projects tracked

## Rollback Plan

If issues arise, we can:
1. Keep the new file but disable the route
2. Revert main.py routing to use old handlers
3. Gradually migrate one intent type at a time

---

**Ready to implement?** This will transform the chatbot from a rigid multi-handler system to a ChatGPT-like unified sales consultant that maintains natural, continuous conversation.
