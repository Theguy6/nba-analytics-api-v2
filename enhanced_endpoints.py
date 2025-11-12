"""
Enhanced API Endpoints for GOAT Tier Features
Add these to your main.py
"""

from fastapi import FastAPI, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

# Import new models
# from database import SeasonAverages, TeamStandings, LeagueLeaders, PlayerInjury, BoxScore

# ========== SEASON AVERAGES ENDPOINTS ==========

@app.get("/analytics/season-averages/{player_name}")
async def get_season_averages(
    player_name: str,
    season: int = Query(2024, description="Season year"),
    db: Session = Depends(get_db)
):
    """
    Get season averages for a player (GOAT tier)
    Example: /analytics/season-averages/Stephen Curry?season=2024
    """
    player = get_player_by_name(db, player_name)
    
    avg = db.query(SeasonAverages).filter(
        SeasonAverages.player_id == player.id,
        SeasonAverages.season == season
    ).first()
    
    if not avg:
        raise HTTPException(status_code=404, detail=f"No season averages found for {player.full_name} in {season}")
    
    return {
        "player": player.full_name,
        "season": season,
        "games_played": avg.games_played,
        "averages": {
            "minutes": round(avg.minutes, 1) if avg.minutes else 0,
            "points": round(avg.pts, 1) if avg.pts else 0,
            "rebounds": round(avg.reb, 1) if avg.reb else 0,
            "assists": round(avg.ast, 1) if avg.ast else 0,
            "steals": round(avg.stl, 1) if avg.stl else 0,
            "blocks": round(avg.blk, 1) if avg.blk else 0,
            "fg_pct": round(avg.fg_pct * 100, 1) if avg.fg_pct else 0,
            "fg3_pct": round(avg.fg3_pct * 100, 1) if avg.fg3_pct else 0,
            "ft_pct": round(avg.ft_pct * 100, 1) if avg.ft_pct else 0,
        }
    }


@app.get("/analytics/compare-seasons/{player_name}")
async def compare_season_averages(
    player_name: str,
    season_1: int = Query(..., description="First season"),
    season_2: int = Query(..., description="Second season"),
    db: Session = Depends(get_db)
):
    """
    Compare a player's season averages across two seasons
    Example: /analytics/compare-seasons/LeBron James?season_1=2023&season_2=2024
    """
    player = get_player_by_name(db, player_name)
    
    avg_1 = db.query(SeasonAverages).filter(
        SeasonAverages.player_id == player.id,
        SeasonAverages.season == season_1
    ).first()
    
    avg_2 = db.query(SeasonAverages).filter(
        SeasonAverages.player_id == player.id,
        SeasonAverages.season == season_2
    ).first()
    
    if not avg_1 or not avg_2:
        raise HTTPException(status_code=404, detail="Season data not found")
    
    return {
        "player": player.full_name,
        "comparison": {
            season_1: {
                "games": avg_1.games_played,
                "ppg": round(avg_1.pts, 1) if avg_1.pts else 0,
                "rpg": round(avg_1.reb, 1) if avg_1.reb else 0,
                "apg": round(avg_1.ast, 1) if avg_1.ast else 0,
                "fg_pct": round(avg_1.fg_pct * 100, 1) if avg_1.fg_pct else 0,
            },
            season_2: {
                "games": avg_2.games_played,
                "ppg": round(avg_2.pts, 1) if avg_2.pts else 0,
                "rpg": round(avg_2.reb, 1) if avg_2.reb else 0,
                "apg": round(avg_2.ast, 1) if avg_2.ast else 0,
                "fg_pct": round(avg_2.fg_pct * 100, 1) if avg_2.fg_pct else 0,
            }
        },
        "differences": {
            "ppg": round((avg_2.pts or 0) - (avg_1.pts or 0), 1),
            "rpg": round((avg_2.reb or 0) - (avg_1.reb or 0), 1),
            "apg": round((avg_2.ast or 0) - (avg_1.ast or 0), 1),
        }
    }


# ========== TEAM STANDINGS ENDPOINTS ==========

@app.get("/standings")
async def get_standings(
    season: int = Query(2024, description="Season year"),
    conference: Optional[str] = Query(None, description="Filter by conference: 'East' or 'West'"),
    db: Session = Depends(get_db)
):
    """
    Get team standings (GOAT tier)
    Example: /standings?season=2024&conference=East
    """
    query = db.query(TeamStandings, Team).join(
        Team, TeamStandings.team_id == Team.id
    ).filter(TeamStandings.season == season)
    
    if conference:
        query = query.filter(Team.conference == conference)
    
    standings = query.order_by(TeamStandings.conference_rank).all()
    
    return {
        "season": season,
        "conference": conference or "All",
        "standings": [
            {
                "rank": standing.conference_rank,
                "team": team.full_name,
                "record": f"{standing.wins}-{standing.losses}",
                "win_pct": round(standing.win_pct, 3) if standing.win_pct else 0,
                "games_back": standing.games_back,
                "streak": standing.streak,
                "last_10": standing.last_10,
                "home": f"{standing.home_wins}-{standing.home_losses}",
                "away": f"{standing.away_wins}-{standing.away_losses}"
            }
            for standing, team in standings
        ]
    }


# ========== LEAGUE LEADERS ENDPOINTS ==========

@app.get("/leaders/{category}")
async def get_league_leaders(
    category: str,
    season: int = Query(2024, description="Season year"),
    limit: int = Query(10, description="Number of leaders to return"),
    db: Session = Depends(get_db)
):
    """
    Get league leaders in a category (GOAT tier)
    Categories: points, assists, rebounds, steals, blocks, fg_pct, ft_pct, fg3_pct
    Example: /leaders/points?season=2024&limit=10
    """
    valid_categories = ["points", "assists", "rebounds", "steals", "blocks", "fg_pct", "ft_pct", "fg3_pct"]
    
    if category not in valid_categories:
        raise HTTPException(status_code=400, detail=f"Invalid category. Choose from: {valid_categories}")
    
    leaders = db.query(LeagueLeaders, Player).join(
        Player, LeagueLeaders.player_id == Player.id
    ).filter(
        LeagueLeaders.season == season,
        LeagueLeaders.category == category
    ).order_by(LeagueLeaders.rank).limit(limit).all()
    
    return {
        "category": category,
        "season": season,
        "leaders": [
            {
                "rank": leader.rank,
                "player": player.full_name,
                "team": player.team_abbreviation,
                "value": round(leader.value, 1) if leader.value else 0
            }
            for leader, player in leaders
        ]
    }


@app.get("/leaders/player/{player_name}")
async def get_player_leader_stats(
    player_name: str,
    season: int = Query(2024, description="Season year"),
    db: Session = Depends(get_db)
):
    """
    Get all leader rankings for a specific player
    Example: /leaders/player/Stephen Curry?season=2024
    """
    player = get_player_by_name(db, player_name)
    
    rankings = db.query(LeagueLeaders).filter(
        LeagueLeaders.player_id == player.id,
        LeagueLeaders.season == season
    ).all()
    
    if not rankings:
        raise HTTPException(status_code=404, detail=f"No leader rankings found for {player.full_name}")
    
    return {
        "player": player.full_name,
        "season": season,
        "rankings": [
            {
                "category": rank.category,
                "rank": rank.rank,
                "value": round(rank.value, 1) if rank.value else 0
            }
            for rank in rankings
        ]
    }


# ========== INJURY REPORT ENDPOINTS ==========

@app.get("/injuries")
async def get_injury_report(
    status: Optional[str] = Query(None, description="Filter by status: 'out', 'questionable', 'day-to-day'"),
    team: Optional[str] = Query(None, description="Filter by team abbreviation"),
    db: Session = Depends(get_db)
):
    """
    Get current injury reports (GOAT tier)
    Example: /injuries?status=out
    """
    query = db.query(PlayerInjury, Player).join(
        Player, PlayerInjury.player_id == Player.id
    )
    
    if status:
        query = query.filter(PlayerInjury.status.ilike(f"%{status}%"))
    
    if team:
        query = query.filter(Player.team_abbreviation.ilike(f"%{team}%"))
    
    injuries = query.all()
    
    return {
        "total_injuries": len(injuries),
        "injuries": [
            {
                "player": player.full_name,
                "team": player.team_abbreviation,
                "injury_type": injury.injury_type,
                "status": injury.status,
                "description": injury.description,
                "date_updated": injury.date_updated.isoformat() if injury.date_updated else None,
                "expected_return": injury.expected_return.isoformat() if injury.expected_return else None
            }
            for injury, player in injuries
        ]
    }


@app.get("/injuries/team/{team_abbr}")
async def get_team_injuries(
    team_abbr: str,
    db: Session = Depends(get_db)
):
    """
    Get injuries for a specific team
    Example: /injuries/team/GSW
    """
    injuries = db.query(PlayerInjury, Player).join(
        Player, PlayerInjury.player_id == Player.id
    ).filter(
        Player.team_abbreviation.ilike(f"%{team_abbr}%")
    ).all()
    
    if not injuries:
        return {
            "team": team_abbr,
            "injuries": [],
            "message": "No current injuries"
        }
    
    return {
        "team": team_abbr,
        "total_injuries": len(injuries),
        "injuries": [
            {
                "player": player.full_name,
                "injury_type": injury.injury_type,
                "status": injury.status,
                "expected_return": injury.expected_return.isoformat() if injury.expected_return else "Unknown"
            }
            for injury, player in injuries
        ]
    }


# ========== ENHANCED SYNC ENDPOINTS ==========

@app.post("/sync/goat-daily")
async def trigger_goat_daily_sync(background_tasks: BackgroundTasks):
    """Trigger enhanced daily sync with all GOAT tier features"""
    from sync_service_enhanced import EnhancedDataSyncService
    
    async def run_sync():
        service = EnhancedDataSyncService()
        await service.perform_enhanced_daily_sync()
    
    background_tasks.add_task(run_sync)
    
    return {
        "message": "Enhanced GOAT tier daily sync started",
        "features": [
            "Teams", "Active Players", "Games", "Stats",
            "Season Averages", "Team Standings", "League Leaders", "Injury Reports"
        ]
    }


@app.post("/sync/season-averages")
async def sync_season_averages_endpoint(
    season: int = Query(2024, description="Season to sync"),
    db: Session = Depends(get_db)
):
    """Manually sync season averages"""
    from sync_service_enhanced import EnhancedDataSyncService
    
    service = EnhancedDataSyncService()
    count = await service.sync_season_averages(db, season)
    
    return {
        "message": "Season averages synced",
        "season": season,
        "players_synced": count
    }
