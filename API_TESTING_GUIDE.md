# API Testing Guide - Real Estate Sales Chatbot

Complete guide for testing all chatbot endpoints using curl or Postman.

## Prerequisites

1. **Start the backend server:**
```bash
cd /Users/anandumv/Downloads/chatbot/backend
source venv/bin/activate  # or: venv\Scripts\activate on Windows
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

2. **Verify server is running:**
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "environment": "development",
  "timestamp": "2026-01-11T..."
}
```

3. **View API documentation:**
Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser for interactive Swagger UI.

---

## Core Chat Endpoint Tests

### Test 1: Vector Search (Data in DB)

**Purpose:** Test retrieval from internal vectorized documents

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the RERA number for Brigade Citrine?",
    "user_id": "test-sales-exec"
  }'
```

**Expected Response:**
```json
{
  "answer": "Brigade Citrine RERA number is PRM/KA/RERA/1250/304/PR/131224/007287...",
  "sources": [
    {
      "document": "Brigade Citrine E-Brochure 01-1",
      "section": "Page 2: Project Overview",
      "page": 2,
      "excerpt": "...",
      "similarity": 0.92
    }
  ],
  "confidence": "High",
  "intent": "project_fact",
  "refusal_reason": null,
  "response_time_ms": 1250
}
```

**Success Criteria:**
- ✅ Response time < 3 seconds
- ✅ Confidence = "High" or "Medium"
- ✅ Sources array has at least 1 item
- ✅ Source includes document name, section, page
- ✅ Similarity >= 0.75

---

### Test 2: Web Search Fallback (Data NOT in DB)

**Purpose:** Test Tavily web search when data not in vector DB

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are current property prices in Whitefield Bangalore?",
    "user_id": "test-sales-exec"
  }'
```

**Expected Response:**
```json
{
  "answer": "ℹ️ **External Source (Web Search):**\n\nWhitefield Bangalore property prices range from...\n\n*This information is from web search results...*",
  "sources": [
    {
      "document": "Web Source 1",
      "section": "Whitefield Property Prices...",
      "page": null,
      "excerpt": "...",
      "similarity": 0.7,
      "url": "https://..."
    }
  ],
  "confidence": "Low (External)",
  "intent": "unsupported",
  "refusal_reason": null,
  "response_time_ms": 2100
}
```

**Success Criteria:**
- ✅ Answer includes "External Source" indicator
- ✅ Confidence = "Low (External)"
- ✅ Sources include URL field
- ✅ Warning about verifying information

**Note:** If TAVILY_API_KEY not set, will fall back to LLM general knowledge with confidence "Low"

---

### Test 3: Sales Query Expansion (2BHK/3BHK)

**Purpose:** Test query expansion for common sales terms

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me 2bhk flats in Brigade Citrine",
    "user_id": "test-sales-exec"
  }'
```

**Expected Response:**
- Answer includes unit types (2BED + 2TOILET - TYPE 3, etc.)
- Carpet area, super built-up area in sqm/sqft
- Sources from brochure specification pages

**Backend Log (check terminal):**
```
INFO: Original query: Show me 2bhk flats in Brigade Citrine
INFO: Expanded query: Show me 2bhk flats in Brigade Citrine 2 bedroom 2bhk apartment flat
```

**Success Criteria:**
- ✅ Query expansion logged (visible in terminal)
- ✅ Answer includes specific unit configurations
- ✅ High/Medium confidence

---

### Test 4: Location & Amenities Query

**Purpose:** Test retrieval of project amenities

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What amenities are available in Brigade Citrine?",
    "user_id": "test-sales-exec"
  }'
```

**Expected Response:**
- Lists amenities (clubhouse, gym, pool, etc.)
- High confidence if in documents
- Formatted as bullet points or list

---

### Test 5: Unsupported Query (Refusal)

**Purpose:** Test refusal logic for future predictions

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What will be the property value in 5 years?",
    "user_id": "test-sales-exec"
  }'
```

**Expected Response:**
```json
{
  "answer": "I cannot provide predictions about future property values, ROI, or market trends.",
  "sources": [],
  "confidence": "Not Available",
  "intent": "unsupported",
  "refusal_reason": "future_prediction",
  "response_time_ms": 800
}
```

**Success Criteria:**
- ✅ Clear refusal message
- ✅ refusal_reason field populated
- ✅ Empty sources array
- ✅ Confidence = "Not Available"

---

## Phase 2 Feature Tests

### Test 6: Persona-Based Pitch (Investor)

**Purpose:** Test investor-focused sales pitch

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Why should I invest in Brigade Citrine?",
    "persona": "investor",
    "user_id": "test-sales-exec"
  }'
```

**Expected Response:**
- Emphasizes ROI, capital appreciation, location advantages
- Mentions brand value, infrastructure development
- Sources from project documents
- Confidence: Medium

**Personas Available:**
- `investor`
- `first_time_buyer`
- `senior_citizen`
- `family`

---

### Test 7: Get Available Personas

**Purpose:** Retrieve list of all buyer personas

```bash
curl "http://localhost:8000/api/personas"
```

**Expected Response:**
```json
[
  {
    "id": "first_time_buyer",
    "name": "First-Time Homebuyer",
    "description": "Focuses on: Affordability and payment plans, Ready-to-move-in condition, Loan assistance"
  },
  {
    "id": "investor",
    "name": "Property Investor",
    "description": "Focuses on: Capital appreciation potential, Rental yield, Location advantages"
  },
  {
    "id": "senior_citizen",
    "name": "Senior Citizen",
    "description": "Focuses on: Accessibility (elevators, ramps), Healthcare facilities nearby, Peaceful environment"
  },
  {
    "id": "family",
    "name": "Family with Children",
    "description": "Focuses on: Schools and educational institutions nearby, Children's play areas, Safe environment"
  }
]
```

---

### Test 8: Multi-Project Comparison

**Purpose:** Compare features across projects

```bash
curl -X POST "http://localhost:8000/api/chat/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare amenities in Brigade Citrine and Avalon",
    "user_id": "test-sales-exec"
  }'
```

**Expected Response:**
- Side-by-side comparison
- Sources from both projects
- Clear labeling of which features belong to which project

**Note:** Requires both projects to be in database with embeddings

---

### Test 9: Get Projects List

**Purpose:** Retrieve all available projects

```bash
curl "http://localhost:8000/api/projects"
```

**Expected Response:**
```json
[
  {
    "id": "uuid-xxx",
    "name": "Brigade Citrine",
    "location": "Old Madras Road, Bengaluru",
    "status": "ongoing",
    "rera_number": "PRM/KA/RERA/1250/304/PR/131224/007287",
    "description": "India's First Net Zero Community"
  },
  {
    "id": "uuid-yyy",
    "name": "Brigade Avalon",
    "location": "...",
    "status": "ongoing",
    ...
  }
]
```

---

### Test 10: Analytics Dashboard

**Purpose:** Get query analytics (admin endpoint)

```bash
curl "http://localhost:8000/api/admin/analytics?user_id=admin&days=7"
```

**Expected Response:**
```json
{
  "total_queries": 45,
  "answered_queries": 38,
  "refused_queries": 7,
  "refusal_rate": 15.56,
  "avg_response_time_ms": 1847.2,
  "top_intents": [
    {"intent": "project_fact", "count": 22},
    {"intent": "sales_pitch", "count": 12},
    {"intent": "unsupported", "count": 7}
  ],
  "recent_refusals": [
    {
      "query": "What will property value be in 5 years?",
      "refusal_reason": "future_prediction",
      "created_at": "2026-01-11T..."
    }
  ]
}
```

**Use Case:** Identify knowledge gaps, common refusal reasons

---

## Performance Testing

### Test 11: Response Time Benchmark

Run multiple queries and measure response times:

```bash
#!/bin/bash
echo "Testing response times..."

for i in {1..10}; do
  start=$(date +%s%3N)
  curl -s -X POST "http://localhost:8000/api/chat/query" \
    -H "Content-Type: application/json" \
    -d '{"query": "What is Brigade Citrine?", "user_id": "perf-test"}' \
    > /dev/null
  end=$(date +%s%3N)
  elapsed=$((end - start))
  echo "Request $i: ${elapsed}ms"
done
```

**Success Criteria:**
- ✅ Average < 3000ms
- ✅ P95 < 4000ms
- ✅ No timeouts

---

## Error Handling Tests

### Test 12: Missing Required Fields

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test"
  }'
```

**Expected:** 422 Validation Error

---

### Test 13: Invalid Persona

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Test query",
    "persona": "invalid_persona",
    "user_id": "test"
  }'
```

**Expected:** Falls back to "first_time_buyer" persona (logged as warning)

---

## Postman Collection

### Import into Postman:

1. Create new collection: "Real Estate Chatbot API"
2. Add environment variables:
   - `base_url`: `http://localhost:8000`
   - `user_id`: `test-sales-exec`

3. Add requests from tests above
4. Set up Tests tab with assertions:

```javascript
// Example test script for query endpoint
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response time < 3000ms", function () {
    pm.expect(pm.response.responseTime).to.be.below(3000);
});

pm.test("Has answer field", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('answer');
});

pm.test("Has sources", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.sources).to.be.an('array');
});
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'tavily'"

**Solution:**
```bash
cd backend
pip install tavily-python
```

---

### Issue: "Tavily API key not found"

**Solution:**
1. Get API key from [https://tavily.com](https://tavily.com)
2. Add to `/Users/anandumv/Downloads/chatbot/backend/.env`:
```
TAVILY_API_KEY=tvly-xxx
```
3. Restart server

---

### Issue: "No chunks retrieved"

**Possible Causes:**
1. Embeddings not generated yet
2. Similarity threshold too high
3. Query too specific

**Solution:**
```bash
# Check if embeddings exist in Supabase
# Run embedding generation if needed:
cd /Users/anandumv/Downloads/chatbot/backend
python scripts/create_embeddings.py --pdf "../Brigade Citrine E_Brochure 01-1.pdf" --project-id "YOUR_UUID" --project-name citrine
```

---

### Issue: Web search not working

**Check logs for:**
```
WARNING: Tavily not installed. Web search will use LLM knowledge only.
```

**If Tavily installed but not working:**
1. Verify `TAVILY_API_KEY` in `.env`
2. Check API quota at tavily.com
3. Review error logs in terminal

---

## Success Checklist

After running all tests, verify:

- ✅ Health endpoint returns "healthy"
- ✅ Vector search returns answers from documents
- ✅ Web fallback provides external information
- ✅ Query expansion works for "2bhk", "3bhk" terms
- ✅ Persona pitches work for all 4 personas
- ✅ Multi-project comparison returns results
- ✅ Analytics endpoint provides metrics
- ✅ Unsupported queries are refused appropriately
- ✅ All response times < 3 seconds
- ✅ Source attribution in 100% of answers

---

## Next Steps

1. **Production Deployment:**
   - Set up environment variables in production
   - Configure CORS for frontend
   - Set up monitoring (response times, error rates)

2. **Frontend Integration:**
   - Use these endpoints in React/Next.js app
   - Display sources as clickable citations
   - Add persona selector UI
   - Show confidence badges

3. **Monitoring:**
   - Track query logs in Supabase
   - Monitor refusal rates
   - Identify knowledge gaps from analytics

---

**Questions?** Check the main README or API documentation at http://localhost:8000/docs
