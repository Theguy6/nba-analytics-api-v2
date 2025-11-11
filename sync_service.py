"""
Data Synchronization Service
Fetches data from Balldontlie API and stores in database
Can be run as a scheduled job (daily at 6 AM) or on-demand
"""

import httpx
import asyncio
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
import os
from sqlalchemy.orm import Session

from database import Player, Team, Game, GameStats, SyncLog
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
                # Update existing team
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
            await asyncio.sleep(0.1)  # Rate limiting
        
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
                # Update existing player
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
            # Fetch stats for this date
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
        
        # Process and store stats
        games_synced = 0
        stats_synced = 0
        
        for stat in all_stats:
            game_data = stat.get("game", {})
            player_data = stat.get("player", {})
            team_data = stat.get("team", {})
            
            # Ensure game exists
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
            
            # Check if stat already exists
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
    
    async def sync_recent_games(self, db: Session, days_back: int = 7) -> int:
        """Sync recent games (last N days)"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        current_season = 2024  # Update based on actual season
        
        return await self.sync_games_for_date_range(db, start_date, end_date, current_season)
    
    async def sync_full_season(self, db: Session, season: int, start_date: date, end_date: date = None) -> int:
        """Sync entire season"""
        if end_date is None:
            end_date = date.today()
        
        return await self.sync_games_for_date_range(db, start_date, end_date, season)
    
    async def perform_daily_sync(self):
        """Main sync function to run daily"""
        print("🚀 Starting daily NBA data sync...")
        
        with get_db_context() as db:
            try:
                # Sync teams (quick, infrequent changes)
                await self.sync_teams(db)
                
                # Sync players (quick, check for roster changes)
                await self.sync_players(db)
                
                # Sync yesterday's games (main data)
                yesterday = date.today() - timedelta(days=1)
                games_synced = await self.sync_games_for_date_range(
                    db, 
                    yesterday, 
                    yesterday,
                    2024  # Current season
                )
                
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
    # Can be run manually for testing
    asyncio.run(run_daily_sync())
