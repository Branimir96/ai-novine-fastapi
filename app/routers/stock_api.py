# Create this as app/routers/stock_api.py

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import aiohttp
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import os
from dataclasses import dataclass
import time

# Try to import your cache manager
try:
    from app.services.simple_redis_manager import simple_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    print("⚠️ Cache not available, using memory fallback")

router = APIRouter(prefix="/api", tags=["stock-prices"])

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class StockPrice:
    symbol: str
    price: float
    change: float
    change_percent: float
    last_updated: datetime

class StockAPIManager:
    """Manages stock price fetching with Alpha Vantage API"""
    
    def __init__(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.base_url = "https://www.alphavantage.co/query"
        self.crypto_base_url = "https://api.coingecko.com/api/v3"
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 12  # 12 seconds between requests (5 requests per minute)
        
        # In-memory cache as fallback
        self.memory_cache = {}
        self.cache_duration = 600  # 10 minutes
        
        if not self.api_key:
            logger.warning("⚠️ ALPHA_VANTAGE_API_KEY not found in environment")
    
    def _get_cache_key(self, symbol: str, data_type: str = "stock") -> str:
        """Generate cache key for symbol"""
        return f"stock_price:{data_type}:{symbol.upper()}"
    
    async def _get_cached_price(self, symbol: str, data_type: str = "stock") -> Optional[Dict]:
        """Get cached price data"""
        cache_key = self._get_cache_key(symbol, data_type)
        
        if CACHE_AVAILABLE:
            try:
                cached_data = await simple_cache.get_news(cache_key)
                if cached_data:
                    logger.info(f"📋 Cache hit for {symbol}")
                    return cached_data[0] if isinstance(cached_data, list) and cached_data else cached_data
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
        
        # Fallback to memory cache
        if cache_key in self.memory_cache:
            cached_item = self.memory_cache[cache_key]
            if datetime.now() - cached_item['timestamp'] < timedelta(seconds=self.cache_duration):
                logger.info(f"📋 Memory cache hit for {symbol}")
                return cached_item['data']
            else:
                del self.memory_cache[cache_key]
        
        return None
    
    async def _set_cached_price(self, symbol: str, data: Dict, data_type: str = "stock"):
        """Set cached price data"""
        cache_key = self._get_cache_key(symbol, data_type)
        
        if CACHE_AVAILABLE:
            try:
                await simple_cache.set_news(cache_key, [data], ttl_seconds=self.cache_duration)
                logger.info(f"💾 Cached {symbol} data")
            except Exception as e:
                logger.warning(f"Cache write error: {e}")
        
        # Always set memory cache as backup
        self.memory_cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now()
        }
    
    async def _wait_for_rate_limit(self):
        """Ensure we don't exceed API rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            logger.info(f"⏳ Rate limiting: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    async def fetch_stock_price(self, symbol: str) -> Dict[str, Any]:
        """Fetch stock price from Alpha Vantage API"""
        
        # Check cache first
        cached_data = await self._get_cached_price(symbol)
        if cached_data:
            return cached_data
        
        if not self.api_key:
            raise HTTPException(
                status_code=500, 
                detail="Alpha Vantage API key not configured"
            )
        
        # Wait for rate limit
        await self._wait_for_rate_limit()
        
        logger.info(f"🔄 Fetching fresh data for {symbol}")
        
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self.api_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Alpha Vantage API error: {response.status}"
                        )
                    
                    data = await response.json()
                    
                    # Check for API error messages
                    if "Error Message" in data:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid symbol: {symbol}"
                        )
                    
                    if "Note" in data:
                        raise HTTPException(
                            status_code=429,
                            detail="API rate limit exceeded. Please try again later."
                        )
                    
                    # Parse the response
                    quote = data.get("Global Quote", {})
                    if not quote:
                        raise HTTPException(
                            status_code=500,
                            detail="Invalid API response format"
                        )
                    
                    # Extract price data
                    price = float(quote.get("05. price", 0))
                    change = float(quote.get("09. change", 0))
                    change_percent_str = quote.get("10. change percent", "0%")
                    change_percent = float(change_percent_str.replace("%", ""))
                    
                    formatted_data = {
                        "symbol": symbol.upper(),
                        "price": price,
                        "change": change,
                        "change_percent": change_percent,
                        "formatted_price": self._format_price(price, symbol),
                        "formatted_change": self._format_change(change_percent),
                        "last_updated": datetime.now().isoformat(),
                        "source": "Alpha Vantage"
                    }
                    
                    # Cache the result
                    await self._set_cached_price(symbol, formatted_data)
                    
                    logger.info(f"✅ Successfully fetched {symbol}: ${price:.2f} ({change_percent:+.2f}%)")
                    return formatted_data
                    
        except aiohttp.ClientError as e:
            logger.error(f"❌ Network error fetching {symbol}: {e}")
            raise HTTPException(
                status_code=503,
                detail="Unable to connect to stock data provider"
            )
        except Exception as e:
            logger.error(f"❌ Error fetching {symbol}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch stock data: {str(e)}"
            )
    
    async def fetch_crypto_price(self, symbol: str) -> Dict[str, Any]:
        """Fetch cryptocurrency price from CoinGecko API (free, no auth required)"""
        
        # Check cache first
        cached_data = await self._get_cached_price(symbol, "crypto")
        if cached_data:
            return cached_data
        
        logger.info(f"🔄 Fetching fresh crypto data for {symbol}")
        
        # Map symbols to CoinGecko IDs
        crypto_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum"
        }
        
        crypto_id = crypto_map.get(symbol.upper())
        if not crypto_id:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported cryptocurrency: {symbol}"
            )
        
        url = f"{self.crypto_base_url}/simple/price"
        params = {
            "ids": crypto_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"CoinGecko API error: {response.status}"
                        )
                    
                    data = await response.json()
                    crypto_data = data.get(crypto_id, {})
                    
                    if not crypto_data:
                        raise HTTPException(
                            status_code=500,
                            detail="Invalid crypto API response"
                        )
                    
                    price = crypto_data.get("usd", 0)
                    change_percent = crypto_data.get("usd_24h_change", 0)
                    
                    formatted_data = {
                        "symbol": symbol.upper(),
                        "price": price,
                        "change": (price * change_percent / 100),  # Calculate absolute change
                        "change_percent": change_percent,
                        "formatted_price": f"${price:,.0f}" if price > 1000 else f"${price:.2f}",
                        "formatted_change": f"{change_percent:+.2f}%",
                        "last_updated": datetime.now().isoformat(),
                        "source": "CoinGecko"
                    }
                    
                    # Cache the result
                    await self._set_cached_price(symbol, formatted_data, "crypto")
                    
                    logger.info(f"✅ Successfully fetched {symbol}: ${price:,.2f} ({change_percent:+.2f}%)")
                    return formatted_data
                    
        except aiohttp.ClientError as e:
            logger.error(f"❌ Network error fetching crypto {symbol}: {e}")
            raise HTTPException(
                status_code=503,
                detail="Unable to connect to crypto data provider"
            )
        except Exception as e:
            logger.error(f"❌ Error fetching crypto {symbol}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch crypto data: {str(e)}"
            )
    
    def _format_price(self, price: float, symbol: str) -> str:
        """Format price based on symbol type"""
        if symbol.upper() in ['CROBEX', 'SPX']:
            return f"{price:,.2f}"
        else:
            return f"${price:.2f}"
    
    def _format_change(self, change_percent: float) -> str:
        """Format change percentage"""
        return f"{change_percent:+.2f}%"

# Initialize the stock API manager
stock_manager = StockAPIManager()

@router.get("/stock/{symbol}")
async def get_stock_price(symbol: str):
    """
    Get stock price for a given symbol
    Supports: AAPL, GOOGL, MSFT, AMZN, NVDA, TSLA, META, ASML, SPX, etc.
    """
    try:
        symbol = symbol.upper()
        logger.info(f"📈 Request for stock price: {symbol}")
        
        data = await stock_manager.fetch_stock_price(symbol)
        return JSONResponse(content={
            "success": True,
            "data": data
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.get("/crypto/{symbol}")
async def get_crypto_price(symbol: str):
    """
    Get cryptocurrency price for a given symbol
    Supports: BTC, ETH
    """
    try:
        symbol = symbol.upper()
        logger.info(f"₿ Request for crypto price: {symbol}")
        
        data = await stock_manager.fetch_crypto_price(symbol)
        return JSONResponse(content={
            "success": True,
            "data": data
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error for crypto {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.get("/prices/all")
async def get_all_prices():
    """
    Get all stock and crypto prices in one request (with smart batching)
    """
    try:
        logger.info("📊 Request for all prices")
        
        # Define all symbols we support
        stock_symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "ASML", "SPX"]
        crypto_symbols = ["BTC", "ETH"]
        
        all_data = {
            "stocks": {},
            "crypto": {},
            "last_updated": datetime.now().isoformat(),
            "success": True
        }
        
        # Fetch stocks with proper rate limiting
        for i, symbol in enumerate(stock_symbols):
            try:
                # Add delay between requests to respect rate limits
                if i > 0:
                    await asyncio.sleep(1)  # 1 second delay between stock requests
                
                data = await stock_manager.fetch_stock_price(symbol)
                all_data["stocks"][symbol] = data
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to fetch {symbol}: {e}")
                all_data["stocks"][symbol] = {
                    "error": str(e),
                    "symbol": symbol
                }
        
        # Fetch crypto (no rate limiting needed for CoinGecko)
        for symbol in crypto_symbols:
            try:
                data = await stock_manager.fetch_crypto_price(symbol)
                all_data["crypto"][symbol] = data
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to fetch crypto {symbol}: {e}")
                all_data["crypto"][symbol] = {
                    "error": str(e),
                    "symbol": symbol
                }
        
        logger.info(f"✅ Batch request completed: {len(all_data['stocks'])} stocks, {len(all_data['crypto'])} crypto")
        return JSONResponse(content=all_data)
        
    except Exception as e:
        logger.error(f"❌ Error in batch request: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch batch prices"
        )

@router.get("/prices/health")
async def check_api_health():
    """
    Check the health of stock price APIs
    """
    health_status = {
        "timestamp": datetime.now().isoformat(),
        "apis": {
            "alpha_vantage": {
                "configured": bool(stock_manager.api_key),
                "status": "unknown"
            },
            "coingecko": {
                "configured": True,
                "status": "unknown"
            }
        },
        "cache": {
            "type": "redis" if CACHE_AVAILABLE else "memory",
            "available": True
        }
    }
    
    # Test Alpha Vantage with a simple request
    if stock_manager.api_key:
        try:
            # Try to get cached data first
            test_data = await stock_manager._get_cached_price("AAPL")
            if test_data:
                health_status["apis"]["alpha_vantage"]["status"] = "healthy (cached)"
            else:
                # Only make API call if no cached data (to preserve rate limits)
                health_status["apis"]["alpha_vantage"]["status"] = "unknown (rate limited)"
                
        except Exception as e:
            health_status["apis"]["alpha_vantage"]["status"] = f"error: {str(e)}"
    
    # Test CoinGecko
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{stock_manager.crypto_base_url}/ping") as response:
                if response.status == 200:
                    health_status["apis"]["coingecko"]["status"] = "healthy"
                else:
                    health_status["apis"]["coingecko"]["status"] = f"error: {response.status}"
                    
    except Exception as e:
        health_status["apis"]["coingecko"]["status"] = f"error: {str(e)}"
    
    return JSONResponse(content=health_status)

@router.post("/cache/clear")
async def clear_price_cache():
    """
    Clear all cached price data (admin function)
    """
    try:
        # Clear Redis cache if available
        if CACHE_AVAILABLE:
            # Clear all stock price cache keys
            for symbol in ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "ASML", "SPX", "BTC", "ETH"]:
                await simple_cache.clear_category(f"stock_price:stock:{symbol}")
                await simple_cache.clear_category(f"stock_price:crypto:{symbol}")
        
        # Clear memory cache
        stock_manager.memory_cache.clear()
        
        logger.info("🗑️ Price cache cleared")
        return JSONResponse(content={
            "success": True,
            "message": "Price cache cleared successfully"
        })
        
    except Exception as e:
        logger.error(f"❌ Error clearing cache: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to clear cache"
        )