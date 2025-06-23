from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import datetime

# Import the smart scheduler
from app.services.smart_scheduler import smart_scheduler
from app.services.simple_redis_manager import simple_cache

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Enhanced admin dashboard with smart scheduler integration"""
    
    # Get scheduler status
    scheduler_status = smart_scheduler.get_schedule_status()
    
    # Get cache status for all categories
    categories = ["Hrvatska", "Svijet", "Ekonomija", "Sport", "Regija"]
    cache_status = {}
    
    for category in categories:
        cached_articles = await simple_cache.get_news(category)
        cache_timestamp = await simple_cache.get_timestamp(category)
        
        # Calculate age in minutes
        age_minutes = None
        if cache_timestamp:
            age_delta = datetime.datetime.now() - cache_timestamp
            age_minutes = int(age_delta.total_seconds() / 60)
        
        cache_status[category] = {
            "cached": cached_articles is not None,
            "articles_count": len(cached_articles) if cached_articles else 0,
            "last_updated": cache_timestamp.isoformat() if cache_timestamp else None,
            "age_minutes": age_minutes
        }
    
    # Get recent scheduler tasks (from stats)
    recent_tasks = []
    if scheduler_status["is_running"]:
        for category, stats in smart_scheduler.refresh_stats["category_stats"].items():
            if stats["success"] > 0 or stats["failed"] > 0:
                recent_tasks.append({
                    "category": category,
                    "successful": stats["success"],
                    "failed": stats["failed"],
                    "priority": smart_scheduler.category_priorities[category]["priority"]
                })
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "title": "AI Novine - Admin Dashboard",
        "scheduler_status": scheduler_status,
        "cache_status": cache_status,
        "recent_tasks": recent_tasks,
        "current_time": datetime.datetime.now(),
        "refresh_stats": smart_scheduler.refresh_stats,
        "today_schedule": smart_scheduler.get_today_schedule()
    })

@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get comprehensive scheduler status"""
    return smart_scheduler.get_schedule_status()

@router.get("/cache-status")
async def get_cache_status():
    """Get detailed cache status for all categories"""
    categories = ["Hrvatska", "Svijet", "Ekonomija", "Sport", "Regija"]
    cache_status = {}
    total_articles = 0
    
    for category in categories:
        cached_articles = await simple_cache.get_news(category)
        cache_timestamp = await simple_cache.get_timestamp(category)
        
        # Calculate age in minutes
        age_minutes = None
        if cache_timestamp:
            age_delta = datetime.datetime.now() - cache_timestamp
            age_minutes = int(age_delta.total_seconds() / 60)
        
        article_count = len(cached_articles) if cached_articles else 0
        total_articles += article_count
        
        cache_status[category] = {
            "cached": cached_articles is not None,
            "articles_count": article_count,
            "last_updated": cache_timestamp.isoformat() if cache_timestamp else None,
            "age_minutes": age_minutes,
            "priority": smart_scheduler.category_priorities[category]["priority"],
            "daily_refreshes": smart_scheduler.category_priorities[category]["frequency"]
        }
    
    scheduler_status = smart_scheduler.get_schedule_status()
    
    return {
        "cache_status": cache_status,
        "scheduler_running": scheduler_status["is_running"],
        "total_cached_articles": total_articles,
        "scheduler_stats": smart_scheduler.refresh_stats,
        "cache_stats": simple_cache.get_stats()
    }

@router.get("/smart-schedule")
async def get_smart_schedule():
    """Get today's smart schedule with priorities"""
    return {
        "schedule": smart_scheduler.get_today_schedule(),
        "status": smart_scheduler.get_schedule_status(),
        "category_priorities": smart_scheduler.category_priorities
    }

@router.post("/refresh/{priority}")
async def refresh_by_priority(priority: str):
    """Refresh all categories of a specific priority level"""
    return await smart_scheduler.manual_refresh_priority(priority)

@router.post("/refresh/category/{category}")
async def refresh_category(category: str):
    """Manually refresh a specific category"""
    if category not in smart_scheduler.category_priorities:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown category: {category}. Available: {list(smart_scheduler.category_priorities.keys())}"
        )
    
    success = await smart_scheduler.manual_refresh_category(category)
    return {
        "category": category,
        "success": success,
        "message": f"Manual refresh {'successful' if success else 'failed'} for {category}",
        "priority": smart_scheduler.category_priorities[category]["priority"],
        "timestamp": datetime.datetime.now().isoformat()
    }

@router.get("/scheduler/next-runs")
async def get_next_runs():
    """Get next scheduled runs for all categories"""
    status = smart_scheduler.get_schedule_status()
    
    if not status["is_running"]:
        return {"error": "Scheduler is not running"}
    
    return {
        "next_runs": status["next_runs_by_category"],
        "all_jobs": status["all_jobs"],
        "total_jobs": status["total_jobs"]
    }

@router.get("/scheduler/performance")
async def get_scheduler_performance():
    """Get detailed performance metrics"""
    stats = smart_scheduler.refresh_stats
    
    performance_data = {
        "overall": {
            "total_refreshes": stats["total_refreshes"],
            "successful_refreshes": stats["successful_refreshes"], 
            "failed_refreshes": stats["failed_refreshes"],
            "success_rate": (
                stats["successful_refreshes"] / max(stats["total_refreshes"], 1) * 100
                if stats["total_refreshes"] > 0 else 0
            )
        },
        "by_category": {},
        "by_priority": {"high": {"success": 0, "failed": 0}, "medium": {"success": 0, "failed": 0}, "low": {"success": 0, "failed": 0}}
    }
    
    # Calculate per-category performance
    for category, category_stats in stats["category_stats"].items():
        total_attempts = category_stats["success"] + category_stats["failed"]
        success_rate = (category_stats["success"] / max(total_attempts, 1) * 100) if total_attempts > 0 else 0
        
        priority = smart_scheduler.category_priorities[category]["priority"]
        
        performance_data["by_category"][category] = {
            **category_stats,
            "success_rate": success_rate,
            "priority": priority,
            "daily_frequency": smart_scheduler.category_priorities[category]["frequency"]
        }
        
        # Aggregate by priority
        performance_data["by_priority"][priority]["success"] += category_stats["success"]
        performance_data["by_priority"][priority]["failed"] += category_stats["failed"]
    
    # Calculate priority-level success rates
    for priority_data in performance_data["by_priority"].values():
        total = priority_data["success"] + priority_data["failed"]
        priority_data["success_rate"] = (priority_data["success"] / max(total, 1) * 100) if total > 0 else 0
    
    return performance_data

@router.post("/scheduler/start")
async def start_scheduler():
    """Start the smart scheduler (if stopped)"""
    try:
        if smart_scheduler.is_running:
            return {"message": "Scheduler is already running", "status": "already_running"}
        
        smart_scheduler.start_scheduler()
        return {"message": "Smart scheduler started successfully", "status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scheduler: {str(e)}")

@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the smart scheduler"""
    try:
        if not smart_scheduler.is_running:
            return {"message": "Scheduler is not running", "status": "already_stopped"}
        
        smart_scheduler.stop_scheduler()
        return {"message": "Smart scheduler stopped successfully", "status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop scheduler: {str(e)}")

@router.get("/scheduler/jobs")
async def get_all_jobs():
    """Get detailed information about all scheduled jobs"""
    status = smart_scheduler.get_schedule_status()
    
    if not status["is_running"]:
        return {"error": "Scheduler is not running", "jobs": []}
    
    # Organize jobs by category and priority
    jobs_by_category = {}
    for job in status["all_jobs"]:
        category = job["category"]
        if category not in jobs_by_category:
            jobs_by_category[category] = {
                "priority": smart_scheduler.category_priorities[category]["priority"],
                "frequency": smart_scheduler.category_priorities[category]["frequency"],
                "jobs": []
            }
        jobs_by_category[category]["jobs"].append(job)
    
    return {
        "total_jobs": status["total_jobs"],
        "jobs_by_category": jobs_by_category,
        "scheduler_running": True
    }