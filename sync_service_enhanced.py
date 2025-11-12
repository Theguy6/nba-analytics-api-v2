"""
Enhanced Sync Service for GOAT Tier Features
Adds syncing for: Season Averages, Advanced Stats, Standings, Leaders, Injuries
"""

import httpx
import asyncio
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
import os
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import sys
import traceback

from database import Player, Team, Game, GameStats, SyncLog
from db_session import get_db_context

# Import the new models (you'll add these to database.py)
# from database import SeasonAverages, TeamStandings, LeagueLeaders, PlayerInjury, BoxScore

BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE_API_KEY")
BALLDONTLIE_BASE_URL = "https://api.balldontlie.io/v1"


class EnhancedDataSyncService:
    """Enhanced sync service with GOAT tier endpoints"""
    
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
    
    # ========== GOAT TIER: SEASON AVERAGES ==========
    
    async def sync_season_averages(self, db: Session, season: int) -> int:
        """Sync season averages for all players (GOAT tier)"""
        print(f"📊 Syncing season averages for {season}...", flush=True)
        
        try:
            all_averages = []
            page = 1
            
            while True:
                print(f"   Fetching season averages page {page}...", flush=True)
                data = await self.fetch_api("season_averages", {
                    "season": season,
                    "per_page": 100,
                    "page": page
                })
                averages_data = data.get("data", [])
                
                if not averages_data:
                    break
                
                all_averages.extend(averages_data)
                print(f"   Got {len(averages_data)} averages (total: {len(all_averages)})", flush=True)
                
                if len(averages_data) < 100:
                    break
                
                page += 1
                await asyncio.sleep(0.1)
            
            print(f"   Total averages to process: {len(all_averages)}", flush=True)
            
            synced = 0
            updated = 0
            
            for idx, avg_data in enumerate(all_averages):
                try:
                    player_data = avg_data.get("player_id")
                    
                    # Check if already exists
                    existing = db.query(SeasonAverages).filter(
                        SeasonAverages.player_id == player_data,
                        SeasonAverages.season == season
                    ).first()
                    
                    if not existing:
                        avg = SeasonAverages(
                            player_id=player_data,
                            season=season,
                            games_played=avg_data.get("games_played"),
                            minutes=avg_data.get("min"),
                            fgm=avg_data.get("fgm"),
                            fga=avg_data.get("fga"),
                            fg_pct=avg_data.get("fg_pct"),
                            fg3m=avg_data.get("fg3m"),
                            fg3a=avg_data.get("fg3a"),
                            fg3_pct=avg_data.get("fg3_pct"),
                            ftm=avg_data.get("ftm"),
                            fta=avg_data.get("fta"),
                            ft_pct=avg_data.get("ft_pct"),
                            oreb=avg_data.get("oreb"),
                            dreb=avg_data.get("dreb"),
                            reb=avg_data.get("reb"),
                            ast=avg_data.get("ast"),
                            stl=avg_data.get("stl"),
                            blk=avg_data.get("blk"),
                            turnover=avg_data.get("turnover"),
                            pf=avg_data.get("pf"),
                            pts=avg_data.get("pts")
                        )
                        db.add(avg)
                        synced += 1
                    else:
                        # Update existing
                        existing.games_played = avg_data.get("games_played")
                        existing.minutes = avg_data.get("min")
                        existing.pts = avg_data.get("pts")
                        # ... update other fields
                        existing.last_updated = datetime.utcnow()
                        updated += 1
                    
                    if (idx + 1) % 50 == 0:
                        db.commit()
                        print(f"   Processed {idx + 1}/{len(all_averages)} averages...", flush=True)
                
                except Exception as e:
                    db.rollback()
                    continue
            
            db.commit()
            print(f"✅ Season averages synced: {synced} new, {updated} updated", flush=True)
            return len(all_averages)
            
        except Exception as e:
            print(f"❌ Season averages sync failed: {e}", flush=True)
            traceback.print_exc()
            return 0
    
    # ========== GOAT TIER: TEAM STANDINGS ==========
    
    async def sync_team_standings(self, db: Session, season: int) -> int:
        """Sync team standings (GOAT tier)"""
        print(f"🏆 Syncing team standings for {season}...", flush=True)
        
        try:
            data = await self.fetch_api("standings", {"season": season})
            standings_data = data.get("data", [])
            
            print(f"   Got {len(standings_data)} team standings", flush=True)
            
            synced = 0
            updated = 0
            
            for standing_data in standings_data:
                try:
                    team_data = standing_data.get("team", {})
                    team_id = team_data.get("id")
                    
                    existing = db.query(TeamStandings).filter(
                        TeamStandings.team_id == team_id,
                        TeamStandings.season == season
                    ).first()
                    
                    if not existing:
                        standing = TeamStandings(
                            team_id=team_id,
                            season=season,
                            wins=standing_data.get("wins"),
                            losses=standing_data.get("losses"),
                            win_pct=standing_data.get("win_pct"),
                            games_back=standing_data.get("games_back"),
                            conference_rank=standing_data.get("conference_rank"),
                            division_rank=standing_data.get("division_rank"),
                            home_wins=standing_data.get("home_wins"),
                            home_losses=standing_data.get("home_losses"),
                            away_wins=standing_data.get("away_wins"),
                            away_losses=standing_data.get("away_losses"),
                            last_10=standing_data.get("last_10"),
                            streak=standing_data.get("streak")
                        )
                        db.add(standing)
                        synced += 1
                    else:
                        # Update existing
                        existing.wins = standing_data.get("wins")
                        existing.losses = standing_data.get("losses")
                        existing.win_pct = standing_data.get("win_pct")
                        # ... update other fields
                        existing.last_updated = datetime.utcnow()
                        updated += 1
                    
                    db.commit()
                
                except Exception as e:
                    db.rollback()
                    continue
            
            print(f"✅ Standings synced: {synced} new, {updated} updated", flush=True)
            return len(standings_data)
            
        except Exception as e:
            print(f"❌ Standings sync failed: {e}", flush=True)
            traceback.print_exc()
            return 0
    
    # ========== GOAT TIER: LEAGUE LEADERS ==========
    
    async def sync_league_leaders(self, db: Session, season: int) -> int:
        """Sync league leaders in various categories (GOAT tier)"""
        print(f"🌟 Syncing league leaders for {season}...", flush=True)
        
        categories = ["points", "assists", "rebounds", "steals", "blocks", "fg_pct", "ft_pct", "fg3_pct"]
        total_synced = 0
        
        try:
            for category in categories:
                print(f"   Fetching leaders for {category}...", flush=True)
                
                data = await self.fetch_api("leaders", {
                    "season": season,
                    "stat_type": category,
                    "per_page": 50  # Top 50 in each category
                })
                leaders_data = data.get("data", [])
                
                for rank, leader_data in enumerate(leaders_data, 1):
                    try:
                        player_data = leader_data.get("player", {})
                        player_id = player_data.get("id")
                        
                        existing = db.query(LeagueLeaders).filter(
                            LeagueLeaders.player_id == player_id,
                            LeagueLeaders.season == season,
                            LeagueLeaders.category == category
                        ).first()
                        
                        if not existing:
                            leader = LeagueLeaders(
                                player_id=player_id,
                                season=season,
                                category=category,
                                value=leader_data.get("value"),
                                rank=rank
                            )
                            db.add(leader)
                            total_synced += 1
                        else:
                            existing.value = leader_data.get("value")
                            existing.rank = rank
                            existing.last_updated = datetime.utcnow()
                    
                    except Exception as e:
                        continue
                
                db.commit()
                await asyncio.sleep(0.1)
            
            print(f"✅ Leaders synced: {total_synced} total across {len(categories)} categories", flush=True)
            return total_synced
            
        except Exception as e:
            print(f"❌ Leaders sync failed: {e}", flush=True)
            traceback.print_exc()
            return 0
    
    # ========== GOAT TIER: PLAYER INJURIES ==========
    
    async def sync_player_injuries(self, db: Session) -> int:
        """Sync current player injury reports (GOAT tier)"""
        print("🏥 Syncing player injuries...", flush=True)
        
        try:
            data = await self.fetch_api("injuries")
            injuries_data = data.get("data", [])
            
            print(f"   Got {len(injuries_data)} injury reports", flush=True)
            
            # Clear old injuries
            db.query(PlayerInjury).delete()
            
            synced = 0
            for injury_data in injuries_data:
                try:
                    player_data = injury_data.get("player", {})
                    player_id = player_data.get("id")
                    
                    injury = PlayerInjury(
                        player_id=player_id,
                        injury_type=injury_data.get("injury_type"),
                        status=injury_data.get("status"),
                        description=injury_data.get("description"),
                        date_reported=datetime.fromisoformat(injury_data.get("date_reported")).date() if injury_data.get("date_reported") else None,
                        date_updated=datetime.fromisoformat(injury_data.get("date_updated")).date() if injury_data.get("date_updated") else None,
                        expected_return=datetime.fromisoformat(injury_data.get("expected_return")).date() if injury_data.get("expected_return") else None
                    )
                    db.add(injury)
                    synced += 1
                
                except Exception as e:
                    continue
            
            db.commit()
            print(f"✅ Injuries synced: {synced} current injuries", flush=True)
            return synced
            
        except Exception as e:
            print(f"❌ Injuries sync failed: {e}", flush=True)
            traceback.print_exc()
            return 0
    
    # ========== ENHANCED DAILY SYNC ==========
    
    async def perform_enhanced_daily_sync(self):
        """Enhanced daily sync with GOAT tier features"""
        print("🐐 Starting ENHANCED daily NBA data sync (GOAT tier)...", flush=True)
        sys.stdout.flush()
        
        with get_db_context() as db:
            try:
                current_season = 2024
                
                # 1. Core data (existing)
                print("\n=== CORE DATA ===", flush=True)
                await self.sync_teams(db)
                await self.sync_active_players(db)
                
                yesterday = date.today() - timedelta(days=1)
                await self.sync_games_for_date_range(db, yesterday, yesterday, current_season)
                
                # 2. GOAT tier features
                print("\n=== GOAT TIER FEATURES ===", flush=True)
                
                # Season averages (run weekly or when requested)
                await self.sync_season_averages(db, current_season)
                
                # Team standings (run daily)
                await self.sync_team_standings(db, current_season)
                
                # League leaders (run weekly)
                await self.sync_league_leaders(db, current_season)
                
                # Injuries (run daily)
                await self.sync_player_injuries(db)
                
                print("\n✅ Enhanced daily sync completed successfully!", flush=True)
                sys.stdout.flush()
                return True
                
            except Exception as e:
                print(f"❌ Enhanced daily sync failed: {e}", flush=True)
                traceback.print_exc()
                sys.stdout.flush()
                return False


# Add these methods to the existing DataSyncService class
# or use this EnhancedDataSyncService
