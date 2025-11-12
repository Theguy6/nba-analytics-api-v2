"""
Data Synchronization Service - GOAT TIER Edition
Fetches data from Balldontlie API with cursor-based pagination and GOAT tier features
Includes: Advanced stats, injuries, betting odds, active players
"""

import httpx
import asyncio
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
import os
from sqlalchemy.orm import Session

from database import Player, Team, Game, GameStats, AdvancedStats, PlayerInjury, BettingOdds, SyncLog
from db_session import get_db_context

BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE_API_KEY")
BALLDONTLIE_BASE_URL = "https://api.balldontlie.io/v1"


class DataSyncService:
    """Service for syncing NBA data from Balldontlie API to database - GOAT Edition"""
    
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
        """Sync all NBA teams using cursor pagination"""
        print("🏀 Syncing teams...")
        
        all_teams = []
        cursor = None
        
        while True:
            params = {"per_page": 100}
            if cursor:
                params["cursor"] = cursor
            
            data = await self.fetch_api("teams", params)
            teams_data = data.get("data", [])
            
            if not teams_data:
                break
            
            all_teams.extend(teams_data)
            
            # Get next cursor
            meta = data.get("meta", {})
            cursor = meta.get("next_cursor")
            
            if not cursor:
                break
            
            await asyncio.sleep(0.1)
        
        synced = 0
        updated = 0
        skipped = 0
        
        for team_data in all_teams:
            # Find by ID (not abbreviation to avoid conflicts)
            team = db.query(Team).filter(Team.id == team_data["id"]).first()
            
            if not team:
                # Check if abbreviation exists with different ID
                existing_abbr = db.query(Team).filter(
                    Team.abbreviation == team_data["abbreviation"],
                    Team.id != team_data["id"]
                ).first()
                
                if existing_abbr:
                    print(f"⚠️ Skipping team {team_data['abbreviation']} (ID {team_data['id']}) - abbreviation already exists for ID {existing_abbr.id}")
                    skipped += 1
                    continue
                
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
                updated += 1
        
        db.commit()
        print(f"✅ Teams synced: {synced} new, {updated} updated, {skipped} skipped")
        return len(all_teams)
    
    async def sync_players(self, db: Session) -> int:
        """Sync all ACTIVE NBA players using cursor pagination (GOAT tier feature)"""
        print("👥 Syncing players...")
        
        all_players = []
        cursor = None
        
        while True:
            params = {"per_page": 100}
            if cursor:
                params["cursor"] = cursor
            
            print(f"   Fetching players (cursor: {cursor or 'initial'})...")
            
            # GOAT tier: Use /players/active endpoint for current rosters only
            data = await self.fetch_api("players/active", params)
            players_data = data.get("data", [])
            
            if not players_data:
                break
            
            all_players.extend(players_data)
            print(f"   ✓ Got {len(players_data)} players (total: {len(all_players)})")
            
            # Get next cursor from meta
            meta = data.get("meta", {})
            cursor = meta.get("next_cursor")
            
            if not cursor:
                break
            
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
        """Sync games and basic stats for a date range using cursor pagination"""
        print(f"📅 Syncing games from {start_date} to {end_date}...")
        
        all_stats = []
        cursor = None
        page_count = 0
        
        # Use cursor-based pagination with date range
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "per_page": 100
        }
        
        while True:
            page_count += 1
            
            if cursor:
                params["cursor"] = cursor
            
            print(f"   Fetching stats page {page_count} (cursor: {cursor or 'initial'})...")
            
            try:
                data = await self.fetch_api("stats", params)
                stats_data = data.get("data", [])
                
                if not stats_data:
                    break
                
                all_stats.extend(stats_data)
                print(f"   ✓ Got {len(stats_data)} stats (total: {len(all_stats)})")
                
                # Get next cursor from meta
                meta = data.get("meta", {})
                cursor = meta.get("next_cursor")
                
                if not cursor:
                    break
                
                await asyncio.sleep(0.1)
            
            except Exception as e:
                print(f"⚠️  Error fetching stats: {e}")
                break
        
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
    
    async def sync_advanced_stats_for_date_range(
        self, 
        db: Session, 
        start_date: date, 
        end_date: date,
        season: int
    ) -> int:
        """Sync advanced stats (GOAT tier feature)"""
        print(f"📊 Syncing advanced stats from {start_date} to {end_date}...")
        
        all_stats = []
        cursor = None
        
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "per_page": 100,
            "seasons[]": season
        }
        
        while True:
            if cursor:
                params["cursor"] = cursor
            
            try:
                # GOAT tier endpoint
                data = await self.fetch_api("stats/advanced", params)
                stats_data = data.get("data", [])
                
                if not stats_data:
                    break
                
                all_stats.extend(stats_data)
                print(f"   ✓ Got {len(stats_data)} advanced stats (total: {len(all_stats)})")
                
                meta = data.get("meta", {})
                cursor = meta.get("next_cursor")
                
                if not cursor:
                    break
                
                await asyncio.sleep(0.1)
            
            except Exception as e:
                print(f"⚠️  Error fetching advanced stats: {e}")
                break
        
        # Store in database
        stats_synced = 0
        for stat in all_stats:
            player_data = stat.get("player", {})
            game_data = stat.get("game", {})
            team_data = stat.get("team", {})
            
            # Check if exists
            existing = db.query(AdvancedStats).filter(
                AdvancedStats.player_id == player_data["id"],
                AdvancedStats.game_id == game_data["id"]
            ).first()
            
            if not existing:
                adv_stat = AdvancedStats(
                    id=stat.get("id"),
                    player_id=player_data["id"],
                    game_id=game_data["id"],
                    team_id=team_data.get("id"),
                    pie=stat.get("pie"),
                    pace=stat.get("pace"),
                    assist_percentage=stat.get("assist_percentage"),
                    assist_ratio=stat.get("assist_ratio"),
                    assist_to_turnover=stat.get("assist_to_turnover"),
                    defensive_rating=stat.get("defensive_rating"),
                    defensive_rebound_percentage=stat.get("defensive_rebound_percentage"),
                    effective_field_goal_percentage=stat.get("effective_field_goal_percentage"),
                    net_rating=stat.get("net_rating"),
                    offensive_rating=stat.get("offensive_rating"),
                    offensive_rebound_percentage=stat.get("offensive_rebound_percentage"),
                    rebound_percentage=stat.get("rebound_percentage"),
                    true_shooting_percentage=stat.get("true_shooting_percentage"),
                    turnover_ratio=stat.get("turnover_ratio"),
                    usage_percentage=stat.get("usage_percentage")
                )
                db.add(adv_stat)
                stats_synced += 1
        
        db.commit()
        print(f"✅ Synced {stats_synced} advanced stats")
        return stats_synced
    
    async def sync_player_injuries(self, db: Session) -> int:
        """Sync current player injuries (ALL-STAR+ tier)"""
        print("🏥 Syncing player injuries...")
        
        cursor = None
        all_injuries = []
        
        while True:
            params = {"per_page": 100}
            if cursor:
                params["cursor"] = cursor
            
            try:
                data = await self.fetch_api("player_injuries", params)
                injuries_data = data.get("data", [])
                
                if not injuries_data:
                    break
                
                all_injuries.extend(injuries_data)
                print(f"   ✓ Got {len(injuries_data)} injuries (total: {len(all_injuries)})")
                
                meta = data.get("meta", {})
                cursor = meta.get("next_cursor")
                
                if not cursor:
                    break
                
                await asyncio.sleep(0.1)
            
            except Exception as e:
                print(f"⚠️  Error fetching injuries: {e}")
                break
        
        # Clear old injuries (they change daily)
        db.query(PlayerInjury).delete()
        
        # Add new ones
        for injury_data in all_injuries:
            player_data = injury_data.get("player", {})
            
            injury = PlayerInjury(
                player_id=player_data["id"],
                return_date=injury_data.get("return_date"),
                description=injury_data.get("description"),
                status=injury_data.get("status")
            )
            db.add(injury)
        
        db.commit()
        print(f"✅ Synced {len(all_injuries)} injuries")
        return len(all_injuries)
    
    async def sync_betting_odds_for_date(self, db: Session, target_date: date) -> int:
        """Sync betting odds for a specific date (GOAT tier)"""
        print(f"💰 Syncing betting odds for {target_date}...")
        
        cursor = None
        all_odds = []
        
        while True:
            params = {
                "dates[]": target_date.isoformat(),
                "per_page": 100
            }
            if cursor:
                params["cursor"] = cursor
            
            try:
                # Note: v2 endpoint for odds!
                url = f"{BALLDONTLIE_BASE_URL.replace('/v1', '/v2')}/odds"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, headers=self.headers, params=params)
                    response.raise_for_status()
                    data = response.json()
                
                odds_data = data.get("data", [])
                
                if not odds_data:
                    break
                
                all_odds.extend(odds_data)
                print(f"   ✓ Got {len(odds_data)} odds lines (total: {len(all_odds)})")
                
                meta = data.get("meta", {})
                cursor = meta.get("next_cursor")
                
                if not cursor:
                    break
                
                await asyncio.sleep(0.1)
            
            except Exception as e:
                print(f"⚠️  Error fetching odds: {e}")
                break
        
        # Store odds
        synced = 0
        for odds in all_odds:
            existing = db.query(BettingOdds).filter(
                BettingOdds.id == odds["id"]
            ).first()
            
            if not existing:
                betting_odds = BettingOdds(
                    id=odds["id"],
                    game_id=odds["game_id"],
                    vendor=odds["vendor"],
                    spread_home_value=odds.get("spread_home_value"),
                    spread_home_odds=odds.get("spread_home_odds"),
                    spread_away_value=odds.get("spread_away_value"),
                    spread_away_odds=odds.get("spread_away_odds"),
                    moneyline_home_odds=odds.get("moneyline_home_odds"),
                    moneyline_away_odds=odds.get("moneyline_away_odds"),
                    total_value=odds.get("total_value"),
                    total_over_odds=odds.get("total_over_odds"),
                    total_under_odds=odds.get("total_under_odds"),
                    updated_at=datetime.fromisoformat(odds["updated_at"].replace('Z', '+00:00'))
                )
                db.add(betting_odds)
                synced += 1
            else:
                # Update existing odds (they change frequently)
                existing.spread_home_value = odds.get("spread_home_value")
                existing.spread_home_odds = odds.get("spread_home_odds")
                existing.spread_away_value = odds.get("spread_away_value")
                existing.spread_away_odds = odds.get("spread_away_odds")
                existing.moneyline_home_odds = odds.get("moneyline_home_odds")
                existing.moneyline_away_odds = odds.get("moneyline_away_odds")
                existing.total_value = odds.get("total_value")
                existing.total_over_odds = odds.get("total_over_odds")
                existing.total_under_odds = odds.get("total_under_odds")
                existing.updated_at = datetime.fromisoformat(odds["updated_at"].replace('Z', '+00:00'))
        
        db.commit()
        print(f"✅ Synced {synced} odds records, {len(all_odds) - synced} updated")
        return synced
    
    async def perform_daily_sync(self):
        """Enhanced daily sync with GOAT tier features"""
        print("🚀 Starting daily NBA data sync (GOAT Edition)...")
        
        with get_db_context() as db:
            try:
                # 1. Sync teams (quick)
                await self.sync_teams(db)
                
                # 2. Sync active players only (GOAT tier)
                await self.sync_players(db)
                
                # 3. Sync yesterday's games and basic stats
                yesterday = date.today() - timedelta(days=1)
                games_synced = await self.sync_games_for_date_range(
                    db, yesterday, yesterday, 2024
                )
                
                # 4. GOAT TIER: Sync advanced stats for yesterday
                await self.sync_advanced_stats_for_date_range(
                    db, yesterday, yesterday, 2024
                )
                
                # 5. GOAT TIER: Sync injuries (daily update)
                await self.sync_player_injuries(db)
                
                # 6. GOAT TIER: Sync betting odds for today
                today = date.today()
                await self.sync_betting_odds_for_date(db, today)
                
                # Log success
                log = SyncLog(
                    sync_date=datetime.utcnow(),
                    season=2024,
                    games_synced=games_synced,
                    status="success"
                )
                db.add(log)
                db.commit()
                
                print("✅ Daily sync completed successfully (GOAT Edition)!")
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
