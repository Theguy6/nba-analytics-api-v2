# NBA Analytics API V2 - Enhanced Deployment Guide

This guide covers deploying the **Enhanced Version** with PostgreSQL database, daily auto-sync, and comprehensive metrics.

## What's New in V2

✅ **PostgreSQL Database** - Fast queries, no API delays
✅ **Daily Auto-Sync** - Automated data collection at 6 AM
✅ **More Metrics** - Assists, steals, points, rebounds, blocks
✅ **Season Comparisons** - "Is player shooting more 3PAs this year?"
✅ **Team Analysis** - Full team stats (coming soon)
✅ **Home/Away Splits** - Already included
✅ **Opponent Breakdowns** - Performance vs specific teams

## Prerequisites

1. **Railway Account** (free tier works!)
2. **Balldontlie API Key**
3. **GitHub Account** (recommended)

---

## Deployment Steps

### Step 1: Create GitHub Repository

```bash
cd nba-analytics-backend-v2
git init
git add .
git commit -m "NBA Analytics API V2 - Enhanced"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/nba-analytics-api-v2.git
git push -u origin main
```

### Step 2: Deploy to Railway

1. Go to https://railway.app
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your `nba-analytics-api-v2` repository
5. Railway auto-detects Python app

### Step 3: Add PostgreSQL Database

1. In your Railway project, click **"+ New"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway automatically creates database and sets `DATABASE_URL`
4. No configuration needed! ✨

### Step 4: Configure Environment Variables

1. Click on your web service
2. Go to **"Variables"** tab
3. Add: `BALLDONTLIE_API_KEY` = `[his actual API key]`
4. `DATABASE_URL` should already be set by Railway

### Step 5: Generate Domain

1. Go to **"Settings"** → **"Networking"**
2. Click **"Generate Domain"**
3. Copy URL (e.g., `https://nba-analytics-api-v2.railway.app`)
4. **SAVE THIS URL** - you need it for the Claude skill!

### Step 6: Enable Background Worker (Important!)

By default, Railway only runs the web service. We need to enable the worker for daily sync.

1. In Railway dashboard, click **"+ New"** → **"Empty Service"**
2. Link it to the same GitHub repo
3. Go to **"Settings"** → **"Deploy"**
4. Set **"Start Command"** to: `python scheduler.py`
5. This runs the daily sync worker

OR use Railway's cron jobs (simpler):
1. In web service settings
2. Add cron job: `0 6 * * * python sync_service.py`

### Step 7: Initial Data Population

After deployment, you need to populate the database with historical data.

**Option A: Via API endpoint (easiest)**
```bash
curl -X POST "https://YOUR_URL.railway.app/sync/initial-setup?season=2024&start_date=2023-10-01"
```

This will take 10-30 minutes but runs in background. Check Railway logs for progress.

**Option B: Via Railway CLI**
```bash
railway run python initial_setup.py
```

---

## Verify Deployment

### Test 1: Health Check
```bash
curl https://YOUR_URL.railway.app/
```

Should return:
```json
{
  "status": "healthy",
  "service": "NBA Analytics API - Enhanced",
  "version": "2.0.0",
  "features": [...]
}
```

### Test 2: Search Player
```bash
curl "https://YOUR_URL.railway.app/player/search?name=curry"
```

### Test 3: Analytics Query
```bash
curl -X POST "https://YOUR_URL.railway.app/analytics/metric-rate?player_name=Stephen+Curry&metric=threes&threshold=3&season=2024"
```

---

## Cost Breakdown

### Railway Free Tier
- **Web service**: 500 hours/month (always running = ~720 hours)
- **PostgreSQL**: 500 MB storage, 1 GB transfer
- **Worker**: Runs daily for ~5 minutes = ~2.5 hours/month

**Your Usage:**
- Web: ~720 hours/month
- Database: <100 MB (plenty of room)
- Worker: ~2.5 hours/month
- **Total: ~722 hours/month**

⚠️ **This EXCEEDS free tier (500 hours)!**

### Cost Options

**Option 1: Hobby Plan (Recommended)**
- **$5/month** flat rate
- Unlimited hours
- 500 MB database (enough)
- Perfect for this use case

**Option 2: Optimize Free Tier**
- Disable worker (run sync manually when needed)
- Sleep web service when not in use
- Stays free but less convenient

**Recommended: Pay $5/month** - Worth it for automation and peace of mind.

---

## Database Management

### View Data
Railway provides a database browser:
1. Click on PostgreSQL service
2. Go to "Data" tab
3. Browse tables

### Backup Database
Railway auto-backs up daily. Manual backup:
```bash
railway pg:dump > backup.sql
```

### Reset Database (if needed)
```bash
# Warning: This deletes all data!
railway pg:reset
# Then re-run initial setup
```

---

## Daily Sync Configuration

The scheduler runs at **6:00 AM UTC** daily. To change:

Edit `scheduler.py`:
```python
scheduler.add_job(
    run_daily_sync,
    trigger=CronTrigger(hour=10, minute=0),  # Change hour here
    ...
)
```

Time zones:
- 6 AM UTC = 1 AM EST / 10 PM PST (perfect for NBA)
- 10 AM UTC = 5 AM EST / 2 AM PST

---

## Monitoring & Maintenance

### Check Sync Status
```bash
# View recent syncs
curl "https://YOUR_URL.railway.app/sync/status"
```

### View Logs
Railway Dashboard → Select Service → "Deployments" → Click latest → "View Logs"

Or via CLI:
```bash
railway logs
```

### Manually Trigger Sync
```bash
curl -X POST "https://YOUR_URL.railway.app/sync/daily"
```

### Update the API
```bash
git add .
git commit -m "Update feature"
git push
# Railway auto-deploys!
```

---

## Troubleshooting

### "Database connection failed"
- Check `DATABASE_URL` is set in Railway
- Verify PostgreSQL service is running
- Check Railway logs for errors

### "Player not found"
- Run initial setup to populate database
- Check player name spelling
- Use search endpoint first

### "No games found"
- Verify initial setup completed
- Check date range in setup
- Ensure daily sync is running

### "Sync takes too long"
- Normal for initial setup (10-30 mins)
- Daily syncs are fast (~1-2 mins)
- Check API key is valid

### "Worker not running"
- Verify worker service is deployed
- Check worker logs in Railway
- Or use Railway cron jobs instead

---

## What Your Friend Can Now Ask

### Three-Point Analysis
- "How often does Steph Curry hit 3+ threes?"
- "Show me Dame's three-point consistency"

### Assists, Steals, etc.
- "How often does LeBron get 5+ assists?"
- "Show me games where Kawhi had 2+ steals"

### Season Comparisons
- "Is Luka shooting more 3PAs this year vs last year?"
- "Did Tatum's FGA increase this season?"

### Home/Away Splits
- "Is Harden better at home or away?"
- "Show me Giannis' away game stats"

### Opponent Analysis
- "How does Booker perform against the Lakers?"
- "Show me all games where KD played the Warriors"

---

## Next Steps

1. ✅ Deploy to Railway
2. ✅ Add PostgreSQL database
3. ✅ Run initial setup
4. ✅ Enable daily sync worker
5. ✅ Test API endpoints
6. ✅ Update Claude skill with new endpoints
7. ✅ Give to your friend!

---

## Support

- **Deployment issues**: Check Railway docs
- **Database issues**: Railway support
- **API issues**: Check logs
- **Sync issues**: Review `sync_service.py`

Your enhanced NBA analytics system is ready! 🏀
