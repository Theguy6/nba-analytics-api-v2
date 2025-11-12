"""
Simple sync test script - Run this to see what's happening
"""

import asyncio
import httpx
import os
from datetime import datetime

BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE_API_KEY")

async def test_api_connection():
    """Test if we can connect to Balldontlie API"""
    print("=" * 60)
    print("TESTING API CONNECTION")
    print("=" * 60)
    
    if not BALLDONTLIE_API_KEY:
        print("❌ BALLDONTLIE_API_KEY not set!")
        return False
    
    print(f"✅ API Key found: {BALLDONTLIE_API_KEY[:10]}...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test teams endpoint
            print("\n📋 Testing /teams endpoint...")
            response = await client.get(
                "https://api.balldontlie.io/v1/teams",
                headers={"Authorization": BALLDONTLIE_API_KEY}
            )
            
            if response.status_code == 200:
                data = response.json()
                teams = data.get("data", [])
                print(f"✅ Teams endpoint works! Got {len(teams)} teams")
            else:
                print(f"❌ Teams endpoint failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
            
            # Test players endpoint
            print("\n👥 Testing /players endpoint...")
            response = await client.get(
                "https://api.balldontlie.io/v1/players",
                headers={"Authorization": BALLDONTLIE_API_KEY},
                params={"per_page": 10, "page": 1}
            )
            
            if response.status_code == 200:
                data = response.json()
                players = data.get("data", [])
                print(f"✅ Players endpoint works! Got {len(players)} players")
                if players:
                    print(f"   Sample: {players[0]['first_name']} {players[0]['last_name']}")
            else:
                print(f"❌ Players endpoint failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
            
            # Test stats endpoint
            print("\n📊 Testing /stats endpoint...")
            response = await client.get(
                "https://api.balldontlie.io/v1/stats",
                headers={"Authorization": BALLDONTLIE_API_KEY},
                params={"per_page": 10}
            )
            
            if response.status_code == 200:
                data = response.json()
                stats = data.get("data", [])
                print(f"✅ Stats endpoint works! Got {len(stats)} stat records")
            else:
                print(f"❌ Stats endpoint failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
            
            print("\n🎉 All API endpoints working!")
            return True
            
    except Exception as e:
        print(f"❌ API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_database_connection():
    """Test if we can connect to database"""
    print("\n" + "=" * 60)
    print("TESTING DATABASE CONNECTION")
    print("=" * 60)
    
    try:
        from database import Team, Player
        from db_session import get_db_context, init_db
        
        # Initialize database
        print("📦 Initializing database...")
        init_db()
        print("✅ Database initialized")
        
        # Test query
        print("\n🔍 Testing database query...")
        with get_db_context() as db:
            team_count = db.query(Team).count()
            player_count = db.query(Player).count()
            
            print(f"✅ Database connected!")
            print(f"   Teams in database: {team_count}")
            print(f"   Players in database: {player_count}")
            
            return True
            
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_minimal_sync():
    """Test a minimal sync - just teams"""
    print("\n" + "=" * 60)
    print("TESTING MINIMAL SYNC (TEAMS ONLY)")
    print("=" * 60)
    
    try:
        from sync_service import DataSyncService
        from db_session import get_db_context
        
        service = DataSyncService()
        
        with get_db_context() as db:
            print("\n🏀 Syncing teams...")
            teams_synced = await service.sync_teams(db)
            print(f"✅ Teams sync complete: {teams_synced} teams")
            
            return True
            
    except Exception as e:
        print(f"❌ Sync test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("\n🧪 NBA ANALYTICS API - DIAGNOSTIC TEST")
    print(f"⏰ Time: {datetime.now()}")
    print("\n")
    
    # Test 1: API Connection
    api_ok = await test_api_connection()
    
    # Test 2: Database Connection
    db_ok = await test_database_connection()
    
    # Test 3: Minimal Sync
    if api_ok and db_ok:
        sync_ok = await test_minimal_sync()
    else:
        print("\n⚠️  Skipping sync test due to previous failures")
        sync_ok = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"API Connection:      {'✅ PASS' if api_ok else '❌ FAIL'}")
    print(f"Database Connection: {'✅ PASS' if db_ok else '❌ FAIL'}")
    print(f"Minimal Sync:        {'✅ PASS' if sync_ok else '❌ FAIL'}")
    print("=" * 60)
    
    if api_ok and db_ok and sync_ok:
        print("\n🎉 All tests passed! Your setup is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())
