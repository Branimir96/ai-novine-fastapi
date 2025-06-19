from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import datetime

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Basic admin dashboard"""
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "title": "AI Novine - Admin Dashboard",
        "scheduler_status": {
            "is_running": False,
            "jobs": [],
            "cache_status": {
                "Hrvatska": {"cached": False, "articles_count": 0, "last_updated": None},
                "Svijet": {"cached": False, "articles_count": 0, "last_updated": None},
                "Ekonomija": {"cached": False, "articles_count": 0, "last_updated": None},
                "Sport": {"cached": False, "articles_count": 0, "last_updated": None},
                "Regija": {"cached": False, "articles_count": 0, "last_updated": None}
            }
        },
        "recent_tasks": [],
        "current_time": datetime.datetime.now()
    })

@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get basic scheduler status"""
    return {
        "is_running": False,
        "jobs": [],
        "message": "Scheduler not yet enabled - basic version running"
    }

@router.get("/cache-status")
async def get_cache_status():
    """Get basic cache status"""
    categories = ["Hrvatska", "Svijet", "Ekonomija", "Sport", "Regija"]
    cache_status = {}
    
    for category in categories:
        cache_status[category] = {
            "cached": False,
            "articles_count": 0,
            "last_updated": None,
            "age_minutes": None
        }
    
    return {
        "cache_status": cache_status,
        "scheduler_running": False,
        "total_cached_articles": 0
    }