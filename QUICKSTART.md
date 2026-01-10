# Quick Start Guide

This guide will get your Real Estate Sales Intelligence Chatbot up and running in ~10 minutes.

## Prerequisites Checklist

- [ ] Python 3.9+ installed
- [ ] Supabase account created
- [ ] OpenAI API key obtained

## Step-by-Step Setup

### 1. Configure Environment (2 minutes)

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
# Required:
#   OPENAI_API_KEY=sk-...
#   SUPABASE_URL=https://xxx.supabase.co
#   SUPABASE_KEY=eyJ...
#   SUPABASE_SERVICE_KEY=eyJ...
```

**Where to find Supabase credentials:**
1. Go to your Supabase project dashboard
2. Click "Settings" → "API"
3. Copy:
   - Project URL → `SUPABASE_URL`
   - anon/public key → `SUPABASE_KEY`
   - service_role key → `SUPABASE_SERVICE_KEY`

### 2. Set Up Database (3 minutes)

1. **Enable pgvector extension:**
   - In Supabase dashboard: Database → Extensions
   - Search for "vector"
   - Click "Enable"

2. **Run schema:**
   - Go to SQL Editor
   - Copy entire contents of `backend/database/schema.sql`
   - Click "Run"
   - Wait for success message

3. **Insert test projects:**
   ```sql
   INSERT INTO projects (name, location, status, rera_number, description) VALUES
   ('Brigade Citrine', 'Old Madras Road, Bengaluru', 'ongoing',
    'PRM/KA/RERA/1250/304/PR/131224/007287',
    'India''s First Net Zero Community');
   ```

   Copy the generated `id` (UUID) - you'll need this for Step 4!

### 3. Install Dependencies (1 minute)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Process Documents (3-5 minutes)

⚠️ **IMPORTANT:** Replace `YOUR_PROJECT_UUID` below with the actual UUID from Step 2!

```bash
# Still in backend/ directory with venv activated

python scripts/create_embeddings.py \
  --pdf "../Brigade Citrine E_Brochure 01-1.pdf" \
  --project-id "YOUR_PROJECT_UUID" \
  --project-name citrine
```

This will:
- Extract 36 pages from the PDF
- Create ~50-70 document chunks
- Generate OpenAI embeddings (costs ~$0.02)
- Store in Supabase

**Expected output:**
```
INFO:__main__:Processing Brigade Citrine brochure...
INFO:__main__:Created 64 chunks from Brigade Citrine brochure
INFO:__main__:Created document record with ID: xxx-xxx-xxx
INFO:__main__:Inserted batch 1: 64 chunks
INFO:__main__:Successfully inserted 64/64 chunks for Brigade Citrine
```

### 5. Start the API (30 seconds)

```bash
# In backend/ directory
uvicorn main:app --reload
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Starting Real Estate Sales Intelligence Chatbot API...
INFO:     Environment: development
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 6. Test It! (1 minute)

Open a new terminal and run:

```bash
# Test 1: Valid query
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the RERA number for Brigade Citrine?",
    "user_id": "test-user"
  }'
```

**Expected:** Should return answer with RERA number and source citation.

```bash
# Test 2: Unsupported query (should refuse)
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What will be the property value in 5 years?",
    "user_id": "test-user"
  }'
```

**Expected:** Should refuse with message about future predictions.

## Success Checklist

After setup, verify:

- [ ] API responds at http://localhost:8000/health
- [ ] Swagger docs available at http://localhost:8000/docs
- [ ] Test query returns answer with sources
- [ ] Unsupported query is refused
- [ ] Response time < 3 seconds

## Troubleshooting

### "ModuleNotFoundError: No module named 'x'"
```bash
# Make sure venv is activated
source venv/bin/activate
pip install -r requirements.txt
```

### "OpenAI API error"
- Check `OPENAI_API_KEY` in `.env`
- Verify you have billing set up in OpenAI account
- Check API quota

### "Supabase connection error"
- Verify URLs and keys in `.env`
- Check if pgvector extension is enabled
- Ensure schema is executed

### "No chunks retrieved"
- Verify Step 4 completed successfully
- Check if embeddings were created:
  ```sql
  SELECT COUNT(*) FROM document_chunks;
  -- Should return > 0
  ```

### "Answer not found"
- Try lowering similarity threshold in `.env`:
  ```
  SIMILARITY_THRESHOLD=0.7
  ```

## Next Steps

1. **Test more queries:** Try the examples in [README.md](README.md#usage)

2. **Review API docs:** Visit http://localhost:8000/docs

3. **Check analytics:**
   ```sql
   SELECT * FROM query_logs ORDER BY created_at DESC LIMIT 10;
   ```

4. **Add more documents:** Process Avalon brochure following Step 4

5. **Phase 2 features:** See [implementation plan](/Users/anandumv/.claude/plans/sorted-greeting-stearns.md)

## Docker Alternative (Optional)

If you prefer Docker:

```bash
# 1. Set up .env file as above
# 2. Run:
docker-compose up -d

# API will be available at http://localhost:8000
```

## Support

Need help?
- Check [README.md](README.md#troubleshooting)
- Review logs in terminal
- Check Supabase dashboard for errors

---

**Total Setup Time:** ~10 minutes
**Ready to answer queries!** 🎉
