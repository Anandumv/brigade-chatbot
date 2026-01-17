# 🚂 Railway Deployment Guide

Quick reference for deploying the Real Estate Sales Chatbot to Railway with PostgreSQL.

---

## 📋 Prerequisites

- [x] Railway account ([railway.app](https://railway.app))
- [x] GitHub repository with your code
- [x] OpenAI API key

---

## 🚀 Deployment Steps

### Step 1: Create New Project

1. Go to [Railway Dashboard](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository
5. Railway creates a service for your app

### Step 2: Add PostgreSQL Database

1. In your project, click **"New"**
2. Select **"Database"**
3. Choose **"PostgreSQL"**
4. Railway provisions database and injects `DATABASE_URL` automatically

✅ **Done!** No manual configuration needed.

### Step 3: Set Environment Variables

1. Go to your **service** (not database)
2. Click **"Variables"** tab
3. Add **"New Variable"**:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```
4. Save

**Note**: `DATABASE_URL` is automatically available (injected by Railway)

### Step 4: Configure Deployment

1. Click **"Settings"** tab
2. Set **Start Command**:
   ```bash
   cd backend && python main.py
   ```
3. Set **Build Command** (if needed):
   ```bash
   cd backend && pip install -r requirements.txt
   ```
4. **Port**: Railway auto-detects (uses `$PORT` env var)

### Step 5: Deploy

1. Railway automatically deploys on git push
2. Or click **"Deploy"** button manually
3. Watch deployment logs

**Successful deployment logs**:
```
🚀 Initializing Railway PostgreSQL database...
✅ user_profiles_schema.sql executed successfully
✅ scheduling_schema.sql executed successfully
✅ reminders_schema.sql executed successfully
✅ Database initialization successful
✅ Using Railway PostgreSQL for user profiles
✅ Using Railway PostgreSQL for scheduling
✅ Using Railway PostgreSQL for reminders
🚀 Starting Real Estate Sales Intelligence Chatbot API v1.1...
```

---

## 🔍 Verification

### 1. Check Database Connection

Visit: `https://your-app.railway.app/health` (if you have a health endpoint)

Or check logs for:
```
✅ Using Railway PostgreSQL for user profiles
✅ Using Railway PostgreSQL for scheduling
✅ Using Railway PostgreSQL for reminders
```

### 2. Test API Endpoints

```bash
# Health check
curl https://your-app.railway.app/

# Chat endpoint
curl -X POST https://your-app.railway.app/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me 3BHK properties under 1.5 Cr"}'
```

### 3. Check Database Tables

1. Go to Railway dashboard
2. Click on **PostgreSQL database**
3. Click **"Data"** tab
4. You should see:
   - `user_profiles`
   - `scheduled_visits`
   - `requested_callbacks`
   - `reminders`

---

## 🔧 Railway-Specific Configuration

### Environment Variables Provided by Railway

Automatically available (no need to set):

- `DATABASE_URL` - PostgreSQL connection string
- `POSTGRES_URL` - Alternative format (same as DATABASE_URL)
- `PORT` - Port your app should bind to
- `RAILWAY_ENVIRONMENT` - deployment/production
- `RAILWAY_PROJECT_NAME` - Your project name
- `RAILWAY_SERVICE_NAME` - Your service name

### Custom Domain (Optional)

1. Go to **service settings**
2. Click **"Domains"**
3. Add your custom domain
4. Update DNS records as shown
5. Railway handles SSL automatically

---

## 📊 Monitoring

### View Logs

1. Click on your **service**
2. Click **"Logs"** tab
3. Real-time log streaming

### Database Metrics

1. Click on **PostgreSQL database**
2. Click **"Metrics"** tab
3. View:
   - CPU usage
   - Memory usage
   - Disk usage
   - Active connections

### Application Metrics

1. Click on your **service**
2. Click **"Metrics"** tab
3. View:
   - CPU usage
   - Memory usage
   - Request counts
   - Response times

---

## 🐛 Troubleshooting

### Database Connection Fails

**Symptoms**: `Database initialization failed`

**Solutions**:
1. Verify PostgreSQL database is running
2. Check `DATABASE_URL` is in environment variables
3. Check database is in same project
4. Restart service
5. Check database logs for errors

**Fallback**: App automatically uses in-memory storage

### OpenAI API Errors

**Symptoms**: `OpenAI API key not configured`

**Solutions**:
1. Verify `OPENAI_API_KEY` is set in service variables
2. Check API key is valid (test in OpenAI Playground)
3. Check API quota/billing
4. Restart service after setting variable

### Port Binding Errors

**Symptoms**: `Address already in use`

**Solutions**:
1. Ensure app binds to `$PORT` environment variable:
   ```python
   port = int(os.getenv("PORT", 8000))
   uvicorn.run(app, host="0.0.0.0", port=port)
   ```
2. Railway automatically sets `$PORT`
3. Don't hardcode port numbers

### Build Fails

**Symptoms**: `pip install` errors

**Solutions**:
1. Check `requirements.txt` exists in `backend/`
2. Verify all dependencies are compatible
3. Check build command path: `cd backend && pip install -r requirements.txt`
4. Check Python version compatibility

---

## 🔄 Updates & Redeployment

### Automatic Deployment

Railway auto-deploys on:
- Git push to main branch
- Manual trigger via dashboard

### Manual Redeployment

1. Go to **service**
2. Click **"Deployments"** tab
3. Click **"Deploy"** on latest deployment
4. Or click **"Redeploy"** button

### Rollback

1. Go to **"Deployments"** tab
2. Find previous successful deployment
3. Click **"..."** menu
4. Select **"Rollback to this version"**

---

## 💰 Pricing

### Railway Pricing Tiers

- **Free Trial**: $5 credit, no credit card
- **Hobby**: $5/month, includes credits
- **Pro**: $20/month, more resources

### PostgreSQL Costs

- Charged based on:
  - Storage used (GB)
  - CPU/RAM usage
  - Data transfer

### Optimization Tips

1. **Database**:
   - Regular vacuum/analyze
   - Index unused columns
   - Delete old data

2. **Application**:
   - Use connection pooling
   - Optimize queries
   - Cache frequently accessed data
   - Use in-memory storage for dev

---

## 🔒 Security

### Best Practices

1. **Environment Variables**:
   - Never commit secrets to git
   - Use Railway variables for all sensitive data
   - Rotate API keys regularly

2. **Database**:
   - Railway PostgreSQL is private by default
   - Only accessible from same project
   - No public internet access

3. **API Keys**:
   - Use separate keys for dev/prod
   - Enable rate limiting
   - Monitor usage

4. **CORS**:
   - Configure `allow_origins` appropriately
   - Don't use `["*"]` in production

---

## 📞 Support

### Railway Support

- **Docs**: [docs.railway.app](https://docs.railway.app)
- **Discord**: [Railway Discord](https://discord.gg/railway)
- **Help**: In-app support chat

### Application Issues

- Check logs first
- Review environment variables
- Test locally with PostgreSQL
- Check database connection

---

## ✅ Deployment Checklist

Before deploying:

- [ ] Code pushed to GitHub
- [ ] `requirements.txt` is up to date
- [ ] Environment variables documented
- [ ] Database schemas tested locally
- [ ] API endpoints tested
- [ ] Error handling implemented
- [ ] Logging configured

After deploying:

- [ ] Check deployment logs for errors
- [ ] Verify database initialization
- [ ] Test API endpoints
- [ ] Check database tables created
- [ ] Monitor resource usage
- [ ] Set up custom domain (optional)
- [ ] Configure alerting (optional)

---

## 🎉 Quick Deploy Command Summary

```bash
# 1. Push to GitHub
git add .
git commit -m "Railway deployment ready"
git push origin main

# 2. In Railway Dashboard:
# - New Project → Deploy from GitHub
# - Add PostgreSQL database
# - Set OPENAI_API_KEY variable
# - Deploy!

# 3. Verify
curl https://your-app.railway.app/

# Done! 🚀
```

---

## 📚 Additional Resources

- [Railway Documentation](https://docs.railway.app)
- [PostgreSQL Best Practices](https://docs.railway.app/databases/postgresql)
- [Environment Variables Guide](../backend/ENVIRONMENT_VARIABLES.md)
- [Migration Guide](../RAILWAY_POSTGRES_MIGRATION_COMPLETE.md)

---

**🚂 Happy Deploying on Railway!**

*For detailed technical implementation, see `RAILWAY_POSTGRES_MIGRATION_COMPLETE.md`*
