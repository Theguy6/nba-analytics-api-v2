"""
Data Synchronization Service - COMPLETE VERSION
Fetches data from Balldontlie API and stores in database
Includes GOAT tier sync functions for season averages, standings, etc.
"""

import httpx
import asyncio
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
import os
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from collections import defaultdict

from database import (
    Player, Team, Game, GameStats, SyncLog, 
    SeasonAverages, TeamStandings, HeadToHead, PerformanceStreak
)
from db_session import get_db_context

BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE_API_KEY")
BALLDONTLIE_BASE_URL = "https://api.balldontlie.io/v1"


class DataSyncService:
    """Service for syncing NBA data from Balldontlie API to database"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or BALLDONTLIE_API_KEY
        self.headers = {"Authorization": self.api_key}
    
    async def fetch_api(self, endpoint: str, params: Dict = None) -> Dict:
        """Fetch data from Balldontlie API"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{BALLDONTLIE_BASE_URL}/{endpoint}",
                headers=self.headers,
                params=params or {}
            )
            response.raise_for_status()
            return response.json()
    
    # ========================================================================
    # CORE SYNC FUNCTIONS
    # ========================================================================
    
    async def sync_teams(self, db: Session) -> int:
        """Sync all NBA teams"""
        print("🏀 Syncing teams...")
        
        data = await self.fetch_api("teams")
        teams_data = data.get("data", [])
        
        synced = 0
        for team_data in teams_data:
            team = db.query(Team).filter(Team.id == team_data["id"]).first()
            
            if not team:
                team = Team(
                    id=team_data["id"],
                    abbreviation=team_data["abbreviation"],
                    city=team_data.get("city"),
                    conference=team_data.get("conference"),
                    division=team_data.get("division"),
                    full_name=team_data.get("full_name"),
                    name=team_data.get("name")
                )
                db.add(team)
                synced += 1
            else:
                team.abbreviation = team_data["abbreviation"]
                team.city = team_data.get("city")
                team.conference = team_data.get("conference")
                team.division = team_data.get("division")
                team.full_name = team_data.get("full_name")
                team.name = team_data.get("name")
        
        db.commit()
        print(f"✅ Teams synced: {synced} new, {len(teams_data) - synced} updated")
        return len(teams_data)
    
    async def sync_players(self, db: Session) -> int:
        """Sync all active NBA players"""
        print("👥 Syncing players...")
        
        all_players = []
        page = 1
        
        while True:
            data = await self.fetch_api("players", {"per_page": 100, "page": page})
            players_data = data.get("data", [])
            
            if not players_data:
                break
            
            all_players.extend(players_data)
            
            if len(players_data) < 100:
                break
            
            page += 1
            await asyncio.sleep(0.1)
        
        synced = 0
        for player_data in all_players:
            player = db.query(Player).filter(Player.id == player_data["id"]).first()
            
            team_data = player_data.get("team", {})
            
            if not player:
                player = Player(
                    id=player_data["id"],
                    first_name=player_data["first_name"],
                    last_name=player_data["last_name"],
                    position=player_data.get("position"),
                    team_id=team_data.get("id") if team_data else None,
                    team_name=team_data.get("full_name") if team_data else None,
                    team_abbreviation=team_data.get("abbreviation") if team_data else None
                )
                db.add(player)
                synced += 1
            else:
                player.first_name = player_data["first_name"]
                player.last_name = player_data["last_name"]
                player.position = player_data.get("position")
                player.team_id = team_data.get("id") if team_data else None
                player.team_name = team_data.get("full_name") if team_data else None
                player.team_abbreviation = team_data.get("abbreviation") if team_data else None
        
        db.commit()
        print(f"✅ Players synced: {synced} new, {len(all_players) - synced} updated")
        return len(all_players)
    
    async def sync_games_for_date_range(
        self, 
        db: Session, 
        start_date: date, 
        end_date: date,
        season: int
    ) -> int:
        """Sync games and stats for a date range"""
        print(f"📅 Syncing games from {start_date} to {end_date}...")
        
        all_stats = []
        current_date = start_date
        
        while current_date <= end_date:
            page = 1
            while True:
                params = {
                    "dates[]": current_date.isoformat(),
                    "per_page": 100,
                    "page": page
                }
                
                try:
                    data = await self.fetch_api("stats", params)
                    stats_data = data.get("data", [])
                    
                    if not stats_data:
                        break
                    
                    all_stats.extend(stats_data)
                    
                    if len(stats_data) < 100:
                        break
                    
                    page += 1
                    await asyncio.sleep(0.1)
                
                except Exception as e:
                    print(f"⚠️  Error fetching stats for {current_date}: {e}")
                    break
            
            current_date += timedelta(days=1)
            await asyncio.sleep(0.1)
        
        games_synced = 0
        stats_synced = 0
        
        for stat in all_stats:
            game_data = stat.get("game", {})
            player_data = stat.get("player", {})
            team_data = stat.get("team", {})
            
            game = db.query(Game).filter(Game.id == game_data["id"]).first()
            if not game:
                game = Game(
                    id=game_data["id"],
                    date=datetime.fromisoformat(game_data["date"].replace('Z', '+00:00')).date(),
                    season=game_data.get("season", season),
                    status=game_data.get("status"),
                    home_team_id=game_data.get("home_team_id"),
                    visitor_team_id=game_data.get("visitor_team_id"),
                    home_team_score=game_data.get("home_team_score"),
                    visitor_team_score=game_data.get("visitor_team_score")
                )
                db.add(game)
                games_synced += 1
            
            existing_stat = db.query(GameStats).filter(
                GameStats.player_id == player_data["id"],
                GameStats.game_id == game_data["id"]
            ).first()
            
            if not existing_stat:
                game_stat = GameStats(
                    player_id=player_data["id"],
                    game_id=game_data["id"],
                    team_id=team_data.get("id"),
                    is_home=game_data.get("home_team_id") == team_data.get("id"),
                    minutes=stat.get("min"),
                    fgm=stat.get("fgm", 0),
                    fga=stat.get("fga", 0),
                    fg_pct=stat.get("fg_pct"),
                    fg3m=stat.get("fg3m", 0),
                    fg3a=stat.get("fg3a", 0),
                    fg3_pct=stat.get("fg3_pct"),
                    ftm=stat.get("ftm", 0),
                    fta=stat.get("fta", 0),
                    ft_pct=stat.get("ft_pct"),
                    oreb=stat.get("oreb", 0),
                    dreb=stat.get("dreb", 0),
                    reb=stat.get("reb", 0),
                    ast=stat.get("ast", 0),
                    stl=stat.get("stl", 0),
                    blk=stat.get("blk", 0),
                    turnover=stat.get("turnover", 0),
                    pf=stat.get("pf", 0),
                    pts=stat.get("pts", 0)
                )
                db.add(game_stat)
                stats_synced += 1
        
        db.commit()
        print(f"✅ Synced {games_synced} games, {stats_synced} player stats")
        return games_synced
    
    # ========================================================================
    # GOAT TIER SYNC FUNCTIONS
    # ========================================================================
    
    async def sync_season_averages(self, db: Session, season: int) -> int:
        """🐐 Calculate and store season averages for all active players"""
        print(f"🐐 Calculating season averages for {season}...")
        
        # Get all players who played this season
        player_stats = db.query(
            GameStats.player_id,
            func.count(GameStats.id).label('games_played'),
            func.avg(GameStats.pts).label('avg_pts'),
            func.avg(GameStats.ast).label('avg_ast'),
            func.avg(GameStats.reb).label('avg_reb'),
            func.avg(GameStats.stl).label('avg_stl'),
            func.avg(GameStats.blk).label('avg_blk'),
            func.avg(GameStats.fgm).label('avg_fgm'),
            func.avg(GameStats.fga).label('avg_fga'),
            func.avg(GameStats.fg3m).label('avg_fg3m'),
            func.avg(GameStats.fg3a).label('avg_fg3a'),
            func.avg(GameStats.ftm).label('avg_ftm'),
            func.avg(GameStats.fta).label('avg_fta'),
            func.avg(GameStats.oreb).label('avg_oreb'),
            func.avg(GameStats.dreb).label('avg_dreb'),
            func.avg(GameStats.turnover).label('avg_turnover'),
            func.avg(GameStats.pf).label('avg_pf'),
            func.sum(GameStats.fgm).label('total_fgm'),
            func.sum(GameStats.fga).label('total_fga'),
            func.sum(GameStats.fg3m).label('total_fg3m'),
            func.sum(GameStats.fg3a).label('total_fg3a'),
            func.sum(GameStats.ftm).label('total_ftm'),
            func.sum(GameStats.fta).label('total_fta'),
            func.sum(GameStats.pts).label('total_pts')
        ).join(Game).filter(
            Game.season == season
        ).group_by(GameStats.player_id).all()
        
        synced = 0
        for stats in player_stats:
            if stats.games_played < 5:  # Skip players with very few games
                continue
            
            # Calculate shooting percentages
            fg_pct = stats.total_fgm / stats.total_fga if stats.total_fga > 0 else 0
            fg3_pct = stats.total_fg3m / stats.total_fg3a if stats.total_fg3a > 0 else 0
            ft_pct = stats.total_ftm / stats.total_fta if stats.total_fta > 0 else 0
            
            # Calculate efficiency metrics
            # True Shooting % = PTS / (2 * (FGA + 0.44 * FTA))
            ts_denominator = 2 * (stats.total_fga + 0.44 * stats.total_fta)
            true_shooting = stats.total_pts / ts_denominator if ts_denominator > 0 else 0
            
            # Effective FG% = (FGM + 0.5 * 3PM) / FGA
            effective_fg = (stats.total_fgm + 0.5 * stats.total_fg3m) / stats.total_fga if stats.total_fga > 0 else 0
            
            # Check if averages already exist
            existing = db.query(SeasonAverages).filter(
                SeasonAverages.player_id == stats.player_id,
                SeasonAverages.season == season
            ).first()
            
            if existing:
                # Update existing
                existing.games_played = stats.games_played
                existing.avg_pts = stats.avg_pts
                existing.avg_ast = stats.avg_ast
                existing.avg_reb = stats.avg_reb
                existing.avg_stl = stats.avg_stl
                existing.avg_blk = stats.avg_blk
                existing.avg_fgm = stats.avg_fgm
                existing.avg_fga = stats.avg_fga
                existing.avg_fg_pct = fg_pct
                existing.avg_fg3m = stats.avg_fg3m
                existing.avg_fg3a = stats.avg_fg3a
                existing.avg_fg3_pct = fg3_pct
                existing.avg_ftm = stats.avg_ftm
                existing.avg_fta = stats.avg_fta
                existing.avg_ft_pct = ft_pct
                existing.avg_oreb = stats.avg_oreb
                existing.avg_dreb = stats.avg_dreb
                existing.avg_turnover = stats.avg_turnover
                existing.avg_pf = stats.avg_pf
                existing.true_shooting_pct = true_shooting
                existing.effective_fg_pct = effective_fg
                existing.last_updated = datetime.utcnow()
            else:
                # Create new
                season_avg = SeasonAverages(
                    player_id=stats.player_id,
                    season=season,
                    games_played=stats.games_played,
                    avg_pts=stats.avg_pts,
                    avg_ast=stats.avg_ast,
                    avg_reb=stats.avg_reb,
                    avg_stl=stats.avg_stl,
                    avg_blk=stats.avg_blk,
                    avg_fgm=stats.avg_fgm,
                    avg_fga=stats.avg_fga,
                    avg_fg_pct=fg_pct,
                    avg_fg3m=stats.avg_fg3m,
                    avg_fg3a=stats.avg_fg3a,
                    avg_fg3_pct=fg3_pct,
                    avg_ftm=stats.avg_ftm,
                    avg_fta=stats.avg_fta,
                    avg_ft_pct=ft_pct,
                    avg_oreb=stats.avg_oreb,
                    avg_dreb=stats.avg_dreb,
                    avg_turnover=stats.avg_turnover,
                    avg_pf=stats.avg_pf,
                    true_shooting_pct=true_shooting,
                    effective_fg_pct=effective_fg
                )
                db.add(season_avg)
            
            synced += 1
        
        db.commit()
        print(f"✅ Season averages synced for {synced} players")
        return synced
    
    async def sync_team_standings(self, db: Session, season: int) -> int:
        """🐐 Calculate and store team standings"""
        print(f"🐐 Calculating team standings for {season}...")
        
        teams = db.query(Team).all()
        synced = 0
        
        for team in teams:
            # Get all games for this team
            home_games = db.query(Game).filter(
                Game.home_team_id == team.id,
                Game.season == season,
                Game.home_team_score != None  # Only completed games
            ).all()
            
            away_games = db.query(Game).filter(
                Game.visitor_team_id == team.id,
                Game.season == season,
                Game.visitor_team_score != None
            ).all()
            
            # Calculate records
            home_wins = sum(1 for g in home_games if g.home_team_score > g.visitor_team_score)
            home_losses = len(home_games) - home_wins
            away_wins = sum(1 for g in away_games if g.visitor_team_score > g.home_team_score)
            away_losses = len(away_games) - away_wins
            
            total_wins = home_wins + away_wins
            total_losses = home_losses + away_losses
            total_games = total_wins + total_losses
            
            if total_games == 0:
                continue
            
            win_pct = total_wins / total_games
            
            # Calculate scoring
            home_points = [g.home_team_score for g in home_games]
            away_points = [g.visitor_team_score for g in away_games]
            all_points_scored = home_points + away_points
            
            home_points_allowed = [g.visitor_team_score for g in home_games]
            away_points_allowed = [g.home_team_score for g in away_games]
            all_points_allowed = home_points_allowed + away_points_allowed
            
            avg_scored = sum(all_points_scored) / len(all_points_scored) if all_points_scored else 0
            avg_allowed = sum(all_points_allowed) / len(all_points_allowed) if all_points_allowed else 0
            
            # Determine current streak
            all_games_chronological = sorted(
                home_games + away_games,
                key=lambda g: g.date,
                reverse=True
            )
            
            current_streak = ""
            if all_games_chronological:
                last_game = all_games_chronological[0]
                is_win = (
                    (last_game.home_team_id == team.id and last_game.home_team_score > last_game.visitor_team_score) or
                    (last_game.visitor_team_id == team.id and last_game.visitor_team_score > last_game.home_team_score)
                )
                
                streak_count = 0
                for game in all_games_chronological:
                    game_is_win = (
                        (game.home_team_id == team.id and game.home_team_score > game.visitor_team_score) or
                        (game.visitor_team_id == team.id and game.visitor_team_score > game.home_team_score)
                    )
                    
                    if game_is_win == is_win:
                        streak_count += 1
                    else:
                        break
                
                current_streak = f"{'W' if is_win else 'L'}{streak_count}"
            
            # Update or create standings
            existing = db.query(TeamStandings).filter(
                TeamStandings.team_id == team.id,
                TeamStandings.season == season
            ).first()
            
            if existing:
                existing.wins = total_wins
                existing.losses = total_losses
                existing.win_pct = win_pct
                existing.home_wins = home_wins
                existing.home_losses = home_losses
                existing.away_wins = away_wins
                existing.away_losses = away_losses
                existing.current_streak = current_streak
                existing.avg_points_scored = avg_scored
                existing.avg_points_allowed = avg_allowed
                existing.last_updated = datetime.utcnow()
            else:
                standing = TeamStandings(
                    team_id=team.id,
                    season=season,
                    wins=total_wins,
                    losses=total_losses,
                    win_pct=win_pct,
                    home_wins=home_wins,
                    home_losses=home_losses,
                    away_wins=away_wins,
                    away_losses=away_losses,
                    current_streak=current_streak,
                    avg_points_scored=avg_scored,
                    avg_points_allowed=avg_allowed
                )
                db.add(standing)
            
            synced += 1
        
        db.commit()
        print(f"✅ Team standings synced for {synced} teams")
        return synced
    
    async def sync_head_to_head(self, db: Session, season: int) -> int:
        """🐐 Calculate head-to-head matchup records"""
        print(f"🐐 Calculating head-to-head matchups for {season}...")
        
        # Get all completed games
        games = db.query(Game).filter(
            Game.season == season,
            Game.home_team_score != None
        ).all()
        
        # Build matchup records
        matchups = defaultdict(lambda: {
            "team1_wins": 0,
            "team2_wins": 0,
            "team1_scores": [],
            "team2_scores": [],
            "last_game": None,
            "last_winner": None,
            "last_score": ""
        })
        
        for game in games:
            # Create consistent key (lower ID first)
            key = tuple(sorted([game.home_team_id, game.visitor_team_id]))
            matchup = matchups[key]
            
            # Determine winner
            home_won = game.home_team_score > game.visitor_team_score
            
            # Update matchup stats
            if key[0] == game.home_team_id:
                if home_won:
                    matchup["team1_wins"] += 1
                else:
                    matchup["team2_wins"] += 1
                matchup["team1_scores"].append(game.home_team_score)
                matchup["team2_scores"].append(game.visitor_team_score)
            else:
                if home_won:
                    matchup["team2_wins"] += 1
                else:
                    matchup["team1_wins"] += 1
                matchup["team2_scores"].append(game.home_team_score)
                matchup["team1_scores"].append(game.visitor_team_score)
            
            # Track last game
            if matchup["last_game"] is None or game.date > matchup["last_game"]:
                matchup["last_game"] = game.date
                matchup["last_winner"] = game.home_team_id if home_won else game.visitor_team_id
                matchup["last_score"] = f"{game.home_team_score}-{game.visitor_team_score}"
        
        # Store in database
        synced = 0
        for (team1_id, team2_id), data in matchups.items():
            team1_avg = sum(data["team1_scores"]) / len(data["team1_scores"]) if data["team1_scores"] else 0
            team2_avg = sum(data["team2_scores"]) / len(data["team2_scores"]) if data["team2_scores"] else 0
            
            existing = db.query(HeadToHead).filter(
                or_(
                    and_(HeadToHead.team_1_id == team1_id, HeadToHead.team_2_id == team2_id),
                    and_(HeadToHead.team_1_id == team2_id, HeadToHead.team_2_id == team1_id)
                ),
                HeadToHead.season == season
            ).first()
            
            if existing:
                existing.team_1_wins = data["team1_wins"]
                existing.team_2_wins = data["team2_wins"]
                existing.team_1_avg_score = team1_avg
                existing.team_2_avg_score = team2_avg
                existing.last_game_date = data["last_game"]
                existing.last_game_winner = data["last_winner"]
                existing.last_game_score = data["last_score"]
                existing.last_updated = datetime.utcnow()
            else:
                h2h = HeadToHead(
                    team_1_id=team1_id,
                    team_2_id=team2_id,
                    season=season,
                    team_1_wins=data["team1_wins"],
                    team_2_wins=data["team2_wins"],
                    team_1_avg_score=team1_avg,
                    team_2_avg_score=team2_avg,
                    last_game_date=data["last_game"],
                    last_game_winner=data["last_winner"],
                    last_game_score=data["last_score"]
                )
                db.add(h2h)
            
            synced += 1
        
        db.commit()
        print(f"✅ Head-to-head records synced for {synced} matchups")
        return synced
    
    async def detect_performance_streaks(self, db: Session, season: int, min_streak: int = 3) -> int:
        """🐐 Detect hot/cold performance streaks for players"""
        print(f"🐐 Detecting performance streaks for {season}...")
        
        # Get all players with recent activity
        recent_date = date.today() - timedelta(days=30)
        
        active_players = db.query(GameStats.player_id).join(Game).filter(
            Game.season == season,
            Game.date >= recent_date
        ).distinct().all()
        
        synced = 0
        metrics = ['pts', 'fg3m', 'ast', 'reb', 'stl', 'blk']
        
        for (player_id,) in active_players:
            # Get player's season average for comparison
            season_avg = db.query(SeasonAverages).filter(
                SeasonAverages.player_id == player_id,
                SeasonAverages.season == season
            ).first()
            
            if not season_avg:
                continue
            
            # Get last 10 games
            recent_games = db.query(GameStats).join(Game).filter(
                GameStats.player_id == player_id,
                Game.season == season
            ).order_by(Game.date.desc()).limit(10).all()
            
            if len(recent_games) < 5:
                continue
            
            # Check each metric for streaks
            for metric in metrics:
                avg_value = getattr(season_avg, f'avg_{metric}')
                if not avg_value or avg_value == 0:
                    continue
                
                # Define hot/cold thresholds
                hot_threshold = avg_value * 1.2  # 20% above average
                cold_threshold = avg_value * 0.8  # 20% below average
                
                # Check for hot streak
                hot_count = 0
                hot_values = []
                for game in recent_games:
                    value = getattr(game, metric, 0)
                    if value >= hot_threshold:
                        hot_count += 1
                        hot_values.append(value)
                    else:
                        break
                
                # Check for cold streak
                cold_count = 0
                cold_values = []
                for game in recent_games:
                    value = getattr(game, metric, 0)
                    if value <= cold_threshold:
                        cold_count += 1
                        cold_values.append(value)
                    else:
                        break
                
                # Store streak if significant
                if hot_count >= min_streak:
                    existing = db.query(PerformanceStreak).filter(
                        PerformanceStreak.player_id == player_id,
                        PerformanceStreak.season == season,
                        PerformanceStreak.metric == metric,
                        PerformanceStreak.streak_type == 'hot',
                        PerformanceStreak.is_active == True
                    ).first()
                    
                    if existing:
                        existing.current_streak = hot_count
                        existing.best_performance = max(hot_values)
                        existing.avg_performance = sum(hot_values) / len(hot_values)
                        existing.last_updated = datetime.utcnow()
                    else:
                        streak = PerformanceStreak(
                            player_id=player_id,
                            season=season,
                            metric=metric,
                            streak_type='hot',
                            threshold=hot_threshold,
                            current_streak=hot_count,
                            streak_start_date=recent_games[hot_count-1].game.date,
                            best_performance=max(hot_values),
                            avg_performance=sum(hot_values) / len(hot_values),
                            is_active=True
                        )
                        db.add(streak)
                    synced += 1
                
                elif cold_count >= min_streak:
                    existing = db.query(PerformanceStreak).filter(
                        PerformanceStreak.player_id == player_id,
                        PerformanceStreak.season == season,
                        PerformanceStreak.metric == metric,
                        PerformanceStreak.streak_type == 'cold',
                        PerformanceStreak.is_active == True
                    ).first()
                    
                    if existing:
                        existing.current_streak = cold_count
                        existing.best_performance = min(cold_values)
                        existing.avg_performance = sum(cold_values) / len(cold_values)
                        existing.last_updated = datetime.utcnow()
                    else:
                        streak = PerformanceStreak(
                            player_id=player_id,
                            season=season,
                            metric=metric,
                            streak_type='cold',
                            threshold=cold_threshold,
                            current_streak=cold_count,
                            streak_start_date=recent_games[cold_count-1].game.date,
                            best_performance=min(cold_values),
                            avg_performance=sum(cold_values) / len(cold_values),
                            is_active=True
                        )
                        db.add(streak)
                    synced += 1
        
        db.commit()
        print(f"✅ Performance streaks detected: {synced}")
        return synced
    
    # ========================================================================
    # DAILY SYNC
    # ========================================================================
    
    async def sync_recent_games(self, db: Session, days_back: int = 7) -> int:
        """Sync recent games (last N days)"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        current_season = 2024
        
        return await self.sync_games_for_date_range(db, start_date, end_date, current_season)
    
    async def perform_daily_sync(self):
        """Main sync function to run daily"""
        print("🚀 Starting daily NBA data sync...")
        
        with get_db_context() as db:
            try:
                # Core sync
                await self.sync_teams(db)
                await self.sync_players(db)
                
                yesterday = date.today() - timedelta(days=1)
                games_synced = await self.sync_games_for_date_range(
                    db, 
                    yesterday, 
                    yesterday,
                    2024
                )
                
                # GOAT tier sync
                await self.sync_season_averages(db, 2024)
                await self.sync_team_standings(db, 2024)
                await self.sync_head_to_head(db, 2024)
                await self.detect_performance_streaks(db, 2024)
                
                # Log sync
                log = SyncLog(
                    sync_date=datetime.utcnow(),
                    season=2024,
                    games_synced=games_synced,
                    status="success"
                )
                db.add(log)
                db.commit()
                
                print("✅ Daily sync completed successfully!")
                return True
                
            except Exception as e:
                print(f"❌ Daily sync failed: {e}")
                log = SyncLog(
                    sync_date=datetime.utcnow(),
                    season=2024,
                    games_synced=0,
                    status="failed",
                    error_message=str(e)[:500]
                )
                db.add(log)
                db.commit()
                return False


async def run_daily_sync():
    """Entry point for scheduled job"""
    service = DataSyncService()
    await service.perform_daily_sync()


if __name__ == "__main__":
    asyncio.run(run_daily_sync())
