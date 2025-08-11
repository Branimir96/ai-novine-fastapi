# Debug script to test EU RSS feeds individually
# Save this as debug_eu_feeds.py and run it to see what's working

import feedparser
import requests
from datetime import datetime

# Your current EU feeds
EU_FEEDS = [
    "https://www.euractiv.com/feed",
    "https://feeds.feedburner.com/euronews/en/home/",
    "https://eureporter.co/feed/",
    "https://voxeurop.eu/en/feed",
    "https://www.euronews.com/business.rss",
    "https://www.euronews.com/news.rss",
    "https://brusselsmorning.com/feed/",
    "https://www.europeanfiles.eu/feed",
    "https://www.euractiv.com/sections/politics/feed/"
]

def test_rss_feed(url):
    """Test individual RSS feed"""
    print(f"\n🔍 Testing: {url}")
    
    try:
        # First test if URL is reachable
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        print(f"   HTTP Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ HTTP Error: {response.status_code}")
            return False
            
        # Test with feedparser
        feed = feedparser.parse(url)
        
        if feed.bozo:
            print(f"   ⚠️ Feed parsing warning: {feed.bozo_exception}")
        
        if not feed.entries:
            print(f"   ❌ No entries found")
            return False
            
        print(f"   ✅ Found {len(feed.entries)} articles")
        print(f"   📰 Latest: {feed.entries[0].title[:80]}...")
        
        # Check if feed has description
        if hasattr(feed.entries[0], 'description'):
            desc_length = len(feed.entries[0].description)
            print(f"   📝 Description length: {desc_length} chars")
        else:
            print(f"   ⚠️ No description field")
            
        return True
        
    except requests.exceptions.Timeout:
        print(f"   ❌ Timeout error")
        return False
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Connection error")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("🔍 Testing EU RSS Feeds")
    print("=" * 50)
    
    working_feeds = []
    broken_feeds = []
    
    for feed_url in EU_FEEDS:
        if test_rss_feed(feed_url):
            working_feeds.append(feed_url)
        else:
            broken_feeds.append(feed_url)
    
    print("\n" + "=" * 50)
    print(f"📊 SUMMARY:")
    print(f"✅ Working feeds: {len(working_feeds)}")
    print(f"❌ Broken feeds: {len(broken_feeds)}")
    
    if working_feeds:
        print(f"\n✅ WORKING FEEDS:")
        for feed in working_feeds:
            print(f"   {feed}")
    
    if broken_feeds:
        print(f"\n❌ BROKEN FEEDS:")
        for feed in broken_feeds:
            print(f"   {feed}")
    
    # Test your EU news function
    print(f"\n🧪 Testing EU news generation...")
    try:
        from app.services.news_service import generiraj_europska_unija_vijesti
        
        print("Calling generiraj_europska_unija_vijesti()...")
        eu_news = generiraj_europska_unija_vijesti()
        
        if eu_news:
            print(f"✅ Generated {len(eu_news)} EU articles")
            for i, article in enumerate(eu_news[:3], 1):
                print(f"   {i}. {article['naslov'][:60]}...")
        else:
            print("❌ No EU news generated")
            
    except ImportError:
        print("❌ Could not import generiraj_europska_unija_vijesti")
    except Exception as e:
        print(f"❌ Error testing EU news function: {e}")

if __name__ == "__main__":
    main()
    