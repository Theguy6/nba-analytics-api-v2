"""
Database Migration Script for GOAT Tier Features
Run this once after deploying the enhanced code
"""

from database import Base
from db_session import engine
import sys

def run_migration():
    """Create all new tables for GOAT tier features"""
    print("🔨 Starting database migration for GOAT tier features...")
    print("=" * 60)
    
    try:
        # This creates all tables that don't exist yet
        # It won't touch existing tables
        Base.metadata.create_all(bind=engine)
        
        print("✅ Migration complete!")
        print("\nNew tables created:")
        print("  - season_averages")
        print("  - advanced_stats")
        print("  - team_standings")
        print("  - league_leaders")
        print("  - player_injuries")
        print("  - box_scores")
        print("\n✅ Your database is now ready for GOAT tier features!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
