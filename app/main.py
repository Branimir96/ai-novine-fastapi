# Safer version of app/main.py with better error handling

from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import datetime
import traceback
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Import your existing routers
from app.routers import news, admin

# Load environment variables
load_dotenv()

# Global variables to track service status
cache_available = False
scheduler_available = False
simple_cache = None
smart_scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown with better error handling"""
    global cache_available, scheduler_available, simple_cache, smart_scheduler
    
    # Startup
    print("🚀 Starting AI Novine FastAPI application...")
    
    # Try to import and connect to cache
    try:
        from app.services.simple_redis_manager import simple_cache as cache_service
        simple_cache = cache_service
        await simple_cache.connect()
        cache_available = True
        print("✅ Cache system initialized successfully")
    except Exception as e:
        cache_available = False
        print(f"⚠️ Cache system failed to initialize: {e}")
        print("📝 Continuing without cache (data will be fetched fresh each time)")
    
    # Try to import and start scheduler
    try:
        from app.services.smart_scheduler import smart_scheduler as scheduler_service
        smart_scheduler = scheduler_service
        smart_scheduler.start_scheduler()
        scheduler_available = True
        print("✅ Smart news scheduler started successfully")
        
        # Log the schedule summary
        if scheduler_available:
            schedule_status = smart_scheduler.get_schedule_status()
            if schedule_status["is_running"]:
                print(f"📊 Scheduler running with {schedule_status['total_jobs']} jobs")
                print(f"📅 Categories: Hrvatska, Svijet, Ekonomija, Tehnologija, Sport, Regija")
    except Exception as e:
        scheduler_available = False
        print(f"⚠️ Smart scheduler failed to start: {e}")
        print("📝 Continuing without automatic scheduling")
    
    if not cache_available and not scheduler_available:
        print("⚠️ Both cache and scheduler failed - running in minimal mode")
        print("📝 News will be fetched fresh on each request")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down AI Novine FastAPI application...")
    try:
        if scheduler_available and smart_scheduler:
            smart_scheduler.stop_scheduler()
            print("✅ Smart scheduler stopped")
    except Exception as e:
        print(f"⚠️ Scheduler shutdown error: {e}")
    
    try:
        if cache_available and simple_cache:
            await simple_cache.disconnect()
            print("✅ Cache disconnected cleanly")
    except Exception as e:
        print(f"⚠️ Cache disconnect error: {e}")

# Create FastAPI app with enhanced functionality
app = FastAPI(
    title="AI Novine",
    description="Croatian News Portal with Smart Scheduling, Redis Caching & Technology News",
    version="2.5.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(news.router)
app.include_router(admin.router)

def calculate_portal_statistics():
    """Calculate dynamic portal statistics with error handling"""
    try:
        # Default values
        categories_count = 6  # We know this is always 6
        total_sources = 54   # Approximate count
        daily_refreshes = 25 # We know this from our configuration
        scheduler_running = False
        total_jobs = 0
        
        # Try to get real scheduler data
        if scheduler_available and smart_scheduler:
            try:
                categories_count = len(smart_scheduler.category_priorities)
                daily_refreshes = sum(
                    config["frequency"] for config in smart_scheduler.category_priorities.values()
                )
                schedule_status = smart_scheduler.get_schedule_status()
                scheduler_running = schedule_status["is_running"]
                total_jobs = schedule_status.get("total_jobs", 0)
            except Exception as e:
                print(f"Warning: Could not get scheduler stats: {e}")
        
        # Try to get real source count
        try:
            from app.services.news_service import RSS_FEEDS
            total_sources = sum(len(feeds) for feeds in RSS_FEEDS.values())
        except Exception as e:
            print(f"Warning: Could not count RSS sources: {e}")
            total_sources = 54  # Fallback value
        
        return {
            "categories_count": categories_count,
            "total_sources": total_sources,
            "daily_refreshes": daily_refreshes,
            "scheduler_running": scheduler_running,
            "total_jobs": total_jobs
        }
    
    except Exception as e:
        print(f"Error calculating portal statistics: {e}")
        # Return safe default values
        return {
            "categories_count": 6,
            "total_sources": 54,
            "daily_refreshes": 25,
            "scheduler_running": False,
            "total_jobs": 0
        }

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with safe error handling"""
    try:
        # Get current date and time
        now = datetime.datetime.now()
        current_date = now.strftime("%A, %d.%m.%Y")
        current_time = now.strftime("%H:%M")
        
        # Translate day names to Croatian
        day_names = {
            "Monday": "Ponedjeljak", "Tuesday": "Utorak", "Wednesday": "Srijeda", 
            "Thursday": "Četvrtak", "Friday": "Petak", "Saturday": "Subota", "Sunday": "Nedjelja"
        }
        day_name = day_names.get(now.strftime("%A"), now.strftime("%A"))
        current_date = f"{day_name}, {now.strftime('%d.%m.%Y')}"
        
        # Safe cache statistics
        cache_stats = {"connected": False, "hit_rate": 0}
        if cache_available and simple_cache:
            try:
                cache_stats = simple_cache.get_stats()
            except Exception as e:
                print(f"Warning: Could not get cache stats: {e}")
        
        # Safe cache article counting
        total_cached = 0
        categories = ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"]
        category_cache_status = {}
        
        if cache_available and simple_cache:
            for category in categories:
                try:
                    cached_news = await simple_cache.get_news(category)
                    count = len(cached_news) if cached_news else 0
                    total_cached += count
                    category_cache_status[category] = {
                        "has_cache": cached_news is not None,
                        "count": count
                    }
                except Exception as e:
                    print(f"Warning: Could not get cache for {category}: {e}")
                    category_cache_status[category] = {
                        "has_cache": False,
                        "count": 0
                    }
        else:
            # No cache available - set all to empty
            for category in categories:
                category_cache_status[category] = {
                    "has_cache": False,
                    "count": 0
                }
        
        # Safe scheduler status
        scheduler_stats = {
            "total_refreshes": 0,
            "successful_refreshes": 0,
            "failed_refreshes": 0
        }
        success_rate = 0
        total_jobs = 0
        
        if scheduler_available and smart_scheduler:
            try:
                scheduler_stats = smart_scheduler.refresh_stats
                if scheduler_stats["total_refreshes"] > 0:
                    success_rate = (scheduler_stats["successful_refreshes"] / scheduler_stats["total_refreshes"]) * 100
                
                schedule_status = smart_scheduler.get_schedule_status()
                total_jobs = schedule_status.get("total_jobs", 0)
            except Exception as e:
                print(f"Warning: Could not get scheduler stats: {e}")
        
        # Calculate dynamic portal statistics
        portal_stats = calculate_portal_statistics()
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "title": "AI Novine - Početna stranica",
            "current_date": current_date,
            "current_time": current_time,
            
            # Dynamic Portal Statistics
            "categories_count": portal_stats["categories_count"],
            "total_sources": portal_stats["total_sources"], 
            "daily_refreshes": portal_stats["daily_refreshes"],
            "scheduler_running": portal_stats["scheduler_running"],
            
            # Cache and Performance Data
            "total_cached_articles": total_cached,
            "category_cache_status": category_cache_status,
            "redis_connected": cache_stats["connected"],
            "cache_hit_rate": cache_stats["hit_rate"],
            
            # Scheduler Performance
            "scheduler_stats": scheduler_stats,
            "success_rate": round(success_rate, 1),
            "total_jobs": total_jobs,
            
            # Service Status
            "cache_available": cache_available,
            "scheduler_available": scheduler_available,
            
            # Additional useful data
            "categories_list": categories,
            "ai_enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
            "last_updated": now.isoformat()
        })
    
    except Exception as e:
        print(f"Error in home route: {e}")
        traceback.print_exc()
        
        # Return minimal safe template
        return templates.TemplateResponse("index.html", {
            "request": request,
            "title": "AI Novine - Početna stranica",
            "current_date": datetime.datetime.now().strftime('%d.%m.%Y'),
            "current_time": datetime.datetime.now().strftime('%H:%M'),
            
            # Safe default values
            "categories_count": 6,
            "total_sources": 54,
            "daily_refreshes": 25,
            "scheduler_running": False,
            "total_cached_articles": 0,
            "category_cache_status": {cat: {"has_cache": False, "count": 0} for cat in ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"]},
            "redis_connected": False,
            "cache_hit_rate": 0,
            "scheduler_stats": {"total_refreshes": 0, "successful_refreshes": 0, "failed_refreshes": 0},
            "success_rate": 0,
            "total_jobs": 0,
            "cache_available": False,
            "scheduler_available": False,
            "categories_list": ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"],
            "ai_enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
            "last_updated": datetime.datetime.now().isoformat(),
            "error_mode": True
        })

@app.get("/health")
async def health_check():
    """Health check with service status"""
    try:
        portal_stats = calculate_portal_statistics()
        
        health_status = {
            "status": "healthy" if (cache_available or scheduler_available) else "degraded",
            "message": "AI Novine is running",
            "services": {
                "cache": "available" if cache_available else "unavailable",
                "scheduler": "available" if scheduler_available else "unavailable",
                "ai": "enabled" if os.getenv("ANTHROPIC_API_KEY") else "disabled"
            },
            "portal_statistics": portal_stats,
            "categories": ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"]
        }
        
        if cache_available and simple_cache:
            try:
                cache_stats = simple_cache.get_stats()
                health_status["cache_stats"] = cache_stats
            except:
                pass
        
        if scheduler_available and smart_scheduler:
            try:
                scheduler_status = smart_scheduler.get_schedule_status()
                health_status["scheduler_status"] = {
                    "running": scheduler_status["is_running"],
                    "jobs": scheduler_status.get("total_jobs", 0)
                }
            except:
                pass
        
        return health_status
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Health check failed: {str(e)}",
            "services": {
                "cache": "error",
                "scheduler": "error", 
                "ai": "unknown"
            }
        }

@app.get("/api/portal-statistics")
async def get_portal_statistics():
    """Get real-time portal statistics with error handling"""
    try:
        portal_stats = calculate_portal_statistics()
        
        # Safe cache data
        total_cached_articles = 0
        cached_categories = 0
        cache_hit_rate = 0
        
        if cache_available and simple_cache:
            try:
                categories = ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"]
                for category in categories:
                    try:
                        cached_news = await simple_cache.get_news(category)
                        if cached_news:
                            total_cached_articles += len(cached_news)
                            cached_categories += 1
                    except:
                        continue
                
                cache_stats = simple_cache.get_stats()
                cache_hit_rate = cache_stats["hit_rate"]
            except Exception as e:
                print(f"Warning: Cache stats error in API: {e}")
        
        # Safe performance data
        performance_data = {
            "total_refreshes": 0,
            "successful_refreshes": 0,
            "success_rate": 0
        }
        
        if scheduler_available and smart_scheduler:
            try:
                stats = smart_scheduler.refresh_stats
                performance_data = {
                    "total_refreshes": stats["total_refreshes"],
                    "successful_refreshes": stats["successful_refreshes"],
                    "success_rate": (
                        stats["successful_refreshes"] / 
                        max(stats["total_refreshes"], 1) * 100
                    )
                }
            except Exception as e:
                print(f"Warning: Scheduler stats error in API: {e}")
        
        return {
            "portal_statistics": portal_stats,
            "cache_statistics": {
                "total_cached_articles": total_cached_articles,
                "cached_categories": cached_categories,
                "cache_hit_rate": cache_hit_rate,
                "cache_available": cache_available
            },
            "performance": performance_data,
            "services": {
                "cache_available": cache_available,
                "scheduler_available": scheduler_available
            },
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    except Exception as e:
        print(f"Error in portal statistics API: {e}")
        return {
            "error": "Could not retrieve statistics",
            "portal_statistics": {
                "categories_count": 6,
                "total_sources": 54,
                "daily_refreshes": 25,
                "scheduler_running": False,
                "total_jobs": 0
            },
            "timestamp": datetime.datetime.now().isoformat()
        }

# Error handlers
@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    print(f"Internal Server Error: {exc}")
    traceback.print_exc()
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error": "Interna greška servera. Molimo pokušajte kasnije."
    }, status_code=500)

@app.exception_handler(404)
async def not_found_error_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error": "Stranica nije pronađena."
    }, status_code=404)

# Continue with your existing endpoints but with error handling...
# (The rest of your endpoints would go here with similar error handling patterns)