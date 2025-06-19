import asyncio
import datetime
import logging
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import json

from app.services.news_service import generiraj_vijesti, parse_news_content

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TaskResult:
    """Represents the result of a background task"""
    task_id: str
    category: str
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    status: str = "running"  # running, completed, failed
    articles_count: int = 0
    error_message: Optional[str] = None
    execution_time: Optional[float] = None

class NewsScheduler:
    """Advanced news scheduling service with monitoring and logging"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone='Europe/Zagreb')
        self.task_history: List[TaskResult] = []
        self.is_running = False
        self.news_cache = {}
        self.cache_timestamps = {}
        
        # Configure scheduler event listeners
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
        
        # Categories to fetch
        self.categories = ["Hrvatska", "Svijet", "Ekonomija", "Sport", "Regija"]
        
        # Load task history from file if exists
        self._load_task_history()
    
    def _job_executed(self, event):
        """Handle successful job execution"""
        logger.info(f"Job {event.job_id} executed successfully")
    
    def _job_error(self, event):
        """Handle job execution errors"""
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    
    def _save_task_history(self):
        """Save task history to file"""
        try:
            history_data = []
            for task in self.task_history[-100:]:  # Keep last 100 tasks
                history_data.append({
                    'task_id': task.task_id,
                    'category': task.category,
                    'start_time': task.start_time.isoformat(),
                    'end_time': task.end_time.isoformat() if task.end_time else None,
                    'status': task.status,
                    'articles_count': task.articles_count,
                    'error_message': task.error_message,
                    'execution_time': task.execution_time
                })
            
            os.makedirs('logs', exist_ok=True)
            with open('logs/task_history.json', 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save task history: {e}")
    
    def _load_task_history(self):
        """Load task history from file"""
        try:
            if os.path.exists('logs/task_history.json'):
                with open('logs/task_history.json', 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                
                for item in history_data:
                    task = TaskResult(
                        task_id=item['task_id'],
                        category=item['category'],
                        start_time=datetime.datetime.fromisoformat(item['start_time']),
                        end_time=datetime.datetime.fromisoformat(item['end_time']) if item['end_time'] else None,
                        status=item['status'],
                        articles_count=item['articles_count'],
                        error_message=item['error_message'],
                        execution_time=item['execution_time']
                    )
                    self.task_history.append(task)
        except Exception as e:
            logger.error(f"Failed to load task history: {e}")
    
    async def fetch_news_for_category(self, category: str) -> TaskResult:
        """Fetch news for a specific category with full logging"""
        task_id = f"{category}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.datetime.now()
        
        task_result = TaskResult(
            task_id=task_id,
            category=category,
            start_time=start_time
        )
        
        logger.info(f"Starting news fetch for {category} (Task: {task_id})")
        
        try:
            # Fetch news using your existing service
            result, filename = generiraj_vijesti(category)
            
            if result and not result.startswith("Trenutno nije moguće"):
                # Parse articles
                articles = parse_news_content(result)
                articles_count = len(articles)
                
                # Update cache
                self.news_cache[category] = articles
                self.cache_timestamps[category] = datetime.datetime.now()
                
                # Complete task result
                end_time = datetime.datetime.now()
                execution_time = (end_time - start_time).total_seconds()
                
                task_result.end_time = end_time
                task_result.status = "completed"
                task_result.articles_count = articles_count
                task_result.execution_time = execution_time
                
                logger.info(f"Successfully fetched {articles_count} articles for {category} in {execution_time:.2f}s")
                
            else:
                # Handle service unavailable
                end_time = datetime.datetime.now()
                execution_time = (end_time - start_time).total_seconds()
                
                task_result.end_time = end_time
                task_result.status = "failed"
                task_result.error_message = f"Service unavailable: {result}"
                task_result.execution_time = execution_time
                
                logger.warning(f"Failed to fetch news for {category}: Service unavailable")
        
        except Exception as e:
            # Handle unexpected errors
            end_time = datetime.datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            task_result.end_time = end_time
            task_result.status = "failed"
            task_result.error_message = str(e)
            task_result.execution_time = execution_time
            
            logger.error(f"Error fetching news for {category}: {e}")
        
        # Add to history and save
        self.task_history.append(task_result)
        self._save_task_history()
        
        return task_result
    
    async def fetch_all_news(self):
        """Fetch news for all categories"""
        logger.info("Starting scheduled news fetch for all categories")
        start_time = datetime.datetime.now()
        
        tasks = []
        for category in self.categories:
            task = asyncio.create_task(self.fetch_news_for_category(category))
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log summary
        total_time = (datetime.datetime.now() - start_time).total_seconds()
        successful = sum(1 for r in results if isinstance(r, TaskResult) and r.status == "completed")
        failed = len(results) - successful
        total_articles = sum(r.articles_count for r in results if isinstance(r, TaskResult))
        
        logger.info(f"Batch news fetch completed in {total_time:.2f}s: {successful} successful, {failed} failed, {total_articles} total articles")
    
    def start_scheduler(self):
        """Start the background scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        try:
            # Schedule morning news fetch (8:00 AM)
            self.scheduler.add_job(
                self.fetch_all_news,
                CronTrigger(hour=8, minute=0),
                id="morning_news_fetch",
                name="Morning News Fetch (8:00 AM)",
                replace_existing=True
            )
            
            # Schedule evening news fetch (6:00 PM)
            self.scheduler.add_job(
                self.fetch_all_news,
                CronTrigger(hour=18, minute=0),
                id="evening_news_fetch",
                name="Evening News Fetch (6:00 PM)",
                replace_existing=True
            )
            
            # Optional: Add a test job every 30 minutes (you can remove this)
            self.scheduler.add_job(
                self.fetch_all_news,
                CronTrigger(minute="0,30"),
                id="test_news_fetch",
                name="Test News Fetch (Every 30 min)",
                replace_existing=True
            )
            
            self.scheduler.start()
            self.is_running = True
            logger.info("News scheduler started successfully")
            logger.info("Scheduled times: 8:00 AM and 6:00 PM daily")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise
    
    def stop_scheduler(self):
        """Stop the background scheduler"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        try:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("News scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
            raise
    
    def get_scheduler_status(self) -> Dict:
        """Get current scheduler status and job information"""
        jobs = []
        if self.is_running:
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run': next_run.isoformat() if next_run else None,
                    'trigger': str(job.trigger)
                })
        
        return {
            'is_running': self.is_running,
            'jobs': jobs,
            'total_tasks_executed': len(self.task_history),
            'cache_status': {
                category: {
                    'cached': category in self.news_cache,
                    'articles_count': len(self.news_cache.get(category, [])),
                    'last_updated': self.cache_timestamps.get(category, '').isoformat() if self.cache_timestamps.get(category) else None
                } for category in self.categories
            }
        }
    
    def get_recent_tasks(self, limit: int = 20) -> List[Dict]:
        """Get recent task execution history"""
        recent_tasks = self.task_history[-limit:] if self.task_history else []
        return [
            {
                'task_id': task.task_id,
                'category': task.category,
                'start_time': task.start_time.isoformat(),
                'end_time': task.end_time.isoformat() if task.end_time else None,
                'status': task.status,
                'articles_count': task.articles_count,
                'error_message': task.error_message,
                'execution_time': task.execution_time
            } for task in reversed(recent_tasks)
        ]
    
    async def manual_fetch(self, category: str) -> TaskResult:
        """Manually trigger news fetch for a category"""
        logger.info(f"Manual news fetch triggered for {category}")
        return await self.fetch_news_for_category(category)

# Global scheduler instance
news_scheduler = NewsScheduler()