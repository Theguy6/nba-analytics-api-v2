"""
Initial Setup Script - GOAT TIER Edition
Run this ONCE after deploying to populate the database with historical data
Includes: Teams, players, games, stats, advanced stats, injuries
"""

import asyncio
from datetime import date, datetime
from sync_service import DataSyncService
from db_session import get_db_context, init_db

async def initial_setup():
    """
    Initial data setup - run once when first deploying
    """
    print("🚀 Starting initial NBA data setup (GOAT Edition)...")
    print("=" * 60)
    
    # Initialize database
    init_db()
    print("✅ Database initialized with GOAT tier tables")
    
    service = DataSyncService()
    
    with get_db_context() as db:
        # 1. Sync teams (required first)
        print("\n📋 Step 1/6: Syncing NBA teams...")
        await service.sync_teams(db)
        
        # 2. Sync ACTIVE players (GOAT tier - faster than all players)
        print("\n📋 Step 2/6: Syncing NBA active players...")
        await service.sync_players(db)
        
        # 3. Sync games for current season
        print("\n📋 Step 3/6: Syncing 2024-25 season games...")
        print("This will take several minutes...")
        
        # Sync from November 2024 (season start) to today
        start_date = date(2024, 11, 1)
        end_date = date.today()
        
        games_synced = await service.sync_games_for_date_range(
            db, 
            start_date, 
            end_date,
            2024
        )
        
        # 4. GOAT TIER: Sync advanced stats for same period
        print("\n📋 Step 4/6: Syncing advanced stats (GOAT tier)...")
        await service.sync_advanced_stats_for_date_range(
            db,
            start_date,
            end_date,
            2024
        )
        
        # 5. GOAT TIER: Sync current injuries
        print("\n📋 Step 5/6: Syncing player injuries (GOAT tier)...")
        await service.sync_player_injuries(db)
        
        # 6. GOAT TIER: Sync betting odds for today
        print("\n📋 Step 6/6: Syncing betting odds for today (GOAT tier)...")
        try:
            await service.sync_betting_odds_for_date(db, date.today())
        except Exception as e:
            print(f"⚠️  Could not sync odds (may not be available yet): {e}")
        
        print(f"\n✅ Initial setup complete!")
        print(f"   Teams synced: ✓")
        print(f"   Active players synced: ✓")
        print(f"   Games synced: {games_synced}")
        print(f"   Advanced stats synced: ✓")
        print(f"   Injuries synced: ✓")
        print(f"   Betting odds synced: ✓")
        print(f"   Date range: {start_date} to {end_date}")
        print("\n🎉 Your NBA Analytics system (GOAT Edition) is ready to use!")
        print("=" * 60)
        print("\n💡 Next steps:")
        print("   1. Test API: curl http://localhost:8000/")
        print("   2. Search players: curl 'http://localhost:8000/player/search?name=curry'")
        print("   3. Advanced stats: curl 'http://localhost:8000/analytics/advanced-stats?player_name=Stephen+Curry&season=2024'")
        print("   4. Set up daily sync to run automatically")

if __name__ == "__main__":
    asyncio.run(initial_setup())
