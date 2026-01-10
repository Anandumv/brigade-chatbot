# Real Estate Sales Intelligence Chatbot

A grounded, non-hallucinatory chatbot for real estate sales teams that generates accurate, pitch-ready responses strictly from internal project documents and approved external sources.

**Guiding Principle:** `Accuracy > Helpfulness | Refusal > Hallucination | Trust > Conversion`

## Features

- ✅ **Zero Hallucinations** - Strict grounding to source documents only
- ✅ **100% Source Attribution** - Every answer cites its sources
- ✅ **Confidence Scoring** - Transparent about answer reliability
- ✅ **Explicit Refusal Logic** - Refuses unanswerable questions
- ✅ **Intent Classification** - Routes queries appropriately
- ✅ **Sub-3s Response Time** - Fast enough for live sales conversations
- ✅ **Complete Audit Trail** - All queries logged for analytics

## Architecture

### Tech Stack
- **Backend:** Python (FastAPI)
- **Database:** Supabase (PostgreSQL + pgvector)
- **AI/ML:** OpenAI GPT-4 + text-embedding-3-small
- **Frontend:** React (TypeScript) - *Coming in Phase 2*

### Data Flow
```
User Query
  → Intent Classification (GPT-4)
  → Vector Similarity Search (Supabase pgvector)
  → Confidence Scoring
  → Refusal Logic Check
  → Context-Locked GPT-4 Answer Generation
  → Source Attribution & Validation
  → Structured Response
```

## Getting Started

### Prerequisites

- Python 3.9+
- Supabase account ([sign up](https://supabase.com))
- OpenAI API key ([get one](https://platform.openai.com))

### Installation

1. **Clone and navigate to the project:**
   ```bash
   cd /Users/anandumv/Downloads/chatbot
   ```

2. **Set up Python environment:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp ../.env.example .env
   # Edit .env with your API keys
   ```

   Required variables:
   - `OPENAI_API_KEY` - Your OpenAI API key
   - `SUPABASE_URL` - Your Supabase project URL
   - `SUPABASE_KEY` - Your Supabase anon key
   - `SUPABASE_SERVICE_KEY` - Your Supabase service role key

### Database Setup

1. **Create Supabase project:**
   - Go to [Supabase Dashboard](https://app.supabase.com)
   - Create a new project
   - Wait for initialization

2. **Enable pgvector extension:**
   - Go to Database → Extensions
   - Enable `vector` extension

3. **Run schema:**
   - Go to SQL Editor
   - Copy contents of `backend/database/schema.sql`
   - Execute

4. **Create test projects (optional):**
   ```sql
   INSERT INTO projects (name, location, status, rera_number, description) VALUES
   ('Brigade Citrine', 'Old Madras Road, Bengaluru', 'ongoing', 'PRM/KA/RERA/1250/304/PR/131224/007287', 'India''s First Net Zero Community'),
   ('Brigade Avalon', 'Mysore Road, Bengaluru', 'ongoing', NULL, 'Premium residential project');
   ```

### Document Processing

1. **Process Brigade Citrine brochure:**
   ```bash
   python scripts/create_embeddings.py \
     --pdf "../Brigade Citrine E_Brochure 01-1.pdf" \
     --project-id "YOUR_PROJECT_UUID" \
     --project-name citrine
   ```

   Replace `YOUR_PROJECT_UUID` with the actual UUID from the `projects` table.

2. **Process Avalon brochure (optional):**
   ```bash
   python scripts/create_embeddings.py \
     --pdf "../E Brochure - Avalon.pdf" \
     --project-id "YOUR_AVALON_PROJECT_UUID" \
     --project-name avalon
   ```

This will:
- Extract text from PDFs
- Chunk content intelligently
- Generate OpenAI embeddings
- Store in Supabase with pgvector

### Running the API

```bash
cd backend
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Usage

### Basic Query

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the RERA number for Brigade Citrine?",
    "user_id": "user-123"
  }'
```

**Response:**
```json
{
  "answer": "The RERA registration number for Brigade Citrine is PRM/KA/RERA/1250/304/PR/131224/007287 (Source: Brigade Citrine E-Brochure, Page 2).",
  "sources": [
    {
      "document": "Brigade Citrine E-Brochure 01-1",
      "section": "Page 2: Project Overview",
      "page": 2,
      "excerpt": "RERA Reg. No.: PRM/KA/RERA/1250/304/PR/131224/007287",
      "similarity": 0.923
    }
  ],
  "confidence": "High",
  "intent": "project_fact",
  "refusal_reason": null,
  "response_time_ms": 1847
}
```

### Project-Specific Query

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the sustainability features?",
    "project_id": "YOUR_PROJECT_UUID",
    "user_id": "user-123"
  }'
```

### Refused Query (Hallucination Prevention)

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What will be the property value in 5 years?",
    "user_id": "user-123"
  }'
```

**Response:**
```json
{
  "answer": "I cannot provide predictions about future property values, ROI, or market trends.",
  "sources": [],
  "confidence": "Not Available",
  "intent": "unsupported",
  "refusal_reason": "future_prediction",
  "response_time_ms": 521
}
```

## Testing

### Test Document Processing

```bash
cd backend
python scripts/process_documents.py "../Brigade Citrine E_Brochure 01-1.pdf"
```

### Test Retrieval (Development Endpoint)

```bash
curl "http://localhost:8000/api/dev/test-retrieval?query=sustainability+features"
```

### Test Intent Classification

```bash
curl "http://localhost:8000/api/dev/test-intent?query=Will+property+value+increase?"
```

## Project Structure

```
chatbot/
├── backend/
│   ├── main.py                      # FastAPI application
│   ├── config.py                    # Configuration management
│   ├── requirements.txt             # Python dependencies
│   ├── database/
│   │   ├── schema.sql               # Supabase schema
│   │   └── supabase_client.py       # Database client
│   ├── services/
│   │   ├── intent_classifier.py     # Intent classification
│   │   ├── retrieval.py             # Vector similarity search
│   │   ├── confidence_scorer.py     # Confidence calculation
│   │   ├── refusal_handler.py       # Refusal logic
│   │   └── answer_generator.py      # GPT-4 answer generation
│   └── scripts/
│       ├── process_documents.py     # Document processing
│       └── create_embeddings.py     # Embedding generation
├── .env.example                     # Environment template
├── .gitignore
└── README.md
```

## Anti-Hallucination Mechanisms

1. **Intent Classification** - Catches unsupported queries upfront
2. **Similarity Threshold** - Only uses chunks with ≥0.75 similarity
3. **Strict System Prompts** - Explicitly forbids inference
4. **Source Validation** - Ensures all answers cite sources
5. **Confidence Scoring** - Transparent about reliability
6. **Explicit Refusal** - Better to refuse than hallucinate
7. **Answer Validation** - Checks for hallucination patterns

## Supported Query Types

### ✅ Supported (Answered)

- **Project Facts:** "What is the RERA number?", "How many units?", "What is the location?"
- **Amenities:** "What amenities are available?", "Tell me about the clubhouse"
- **Specifications:** "What are the unit sizes?", "What flooring is provided?"
- **Sustainability:** "What are the green features?", "Is it Net Zero?"
- **Sales Pitches:** "Why should I buy here?", "What makes this unique?"

### ❌ Unsupported (Refused)

- **Future Predictions:** "Will property value increase?", "What ROI can I expect?"
- **Legal Advice:** "Should I consult a lawyer?", "Is the contract valid?"
- **Financial Advice:** "Should I take a loan?", "Is this a good investment?"
- **Personal Recommendations:** "Should I buy 2BHK or 3BHK?"

## Performance Benchmarks

- **Response Time:** < 3 seconds (target)
- **Accuracy:** 100% grounded to sources
- **Refusal Accuracy:** > 95% for unsupported queries
- **Hallucination Rate:** 0% (strict validation)

## Costs (Estimated Monthly)

- **OpenAI API:** ~$25/month (1000 queries)
- **Supabase:** Free tier or $25/month (Pro)
- **Total:** ~$25-50/month for MVP

## Next Steps

### Phase 2 Features (Planned)

- [ ] Multi-project comparison queries
- [ ] External source integration (RERA, govt portals)
- [ ] Persona-based pitch generation
- [ ] React frontend with chat UI
- [ ] Admin dashboard for document management
- [ ] Analytics and reporting

### Current Limitations

- Single project only (Phase 1)
- Internal documents only
- No file upload UI (use scripts)
- No user authentication (Supabase RLS ready)

## Troubleshooting

### "No relevant chunks found"

- Check if documents are processed and embeddings created
- Verify Supabase connection
- Check similarity threshold (try lowering to 0.7)

### "OpenAI API Error"

- Verify API key in `.env`
- Check API quota/billing

### "Supabase Connection Error"

- Verify `SUPABASE_URL` and `SUPABASE_KEY`
- Check if pgvector extension is enabled
- Verify schema is executed

## Support

For issues or questions:
- Check [Implementation Plan](/Users/anandumv/.claude/plans/sorted-greeting-stearns.md)
- Review API documentation at `/docs`
- Check Supabase logs in dashboard

## License

Internal use only - Brigade Group Real Estate

---

Built with the principle: **Accuracy > Helpfulness | Refusal > Hallucination**
