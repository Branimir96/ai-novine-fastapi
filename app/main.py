# Update your app/main.py to include the Technology category

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Import your existing routers
from app.routers import news, admin
from app.services.simple_redis_manager import simple_cache
from app.services.smart_scheduler import smart_scheduler

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown with cache and scheduler"""
    # Startup
    print("🚀 Starting AI Novine FastAPI application...")
    
    try:
        # Connect to cache
        await simple_cache.connect()
        print("✅ Cache system initialized")
        
        # Start the smart scheduler
        smart_scheduler.start_scheduler()
        print("✅ Smart news scheduler started")
        
        # Log the schedule summary with Technology
        schedule_status = smart_scheduler.get_schedule_status()
        if schedule_status["is_running"]:
            print(f"📊 Scheduler running with {schedule_status['total_jobs']} jobs")
            print(f"📅 Categories: Hrvatska, Svijet, Ekonomija, Tehnologija, Sport, Regija")
            
            # Log next runs for each category
            for category, next_run in schedule_status["next_runs_by_category"].items():
                if next_run:
                    next_time = datetime.datetime.fromisoformat(next_run.replace('Z', '+00:00'))
                    print(f"📅 Next {category}: {next_time.strftime('%H:%M')}")
        
    except Exception as e:
        print(f"⚠️ Startup error: {e}")
        print("📝 Continuing with limited functionality...")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down AI Novine FastAPI application...")
    try:
        # Stop the scheduler
        smart_scheduler.stop_scheduler()
        print("✅ Smart scheduler stopped")
        
        # Disconnect cache
        await simple_cache.disconnect()
        print("✅ Cache disconnected cleanly")
    except Exception as e:
        print(f"⚠️ Shutdown error: {e}")

# Create FastAPI app with enhanced functionality
app = FastAPI(
    title="AI Novine",
    description="Croatian News Portal with Smart Scheduling, Redis Caching & Technology News",
    version="2.4.0",  # Updated version for Technology category
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(news.router)
app.include_router(admin.router)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
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
    
    # Get cache statistics - updated with Technology
    cache_stats = simple_cache.get_stats()
    
    # Count cached articles - updated with Technology
    total_cached = 0
    categories = ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"]
    for category in categories:
        cached_news = await simple_cache.get_news(category)
        if cached_news:
            total_cached += len(cached_news)
    
    # Get scheduler status
    scheduler_status = smart_scheduler.get_schedule_status()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "AI Novine - Početna stranica",
        "current_date": current_date,
        "current_time": current_time,
        "scheduler_running": scheduler_status["is_running"],
        "total_cached_articles": total_cached,
        "redis_connected": cache_stats["connected"],
        "cache_hit_rate": cache_stats["hit_rate"],
        "scheduler_stats": smart_scheduler.refresh_stats,
        "categories_count": 6,  # Updated to 6 categories
        "new_category": "Tehnologija"  # Highlight new category
    })

@app.get("/health")
async def health_check():
    """Health check with cache and scheduler status - updated for Technology"""
    cache_stats = simple_cache.get_stats()
    scheduler_status = smart_scheduler.get_schedule_status()
    
    return {
        "status": "healthy", 
        "message": "AI Novine FastAPI with smart scheduling and Technology news is running!",
        "categories": ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"],
        "cache": cache_stats,
        "scheduler": {
            "running": scheduler_status["is_running"],
            "jobs": scheduler_status.get("total_jobs", 0),
            "stats": smart_scheduler.refresh_stats
        }
    }

# New endpoints for scheduler management - updated for Technology
@app.get("/scheduler/status")
async def get_detailed_scheduler_status():
    """Get detailed scheduler status and statistics - includes Technology"""
    return smart_scheduler.get_schedule_status()

@app.get("/scheduler/today-schedule")
async def get_today_schedule():
    """Get today's complete refresh schedule - includes Technology"""
    return {
        "schedule": smart_scheduler.get_today_schedule(),
        "total_refreshes_today": sum(
            config["frequency"] for config in smart_scheduler.category_priorities.values()
        ),
        "current_time": datetime.datetime.now().strftime("%H:%M"),
        "timezone": "Europe/Zagreb",
        "categories": list(smart_scheduler.category_priorities.keys())
    }

@app.post("/scheduler/refresh/{category}")
async def manual_refresh_category(category: str):
    """Manually trigger refresh for a specific category - supports Technology"""
    if category not in smart_scheduler.category_priorities:
        return {
            "error": f"Unknown category: {category}",
            "available_categories": list(smart_scheduler.category_priorities.keys())
        }
    
    success = await smart_scheduler.manual_refresh_category(category)
    return {
        "category": category,
        "success": success,
        "message": f"Manual refresh {'successful' if success else 'failed'} for {category}",
        "timestamp": datetime.datetime.now().isoformat()
    }

@app.post("/scheduler/refresh-priority/{priority}")
async def manual_refresh_priority(priority: str):
    """Manually refresh all categories of a specific priority - includes Technology in medium"""
    result = await smart_scheduler.manual_refresh_priority(priority)
    return result

@app.get("/scheduler/stats")
async def get_scheduler_statistics():
    """Get detailed scheduler statistics and performance metrics - includes Technology"""
    stats = smart_scheduler.refresh_stats
    status = smart_scheduler.get_schedule_status()
    
    return {
        "refresh_statistics": stats,
        "scheduler_status": status["is_running"],
        "total_jobs": status.get("total_jobs", 0),
        "categories": list(smart_scheduler.category_priorities.keys()),
        "success_rate": (
            stats["successful_refreshes"] / max(stats["total_refreshes"], 1) * 100
            if stats["total_refreshes"] > 0 else 0
        ),
        "category_performance": {
            cat: {
                **stats["category_stats"][cat],
                "success_rate": (
                    stats["category_stats"][cat]["success"] / 
                    max(stats["category_stats"][cat]["success"] + stats["category_stats"][cat]["failed"], 1) * 100
                )
            }
            for cat in stats["category_stats"]
        }
    }

@app.get("/test-news")
async def test_news():
    """Test news service with cache info - includes Technology testing"""
    try:
        from app.services.news_service import generiraj_vijesti
        
        # Test basic news fetching for all categories
        categories = ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"]
        test_results = {}
        
        for category in categories:
            try:
                result, filename = generiraj_vijesti(category)
                test_results[category] = {
                    "status": "success" if result and not result.startswith("Trenutno nije moguće") else "failed",
                    "has_content": bool(result)
                }
            except Exception as e:
                test_results[category] = {"status": "error", "error": str(e)}
        
        # Get cache stats
        cache_stats = simple_cache.get_stats()
        
        return {
            "status": "success", 
            "message": "News service test completed!", 
            "category_results": test_results,
            "cache_stats": cache_stats
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/cache-stats")
async def cache_stats():
    """Get detailed cache statistics - includes Technology"""
    stats = simple_cache.get_stats()
    
    # Get cache status for all categories including Technology
    categories = ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"]
    category_status = {}
    
    for category in categories:
        cached_articles = await simple_cache.get_news(category)
        cache_timestamp = await simple_cache.get_timestamp(category)
        
        category_status[category] = {
            "has_cache": cached_articles is not None,
            "article_count": len(cached_articles) if cached_articles else 0,
            "last_cached": cache_timestamp.isoformat() if cache_timestamp else None
        }
    
    return {
        "cache_stats": stats,
        "categories": category_status,
        "total_categories": len(categories),
        "timestamp": datetime.datetime.now().isoformat()
    }

# Technology-specific endpoints
@app.get("/api/technology-sources")
async def get_technology_sources():
    """Get list of technology news sources"""
    from app.services.news_service import RSS_FEEDS
    
    tech_feeds = RSS_FEEDS.get("Tehnologija", [])
    
    return {
        "category": "Tehnologija",
        "sources": tech_feeds,
        "source_count": len(tech_feeds),
        "description": "International technology news sources translated to Croatian"
    }

@app.get("/api/category-info/{category}")
async def get_category_info(category: str):
    """Get detailed information about a specific category"""
    category_info = {
        "Hrvatska": {
            "description": "Najnovije vijesti iz domaćih medija",
            "language": "Croatian",
            "priority": "high",
            "frequency": "6x/day"
        },
        "Svijet": {
            "description": "Međunarodne vijesti prevedene na hrvatski",
            "language": "English → Croatian",
            "priority": "high",
            "frequency": "6x/day"
        },
        "Ekonomija": {
            "description": "Poslovne i ekonomske vijesti",
            "language": "English → Croatian",
            "priority": "medium",
            "frequency": "4x/day"
        },
        "Tehnologija": {
            "description": "Najnoviji tehnološki trendovi i inovacije",
            "language": "English → Croatian",
            "priority": "medium",
            "frequency": "4x/day"
        },
        "Sport": {
            "description": "Sportske vijesti iz Hrvatske i svijeta",
            "language": "Mixed → Croatian",
            "priority": "medium",
            "frequency": "4x/day"
        },
        "Regija": {
            "description": "Najvažnije vijesti iz susjednih zemalja",
            "language": "Mixed → Croatian",
            "priority": "low",
            "frequency": "1x/day"
        }
    }
    
    if category.capitalize() not in category_info:
        return {"error": f"Unknown category: {category}"}
    
    return {
        "category": category.capitalize(),
        "info": category_info[category.capitalize()],
        "available_categories": list(category_info.keys())
    }