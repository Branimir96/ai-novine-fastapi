# Create this as app/services/smart_scheduler.py

import asyncio
import datetime
import logging
from typing import Dict, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.simple_redis_manager import simple_cache
from app.services.news_service import generiraj_vijesti, parse_news_content

logger = logging.getLogger(__name__)

class SmartNewsScheduler:
    """Priority-based staggered news scheduler"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone='Europe/Zagreb')
        self.is_running = False
        
        # Category priorities and frequencies
        self.category_priorities = {
            # High priority - 6 times/day
            "Hrvatska": {
                "priority": "high",
                "frequency": 6,
                "times": ["06:00", "09:15", "15:15", "18:15", "23:00", "02:00"]
            },
            "Svijet": {
                "priority": "high", 
                "frequency": 6,
                "times": ["06:15", "12:15", "18:00", "21:15", "02:00", "09:00"]
            },
            # Medium priority - 4 times/day
            "Ekonomija": {
                "priority": "medium",
                "frequency": 4,
                "times": ["09:00", "15:00", "12:00", "18:30"]
            },
            "Sport": {
                "priority": "medium",
                "frequency": 4, 
                "times": ["12:00", "21:00", "15:30", "09:30"]
            },
            # Low priority - 1 time/day
            "Regija": {
                "priority": "low",
                "frequency": 1,
                "times": ["23:15"]
            }
        }
        
        # Statistics tracking
        self.refresh_stats = {
            "total_refreshes": 0,
            "successful_refreshes": 0,
            "failed_refreshes": 0,
            "category_stats": {cat: {"success": 0, "failed": 0} for cat in self.category_priorities.keys()}
        }
    
    async def fetch_category_news(self, category: str, scheduled_time: str = None):
        """Fetch and cache news for a specific category"""
        start_time = datetime.datetime.now()
        
        try:
            logger.info(f"🔄 [{scheduled_time}] Starting scheduled refresh for {category}")
            
            # Fetch fresh news
            result, filename = generiraj_vijesti(category)
            
            if result and not result.startswith("Trenutno nije moguće"):
                # Parse and cache articles
                articles = parse_news_content(result)
                
                # Cache with appropriate TTL based on priority
                ttl = self._get_cache_ttl(category)
                cache_success = await simple_cache.set_news(category, articles, ttl_seconds=ttl)
                
                if cache_success:
                    execution_time = (datetime.datetime.now() - start_time).total_seconds()
                    
                    logger.info(f"✅ [{scheduled_time}] {category}: {len(articles)} articles cached in {execution_time:.1f}s")
                    
                    # Update statistics
                    self.refresh_stats["successful_refreshes"] += 1
                    self.refresh_stats["category_stats"][category]["success"] += 1
                    
                    return True
                else:
                    raise Exception("Cache operation failed")
            else:
                raise Exception(f"News service unavailable: {result}")
                
        except Exception as e:
            execution_time = (datetime.datetime.now() - start_time).total_seconds()
            logger.error(f"❌ [{scheduled_time}] {category} failed after {execution_time:.1f}s: {e}")
            
            # Update failure statistics
            self.refresh_stats["failed_refreshes"] += 1
            self.refresh_stats["category_stats"][category]["failed"] += 1
            
            return False
        
        finally:
            self.refresh_stats["total_refreshes"] += 1
    
    def _get_cache_ttl(self, category: str) -> int:
        """Get appropriate cache TTL based on category priority"""
        priority = self.category_priorities[category]["priority"]
        
        if priority == "high":
            return 14400  # 4 hours (refreshes every ~4 hours)
        elif priority == "medium":
            return 21600  # 6 hours (refreshes every ~6 hours)
        else:  # low priority
            return 86400  # 24 hours (refreshes daily)
    
    def start_scheduler(self):
        """Start the priority-based staggered scheduler"""
        if self.is_running:
            logger.warning("Smart scheduler is already running")
            return
        
        try:
            # Schedule each category based on its priority and times
            for category, config in self.category_priorities.items():
                priority = config["priority"]
                times = config["times"]
                
                for time_slot in times:
                    hour, minute = map(int, time_slot.split(':'))
                    
                    # Create unique job ID
                    job_id = f"{category}_{time_slot.replace(':', '')}"
                    job_name = f"{priority.title()} Priority: {category} at {time_slot}"
                    
                    # Schedule the job
                    self.scheduler.add_job(
                        func=self.fetch_category_news,
                        args=[category, time_slot],
                        trigger=CronTrigger(hour=hour, minute=minute),
                        id=job_id,
                        name=job_name,
                        replace_existing=True,
                        max_instances=1  # Prevent overlapping runs
                    )
                    
                    logger.info(f"📅 Scheduled {category} ({priority}) at {time_slot}")
            
            # Start the scheduler
            self.scheduler.start()
            self.is_running = True
            
            # Log schedule summary
            total_jobs = sum(len(config["times"]) for config in self.category_priorities.values())
            logger.info(f"✅ Smart scheduler started with {total_jobs} scheduled jobs")
            logger.info(f"📊 Daily schedule: High=12, Medium=8, Low=1 total refreshes")
            
        except Exception as e:
            logger.error(f"❌ Failed to start smart scheduler: {e}")
            raise
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        if not self.is_running:
            logger.warning("Smart scheduler is not running")
            return
        
        try:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("✅ Smart scheduler stopped successfully")
        except Exception as e:
            logger.error(f"❌ Error stopping smart scheduler: {e}")
            raise
    
    def get_schedule_status(self) -> Dict:
        """Get current schedule status and next runs"""
        if not self.is_running:
            return {
                "is_running": False,
                "message": "Smart scheduler is not running"
            }
        
        # Get next scheduled runs for each category
        next_runs = {}
        jobs_info = []
        
        for job in self.scheduler.get_jobs():
            category = job.id.split('_')[0]
            next_run = job.next_run_time
            
            if category not in next_runs or (next_run and next_run < next_runs[category]):
                next_runs[category] = next_run
            
            jobs_info.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
                "category": category
            })
        
        return {
            "is_running": True,
            "total_jobs": len(jobs_info),
            "next_runs_by_category": {
                cat: next_run.isoformat() if next_run else None 
                for cat, next_run in next_runs.items()
            },
            "category_priorities": self.category_priorities,
            "refresh_stats": self.refresh_stats,
            "all_jobs": jobs_info
        }
    
    def get_today_schedule(self) -> List[Dict]:
        """Get today's complete refresh schedule sorted by time"""
        schedule = []
        
        for category, config in self.category_priorities.items():
            priority = config["priority"]
            for time_slot in config["times"]:
                schedule.append({
                    "time": time_slot,
                    "category": category,
                    "priority": priority,
                    "frequency": f"{config['frequency']}x/day"
                })
        
        # Sort by time
        schedule.sort(key=lambda x: x["time"])
        return schedule
    
    async def manual_refresh_category(self, category: str) -> bool:
        """Manually trigger refresh for a specific category"""
        if category not in self.category_priorities:
            logger.error(f"❌ Unknown category: {category}")
            return False
        
        logger.info(f"🔄 Manual refresh triggered for {category}")
        return await self.fetch_category_news(category, "MANUAL")
    
    async def manual_refresh_priority(self, priority: str) -> Dict:
        """Manually refresh all categories of a specific priority"""
        if priority not in ["high", "medium", "low"]:
            return {"error": "Invalid priority. Use: high, medium, low"}
        
        categories = [
            cat for cat, config in self.category_priorities.items() 
            if config["priority"] == priority
        ]
        
        results = {}
        for category in categories:
            results[category] = await self.manual_refresh_category(category)
        
        return {
            "priority": priority,
            "categories_refreshed": categories,
            "results": results,
            "successful": sum(1 for success in results.values() if success),
            "failed": sum(1 for success in results.values() if not success)
        }

# Global smart scheduler instance
smart_scheduler = SmartNewsScheduler()