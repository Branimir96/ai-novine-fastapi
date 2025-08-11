from app.services.news_service import generiraj_europska_unija_vijesti

print("Testing fixed EU news function...")
result = generiraj_europska_unija_vijesti()

if result:
    print(f"✅ SUCCESS: Got {len(result)} articles")
    for i, article in enumerate(result[:3], 1):
        print(f"{i}. {article['naslov'][:50]}...")
        print(f"   Source: {article['izvor']}")
        print(f"   Text: {article['tekst'][:100]}...")
        if 'ai_enhanced_content' in article:
            print(f"   AI Enhanced: Yes")
        print()
else:
    print("❌ FAILED: No articles returned")