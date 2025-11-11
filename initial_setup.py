"""
Initial Setup Script
Run this ONCE after deploying to populate the database with historical data
"""

import asyncio
from datetime import date, datetime
from sync_service import DataSyncService
from db_session import get_db_context, init_db

async def initial_setup():
    """
    Initial data setup - run once when first deploying
    """
    print("🚀 Starting initial NBA data setup...")
    print("=" * 60)
    
    # Initialize database
    init_db()
    print("✅ Database initialized")
    
    service = DataSyncService()
    
    with get_db_context() as db:
        # 1. Sync teams (required first)
        print("\n📋 Step 1/3: Syncing NBA teams...")
        await service.sync_teams(db)
        
        # 2. Sync players (required second)
        print("\n📋 Step 2/3: Syncing NBA players...")
        await service.sync_players(db)
        
        # 3. Sync games for current season
        print("\n📋 Step 3/3: Syncing 2023-24 season games...")
        print("This will take several minutes...")
        
        # Sync from October 2023 (season start) to today
        start_date = date(2023, 10, 1)
        end_date = date.today()
        
        games_synced = await service.sync_games_for_date_range(
            db, 
            start_date, 
            end_date,
            2024
        )
        
        print(f"\n✅ Initial setup complete!")
        print(f"   Teams synced: ✓")
        print(f"   Players synced: ✓")
        print(f"   Games synced: {games_synced}")
        print(f"   Date range: {start_date} to {end_date}")
        print("\n🎉 Your NBA Analytics system is ready to use!")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(initial_setup())
