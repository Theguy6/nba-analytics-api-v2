"""
NBA Analytics Backend API - COMPLETE VERSION
With PostgreSQL database, daily sync, comprehensive metrics, and GOAT tier features
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from collections import defaultdict

from database import (
    Player, Team, Game, GameStats, MetricCache, SeasonAverages, 
    TeamStandings, HeadToHead, PerformanceStreak
)
from db_session import init_db, get_db
from sync_service import DataSyncService

app = FastAPI(title="NBA Analytics API - GOAT Edition", version="3.0.0")

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
    print("✅ Database initialized - GOAT Edition")

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
        player = db.query(Player).filter(
            or_(
                Player.first_name.ilike(f"%{player_name}%"),
                Player.last_name.ilike(f"%{player_name}%")
            )
        ).first()
    else:
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
    """Calculate rolling window metric for any stat"""
    if len(games) < window_size:
        return {
            "error": f"Not enough games. Need {window_size}, have {len(games)}",
            "games_played": len(games)
        }
    
    sorted_games = sorted(games, key=lambda x: x.game.date)
    
    results = {
        "total_games": len(sorted_games),
        "windows_analyzed": [],
        "overall_rate": 0.0,
        "home_away_splits": {"home": {"games": 0, "threshold_met": 0}, "away": {"games": 0, "threshold_met": 0}},
        "opponent_breakdown": defaultdict(lambda: {"games": 0, "threshold_met": 0})
    }
    
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
            
            if is_home:
                opponent_id = game_stat.game.visitor_team_id
                opponent = game_stat.game.visitor_team
            else:
                opponent_id = game_stat.game.home_team_id
                opponent = game_stat.game.home_team
            
            opponent_abbr = opponent.abbreviation if opponent else "UNK"
            met_threshold = value >= threshold
            
            location = "home" if is_home else "away"
            results["home_away_splits"][location]["games"] += 1
            if met_threshold:
                results["home_away_splits"][location]["threshold_met"] += 1
            
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
    
    total_games_in_windows = num_windows * window_size
    results["overall_rate"] = round((total_threshold_met / total_games_in_windows) * 100, 1)
    
    for location in ["home", "away"]:
        split = results["home_away_splits"][location]
        if split["games"] > 0:
            split["rate"] = round((split["threshold_met"] / split["games"]) * 100, 1)
    
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

# === CORE ENDPOINTS ===

@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "healthy",
        "service": "NBA Analytics API - GOAT Edition",
        "version": "3.0.0",
        "features": [
            "PostgreSQL database",
            "Daily auto-sync",
            "Multiple metrics (3PT, assists, steals, etc.)",
            "Season comparisons",
            "Home/away splits",
            "🐐 GOAT: Season averages",
            "🐐 GOAT: Team standings",
            "🐐 GOAT: Head-to-head matchups",
            "🐐 GOAT: Performance streaks",
            "🐐 GOAT: Player comparisons"
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
    metric: str = Query(..., description="Metric: 'threes', 'assists', 'steals', 'points', 'rebounds', 'blocks'"),
    threshold: int = Query(..., description="Minimum value to meet threshold"),
    season: int = Query(2024, description="NBA season year"),
    window_size: int = Query(10, description="Game window size"),
    db: Session = Depends(get_db)
):
    """Universal metric rate analyzer"""
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
        raise HTTPException(status_code=400, detail=f"Unknown metric: {metric}")
    
    player = get_player_by_name(db, player_name)
    
    games = db.query(GameStats).join(Game).filter(
        GameStats.player_id == player.id,
        Game.season == season
    ).all()
    
    if not games:
        raise HTTPException(status_code=404, detail=f"No games found for {player.full_name} in {season}")
    
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
    stat: str = Query(..., description="Stat: 'fga', 'fg3a', 'minutes', 'pts', 'ast'"),
    season_1: int = Query(2023, description="First season"),
    season_2: int = Query(2024, description="Second season"),
    db: Session = Depends(get_db)
):
    """Compare player stats across two seasons"""
    valid_stats = ['fga', 'fg3a', 'fgm', 'fg3m', 'pts', 'ast', 'reb', 'stl', 'blk', 'minutes']
    if stat not in valid_stats:
        raise HTTPException(status_code=400, detail=f"Invalid stat. Choose from: {valid_stats}")
    
    player = get_player_by_name(db, player_name)
    
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
    opponent: Optional[str] = Query(None, description="Filter by opponent abbreviation"),
    db: Session = Depends(get_db)
):
    """Get detailed player statistics with filters"""
    player = get_player_by_name(db, player_name)
    
    query = db.query(GameStats).join(Game).filter(
        GameStats.player_id == player.id,
        Game.season == season
    )
    
    if home_away:
        is_home = home_away.lower() == "home"
        query = query.filter(GameStats.is_home == is_home)
    
    if opponent:
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

# === GOAT TIER ENDPOINTS ===

@app.get("/analytics/season-averages/{player_name}")
async def get_season_averages(
    player_name: str,
    season: int = Query(2024, description="Season"),
    db: Session = Depends(get_db)
):
    """🐐 Get pre-calculated season averages for a player"""
    player = get_player_by_name(db, player_name)
    
    averages = db.query(SeasonAverages).filter(
        SeasonAverages.player_id == player.id,
        SeasonAverages.season == season
    ).first()
    
    if not averages:
        raise HTTPException(status_code=404, detail=f"No season averages found for {player.full_name} in {season}")
    
    return {
        "player": player.full_name,
        "season": season,
        "games_played": averages.games_played,
        "scoring": {
            "ppg": round(averages.avg_pts, 1),
            "fg_pct": round(averages.avg_fg_pct * 100, 1) if averages.avg_fg_pct else 0,
            "fg3_pct": round(averages.avg_fg3_pct * 100, 1) if averages.avg_fg3_pct else 0,
            "ft_pct": round(averages.avg_ft_pct * 100, 1) if averages.avg_ft_pct else 0,
            "fga": round(averages.avg_fga, 1),
            "fg3a": round(averages.avg_fg3a, 1)
        },
        "other": {
            "apg": round(averages.avg_ast, 1),
            "rpg": round(averages.avg_reb, 1),
            "spg": round(averages.avg_stl, 1),
            "bpg": round(averages.avg_blk, 1),
            "topg": round(averages.avg_turnover, 1)
        },
        "efficiency": {
            "ts_pct": round(averages.true_shooting_pct * 100, 1) if averages.true_shooting_pct else 0,
            "efg_pct": round(averages.effective_fg_pct * 100, 1) if averages.effective_fg_pct else 0,
            "usage_rate": round(averages.usage_rate * 100, 1) if averages.usage_rate else 0
        },
        "last_updated": averages.last_updated.isoformat()
    }

@app.get("/analytics/team-standings")
async def get_team_standings(
    season: int = Query(2024, description="Season"),
    conference: Optional[str] = Query(None, description="East or West"),
    db: Session = Depends(get_db)
):
    """🐐 Get team standings for a season"""
    query = db.query(TeamStandings).join(Team).filter(
        TeamStandings.season == season
    )
    
    if conference:
        query = query.filter(Team.conference.ilike(f"%{conference}%"))
    
    standings = query.order_by(desc(TeamStandings.win_pct)).all()
    
    if not standings:
        raise HTTPException(status_code=404, detail=f"No standings found for {season} season")
    
    results = []
    for idx, standing in enumerate(standings, 1):
        results.append({
            "rank": idx,
            "team": standing.team.full_name,
            "abbreviation": standing.team.abbreviation,
            "wins": standing.wins,
            "losses": standing.losses,
            "win_pct": round(standing.win_pct * 100, 1),
            "home_record": f"{standing.home_wins}-{standing.home_losses}",
            "away_record": f"{standing.away_wins}-{standing.away_losses}",
            "streak": standing.current_streak,
            "ppg": round(standing.avg_points_scored, 1),
            "opp_ppg": round(standing.avg_points_allowed, 1),
            "conference_rank": standing.conference_rank,
            "division_rank": standing.division_rank
        })
    
    return {
        "season": season,
        "conference": conference or "All",
        "standings": results
    }

@app.get("/analytics/head-to-head")
async def get_head_to_head(
    team1: str = Query(..., description="First team abbreviation"),
    team2: str = Query(..., description="Second team abbreviation"),
    season: int = Query(2024, description="Season"),
    db: Session = Depends(get_db)
):
    """🐐 Get head-to-head matchup data"""
    t1 = db.query(Team).filter(Team.abbreviation.ilike(team1)).first()
    t2 = db.query(Team).filter(Team.abbreviation.ilike(team2)).first()
    
    if not t1 or not t2:
        raise HTTPException(status_code=404, detail="One or both teams not found")
    
    h2h = db.query(HeadToHead).filter(
        or_(
            and_(HeadToHead.team_1_id == t1.id, HeadToHead.team_2_id == t2.id),
            and_(HeadToHead.team_1_id == t2.id, HeadToHead.team_2_id == t1.id)
        ),
        HeadToHead.season == season
    ).first()
    
    if not h2h:
        raise HTTPException(status_code=404, detail="No head-to-head data found")
    
    # Determine which team is which in the stored data
    if h2h.team_1_id == t1.id:
        team1_wins = h2h.team_1_wins
        team2_wins = h2h.team_2_wins
        team1_avg = h2h.team_1_avg_score
        team2_avg = h2h.team_2_avg_score
    else:
        team1_wins = h2h.team_2_wins
        team2_wins = h2h.team_1_wins
        team1_avg = h2h.team_2_avg_score
        team2_avg = h2h.team_1_avg_score
    
    return {
        "season": season,
        "matchup": f"{t1.full_name} vs {t2.full_name}",
        "series": {
            t1.abbreviation: team1_wins,
            t2.abbreviation: team2_wins
        },
        "scoring_avg": {
            t1.abbreviation: round(team1_avg, 1),
            t2.abbreviation: round(team2_avg, 1)
        },
        "last_game": {
            "date": h2h.last_game_date.isoformat() if h2h.last_game_date else None,
            "score": h2h.last_game_score
        }
    }

@app.get("/analytics/player-streaks/{player_name}")
async def get_player_streaks(
    player_name: str,
    season: int = Query(2024, description="Season"),
    active_only: bool = Query(True, description="Show only active streaks"),
    db: Session = Depends(get_db)
):
    """🐐 Get hot/cold performance streaks for a player"""
    player = get_player_by_name(db, player_name)
    
    query = db.query(PerformanceStreak).filter(
        PerformanceStreak.player_id == player.id,
        PerformanceStreak.season == season
    )
    
    if active_only:
        query = query.filter(PerformanceStreak.is_active == True)
    
    streaks = query.all()
    
    if not streaks:
        return {
            "player": player.full_name,
            "season": season,
            "message": "No active streaks found"
        }
    
    results = []
    for streak in streaks:
        results.append({
            "metric": streak.metric,
            "type": streak.streak_type,
            "current_streak": streak.current_streak,
            "streak_start": streak.streak_start_date.isoformat(),
            "best_performance": round(streak.best_performance, 1),
            "avg_performance": round(streak.avg_performance, 1),
            "threshold": round(streak.threshold, 1),
            "is_active": streak.is_active
        })
    
    return {
        "player": player.full_name,
        "season": season,
        "streaks": results
    }

@app.get("/analytics/compare-players")
async def compare_players(
    player1: str = Query(..., description="First player name"),
    player2: str = Query(..., description="Second player name"),
    season: int = Query(2024, description="Season"),
    db: Session = Depends(get_db)
):
    """🐐 Compare two players' season averages"""
    p1 = get_player_by_name(db, player1)
    p2 = get_player_by_name(db, player2)
    
    avgs1 = db.query(SeasonAverages).filter(
        SeasonAverages.player_id == p1.id,
        SeasonAverages.season == season
    ).first()
    
    avgs2 = db.query(SeasonAverages).filter(
        SeasonAverages.player_id == p2.id,
        SeasonAverages.season == season
    ).first()
    
    if not avgs1 or not avgs2:
        raise HTTPException(status_code=404, detail="Season averages not found for one or both players")
    
    comparison = {
        "season": season,
        "player1": {
            "name": p1.full_name,
            "ppg": round(avgs1.avg_pts, 1),
            "apg": round(avgs1.avg_ast, 1),
            "rpg": round(avgs1.avg_reb, 1),
            "fg_pct": round(avgs1.avg_fg_pct * 100, 1) if avgs1.avg_fg_pct else 0,
            "fg3_pct": round(avgs1.avg_fg3_pct * 100, 1) if avgs1.avg_fg3_pct else 0,
            "ts_pct": round(avgs1.true_shooting_pct * 100, 1) if avgs1.true_shooting_pct else 0
        },
        "player2": {
            "name": p2.full_name,
            "ppg": round(avgs2.avg_pts, 1),
            "apg": round(avgs2.avg_ast, 1),
            "rpg": round(avgs2.avg_reb, 1),
            "fg_pct": round(avgs2.avg_fg_pct * 100, 1) if avgs2.avg_fg_pct else 0,
            "fg3_pct": round(avgs2.avg_fg3_pct * 100, 1) if avgs2.avg_fg3_pct else 0,
            "ts_pct": round(avgs2.true_shooting_pct * 100, 1) if avgs2.true_shooting_pct else 0
        },
        "winner": {}
    }
    
    # Determine winners
    comparison["winner"]["scoring"] = p1.full_name if avgs1.avg_pts > avgs2.avg_pts else p2.full_name
    comparison["winner"]["assists"] = p1.full_name if avgs1.avg_ast > avgs2.avg_ast else p2.full_name
    comparison["winner"]["rebounds"] = p1.full_name if avgs1.avg_reb > avgs2.avg_reb else p2.full_name
    comparison["winner"]["efficiency"] = p1.full_name if (avgs1.true_shooting_pct or 0) > (avgs2.true_shooting_pct or 0) else p2.full_name
    
    return comparison

# === SYNC ENDPOINTS ===

@app.post("/sync/daily")
async def trigger_daily_sync(background_tasks: BackgroundTasks):
    """Manually trigger daily data sync"""
    from sync_service import run_daily_sync
    
    background_tasks.add_task(run_daily_sync)
    
    return {
        "message": "Daily sync started in background",
        "status": "running"
    }

@app.post("/sync/goat-daily")
async def trigger_goat_sync(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """🐐 Trigger daily GOAT tier data sync"""
    service = DataSyncService()
    
    async def run_goat_sync():
        season = 2024
        await service.sync_season_averages(db, season)
        await service.sync_team_standings(db, season)
        await service.sync_head_to_head(db, season)
        await service.detect_performance_streaks(db, season)
        print("✅ GOAT tier sync completed!")
    
    background_tasks.add_task(run_goat_sync)
    
    return {
        "message": "GOAT tier sync started",
        "status": "running",
        "syncing": ["season_averages", "team_standings", "head_to_head", "performance_streaks"]
    }

@app.post("/sync/initial-setup")
async def initial_data_setup(
    season: int = Query(2024, description="Season to sync"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """Initial data setup - sync historical data"""
    try:
        service = DataSyncService()
        
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date() if end_date else date.today()
        
        print(f"🚀 Starting initial setup for {season} season")
        print(f"📅 Date range: {start} to {end}")
        
        # Sync teams and players first
        try:
            teams_count = await service.sync_teams(db)
            print(f"✅ Synced {teams_count} teams")
        except Exception as e:
            print(f"⚠️ Error syncing teams (may already exist): {e}")
        
        try:
            players_count = await service.sync_players(db)
            print(f"✅ Synced {players_count} players")
        except Exception as e:
            print(f"⚠️ Error syncing players (may already exist): {e}")
        
        # Sync games
        games_synced = await service.sync_games_for_date_range(db, start, end, season)
        
        return {
            "status": "success",
            "message": "Initial setup completed",
            "season": season,
            "date_range": f"{start} to {end}",
            "games_synced": games_synced
        }
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Initial setup failed: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Setup failed: {str(e)}")

@app.get("/sync/status")
async def get_sync_status(db: Session = Depends(get_db)):
    """Get recent sync status"""
    from database import SyncLog
    
    recent_syncs = db.query(SyncLog).order_by(desc(SyncLog.sync_date)).limit(10).all()
    
    return {
        "recent_syncs": [
            {
                "date": sync.sync_date.isoformat(),
                "season": sync.season,
                "games_synced": sync.games_synced,
                "status": sync.status,
                "error": sync.error_message
            }
            for sync in recent_syncs
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
