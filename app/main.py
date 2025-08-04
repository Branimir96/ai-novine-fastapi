# Update your app/main.py to include the stock API router

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
from app.routers import stock_api  # Add this new import
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
        
        # Check stock API configuration
        alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if alpha_vantage_key:
            print("✅ Alpha Vantage API key configured")
        else:
            print("⚠️ Alpha Vantage API key not found - stock prices will not work")
        
        # Log the schedule summary
        schedule_status = smart_scheduler.get_schedule_status()
        if schedule_status["is_running"]:
            print(f"📊 Scheduler running with {schedule_status['total_jobs']} jobs")
            
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
    description="Croatian News Portal with Smart Scheduling, Redis Caching & Real-time Stock Prices",
    version="2.3.0",  # Updated version
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(news.router)
app.include_router(admin.router)
app.include_router(stock_api.router)  # Add the new stock API router

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
    
    # Get cache statistics
    cache_stats = simple_cache.get_stats()
    
    # Count cached articles
    total_cached = 0
    categories = ["Hrvatska", "Svijet", "Ekonomija", "Sport", "Regija"]
    for category in categories:
        cached_news = await simple_cache.get_news(category)
        if cached_news:
            total_cached += len(cached_news)
    
    # Get scheduler status
    scheduler_status = smart_scheduler.get_schedule_status()
    
    # Check if stock API is configured
    stock_api_configured = bool(os.getenv("ALPHA_VANTAGE_API_KEY"))
    
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
        "stock_api_configured": stock_api_configured  # Add stock API status
    })

@app.get("/health")
async def health_check():
    """Health check with cache, scheduler, and stock API status"""
    cache_stats = simple_cache.get_stats()
    scheduler_status = smart_scheduler.get_schedule_status()
    
    return {
        "status": "healthy", 
        "message": "AI Novine FastAPI with smart scheduling and stock prices is running!",
        "cache": cache_stats,
        "scheduler": {
            "running": scheduler_status["is_running"],
            "jobs": scheduler_status.get("total_jobs", 0),
            "stats": smart_scheduler.refresh_stats
        },
        "stock_api": {
            "configured": bool(os.getenv("ALPHA_VANTAGE_API_KEY")),
            "endpoints": ["/api/stock/{symbol}", "/api/crypto/{symbol}", "/api/prices/all"]
        }
    }

# New endpoints for scheduler management
@app.get("/scheduler/status")
async def get_detailed_scheduler_status():
    """Get detailed scheduler status and statistics"""
    return smart_scheduler.get_schedule_status()

@app.get("/scheduler/today-schedule")
async def get_today_schedule():
    """Get today's complete refresh schedule"""
    return {
        "schedule": smart_scheduler.get_today_schedule(),
        "total_refreshes_today": sum(
            config["frequency"] for config in smart_scheduler.category_priorities.values()
        ),
        "current_time": datetime.datetime.now().strftime("%H:%M"),
        "timezone": "Europe/Zagreb"
    }

@app.post("/scheduler/refresh/{category}")
async def manual_refresh_category(category: str):
    """Manually trigger refresh for a specific category"""
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
    """Manually refresh all categories of a specific priority"""
    result = await smart_scheduler.manual_refresh_priority(priority)
    return result

@app.get("/scheduler/stats")
async def get_scheduler_statistics():
    """Get detailed scheduler statistics and performance metrics"""
    stats = smart_scheduler.refresh_stats
    status = smart_scheduler.get_schedule_status()
    
    return {
        "refresh_statistics": stats,
        "scheduler_status": status["is_running"],
        "total_jobs": status.get("total_jobs", 0),
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

# Financial widget endpoint for easy integration
@app.get("/widget/financial")
async def get_financial_widget(request: Request):
    """Get the financial widget HTML for embedding"""
    return templates.TemplateResponse("financial_widget.html", {
        "request": request,
        "title": "Financial Widget",
        "standalone": True
    })

@app.get("/test-news")
async def test_news():
    """Test news service with cache info"""
    try:
        from app.services.news_service import generiraj_vijesti
        
        # Test basic news fetching
        result, filename = generiraj_vijesti("Hrvatska")
        
        # Get cache stats
        cache_stats = simple_cache.get_stats()
        
        return {
            "status": "success", 
            "message": "News service working!", 
            "has_content": bool(result),
            "cache_stats": cache_stats
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/test-stocks")
async def test_stocks():
    """Test stock API functionality"""
    try:
        alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        
        if not alpha_vantage_key:
            return {
                "status": "error",
                "message": "Alpha Vantage API key not configured",
                "setup_url": "https://www.alphavantage.co/support/#api-key"
            }
        
        # Test a simple stock request
        import aiohttp
        test_url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey={alpha_vantage_key}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(test_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if "Global Quote" in data:
                        return {
                            "status": "success",
                            "message": "Stock API working!",
                            "test_symbol": "AAPL",
                            "api_response": "Valid"
                        }
                    elif "Note" in data:
                        return {
                            "status": "warning",
                            "message": "API rate limit reached - this is normal",
                            "note": data["Note"]
                        }
                    else:
                        return {
                            "status": "error",
                            "message": "Invalid API response",
                            "response": data
                        }
                else:
                    return {
                        "status": "error",
                        "message": f"API returned status {response.status}"
                    }
                    
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/cache-stats")
async def cache_stats():
    """Get detailed cache statistics including stock prices"""
    stats = simple_cache.get_stats()
    
    # Get cache status for all categories
    categories = ["Hrvatska", "Svijet", "Ekonomija", "Sport", "Regija"]
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
        "stock_api_available": bool(os.getenv("ALPHA_VANTAGE_API_KEY")),
        "timestamp": datetime.datetime}