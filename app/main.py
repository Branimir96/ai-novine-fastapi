# Fixed main.py - removed dynamic statistics that were causing zeros

from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import datetime
import traceback
from contextlib import asynccontextmanager  # Fixed import
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
    
    # Try to import and start scheduler
    try:
        from app.services.smart_scheduler import smart_scheduler as scheduler_service
        smart_scheduler = scheduler_service
        smart_scheduler.start_scheduler()
        scheduler_available = True
        print("✅ Smart news scheduler started successfully")
    except Exception as e:
        scheduler_available = False
        print(f"⚠️ Smart scheduler failed to start: {e}")
    
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

# Create FastAPI app
app = FastAPI(
    title="AI Novine",
    description="Croatian News Portal with Smart Scheduling, Redis Caching & Technology News",
    version="2.5.3",
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
    """Home page with simplified template data - no dynamic statistics"""
    
    print("\n🏠 Home route called...")
    
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
        
        # Safe cache article counting for category status only
        categories = ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"]
        category_cache_status = {}
        
        for category in categories:
            try:
                if cache_available and simple_cache:
                    cached_news = await simple_cache.get_news(category)
                    count = len(cached_news) if cached_news else 0
                    category_cache_status[category] = {
                        "has_cache": cached_news is not None,
                        "count": count
                    }
                else:
                    category_cache_status[category] = {"has_cache": False, "count": 0}
            except Exception as e:
                print(f"Warning: Could not get cache for {category}: {e}")
                category_cache_status[category] = {"has_cache": False, "count": 0}
        
        # MINIMAL template data - no dynamic statistics that could show zeros
        template_data = {
            "request": request,
            "title": "AI Novine - Početna stranica",
            "current_date": current_date,
            "current_time": current_time,
            
            # Only category cache status - no main statistics
            "category_cache_status": category_cache_status,
            
            # Service status (not displayed in template)
            "cache_available": cache_available,
            "scheduler_available": scheduler_available,
            "ai_enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
            "last_updated": now.isoformat()
        }
        
        print(f"✅ Template data prepared successfully")
        return templates.TemplateResponse("index.html", template_data)
    
    except Exception as e:
        print(f"❌ Error in home route: {e}")
        traceback.print_exc()
        
        # Emergency fallback - minimal data
        return templates.TemplateResponse("index.html", {
            "request": request,
            "title": "AI Novine - Početna stranica",
            "current_date": datetime.datetime.now().strftime('%d.%m.%Y'),
            "current_time": datetime.datetime.now().strftime('%H:%M'),
            "category_cache_status": {cat: {"has_cache": False, "count": 0} for cat in ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"]},
            "cache_available": False,
            "scheduler_available": False,
            "ai_enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
            "last_updated": datetime.datetime.now().isoformat(),
            "error_mode": True
        })

@app.get("/health")
async def health_check():
    """Health check with service status"""
    try:
        return {
            "status": "healthy",
            "message": "AI Novine is running",
            "services": {
                "cache": "available" if cache_available else "unavailable",
                "scheduler": "available" if scheduler_available else "unavailable",
                "ai": "enabled" if os.getenv("ANTHROPIC_API_KEY") else "disabled"
            },
            "categories": ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"]
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Health check failed: {str(e)}"
        }