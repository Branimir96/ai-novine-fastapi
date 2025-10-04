from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from app.services.news_service import generiraj_vijesti, parse_news_content
from app.services.simple_redis_manager import simple_cache
from app.services.auth_service import auth_service
import datetime
import os
from typing import Optional

# Initialize router and templates FIRST
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Personalized news feed endpoint
# Only the section of news.py that needs to be changed
# Replace the my_personalized_news function with this fixed version:

@router.get("/my-news", response_class=HTMLResponse)
async def my_personalized_news(request: Request):
    """Personalized news feed based on user's selected categories"""
    
    try:
        # Get user from cookie
        token = request.cookies.get("access_token")
        
        if not token:
            return templates.TemplateResponse("login_required.html", {
                "request": request,
                "title": "Prijava potrebna - AI Novine",
                "message": "Molimo prijavite se da biste vidjeli personalizirane vijesti"
            })
        
        if token.startswith("Bearer "):
            token = token[7:]
        
        payload = auth_service.decode_access_token(token)
        if not payload:
            return templates.TemplateResponse("login_required.html", {
                "request": request,
                "title": "Prijava potrebna - AI Novine",
                "message": "Vaša sesija je istekla, molimo prijavite se ponovno"
            })
        
        user_id = payload.get("user_id")
        if not user_id:
            return templates.TemplateResponse("login_required.html", {
                "request": request,
                "title": "Prijava potrebna - AI Novine"
            })
        
        from app.models.database import get_db_session
        
        # FIXED: Use async with instead of async for
        async with get_db_session() as session:
            user = await auth_service.get_user_by_id(session, user_id)
            
            if not user or not user.is_active:
                return templates.TemplateResponse("login_required.html", {
                    "request": request,
                    "title": "Prijava potrebna - AI Novine"
                })
            
            selected_categories = user.selected_categories
            
            if not selected_categories:
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "error": "Nemate odabrane kategorije. Molimo kontaktirajte podršku."
                })
            
            all_articles = []
            category_stats = {}
            
            for category in selected_categories:
                print(f"📰 Fetching news for user's category: {category}")
                
                cached_articles = await simple_cache.get_news(category)
                
                if cached_articles:
                    articles = cached_articles
                    print(f"✅ Using cached articles for {category}")
                else:
                    print(f"🔄 Fetching fresh news for {category}")
                    result, filename = generiraj_vijesti(category)
                    
                    if result and not result.startswith("Trenutno nije moguće"):
                        articles = parse_news_content(result)
                        await simple_cache.set_news(category, articles, ttl_seconds=7200)
                    else:
                        articles = []
                
                for article in articles:
                    article['user_category'] = category
                
                all_articles.extend(articles)
                category_stats[category] = len(articles)
            
            import random
            
            articles_by_category = {}
            for article in all_articles:
                cat = article.get('user_category', 'Unknown')
                if cat not in articles_by_category:
                    articles_by_category[cat] = []
                articles_by_category[cat].append(article)
            
            mixed_articles = []
            max_per_category = 5
            
            for category in selected_categories:
                if category in articles_by_category:
                    cat_articles = articles_by_category[category][:max_per_category]
                    mixed_articles.extend(cat_articles)
            
            random.shuffle(mixed_articles)
            mixed_articles = mixed_articles[:25]
            
            print(f"✅ Personalized feed: {len(mixed_articles)} articles from {len(selected_categories)} categories")
            
            return templates.TemplateResponse("my_news.html", {
                "request": request,
                "title": f"Moje Vijesti - AI Novine",
                "user": user,
                "articles": mixed_articles,
                "selected_categories": selected_categories,
                "category_stats": category_stats,
                "total_articles": len(mixed_articles)
            })
    
    except Exception as e:
        print(f"❌ Error in personalized feed: {e}")
        import traceback
        traceback.print_exc()
        
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"Greška pri učitavanju personaliziranih vijesti: {str(e)}"
        })

@router.get("/news/{category}", response_class=HTMLResponse)
async def show_news(request: Request, category: str):
    """Display news for a specific category with caching"""
    try:
        if category.lower() == "europska-unija":
            category = "Europska_unija"
        else:
            category = category.capitalize()
        
        display_category = category.replace('_', ' ')
        
        print(f"📰 Requesting news for: {category}")
        
        cached_articles = await simple_cache.get_news(category)
        cache_timestamp = await simple_cache.get_timestamp(category)
        
        if cached_articles:
            articles = cached_articles
            cache_status = "redis_cache"
            last_updated = cache_timestamp
            cache_age_minutes = (datetime.datetime.now() - cache_timestamp).total_seconds() / 60 if cache_timestamp else 0
            
            print(f"✅ Using cached articles for {category} (age: {cache_age_minutes:.1f} minutes)")
            
        else:
            print(f"🔄 Cache miss for {category}, fetching fresh news...")
            
            result, filename = generiraj_vijesti(category)
            
            if result and not result.startswith("Trenutno nije moguće"):
                articles = parse_news_content(result)
                cache_status = "fresh_fetch"
                last_updated = datetime.datetime.now()
                
                if category == "Europska_unija":
                    ttl_seconds = 21600
                else:
                    ttl_seconds = 7200
                
                cache_success = await simple_cache.set_news(category, articles, ttl_seconds=ttl_seconds)
                
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
            "category": display_category,
            "articles": articles,
            "title": f"AI Novine - {display_category}",
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
        if category.lower() == "europska-unija":
            category = "Europska_unija"
        else:
            category = category.capitalize()
        
        print(f"📡 API request for: {category}")
        
        cached_articles = await simple_cache.get_news(category)
        cache_timestamp = await simple_cache.get_timestamp(category)
        
        if cached_articles:
            cache_age_seconds = (datetime.datetime.now() - cache_timestamp).total_seconds() if cache_timestamp else 0
            
            return {
                "category": category.replace('_', ' '),
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
            result, filename = generiraj_vijesti(category)
            
            if result and not result.startswith("Trenutno nije moguće"):
                articles = parse_news_content(result)
                current_time = datetime.datetime.now()
                
                if category == "Europska_unija":
                    ttl_seconds = 21600
                else:
                    ttl_seconds = 7200
                
                await simple_cache.set_news(category, articles, ttl_seconds=ttl_seconds)
                
                return {
                    "category": category.replace('_', ' '),
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
        if category.lower() == "europska-unija":
            category = "Europska_unija"
        else:
            category = category.capitalize()
        
        valid_categories = ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija", "Europska_unija"]
        if category not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        
        cleared = await simple_cache.clear_category(category)
        print(f"🗑️ Cleared cache for {category}: {cleared}")
        
        background_tasks.add_task(trigger_fresh_fetch_and_cache, category)
        
        return {
            "status": "success",
            "message": f"Cache cleared and fresh fetch started for {category.replace('_', ' ')}",
            "category": category.replace('_', ' '),
            "cache_cleared": cleared
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/cache-status")
async def cache_status():
    """Get cache status for all categories including EU"""
    categories = ["Hrvatska", "Svijet", "Ekonomija", "Tehnologija", "Sport", "Regija", "Europska_unija"]
    status = {}
    
    for category in categories:
        cached_articles = await simple_cache.get_news(category)
        cache_timestamp = await simple_cache.get_timestamp(category)
        
        display_name = category.replace('_', ' ')
        
        if cached_articles and cache_timestamp:
            cache_age_seconds = (datetime.datetime.now() - cache_timestamp).total_seconds()
            cache_age_minutes = cache_age_seconds / 60
            
            if category == "Europska_unija":
                cache_valid_seconds = 21600
            else:
                cache_valid_seconds = 7200
            
            status[display_name] = {
                "cached": True,
                "articles_count": len(cached_articles),
                "last_updated": cache_timestamp.isoformat(),
                "cache_age_seconds": cache_age_seconds,
                "cache_age_minutes": cache_age_minutes,
                "cache_valid": cache_age_seconds < cache_valid_seconds,
                "source": "redis"
            }
        else:
            status[display_name] = {
                "cached": False,
                "articles_count": 0,
                "last_updated": None,
                "cache_age_seconds": None,
                "cache_age_minutes": None,
                "cache_valid": False,
                "source": None
            }
    
    cache_stats = simple_cache.get_stats()
    
    return {
        "categories": status,
        "cache_stats": cache_stats,
        "total_cached_articles": sum(cat['articles_count'] for cat in status.values() if cat['cached']),
        "timestamp": datetime.datetime.now().isoformat()
    }

@router.get("/api/eu-sources")
async def get_eu_sources():
    """Get information about EU RSS sources"""
    eu_sources = {
        "sources": [
            {"name": "Euronews", "url": "https://feeds.feedburner.com/euronews/en/home/", "description": "European news and current affairs", "type": "News"},
            {"name": "VoxEurop", "url": "https://voxeurop.eu/en/feed", "description": "European news and debate website", "type": "Analysis"},
            {"name": "Brussels Morning", "url": "https://brusselsmorning.com/feed/", "description": "Brussels-based European affairs news", "type": "News"},
            {"name": "The European Files", "url": "https://www.europeanfiles.eu/feed", "description": "European policy analysis and insights", "type": "Policy"},
            {"name": "France24 Europe", "url": "https://www.france24.com/en/europe/rss", "description": "European news from France24", "type": "News"}
        ],
        "total_sources": 5,
        "update_frequency": "3 times daily",
        "focus": "Croatian impact analysis",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    return eu_sources

@router.get("/api/categories")
async def get_all_categories():
    """Get all available news categories"""
    categories = {
        "Hrvatska": {"name": "Hrvatska", "icon": "🇭🇷", "description": "Najnovije vijesti iz domaćih medija", "url": "/news/hrvatska", "priority": "high", "frequency": "6x/day"},
        "Svijet": {"name": "Svijet", "icon": "🌍", "description": "Međunarodne vijesti prevedene na hrvatski", "url": "/news/svijet", "priority": "high", "frequency": "6x/day"},
        "Ekonomija": {"name": "Ekonomija", "icon": "💼", "description": "Poslovne i ekonomske vijesti", "url": "/news/ekonomija", "priority": "medium", "frequency": "4x/day"},
        "Tehnologija": {"name": "Tehnologija", "icon": "💻", "description": "Najnoviji tehnološki trendovi", "url": "/news/tehnologija", "priority": "medium", "frequency": "4x/day"},
        "Sport": {"name": "Sport", "icon": "⚽", "description": "Sportske vijesti iz Hrvatske i svijeta", "url": "/news/sport", "priority": "medium", "frequency": "4x/day"},
        "Regija": {"name": "Regija", "icon": "🏛️", "description": "Vijesti iz susjednih zemalja", "url": "/news/regija", "priority": "low", "frequency": "1x/day"},
        "Europska unija": {"name": "Europska unija", "icon": "🇪🇺", "description": "EU vijesti objašnjene za hrvatske građane", "url": "/news/europska-unija", "priority": "medium", "frequency": "3x/day"}
    }
    
    return {"categories": categories, "total_categories": len(categories), "timestamp": datetime.datetime.now().isoformat()}

async def trigger_fresh_fetch_and_cache(category: str):
    """Background task to fetch fresh news and cache it"""
    try:
        print(f"🔄 Background fetch starting for {category}")
        
        result, filename = generiraj_vijesti(category)
        
        if result and not result.startswith("Trenutno nije moguće"):
            articles = parse_news_content(result)
            
            if category == "Europska_unija":
                ttl_seconds = 21600
            else:
                ttl_seconds = 7200
            
            cache_success = await simple_cache.set_news(category, articles, ttl_seconds=ttl_seconds)
            
            if cache_success:
                print(f"✅ Background fetch completed for {category}: {len(articles)} articles cached")
            else:
                print(f"⚠️ Background fetch completed for {category} but caching failed")
        else:
            print(f"❌ Background fetch failed for {category}")
            
    except Exception as e:
        print(f"❌ Background fetch error for {category}: {e}")