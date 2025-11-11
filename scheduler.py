"""
Scheduler for automated daily data synchronization
Runs at 6 AM daily (after NBA games finish)
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
from sync_service import run_daily_sync
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_scheduler():
    """Start the scheduler for daily sync"""
    scheduler = AsyncIOScheduler()
    
    # Schedule daily sync at 6 AM UTC (adjust timezone as needed)
    scheduler.add_job(
        run_daily_sync,
        trigger=CronTrigger(hour=6, minute=0),
        id='daily_nba_sync',
        name='Daily NBA Data Sync',
        replace_existing=True
    )
    
    logger.info("📅 Scheduler started - daily sync at 6:00 AM UTC")
    scheduler.start()
    
    return scheduler

if __name__ == "__main__":
    scheduler = start_scheduler()
    
    # Keep the script running
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
