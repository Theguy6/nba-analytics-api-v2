"""
NBA Analytics Backend API - Enhanced Version
With PostgreSQL database, daily sync, and comprehensive metrics
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from collections import defaultdict

from database import Player, Team, Game, GameStats, MetricCache
from db_session import init_db, get_db
from sync_service import DataSyncService

app = FastAPI(title="NBA Analytics API - Enhanced", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Database initialized")

# === MODELS ===

class PlayerSearchResult(BaseModel):
    id: int
    name: str
    team: Optional[str]
    position: Optional[str]

class MetricAnalysis(BaseModel):
    player_name: str
    season: int
    metric_type: str
    overall_rate: float
    games_analyzed: int
    windows: List[Dict[str, Any]]
    home_away_splits: Dict[str, Any]
    opponent_breakdown: List[Dict[str, Any]]

# === HELPER FUNCTIONS ===

def get_player_by_name(db: Session, player_name: str) -> Player:
    """Find player by name"""
    parts = player_name.strip().split()
    
    if len(parts) < 2:
        # Try searching in both first and last name
        player = db.query(Player).filter(
            or_(
                Player.first_name.ilike(f"%{player_name}%"),
                Player.last_name.ilike(f"%{player_name}%")
            )
        ).first()
    else:
        # Assume first part is first name, rest is last name
        first = parts[0]
        last = " ".join(parts[1:])
        
        player = db.query(Player).filter(
            Player.first_name.ilike(f"%{first}%"),
            Player.last_name.ilike(f"%{last}%")
        ).first()
    
    if not player:
        raise HTTPException(status_code=404, detail=f"Player '{player_name}' not found")
    
    return player

def calculate_rolling_metric(
    games: List[GameStats],
    metric_field: str,
    threshold: int,
    window_size: int = 10
) -> Dict[str, Any]:
    """
    Calculate rolling window metric for any stat
    metric_field: 'fg3m', 'ast', 'stl', 'pts', etc.
    threshold: minimum value to meet threshold (e.g., 3+ threes)
    """
    if len(games) < window_size:
        return {
            "error": f"Not enough games. Need {window_size}, have {len(games)}",
            "games_played": len(games)
        }
    
    # Sort by date
    sorted_games = sorted(games, key=lambda x: x.game.date)
    
    results = {
        "total_games": len(sorted_games),
        "windows_analyzed": [],
        "overall_rate": 0.0,
        "home_away_splits": {"home": {"games": 0, "threshold_met": 0}, "away": {"games": 0, "threshold_met": 0}},
        "opponent_breakdown": defaultdict(lambda: {"games": 0, "threshold_met": 0})
    }
    
    # Analyze rolling windows
    num_windows = len(sorted_games) // window_size
    total_threshold_met = 0
    
    for window_num in range(num_windows):
        start_idx = window_num * window_size
        end_idx = start_idx + window_size
        window_games = sorted_games[start_idx:end_idx]
        
        threshold_count = sum(1 for g in window_games if getattr(g, metric_field, 0) >= threshold)
        rate = (threshold_count / window_size) * 100
        
        window_info = {
            "games": f"{start_idx + 1}-{end_idx}",
            "threshold_met": threshold_count,
            "rate": round(rate, 1),
            "details": []
        }
        
        for game_stat in window_games:
            value = getattr(game_stat, metric_field, 0)
            is_home = game_stat.is_home
            
            # Get opponent
            if is_home:
                opponent_id = game_stat.game.visitor_team_id
                opponent = game_stat.game.visitor_team
            else:
                opponent_id = game_stat.game.home_team_id
                opponent = game_stat.game.home_team
            
            opponent_abbr = opponent.abbreviation if opponent else "UNK"
            met_threshold = value >= threshold
            
            # Track home/away
            location = "home" if is_home else "away"
            results["home_away_splits"][location]["games"] += 1
            if met_threshold:
                results["home_away_splits"][location]["threshold_met"] += 1
            
            # Track opponent
            results["opponent_breakdown"][opponent_abbr]["games"] += 1
            if met_threshold:
                results["opponent_breakdown"][opponent_abbr]["threshold_met"] += 1
            
            window_info["details"].append({
                "date": game_stat.game.date.isoformat(),
                "opponent": opponent_abbr,
                "value": value,
                "met_threshold": met_threshold,
                "location": location
            })
        
        total_threshold_met += threshold_count
        results["windows_analyzed"].append(window_info)
    
    # Calculate rates
    total_games_in_windows = num_windows * window_size
    results["overall_rate"] = round((total_threshold_met / total_games_in_windows) * 100, 1)
    
    for location in ["home", "away"]:
        split = results["home_away_splits"][location]
        if split["games"] > 0:
            split["rate"] = round((split["threshold_met"] / split["games"]) * 100, 1)
    
    # Convert opponent breakdown
    opponent_list = []
    for opp, stats in results["opponent_breakdown"].items():
        opponent_list.append({
            "opponent": opp,
            "games": stats["games"],
            "threshold_met": stats["threshold_met"],
            "rate": round((stats["threshold_met"] / stats["games"]) * 100, 1) if stats["games"] > 0 else 0
        })
    
    results["opponent_breakdown"] = sorted(opponent_list, key=lambda x: x["games"], reverse=True)
    
    return results

def compare_season_stats(games_season_1: List[GameStats], games_season_2: List[GameStats], stat_field: str) -> Dict:
    """Compare a stat across two seasons"""
    
    def calc_average(games, field):
        if not games:
            return 0
        total = sum(getattr(g, field, 0) for g in games)
        return round(total / len(games), 2)
    
    return {
        "season_1": {
            "games": len(games_season_1),
            f"avg_{stat_field}": calc_average(games_season_1, stat_field),
            f"total_{stat_field}": sum(getattr(g, stat_field, 0) for g in games_season_1)
        },
        "season_2": {
            "games": len(games_season_2),
            f"avg_{stat_field}": calc_average(games_season_2, stat_field),
            f"total_{stat_field}": sum(getattr(g, stat_field, 0) for g in games_season_2)
        }
    }

# === ENDPOINTS ===

@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "healthy",
        "service": "NBA Analytics API - Enhanced",
        "version": "2.0.0",
        "features": [
            "PostgreSQL database",
            "Daily auto-sync",
            "Multiple metrics (3PT, assists, steals, etc.)",
            "Team analysis",
            "Season comparisons",
            "Home/away splits"
        ]
    }

@app.get("/player/search")
async def search_player(
    name: str = Query(..., description="Player name to search"),
    db: Session = Depends(get_db)
):
    """Search for players by name"""
    search_term = f"%{name}%"
    
    players = db.query(Player).filter(
        or_(
            Player.first_name.ilike(search_term),
            Player.last_name.ilike(search_term)
        )
    ).limit(20).all()
    
    return {
        "query": name,
        "results": [
            PlayerSearchResult(
                id=p.id,
                name=p.full_name,
                team=p.team_name,
                position=p.position
            )
            for p in players
        ]
    }

@app.post("/analytics/metric-rate")
async def analyze_metric_rate(
    player_name: str = Query(..., description="Player full name"),
    metric: str = Query(..., description="Metric to analyze: 'threes', 'assists', 'steals', 'points', 'rebounds', 'blocks'"),
    threshold: int = Query(..., description="Minimum value to meet threshold"),
    season: int = Query(2024, description="NBA season year"),
    window_size: int = Query(10, description="Game window size"),
    db: Session = Depends(get_db)
):
    """
    Universal metric rate analyzer - works for ANY stat!
    
    Examples:
    - metric='threes', threshold=3: How often does player hit 3+ threes?
    - metric='assists', threshold=5: How often does player get 5+ assists?
    - metric='steals', threshold=2: How often does player get 2+ steals?
    """
    # Map metric names to database fields
    metric_map = {
        "threes": "fg3m",
        "three_pointers": "fg3m",
        "3pt": "fg3m",
        "assists": "ast",
        "steals": "stl",
        "points": "pts",
        "rebounds": "reb",
        "blocks": "blk"
    }
    
    metric_field = metric_map.get(metric.lower())
    if not metric_field:
        raise HTTPException(status_code=400, detail=f"Unknown metric: {metric}. Available: {list(metric_map.keys())}")
    
    # Get player
    player = get_player_by_name(db, player_name)
    
    # Get games for season
    games = db.query(GameStats).join(Game).filter(
        GameStats.player_id == player.id,
        Game.season == season
    ).all()
    
    if not games:
        raise HTTPException(status_code=404, detail=f"No games found for {player.full_name} in {season} season")
    
    # Calculate metric
    analytics = calculate_rolling_metric(games, metric_field, threshold, window_size)
    
    return {
        "player": player.full_name,
        "season": season,
        "metric": metric,
        "threshold": f"{threshold}+",
        "analytics": analytics
    }

@app.get("/analytics/season-comparison")
async def compare_seasons(
    player_name: str = Query(..., description="Player name"),
    stat: str = Query(..., description="Stat to compare: 'fga', 'fg3a', 'minutes', 'pts', 'ast'"),
    season_1: int = Query(2023, description="First season"),
    season_2: int = Query(2024, description="Second season"),
    db: Session = Depends(get_db)
):
    """
    Compare a player's stats across two seasons
    Answers: "Does player have higher FGA/3PA this year vs last year?"
    """
    # Validate stat field
    valid_stats = ['fga', 'fg3a', 'fgm', 'fg3m', 'pts', 'ast', 'reb', 'stl', 'blk', 'minutes']
    if stat not in valid_stats:
        raise HTTPException(status_code=400, detail=f"Invalid stat. Choose from: {valid_stats}")
    
    player = get_player_by_name(db, player_name)
    
    # Get games for both seasons
    games_s1 = db.query(GameStats).join(Game).filter(
        GameStats.player_id == player.id,
        Game.season == season_1
    ).all()
    
    games_s2 = db.query(GameStats).join(Game).filter(
        GameStats.player_id == player.id,
        Game.season == season_2
    ).all()
    
    if not games_s1:
        raise HTTPException(status_code=404, detail=f"No data for {season_1} season")
    if not games_s2:
        raise HTTPException(status_code=404, detail=f"No data for {season_2} season")
    
    comparison = compare_season_stats(games_s1, games_s2, stat)
    
    # Calculate difference
    avg_1 = comparison["season_1"][f"avg_{stat}"]
    avg_2 = comparison["season_2"][f"avg_{stat}"]
    difference = round(avg_2 - avg_1, 2)
    percent_change = round((difference / avg_1) * 100, 1) if avg_1 > 0 else 0
    
    return {
        "player": player.full_name,
        "stat": stat,
        "comparison": comparison,
        "summary": {
            "difference": difference,
            "percent_change": percent_change,
            "trend": "increased" if difference > 0 else "decreased" if difference < 0 else "stayed_same"
        }
    }

@app.get("/analytics/player-stats")
async def get_player_stats(
    player_name: str = Query(..., description="Player name"),
    season: int = Query(2024, description="Season"),
    home_away: Optional[str] = Query(None, description="Filter: 'home' or 'away'"),
    opponent: Optional[str] = Query(None, description="Filter by opponent team abbreviation"),
    db: Session = Depends(get_db)
):
    """
    Get detailed player statistics with optional filters
    """
    player = get_player_by_name(db, player_name)
    
    # Build query
    query = db.query(GameStats).join(Game).filter(
        GameStats.player_id == player.id,
        Game.season == season
    )
    
    if home_away:
        is_home = home_away.lower() == "home"
        query = query.filter(GameStats.is_home == is_home)
    
    if opponent:
        # Join with teams to filter by opponent
        query = query.join(Team, or_(
            Game.home_team_id == Team.id,
            Game.visitor_team_id == Team.id
        )).filter(
            Team.abbreviation.ilike(f"%{opponent}%"),
            or_(
                and_(GameStats.is_home == True, Game.visitor_team_id == Team.id),
                and_(GameStats.is_home == False, Game.home_team_id == Team.id)
            )
        )
    
    games = query.all()
    
    if not games:
        return {"error": "No games found with specified filters"}
    
    # Calculate averages
    total_games = len(games)
    
    averages = {
        "games_played": total_games,
        "avg_points": round(sum(g.pts for g in games) / total_games, 1),
        "avg_assists": round(sum(g.ast for g in games) / total_games, 1),
        "avg_rebounds": round(sum(g.reb for g in games) / total_games, 1),
        "avg_steals": round(sum(g.stl for g in games) / total_games, 1),
        "avg_blocks": round(sum(g.blk for g in games) / total_games, 1),
        "avg_threes_made": round(sum(g.fg3m for g in games) / total_games, 1),
        "avg_threes_attempted": round(sum(g.fg3a for g in games) / total_games, 1),
        "avg_fga": round(sum(g.fga for g in games) / total_games, 1),
        "fg_pct": round(sum(g.fgm for g in games) / sum(g.fga for g in games) * 100, 1) if sum(g.fga for g in games) > 0 else 0,
        "three_pt_pct": round(sum(g.fg3m for g in games) / sum(g.fg3a for g in games) * 100, 1) if sum(g.fg3a for g in games) > 0 else 0
    }
    
    return {
        "player": player.full_name,
        "season": season,
        "filters": {
            "home_away": home_away,
            "opponent": opponent
        },
        "statistics": averages
    }

@app.post("/sync/daily")
async def trigger_daily_sync(background_tasks: BackgroundTasks):
    """Manually trigger daily data sync"""
    from sync_service import run_daily_sync
    
    background_tasks.add_task(run_daily_sync)
    
    return {
        "message": "Daily sync started in background",
        "status": "running"
    }

@app.post("/sync/initial-setup")
async def initial_data_setup(
    season: int = Query(2024, description="Season to sync"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD, defaults to today)"),
    db: Session = Depends(get_db)
):
    """
    Initial data setup - sync historical data for a season
    Run this once when first setting up the system
    """
    service = DataSyncService()
    
    start = datetime.fromisoformat(start_date).date()
    end = datetime.fromisoformat(end_date).date() if end_date else date.today()
    
    # Sync teams and players first
    await service.sync_teams(db)
    await service.sync_players(db)
    
    # Sync games
    games_synced = await service.sync_games_for_date_range(db, start, end, season)
    
    return {
        "message": "Initial setup completed",
        "season": season,
        "date_range": f"{start} to {end}",
        "games_synced": games_synced
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
