# NBA Analytics API V2 - Enhanced Edition

Backend API for comprehensive NBA statistics and analytics with PostgreSQL database and daily automated data sync.

## Features

- ✅ **PostgreSQL Database** - Fast queries, persistent storage
- ✅ **Daily Auto-Sync** - Automated data collection at 6 AM
- ✅ **Multiple Metrics** - 3PT, assists, steals, points, rebounds, blocks
- ✅ **Season Comparisons** - Compare stats across seasons
- ✅ **Home/Away Splits** - Location-based analysis
- ✅ **Opponent Breakdowns** - Performance vs specific teams
- ✅ **RESTful API** - Clean, documented endpoints

## Quick Start

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file:
```bash
cp .env.example .env
# Edit .env and add your BALLDONTLIE_API_KEY
```

3. Run initial setup (populates database):
```bash
python initial_setup.py
```

4. Start the API:
```bash
python main.py
```

5. Visit `http://localhost:8000/docs` for interactive API documentation

### Production Deployment

See `DEPLOYMENT_GUIDE_V2.md` for Railway deployment instructions.

## API Endpoints

### Core Endpoints

- `GET /` - Health check
- `GET /player/search?name={name}` - Search for players
- `POST /analytics/metric-rate` - Analyze any metric (3PT, assists, steals, etc.)
- `GET /analytics/season-comparison` - Compare stats across seasons
- `GET /analytics/player-stats` - Get player stats with filters

### Sync Endpoints

- `POST /sync/daily` - Manually trigger daily sync
- `POST /sync/initial-setup` - Initial data population

## Environment Variables

```bash
# Required
BALLDONTLIE_API_KEY=your_api_key_here

# Optional (auto-set by Railway)
DATABASE_URL=postgresql://user:password@host:port/dbname
```

## Daily Sync

The system automatically syncs new game data daily at 6:00 AM UTC using the included scheduler.

### Manual Sync
```bash
python sync_service.py
```

### Schedule Configuration
Edit `scheduler.py` to change sync time.

## Database Schema

- **players** - NBA player information
- **teams** - NBA team information
- **games** - Game details and scores
- **game_stats** - Player statistics per game
- **metric_cache** - Pre-calculated metrics (future)
- **sync_log** - Sync history and status

## Testing

```bash
# Test local API
curl http://localhost:8000/

# Search for a player
curl "http://localhost:8000/player/search?name=curry"

# Analyze three-point shooting
curl -X POST "http://localhost:8000/analytics/metric-rate?player_name=Stephen+Curry&metric=threes&threshold=3"
```

## Architecture

```
FastAPI (main.py)
    ↓
PostgreSQL Database
    ↓
Daily Sync Worker (scheduler.py)
    ↓
Balldontlie API
```

## License

MIT
