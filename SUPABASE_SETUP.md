# Supabase Setup for Brigade Chatbot

To ensure your project data (76 projects, logs, etc.) is saved permanently without paying for a managed database, we use **Supabase** (Free Tier).

## 1. Create Database
1. Go to [database.new](https://database.new) (Supabase).
2. Sign in with GitHub.
3. Create a new organization (if needed) and a new project (e.g., "Brigade Bot").
4. **Set a strong password** for your database.
5. Wait ~2 minutes for it to setup.

## 2. Get Connection String
1. In your Supabase Project Dashboard, go to **Project Settings** (gear icon) -> **Database**.
2. Under "Connection params", find the **Connection String** box.
3. Click "URI" (not pgbouncer).
4. Copy the string. It looks like:
   `postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres`
5. Replace `[YOUR-PASSWORD]` with the password you set in Step 1.

## 3. Configure Render
1. Go to your [Render Dashboard](https://dashboard.render.com).
2. Select your `brigade-chatbot-api` service.
3. Go to **Environment**.
4. Add/Update the Environment Variable:
   - **Key:** `PIXELTABLE_DB_URL`
   - **Value:** (Paste your connection string from Step 2)
5. Save Changes. Render will re-deploy automatically.

## 4. Verify
Once deployed, the logs should show:
`Initializing Pixeltable with external DB: postgresql://...`

Your data is now persistent!
