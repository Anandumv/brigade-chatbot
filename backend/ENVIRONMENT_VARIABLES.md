# Environment Variables Configuration

This document describes all environment variables used by the Real Estate Sales Chatbot.

## Required Variables

### OpenAI API

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

**Description**: API key for OpenAI GPT models used for conversational AI.  
**Required**: Yes  
**Where to get**: [OpenAI Platform](https://platform.openai.com/api-keys)

## Optional Variables

### Railway PostgreSQL Database

```bash
DATABASE_URL=postgresql://user:password@host:5432/database
# OR
POSTGRES_URL=postgresql://user:password@host:5432/database
```

**Description**: PostgreSQL database connection URL for persistent storage.  
**Required**: No (falls back to in-memory storage)  
**Format**: `postgresql://user:password@host:port/database`  
**Railway**: Automatically provided when PostgreSQL is provisioned  

**Features using database**:
- User profiles (cross-session memory)
- Site visit scheduling
- Callback requests
- Automated reminders

**Without database**:
- All features work but data doesn't persist between restarts
- Suitable for development and testing
- Data stored in memory only

### Pixeltable Configuration

```bash
PIXELTABLE_HOME=.pixeltable
```

**Description**: Directory for Pixeltable data storage (projects, units, documents).  
**Default**: `.pixeltable`  
**Required**: No

### Application Settings

```bash
ENVIRONMENT=development
```

**Description**: Application environment.  
**Values**: `development`, `staging`, `production`  
**Default**: `development`

```bash
SIMILARITY_THRESHOLD=0.5
```

**Description**: Threshold for semantic similarity search (0.0 - 1.0).  
**Default**: `0.5`

```bash
EMBEDDING_MODEL=text-embedding-3-small
```

**Description**: OpenAI embedding model for semantic search.  
**Default**: `text-embedding-3-small`  
**Options**: `text-embedding-3-small`, `text-embedding-3-large`

### External Services (Future)

These are placeholders for future integrations:

```bash
# Email Service (SendGrid, AWS SES, etc.)
EMAIL_SERVICE_API_KEY=your_email_api_key
EMAIL_FROM=noreply@yourdomain.com

# SMS Service (Twilio, AWS SNS, etc.)
SMS_SERVICE_ACCOUNT_SID=your_twilio_account_sid
SMS_SERVICE_AUTH_TOKEN=your_twilio_auth_token
SMS_SERVICE_PHONE_NUMBER=+1234567890

# Calendar Integration (Google Calendar, Outlook, etc.)
GOOGLE_CALENDAR_CREDENTIALS_FILE=credentials.json
GOOGLE_CALENDAR_TOKEN_FILE=token.json
```

## Setup Instructions

### Local Development

1. **Create `.env` file** in the `backend/` directory:

```bash
cd backend
touch .env
```

2. **Add required variables**:

```bash
OPENAI_API_KEY=sk-...your-key...
```

3. **Optional: Add database URL** for persistent storage:

```bash
# For local PostgreSQL
DATABASE_URL=postgresql://localhost:5432/chatbot

# Or leave commented for in-memory storage
# DATABASE_URL=postgresql://localhost:5432/chatbot
```

4. **Run the application**:

```bash
python main.py
```

### Railway Deployment

1. **Create PostgreSQL database** in Railway dashboard:
   - Click "New" → "Database" → "PostgreSQL"
   - Railway automatically creates and injects `DATABASE_URL`

2. **Set environment variables** in Railway:
   - Go to your service settings
   - Navigate to "Variables" tab
   - Add `OPENAI_API_KEY=sk-...`
   - `DATABASE_URL` is automatically available (no need to set)

3. **Deploy**:
   - Railway automatically initializes database on first startup
   - All schemas are created automatically
   - No manual database setup required

## Database Behavior

### With DATABASE_URL Set

- ✅ **User profiles** stored in PostgreSQL
- ✅ **Site visits** stored in PostgreSQL
- ✅ **Callbacks** stored in PostgreSQL
- ✅ **Reminders** stored in PostgreSQL
- ✅ **Data persists** between restarts
- ✅ **Cross-session memory** works
- ✅ **Lead scoring** persists

### Without DATABASE_URL

- ⚠️ **User profiles** stored in memory
- ⚠️ **Site visits** stored in memory
- ⚠️ **Callbacks** stored in memory
- ⚠️ **Reminders** stored in memory
- ⚠️ **Data lost** on restart
- ✅ **All features work** (just ephemeral)
- ✅ **Good for development** and testing

## Automatic Fallback

The application automatically detects if `DATABASE_URL` is available:

```python
# Automatic detection in services
if DATABASE_URL is set:
    Use PostgreSQL for persistent storage
else:
    Use in-memory storage (development mode)
```

**No code changes needed** to switch between modes!

## Verification

Check logs on startup to verify database connection:

```
✅ Using Railway PostgreSQL for user profiles
✅ Using Railway PostgreSQL for scheduling
✅ Using Railway PostgreSQL for reminders
✅ Database initialization successful
```

Or in development mode:

```
⚠️ No DATABASE_URL - using in-memory storage for user profiles
⚠️ No DATABASE_URL - using in-memory storage for scheduling
⚠️ No DATABASE_URL - using in-memory storage for reminders
ℹ️ No DATABASE_URL configured - using in-memory storage
```

## Troubleshooting

### Database connection fails

**Error**: `Database initialization failed`

**Solutions**:
1. Verify `DATABASE_URL` format is correct
2. Check database is running and accessible
3. Verify credentials are correct
4. Check firewall/network settings
5. Application will automatically fall back to in-memory storage

### Missing OPENAI_API_KEY

**Error**: `OpenAI API key not configured`

**Solution**: Set `OPENAI_API_KEY` in `.env` file or Railway environment variables

### Pixeltable errors

**Error**: `Pixeltable initialization failed`

**Solution**: Ensure write permissions for `PIXELTABLE_HOME` directory

## Security Notes

⚠️ **Never commit `.env` file to git**  
⚠️ **Never expose API keys in code**  
⚠️ **Use Railway/platform environment variables for production**  
⚠️ **Rotate keys regularly**  
⚠️ **Use separate keys for development and production**

## Railway-Specific Notes

### Database URL Format

Railway provides `DATABASE_URL` in this format:

```
postgresql://postgres:password@containers-us-west-123.railway.app:5432/railway
```

Both `DATABASE_URL` and `POSTGRES_URL` are supported (Railway provides both).

### Automatic Injection

Railway automatically injects:
- `DATABASE_URL` - when PostgreSQL database is provisioned
- `PORT` - for web service binding
- `RAILWAY_ENVIRONMENT` - deployment environment

### Database Initialization

On first startup with `DATABASE_URL`:
1. Application detects database connection
2. Runs all schema files automatically:
   - `user_profiles_schema.sql`
   - `scheduling_schema.sql`
   - `reminders_schema.sql`
3. Creates tables, indexes, and constraints
4. Ready to use immediately

**No manual database setup required!** 🎉
