from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from app.services.news_service import generiraj_vijesti, parse_news_content
from app.services.simple_redis_manager import simple_cache
import datetime
import os

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/news/{category}", response_class=HTMLResponse)
async def show_news(request: Request, category: str):
    """Display news for a specific category with caching"""
    try:
        category = category.capitalize()
        
        print(f"📰 Requesting news for: {category}")
        
        # Step 1: Try to get from cache first
        cached_articles = await simple_cache.get_news(category)
        cache_timestamp = await simple_cache.get_timestamp(category)
        
        if cached_articles:
            # We have cached articles - use them!
            articles = cached_articles
            cache_status = "redis_cache"
            last_updated = cache_timestamp
            cache_age_minutes = (datetime.datetime.now() - cache_timestamp).total_seconds() / 60 if cache_timestamp else 0
            
            print(f"✅ Using cached articles for {category} (age: {cache_age_minutes:.1f} minutes)")
            
        else:
            # No cache - fetch fresh news
            print(f"🔄 Cache miss for {category}, fetching fresh news...")
            
            result, filename = generiraj_vijesti(category)
            
            if result and not result.startswith("Trenutno nije moguće"):
                articles = parse_news_content(result)
                cache_status = "fresh_fetch"
                last_updated = datetime.datetime.now()
                
                # Cache the fresh articles for next time
                cache_success = await simple_cache.set_news(category, articles, ttl_seconds=7200)  # 2 hours
                
                if cache_success:
                    print(f"✅ Cached {len(articles)} articles for {category}")
                else:
                    print(f"⚠️ Failed to cache articles for {category}")
                
            else:
                articles = []
                cache_status = "fetch_error"
                last_updated = None
                print(f"❌ Failed to fetch news for {category}")
        
        return templates.TemplateResponse("news.html", {
            "request": request,
            "category": category,
            "articles": articles,
            "title": f"AI Novine - {category}",
            "cache_status": cache_status,
            "last_updated": last_updated,
            "cache_age_minutes": cache_age_minutes if 'cache_age_minutes' in locals() else None
        })
        
    except Exception as e:
        print(f"❌ Error in show_news: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": str(e),
            "title": "Greška"
        })

@router.get("/api/news/{category}")
async def get_news_api(category: str):
    """API endpoint for news with caching"""
    try:
        category = category.capitalize()
        
        print(f"📡 API request for: {category}")
        
        # Try cache first
        cached_articles = await simple_cache.get_news(category)
        cache_timestamp = await simple_cache.get_timestamp(category)
        
        if cached_articles:
            # Return cached data
            cache_age_seconds = (datetime.datetime.now() - cache_timestamp).total_seconds() if cache_timestamp else 0
            
            return {
                "category": category,
                "articles": cached_articles,
                "count": len(cached_articles),
                "cache_info": {
                    "from_cache": True,
                    "cache_age_seconds": cache_age_seconds,
                    "last_updated": cache_timestamp.isoformat() if cache_timestamp else None,
                    "source": "redis_cache"
                },
                "timestamp": datetime.datetime.now().isoformat()
            }
        else:
            # Fetch fresh data
            result, filename = generiraj_vijesti(category)
            
            if result and not result.startswith("Trenutno nije moguće"):
                articles = parse_news_content(result)
                current_time = datetime.datetime.now()
                
                # Cache the fresh data
                await simple_cache.set_news(category, articles, ttl_seconds=7200)
                
                return {
                    "category": category,
                    "articles": articles,
                    "count": len(articles),
                    "cache_info": {
                        "from_cache": False,
                        "last_updated": current_time.isoformat(),
                        "source": "fresh_fetch"
                    },
                    "timestamp": current_time.isoformat()
                }
            else:
                raise HTTPException(status_code=503, detail="News service unavailable")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/refresh/{category}")
async def refresh_news(category: str, background_tasks: BackgroundTasks):
    """Force refresh news for a category (clears cache)"""
    try:
        category = category.capitalize()
        
        # Validate category
        valid_categories = ["Hrvatska", "Svijet", "Ekonomija", "Sport", "Regija"]
        if category not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        
        # Clear the cache first
        cleared = await simple_cache.clear_category(category)
        print(f"🗑️ Cleared cache for {category}: {cleared}")
        
        # Trigger fresh fetch in background
        background_tasks.add_task(trigger_fresh_fetch_and_cache, category)
        
        return {
            "status": "success",
            "message": f"Cache cleared and fresh fetch started for {category}",
            "category": category,
            "cache_cleared": cleared
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/cache-status")
async def cache_status():
    """Get cache status for all categories"""
    categories = ["Hrvatska", "Svijet", "Ekonomija", "Sport", "Regija"]
    status = {}
    
    for category in categories:
        cached_articles = await simple_cache.get_news(category)
        cache_timestamp = await simple_cache.get_timestamp(category)
        
        if cached_articles and cache_timestamp:
            cache_age_seconds = (datetime.datetime.now() - cache_timestamp).total_seconds()
            cache_age_minutes = cache_age_seconds / 60
            
            status[category] = {
                "cached": True,
                "articles_count": len(cached_articles),
                "last_updated": cache_timestamp.isoformat(),
                "cache_age_seconds": cache_age_seconds,
                "cache_age_minutes": cache_age_minutes,
                "cache_valid": cache_age_seconds < 7200,  # 2 hours
                "source": "redis"
            }
        else:
            status[category] = {
                "cached": False,
                "articles_count": 0,
                "last_updated": None,
                "cache_age_seconds": None,
                "cache_age_minutes": None,
                "cache_valid": False,
                "source": None
            }
    
    # Get cache statistics
    cache_stats = simple_cache.get_stats()
    
    return {
        "categories": status,
        "cache_stats": cache_stats,
        "total_cached_articles": sum(cat['articles_count'] for cat in status.values() if cat['cached']),
        "timestamp": datetime.datetime.now().isoformat()
    }

# Background task functions
async def trigger_fresh_fetch_and_cache(category: str):
    """Background task to fetch fresh news and cache it"""
    try:
        print(f"🔄 Background fetch starting for {category}")
        
        result, filename = generiraj_vijesti(category)
        
        if result and not result.startswith("Trenutno nije moguće"):
            articles = parse_news_content(result)
            
            # Cache the fresh articles
            cache_success = await simple_cache.set_news(category, articles, ttl_seconds=7200)
            
            if cache_success:
                print(f"✅ Background fetch completed for {category}: {len(articles)} articles cached")
            else:
                print(f"⚠️ Background fetch completed for {category} but caching failed")
        else:
            print(f"❌ Background fetch failed for {category}")
            
    except Exception as e:
        print(f"❌ Background fetch error for {category}: {e}")