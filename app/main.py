from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Import your routers
from app.routers import news, admin
from app.services.simple_redis_manager import simple_cache

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown with cache"""
    # Startup
    print("🚀 Starting AI Novine FastAPI application...")
    
    try:
        # Connect to cache
        await simple_cache.connect()
        print("✅ Cache system initialized")
        
    except Exception as e:
        print(f"⚠️ Cache startup error: {e}")
        print("📝 Continuing without cache...")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down AI Novine FastAPI application...")
    try:
        await simple_cache.disconnect()
        print("✅ Cache disconnected cleanly")
    except Exception as e:
        print(f"⚠️ Cache shutdown error: {e}")

# Create FastAPI app with cache lifespan management
app = FastAPI(
    title="AI Novine",
    description="Croatian News Portal with Redis Caching",
    version="2.1.0",
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
    
    # Get cache statistics
    cache_stats = simple_cache.get_stats()
    
    # Count cached articles
    total_cached = 0
    categories = ["Hrvatska", "Svijet", "Ekonomija", "Sport", "Regija"]
    for category in categories:
        cached_news = await simple_cache.get_news(category)
        if cached_news:
            total_cached += len(cached_news)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "AI Novine - Početna stranica",
        "current_date": current_date,
        "current_time": current_time,
        "scheduler_running": False,  # We'll add scheduler later
        "total_cached_articles": total_cached,
        "redis_connected": cache_stats["connected"],
        "cache_hit_rate": cache_stats["hit_rate"]
    })

@app.get("/health")
async def health_check():
    """Health check with cache status"""
    cache_stats = simple_cache.get_stats()
    
    return {
        "status": "healthy", 
        "message": "AI Novine FastAPI with caching is running!",
        "cache": cache_stats,
        "timestamp": datetime.datetime.now().isoformat()
    }

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

@app.get("/cache-stats")
async def cache_stats():
    """Get detailed cache statistics"""
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
        "timestamp": datetime.datetime.now().isoformat()
    }