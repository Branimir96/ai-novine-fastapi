from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import datetime
from typing import Optional, List

from app.services.fallback_redis_manager import fallback_redis_manager as redis_manager
from app.services.redis_scheduler import redis_news_scheduler

router = APIRouter(prefix="/admin", tags=["redis-admin"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/redis", response_class=HTMLResponse)
async def redis_admin_dashboard(request: Request):
    """Redis admin dashboard with cache analytics and controls"""
    scheduler_status = await redis_news_scheduler.get_scheduler_status()
    recent_tasks = redis_news_scheduler.get_recent_tasks(10)
    redis_stats = await redis_manager.get_stats()
    key_details = await redis_manager.get_key_details()
    cache_health = await redis_manager.health_check()
    
    return templates.TemplateResponse("redis_admin.html", {
        "request": request,
        "title": "AI Novine - Redis Admin",
        "scheduler_status": scheduler_status,
        "recent_tasks": recent_tasks,
        "redis_stats": redis_stats,
        "key_details": key_details,
        "cache_health": cache_health,
        "current_time": datetime.datetime.now()
    })

@router.get("/redis/stats")
async def get_redis_stats():
    """Get comprehensive Redis statistics"""
    try:
        stats = await redis_manager.get_stats()
        health = await redis_manager.health_check()
        key_details = await redis_manager.get_key_details()
        
        return {
            "stats": stats.__dict__,
            "health": health,
            "key_count": len(key_details),
            "keys": key_details,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Redis stats: {str(e)}")

@router.get("/redis/keys")
async def get_redis_keys():
    """Get detailed information about all Redis keys"""
    try:
        key_details = await redis_manager.get_key_details()
        
        return {
            "keys": key_details,
            "total_keys": len(key_details),
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Redis keys: {str(e)}")

@router.post("/redis/cache/warm")
async def warm_cache(
    categories: Optional[List[str]] = None, 
    background_tasks: BackgroundTasks = None
):
    """Warm cache by pre-loading fresh content"""
    try:
        categories = categories or redis_news_scheduler.categories
        
        # Validate categories
        invalid_categories = [cat for cat in categories if cat not in redis_news_scheduler.categories]
        if invalid_categories:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid categories: {invalid_categories}"
            )
        
        # Start cache warming in background
        if background_tasks:
            background_tasks.add_task(redis_news_scheduler.warm_cache, categories)
        else:
            await redis_news_scheduler.warm_cache(categories)
        
        return {
            "status": "success",
            "message": f"Cache warming started for {len(categories)} categories",
            "categories": categories
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to warm cache: {str(e)}")

@router.delete("/redis/cache/{category}")
async def clear_category_cache(category: str):
    """Clear Redis cache for a specific category"""
    try:
        if category.capitalize() not in redis_news_scheduler.categories:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        
        cleared = await redis_news_scheduler.clear_category_cache(category.capitalize())
        
        return {
            "status": "success" if cleared else "info",
            "message": f"Cache cleared for {category.capitalize()}" if cleared else f"No cache found for {category.capitalize()}",
            "category": category.capitalize(),
            "was_cached": cleared
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@router.delete("/redis/cache/all")
async def clear_all_cache():
    """Clear all Redis cache"""
    try:
        cleared = await redis_news_scheduler.clear_all_cache()
        
        return {
            "status": "success" if cleared else "info",
            "message": "All cache cleared" if cleared else "No cache found to clear",
            "categories": redis_news_scheduler.categories
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear all cache: {str(e)}")

@router.delete("/redis/keys/pattern/{pattern}")
async def clear_keys_by_pattern(pattern: str):
    """Clear Redis keys matching a pattern"""
    try:
        deleted_count = await redis_manager.clear_pattern(pattern)
        
        return {
            "status": "success",
            "message": f"Cleared {deleted_count} keys matching pattern: {pattern}",
            "deleted_count": deleted_count,
            "pattern": pattern
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear keys: {str(e)}")

@router.get("/redis/health")
async def redis_health_check():
    """Redis health check endpoint"""
    try:
        health = await redis_manager.health_check()
        stats = await redis_manager.get_stats()
        
        return {
            "health": health,
            "stats": {
                "total_keys": stats.total_keys,
                "memory_usage": stats.memory_usage,
                "hit_rate": stats.hit_rate,
                "uptime_seconds": stats.uptime_seconds
            },
            "scheduler_running": redis_news_scheduler.is_running,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "health": {
                "status": "error",
                "redis_connected": False,
                "error": str(e)
            },
            "timestamp": datetime.datetime.now().isoformat()
        }

@router.get("/redis/metrics/daily")
async def get_daily_metrics(date: Optional[str] = None):
    """Get daily metrics for cache operations"""
    try:
        if date:
            try:
                date_obj = datetime.datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            date_obj = None
        
        metrics = await redis_news_scheduler.get_daily_metrics(date_obj)
        
        return {
            "metrics": metrics,
            "date": metrics.get('date', 'unknown')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get daily metrics: {str(e)}")

@router.get("/redis/analytics")
async def get_cache_analytics():
    """Get comprehensive cache analytics"""
    try:
        # Get current stats
        stats = await redis_manager.get_stats()
        health = await redis_manager.health_check()
        
        # Get recent tasks with cache usage
        recent_tasks = redis_news_scheduler.get_recent_tasks(50)
        
        # Calculate cache effectiveness
        cache_tasks = [t for t in recent_tasks if t.get('cache_used')]
        fresh_tasks = [t for t in recent_tasks if not t.get('cache_used')]
        
        cache_hit_rate = len(cache_tasks) / len(recent_tasks) * 100 if recent_tasks else 0
        
        # Average execution times
        cache_avg_time = sum(t.get('execution_time', 0) for t in cache_tasks) / len(cache_tasks) if cache_tasks else 0
        fresh_avg_time = sum(t.get('execution_time', 0) for t in fresh_tasks) / len(fresh_tasks) if fresh_tasks else 0
        
        # Category breakdown
        category_stats = {}
        for category in redis_news_scheduler.categories:
            category_tasks = [t for t in recent_tasks if t['category'] == category]
            category_cache_tasks = [t for t in category_tasks if t.get('cache_used')]
            
            category_stats[category] = {
                'total_tasks': len(category_tasks),
                'cache_hits': len(category_cache_tasks),
                'cache_hit_rate': len(category_cache_tasks) / len(category_tasks) * 100 if category_tasks else 0,
                'avg_execution_time': sum(t.get('execution_time', 0) for t in category_tasks) / len(category_tasks) if category_tasks else 0
            }
        
        return {
            "redis_stats": stats.__dict__,
            "health": health,
            "cache_effectiveness": {
                "overall_hit_rate": cache_hit_rate,
                "cache_avg_time": cache_avg_time,
                "fresh_avg_time": fresh_avg_time,
                "time_savings": fresh_avg_time - cache_avg_time if fresh_avg_time > cache_avg_time else 0
            },
            "category_breakdown": category_stats,
            "analysis_period": {
                "tasks_analyzed": len(recent_tasks),
                "cache_hits": len(cache_tasks),
                "fresh_fetches": len(fresh_tasks)
            },
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache analytics: {str(e)}")

@router.post("/redis/connection/test")
async def test_redis_connection():
    """Test Redis connection and reconnect if necessary"""
    try:
        # Disconnect and reconnect
        await redis_manager.disconnect()
        await redis_manager.connect()
        
        # Test connection
        health = await redis_manager.health_check()
        
        return {
            "status": "success",
            "message": "Redis connection tested and refreshed",
            "health": health,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to test Redis connection: {str(e)}",
            "timestamp": datetime.datetime.now().isoformat()
        }

@router.get("/redis/memory/usage")
async def get_memory_usage():
    """Get detailed Redis memory usage information"""
    try:
        if not redis_manager.is_connected:
            raise HTTPException(status_code=503, detail="Redis not connected")
        
        # Get Redis info
        info = await redis_manager.async_redis.info("memory")
        
        # Get our key sizes
        key_details = await redis_manager.get_key_details()
        total_our_memory = sum(key.get('size', 0) for key in key_details)
        
        return {
            "redis_memory": {
                "used_memory": info.get('used_memory', 0),
                "used_memory_human": info.get('used_memory_human', 'Unknown'),
                "used_memory_peak": info.get('used_memory_peak', 0),
                "used_memory_peak_human": info.get('used_memory_peak_human', 'Unknown'),
                "maxmemory": info.get('maxmemory', 0),
                "maxmemory_human": info.get('maxmemory_human', 'Unknown') if info.get('maxmemory', 0) > 0 else 'No limit'
            },
            "our_usage": {
                "total_keys": len(key_details),
                "estimated_memory_bytes": total_our_memory,
                "estimated_memory_human": f"{total_our_memory / 1024 / 1024:.2f} MB" if total_our_memory > 0 else "Unknown"
            },
            "key_breakdown": [
                {
                    "key": key['key'],
                    "size_bytes": key.get('size', 0),
                    "size_human": f"{key.get('size', 0) / 1024:.2f} KB" if key.get('size', 0) > 0 else "Unknown"
                }
                for key in sorted(key_details, key=lambda x: x.get('size', 0), reverse=True)
            ],
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get memory usage: {str(e)}")

# Background task functions for async operations
async def trigger_cache_warm(categories: List[str]):
    """Background task to warm cache"""
    try:
        await redis_news_scheduler.warm_cache(categories)
        print(f"Cache warming completed for categories: {categories}")
    except Exception as e:
        print(f"Cache warming failed: {e}")