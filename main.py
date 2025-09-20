# Updated main.py with PostgreSQL database integration

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
database_available = False
simple_cache = None
smart_scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown with database support"""
    global cache_available, scheduler_available, database_available, simple_cache, smart_scheduler
    
    # Startup
    print("🚀 Starting AI Novine FastAPI application...")
    
    # Initialize database FIRST
    try:
        from app.models.database import init_database
        db_success = await init_database()
        if db_success:
            database_available = True
            print("✅ PostgreSQL database initialized successfully")
        else:
            database_available = False
            print("⚠️ Database initialization failed, continuing without DB")
    except Exception as e:
        database_available = False
        print(f"⚠️ Database setup error: {e}")
    
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
    
    # Close database connection
    try:
        if database_available:
            from app.models.database import close_database
            await close_database()
            print("✅ Database connection closed")
    except Exception as e:
        print(f"⚠️ Database shutdown error: {e}")
    
    # Stop scheduler
    try:
        if scheduler_available and smart_scheduler:
            smart_scheduler.stop_scheduler()
            print("✅ Smart scheduler stopped")
    except Exception as e:
        print(f"⚠️ Scheduler shutdown error: {e}")
    
    # Disconnect cache
    try:
        if cache_available and simple_cache:
            await simple_cache.disconnect()
            print("✅ Cache disconnected cleanly")
    except Exception as e:
        print(f"⚠️ Cache disconnect error: {e}")

# Create FastAPI app
app = FastAPI(
    title="AI Novine",
    description="Croatian News Portal with Smart Scheduling, PostgreSQL Database & Technology News",
    version="2.6.0",
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
    """Home page with database integration"""
    
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
        
        # Get database statistics if available
        database_stats = {}
        if database_available:
            try:
                from app.services.database_service import db_service
                database_stats = await db_service.get_database_stats()
                print(f"📊 Database stats: {database_stats}")
            except Exception as e:
                print(f"⚠️ Failed to get database stats: {e}")
                database_stats = {"total_articles": 0, "categories": {}, "database_connected": False}
        
        # Safe cache article counting for category status
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
        
        # Template data with database info
        template_data = {
            "request": request,
            "title": "AI Novine - Početna stranica",
            "current_date": current_date,
            "current_time": current_time,
            
            # Category cache status
            "category_cache_status": category_cache_status,
            
            # Database statistics
            "database_stats": database_stats,
            "total_database_articles": database_stats.get("total_articles", 0),
            
            # Service status
            "cache_available": cache_available,
            "scheduler_available": scheduler_available,
            "database_available": database_available,
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
            "database_stats": {"total_articles": 0, "categories": {}, "database_connected": False},
            "total_database_articles": 0,
            "cache_available": False,
            "scheduler_available": False,
            "database_available": False,
            "ai_enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
            "last_updated": datetime.datetime.now().isoformat(),
            "error_mode": True
        })

@app.get("/health")
async def health_check():
    """Detailed health check with database status"""
    try:
        # Test database if available
        database_status = "unavailable"
        database_articles = 0
        
        if database_available:
            try:
                from app.services.database_service import db_service
                db_stats = await db_service.get_database_stats()
                database_status = "connected" if db_stats.get("database_connected") else "error"
                database_articles = db_stats.get("total_articles", 0)
            except Exception as e:
                database_status = f"error: {str(e)}"
        
        # Test cache
        cache_status = "unavailable"
        if cache_available and simple_cache:
            try:
                cache_stats = simple_cache.get_stats()
                cache_status = "connected" if cache_stats.get("connected") else "disconnected"
            except Exception as e:
                cache_status = f"error: {str(e)}"
        
        return {
            "status": "healthy",
            "message": "AI Novine is running",
            "timestamp": datetime.datetime.now().isoformat(),
            "services": {
                "database": database_status,
                "cache": cache_status,
                "scheduler": "available" if scheduler_available else "unavailable",
                "ai": "enabled" if os.getenv("ANTHROPIC_API_KEY") else "disabled"
            },
            "statistics": {
                "database_articles": database_articles,
                "categories_supported": 6
            },
            "categories": ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija"]
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Health check failed: {str(e)}",
            "timestamp": datetime.datetime.now().isoformat()
        }

@app.get("/ping")
async def ping():
    """Simple ping endpoint for monitoring"""
    return {
        "status": "alive",
        "timestamp": datetime.datetime.now().isoformat(),
        "message": "AI Novine server is running!",
        "version": "2.6.0",
        "services": {
            "database": database_available,
            "cache": cache_available,
            "scheduler": scheduler_available
        }
    }

@app.get("/api/database/status")
async def database_status():
    """Get detailed database status"""
    if not database_available:
        return {
            "connected": False,
            "message": "Database not initialized"
        }
    
    try:
        from app.services.database_service import db_service
        stats = await db_service.get_database_stats()
        return {
            "connected": stats.get("database_connected", False),
            "total_articles": stats.get("total_articles", 0),
            "categories": stats.get("categories", {}),
            "message": "Database operational"
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "message": "Database error"
        }