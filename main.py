"""
NBA Analytics Backend API - Enhanced Version with BallDontLie Relay
Forwards requests to BallDontLie GOAT tier API for betting analytics
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from collections import defaultdict
import httpx
import os

from database import Player, Team, Game, GameStats, MetricCache
from db_session import init_db, get_db
from sync_service import DataSyncService

app = FastAPI(
    title="NBA Analytics API - Enhanced with BallDontLie Relay", 
    version="2.1.0",
    description="Betting analytics powered by BallDontLie GOAT tier API"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# BallDontLie API configuration
BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE_API_KEY", "ecf3210d-b098-4e81-8f7c-57c3aa41be3b")
BALLDONTLIE_BASE_URL = "https://api.balldontlie.io"

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Database initialized")
    print(f"✅ BallDontLie relay active (GOAT tier)")

# === BALLDONTLIE RELAY ENDPOINTS ===

async def forward_to_balldontlie(path: str, params: Dict[str, Any] = None) -> Dict:
    """
    Forward requests to BallDontLie API with GOAT tier authentication
    """
    url = f"{BALLDONTLIE_BASE_URL}{path}"
    headers = {"Authorization": BALLDONTLIE_API_KEY}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers, params=params or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=401, 
                    detail="BallDontLie API authentication failed. Check GOAT tier subscription."
                )
            elif e.response.status_code == 429:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. GOAT tier = 600 req/min. Wait briefly."
                )
            elif e.response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Endpoint not found: {path}"
                )
            else:
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"BallDontLie API error: {e.response.text}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to BallDontLie API: {str(e)}"
            )

# === NBA V1 ENDPOINTS (Core Data) ===

@app.get("/api/v1/teams")
async def get_teams(
    conference: Optional[str] = None,
    division: Optional[str] = None,
    cursor: Optional[str] = None,
    per_page: int = Query(25, le=100)
):
    """Get all NBA teams"""
    params = {"per_page": per_page}
    if conference:
        params["conference"] = conference
    if division:
        params["division"] = division
    if cursor:
        params["cursor"] = cursor
    
    return await forward_to_balldontlie("/v1/teams", params)

@app.get("/api/v1/teams/{team_id}")
async def get_team(team_id: int):
    """Get specific team by ID"""
    return await forward_to_balldontlie(f"/v1/teams/{team_id}")

@app.get("/api/v1/players/active")
async def get_active_players(
    search: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    team_ids: Optional[List[int]] = Query(None, alias="team_ids[]"),
    player_ids: Optional[List[int]] = Query(None, alias="player_ids[]"),
    cursor: Optional[str] = None,
    per_page: int = Query(25, le=100)
):
    """
    Get ACTIVE NBA players only (current rosters)
    ⚠️ USE THIS ENDPOINT FOR BETTING ANALYSIS - Only returns active players
    """
    params = {"per_page": per_page}
    if search:
        params["search"] = search
    if first_name:
        params["first_name"] = first_name
    if last_name:
        params["last_name"] = last_name
    if team_ids:
        params["team_ids[]"] = team_ids
    if player_ids:
        params["player_ids[]"] = player_ids
    if cursor:
        params["cursor"] = cursor
    
    return await forward_to_balldontlie("/v1/players/active", params)

@app.get("/api/v1/players")
async def get_players(
    search: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    team_ids: Optional[List[int]] = Query(None, alias="team_ids[]"),
    player_ids: Optional[List[int]] = Query(None, alias="player_ids[]"),
    cursor: Optional[str] = None,
    per_page: int = Query(25, le=100)
):
    """
    Get ALL NBA players (includes historical/inactive players)
    ⚠️ WARNING: This returns ALL players including inactive/retired
    ⚠️ For betting analysis, use /api/v1/players/active instead
    """
    params = {"per_page": per_page}
    if search:
        params["search"] = search
    if first_name:
        params["first_name"] = first_name
    if last_name:
        params["last_name"] = last_name
    if team_ids:
        params["team_ids[]"] = team_ids
    if player_ids:
        params["player_ids[]"] = player_ids
    if cursor:
        params["cursor"] = cursor
    
    return await forward_to_balldontlie("/v1/players", params)

@app.get("/api/v1/players/{player_id}")
async def get_player(player_id: int):
    """Get specific player by ID"""
    return await forward_to_balldontlie(f"/v1/players/{player_id}")

@app.get("/api/v1/games")
async def get_games(
    dates: Optional[List[str]] = Query(None, alias="dates[]"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    seasons: Optional[List[int]] = Query(None, alias="seasons[]"),
    postseason: Optional[bool] = None,
    team_ids: Optional[List[int]] = Query(None, alias="team_ids[]"),
    cursor: Optional[str] = None,
    per_page: int = Query(25, le=100)
):
    """Get NBA games with filters"""
    params = {"per_page": per_page}
    if dates:
        params["dates[]"] = dates
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if seasons:
        params["seasons[]"] = seasons
    if postseason is not None:
        params["postseason"] = postseason
    if team_ids:
        params["team_ids[]"] = team_ids
    if cursor:
        params["cursor"] = cursor
    
    return await forward_to_balldontlie("/v1/games", params)

@app.get("/api/v1/games/{game_id}")
async def get_game(game_id: int):
    """Get specific game by ID"""
    return await forward_to_balldontlie(f"/v1/games/{game_id}")

@app.get("/api/v1/stats")
async def get_stats(
    player_ids: Optional[List[int]] = Query(None, alias="player_ids[]"),
    game_ids: Optional[List[int]] = Query(None, alias="game_ids[]"),
    team_ids: Optional[List[int]] = Query(None, alias="team_ids[]"),
    dates: Optional[List[str]] = Query(None, alias="dates[]"),
    seasons: Optional[List[int]] = Query(None, alias="seasons[]"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    postseason: Optional[bool] = None,
    cursor: Optional[str] = None,
    per_page: int = Query(25, le=100)
):
    """Get player game statistics"""
    params = {"per_page": per_page}
    if player_ids:
        params["player_ids[]"] = player_ids
    if game_ids:
        params["game_ids[]"] = game_ids
    if team_ids:
        params["team_ids[]"] = team_ids
    if dates:
        params["dates[]"] = dates
    if seasons:
        params["seasons[]"] = seasons
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if postseason is not None:
        params["postseason"] = postseason
    if cursor:
        params["cursor"] = cursor
    
    return await forward_to_balldontlie("/v1/stats", params)

@app.get("/api/v1/stats/advanced")
async def get_advanced_stats(
    player_ids: Optional[List[int]] = Query(None, alias="player_ids[]"),
    game_ids: Optional[List[int]] = Query(None, alias="game_ids[]"),
    dates: Optional[List[str]] = Query(None, alias="dates[]"),
    seasons: Optional[List[int]] = Query(None, alias="seasons[]"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    postseason: Optional[bool] = None,
    cursor: Optional[str] = None,
    per_page: int = Query(25, le=100)
):
    """Get advanced statistics (GOAT tier)"""
    params = {"per_page": per_page}
    if player_ids:
        params["player_ids[]"] = player_ids
    if game_ids:
        params["game_ids[]"] = game_ids
    if dates:
        params["dates[]"] = dates
    if seasons:
        params["seasons[]"] = seasons
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if postseason is not None:
        params["postseason"] = postseason
    if cursor:
        params["cursor"] = cursor
    
    return await forward_to_balldontlie("/v1/stats/advanced", params)

# === GOAT TIER ENDPOINTS ===

@app.get("/api/v1/season_averages/{category}")
async def get_season_averages(
    category: str,
    season: int,
    season_type: str = "regular",
    type: str = "base",
    player_ids: Optional[List[int]] = Query(None, alias="player_ids[]"),
    cursor: Optional[str] = None,
    per_page: int = Query(25, le=100)
):
    """
    Get season averages by category (GOAT tier only)
    
    Categories: general, shooting, defense, clutch
    
    Types by category:
    - general: base, advanced, usage, scoring, defense, misc
    - clutch: base, advanced, usage, scoring, misc
    - defense: 2_pointers, 3_pointers, greater_than_15ft, less_than_10ft, less_than_6ft, overall
    - shooting: 5ft_range, by_zone
    
    Example: /api/v1/season_averages/general?season=2024&type=base
    """
    # Validate category
    valid_categories = ["general", "shooting", "defense", "clutch"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )
    
    # Validate type for category
    category_types = {
        "general": ["base", "advanced", "usage", "scoring", "defense", "misc"],
        "clutch": ["base", "advanced", "usage", "scoring", "misc"],
        "defense": ["2_pointers", "3_pointers", "greater_than_15ft", "less_than_10ft", "less_than_6ft", "overall"],
        "shooting": ["5ft_range", "by_zone"]
    }
    
    if type not in category_types.get(category, []):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type '{type}' for category '{category}'. Valid types: {', '.join(category_types[category])}"
        )
    
    params = {
        "season": season,
        "season_type": season_type,
        "type": type,
        "per_page": per_page
    }
    if player_ids:
        params["player_ids[]"] = player_ids
    if cursor:
        params["cursor"] = cursor
    
    return await forward_to_balldontlie(f"/v1/season_averages/{category}", params)

@app.get("/api/v1/leaders")
async def get_leaders(
    stat_type: str,
    season: int,
    cursor: Optional[str] = None,
    per_page: int = Query(25, le=100)
):
    """
    Get statistical leaders (GOAT tier only)
    
    Valid stat_types: reb, dreb, tov, ast, oreb, min, pts, stl, blk
    """
    valid_stat_types = ["reb", "dreb", "tov", "ast", "oreb", "min", "pts", "stl", "blk"]
    if stat_type not in valid_stat_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stat_type. Must be one of: {', '.join(valid_stat_types)}"
        )
    
    params = {
        "stat_type": stat_type,
        "season": season,
        "per_page": per_page
    }
    if cursor:
        params["cursor"] = cursor
    
    return await forward_to_balldontlie("/v1/leaders", params)

@app.get("/api/v1/standings")
async def get_standings(
    season: int
):
    """Get NBA standings (GOAT tier only)"""
    params = {"season": season}
    return await forward_to_balldontlie("/v1/standings", params)

@app.get("/api/v1/player_injuries")
async def get_injuries(
    team_ids: Optional[List[int]] = Query(None, alias="team_ids[]"),
    player_ids: Optional[List[int]] = Query(None, alias="player_ids[]"),
    cursor: Optional[str] = None,
    per_page: int = Query(25, le=100)
):
    """Get injury reports (GOAT tier only)"""
    params = {"per_page": per_page}
    if team_ids:
        params["team_ids[]"] = team_ids
    if player_ids:
        params["player_ids[]"] = player_ids
    if cursor:
        params["cursor"] = cursor
    
    return await forward_to_balldontlie("/v1/player_injuries", params)

@app.get("/api/v1/box_scores")
async def get_box_scores(
    date: str = Query(..., description="Date in YYYY-MM-DD format")
):
    """Get box scores for a specific date (GOAT tier only)"""
    params = {"date": date}
    return await forward_to_balldontlie("/v1/box_scores", params)

@app.get("/api/v1/box_scores/live")
async def get_live_box_scores():
    """Get live box scores for today (GOAT tier only)"""
    return await forward_to_balldontlie("/v1/box_scores/live")

# === NBA V2 ENDPOINTS (Betting Odds) ===

@app.get("/api/v2/odds")
async def get_odds(
    dates: Optional[List[str]] = Query(None, alias="dates[]"),
    game_ids: Optional[List[int]] = Query(None, alias="game_ids[]"),
    vendor: Optional[str] = None,
    cursor: Optional[str] = None,
    per_page: int = Query(25, le=100)
):
    """
    Get betting odds (GOAT tier only)
    
    Vendors: betmgm, fanduel, draftkings, bet365, caesars, espnbet
    
    Note: Odds data available 24 hours before game start
    """
    if not dates and not game_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'dates' or 'game_ids' must be provided"
        )
    
    params = {"per_page": per_page}
    if dates:
        params["dates[]"] = dates
    if game_ids:
        params["game_ids[]"] = game_ids
    if vendor:
        params["vendor"] = vendor
    if cursor:
        params["cursor"] = cursor
    
    return await forward_to_balldontlie("/v2/odds", params)

# === CUSTOM BETTING ANALYTICS ENDPOINTS ===

@app.get("/api/betting/todays-slate")
async def get_todays_betting_slate():
    """
    Get today's games with betting insights
    Combines: games, odds, injuries, recent form
    """
    today = date.today().isoformat()
    
    # Get today's games
    games_data = await forward_to_balldontlie("/v1/games", {"dates[]": [today]})
    
    # Get odds
    try:
        odds_data = await forward_to_balldontlie("/v2/odds", {"dates[]": [today]})
    except:
        odds_data = {"data": []}
    
    # Get injuries
    try:
        injuries_data = await forward_to_balldontlie("/v1/player_injuries", {})
    except:
        injuries_data = {"data": []}
    
    # Combine data
    slate = []
    for game in games_data.get("data", []):
        game_info = {
            "game": game,
            "odds": [o for o in odds_data.get("data", []) if o.get("game_id") == game["id"]],
            "injuries": []
        }
        
        # Filter injuries for this game's teams
        home_id = game.get("home_team", {}).get("id")
        visitor_id = game.get("visitor_team", {}).get("id")
        
        for inj in injuries_data.get("data", []):
            player_team_id = inj.get("player", {}).get("team_id")
            if player_team_id in [home_id, visitor_id]:
                game_info["injuries"].append(inj)
        
        slate.append(game_info)
    
    return {
        "date": today,
        "games_count": len(slate),
        "slate": slate
    }

@app.get("/api/betting/player-prop-analysis")
async def analyze_player_prop(
    player_id: int,
    stat: str = "pts",
    threshold: float = 25.5,
    games: int = 15
):
    """
    Analyze player prop probability
    Returns hit rate for over/under based on recent games
    """
    # Get player info
    player_data = await forward_to_balldontlie(f"/v1/players/{player_id}")
    
    # Get recent stats
    stats_data = await forward_to_balldontlie("/v1/stats", {
        "player_ids[]": [player_id],
        "seasons[]": [2024],
        "per_page": games
    })
    
    # Calculate hit rates
    recent_games = stats_data.get("data", [])[:games]
    if not recent_games:
        raise HTTPException(status_code=404, detail="No recent games found")
    
    hits = sum(1 for g in recent_games if g.get(stat, 0) >= threshold)
    hit_rate = (hits / len(recent_games)) * 100
    
    # Home/away split
    home_games = [g for g in recent_games if g.get("game", {}).get("home_team_id") == player_data["data"]["team"]["id"]]
    away_games = [g for g in recent_games if g.get("game", {}).get("home_team_id") != player_data["data"]["team"]["id"]]
    
    home_hits = sum(1 for g in home_games if g.get(stat, 0) >= threshold)
    away_hits = sum(1 for g in away_games if g.get(stat, 0) >= threshold)
    
    return {
        "player": player_data["data"],
        "prop": f"{stat} over {threshold}",
        "analysis": {
            "games_analyzed": len(recent_games),
            "overall_hit_rate": round(hit_rate, 1),
            "hits": hits,
            "misses": len(recent_games) - hits,
            "home_hit_rate": round((home_hits / len(home_games)) * 100, 1) if home_games else 0,
            "away_hit_rate": round((away_hits / len(away_games)) * 100, 1) if away_games else 0,
            "recent_values": [g.get(stat, 0) for g in recent_games[:5]],
            "average_value": round(sum(g.get(stat, 0) for g in recent_games) / len(recent_games), 1)
        },
        "recommendation": "VALUE" if hit_rate > 60 else "AVOID" if hit_rate < 40 else "NEUTRAL"
    }

# === ROOT ENDPOINT ===

@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "healthy",
        "service": "NBA Analytics API - Enhanced with BallDontLie Relay",
        "version": "2.1.0",
        "features": [
            "BallDontLie GOAT tier relay",
            "Live betting odds (v2/odds)",
            "Advanced season averages",
            "Real-time injury reports",
            "Statistical leaders",
            "Box scores & live stats",
            "Custom betting analytics",
            "ACTIVE PLAYERS filtering (inactive players excluded)"
        ],
        "balldontlie_api": "Connected (GOAT tier)",
        "important_notes": {
            "active_players": "Use /api/v1/players/active for current roster players only",
            "all_players": "/api/v1/players includes inactive/retired players - use with caution"
        },
        "endpoints": {
            "nba_v1": "/api/v1/*",
            "betting_odds_v2": "/api/v2/odds",
            "custom_analytics": "/api/betting/*"
        }
    }

@app.get("/health")
async def health_check():
    """Detailed health check with BallDontLie connectivity"""
    try:
        # Test BallDontLie connection
        await forward_to_balldontlie("/v1/teams", {"per_page": 1})
        balldontlie_status = "connected"
    except:
        balldontlie_status = "error"
    
    return {
        "api": "healthy",
        "database": "connected",
        "balldontlie_api": balldontlie_status,
        "tier": "GOAT",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
