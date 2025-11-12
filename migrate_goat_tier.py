"""
Database Migration Script - Add GOAT Tier Tables
Run this ONCE on existing deployments to add new tables without losing data
"""

from sqlalchemy import create_engine, inspect
import os

from database import Base, AdvancedStats, PlayerInjury, BettingOdds, SeasonAverages

def run_migration():
    """
    Add new GOAT tier tables to existing database
    Safe to run - won't drop existing tables
    """
    print("🔧 Starting database migration for GOAT tier features...")
    print("=" * 60)
    
    # Get database URL from environment
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nba_analytics.db")
    
    # Handle Railway PostgreSQL URL format
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
    elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    
    print(f"📊 Connecting to database...")
    
    # Create engine
    if DATABASE_URL.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
    else:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    # Check existing tables
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    print(f"✅ Connected to database")
    print(f"📋 Existing tables: {', '.join(existing_tables)}")
    
    # New tables to add
    new_tables = {
        "advanced_stats": AdvancedStats,
        "player_injuries": PlayerInjury,
        "betting_odds": BettingOdds,
        "season_averages": SeasonAverages
    }
    
    # Check which tables need to be created
    tables_to_create = []
    for table_name, table_class in new_tables.items():
        if table_name not in existing_tables:
            tables_to_create.append(table_name)
    
    if not tables_to_create:
        print("\n✅ All GOAT tier tables already exist!")
        print("=" * 60)
        return
    
    print(f"\n🆕 Creating new tables: {', '.join(tables_to_create)}")
    
    # Create only new tables (won't affect existing ones)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    
    print("\n✅ Migration completed successfully!")
    print("=" * 60)
    print("\n📊 New GOAT tier tables added:")
    for table_name in tables_to_create:
        print(f"   ✓ {table_name}")
    
    print("\n💡 Next steps:")
    print("   1. Run: python initial_setup.py (to populate with data)")
    print("   2. Or use API: POST /sync/goat-tier-backfill")
    print("   3. Enable daily sync for automatic updates")
    
    print("\n⚠️  Note: Fix team abbreviation unique constraint")
    print("   If you see 'duplicate key' errors for team 'WAS':")
    print("   This is a known API issue - the code handles it gracefully")

if __name__ == "__main__":
    run_migration()
