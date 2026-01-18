# How "distance of airport from brigade avalon" is Handled

## Query Flow

### 1. **Intent Classification** (`gpt_intent_classifier.py`)
- **Query**: "distance of airport form brigade avalon" (with typo "form" instead of "from")
- **GPT Understanding**: 
  - Recognizes "distance" + "airport" keywords → **Distance/Connectivity Question**
  - Matches "brigade avalon" → **Project Name: "Brigade Avalon"**
  - Handles typo "form" → understands as "from"
  
- **Classification Result**:
```json
{
  "intent": "sales_conversation",
  "data_source": "gpt_generation",
  "confidence": 0.95,
  "reasoning": "Distance question - not in database, route to GPT. Project name extracted for context.",
  "extraction": {
    "project_name": "Brigade Avalon",
    "topic": "connectivity",
    "fact_type": "distance"
  }
}
```

**Key Decision**: Even though a project is mentioned, distance questions are **ALWAYS routed to GPT** because:
- Distance calculations are not stored in the database
- GPT can provide accurate distance information based on project location
- The system extracts `project_name` for context but uses GPT for the answer

### 2. **Routing** (`main.py`)
- Intent = `"sales_conversation"` → Routes to **PATH 2: GPT Sales Consultant**
- Extracts `project_name: "Brigade Avalon"` from classification
- Passes `extraction` data to GPT consultant

### 3. **GPT Consultant** (`gpt_sales_consultant.py`)
- Receives:
  - Query: "distance of airport from brigade avalon"
  - Project context: `project_name: "Brigade Avalon"`
  - Session context (if available): last shown projects, conversation history
  
- **Goal Determination**:
  - Detects distance query keywords
  - Sees `project_name` in extraction
  - Sets goal: *"Answer the distance/connectivity question about Brigade Avalon. Provide specific distance information (in km or minutes) from the mentioned location (airport) to Brigade Avalon. Use bullet points, be concise, and include actionable information."*

- **System Prompt** (from `sales_agent_prompt.py`):
  - Uses production Sales Agent GPT prompt
  - Enforces: bullet points, ≤ 1 line each, speakable in call
  - No marketing fluff, no long explanations

### 4. **GPT Response Generation**
- GPT understands:
  - Project: Brigade Avalon
  - Location: Whitefield, Bangalore (from context or database knowledge)
  - Question: Distance to Kempegowda International Airport (BIAL)
  
- **Expected Response Format**:
```
• Brigade Avalon is approximately 35-40 km from Kempegowda International Airport
• Travel time: 45-60 mins via ORR (depending on traffic)
• Nearest airport access: Via Varthur Road → ORR → Airport Road
• Alternative route: Via Whitefield Main Road → NH44 (slightly longer)
```

### 5. **Context Preservation**
- Project "Brigade Avalon" is added to `session.last_shown_projects` (if not already present)
- Query and response are saved to conversation history
- `session.last_intent = "sales_conversation"`
- `session.last_topic = "connectivity"`

## Key Improvements Made

### ✅ **Enhanced Intent Classifier**
- Added explicit rule: Distance/connectivity questions → **ALWAYS route to GPT**, even if project mentioned
- Extracts `project_name` for context but classifies as `sales_conversation` with `data_source: "gpt_generation"`

### ✅ **Project Context Injection**
- `generate_consultant_response()` now accepts `extraction` parameter
- If `project_name` is in extraction, it's added to context for GPT
- GPT knows which project to answer about

### ✅ **Distance Query Goal**
- `determine_conversation_goal()` detects distance queries
- Sets specific goal for GPT: "Answer distance question about [project] with specific km/minutes"
- Ensures GPT provides actionable, concise distance information

### ✅ **Typo Handling**
- GPT's natural language understanding handles typos ("form" → "from")
- No keyword matching required - GPT infers intent

## Why This Works Better Than Before

**Before**: 
- Query might be classified as `project_facts` → Shows project details card
- Distance question not answered
- Context lost

**Now**:
- Query correctly classified as `sales_conversation` → Routes to GPT
- Project name extracted for context
- GPT answers distance question directly
- Context preserved for follow-ups

## Example Follow-up Queries

After "distance of airport from brigade avalon", these queries will work:

1. **"what about metro?"** → GPT understands: "metro distance from Brigade Avalon"
2. **"nearby schools?"** → GPT understands: "schools near Brigade Avalon"
3. **"more details"** → GPT provides more connectivity info about Brigade Avalon
4. **"price?"** → Routes to database (project_facts) for Brigade Avalon price

All queries maintain context because:
- Project is in `session.last_shown_projects`
- Conversation history is preserved
- GPT uses session context to infer intent
