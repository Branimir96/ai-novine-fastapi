# debug_translation.py
import os
import sys
from dotenv import load_dotenv

def debug_translation():
    print("🔍 COMPREHENSIVE TRANSLATION DEBUG")
    print("=" * 50)
    
    # Step 1: Check environment
    print("\n1. 🔧 ENVIRONMENT CHECK:")
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if api_key:
        print(f"✅ API Key found: {api_key[:15]}...")
        print(f"   Key length: {len(api_key)} characters")
    else:
        print("❌ API Key NOT found!")
        print("   Check your .env file exists and contains ANTHROPIC_API_KEY=...")
        return False
    
    # Step 2: Test basic API connection
    print("\n2. 🌐 API CONNECTION TEST:")
    try:
        from langchain_anthropic import ChatAnthropic
        client = ChatAnthropic(
            anthropic_api_key=api_key,
            model_name="claude-3-haiku-20240307"
        )
        
        response = client.invoke("Translate 'Hello world' to Croatian")
        print("✅ API connection successful!")
        print(f"   Test response: {response.content[:100]}...")
        
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False
    
    # Step 3: Test news fetching
    print("\n3. 📰 NEWS FETCHING TEST:")
    try:
        sys.path.append('.')
        from app.services.news_service import dohvati_vijesti_iz_rss
        
        # Test fetching English news
        world_news = dohvati_vijesti_iz_rss("Svijet", broj_vijesti=2)
        
        if world_news:
            print(f"✅ Fetched {len(world_news)} world news articles")
            print(f"   Sample title: {world_news[0]['naslov'][:50]}...")
            print(f"   Sample source: {world_news[0]['izvor']}")
        else:
            print("❌ Failed to fetch world news")
            return False
            
    except Exception as e:
        print(f"❌ News fetching failed: {e}")
        return False
    
    # Step 4: Test translation function directly
    print("\n4. 🔄 TRANSLATION FUNCTION TEST:")
    try:
        from app.services.news_service import prevedi_vijesti
        
        print("   Testing translation function...")
        
        # Use the fetched news for translation test
        translated_news = prevedi_vijesti(world_news, "en", "hr")
        
        if translated_news:
            print(f"✅ Translation function returned {len(translated_news)} articles")
            
            # Check if articles were actually translated
            original_title = world_news[0]['naslov']
            translated_title = translated_news[0]['naslov']
            
            print(f"   Original title: {original_title}")
            print(f"   Translated title: {translated_title}")
            print(f"   Source: {translated_news[0]['izvor']}")
            
            if original_title != translated_title:
                print("✅ Translation appears to be working!")
                return True
            else:
                print("⚠️ Translation returned same text - may not be working")
                return False
        else:
            print("❌ Translation function returned None")
            return False
            
    except Exception as e:
        print(f"❌ Translation function failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 5: Test full news generation
    print("\n5. 🌍 FULL NEWS GENERATION TEST:")
    try:
        from app.services.news_service import generiraj_svijet_vijesti
        
        print("   Testing full world news generation...")
        result = generiraj_svijet_vijesti()
        
        if result:
            print(f"✅ Full news generation successful: {len(result)} articles")
            
            # Check if any articles are marked as translated
            translated_count = sum(1 for article in result if 'prevedeno' in article.get('izvor', ''))
            print(f"   Articles marked as translated: {translated_count}")
            
            if translated_count > 0:
                print("✅ Translation is working in full pipeline!")
            else:
                print("⚠️ No articles marked as translated")
                
            return True
        else:
            print("❌ Full news generation returned None")
            return False
            
    except Exception as e:
        print(f"❌ Full news generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_translation()
    if success:
        print("\n🎉 Translation system appears to be working!")
    else:
        print("\n❌ Translation system has issues that need fixing.")