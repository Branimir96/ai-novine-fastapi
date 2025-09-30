# init_tables.py

import asyncio
import sys
import os
from dotenv import load_dotenv  # ← MISSING THIS!

# Load environment variables FIRST
load_dotenv()  # ← MISSING THIS!

# Windows async fix
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.models.database import init_database, Base, engine
from app.models.user import User  # Import User model
from app.models.database import Article  # Import Article model

async def create_tables():
    """Create all database tables"""
    
    print("🔄 Creating database tables...")
    print(f"📋 Checking DATABASE_URL...")
    
    # Verify DATABASE_URL is loaded
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        print(f"✅ DATABASE_URL found: {database_url[:30]}...{database_url[-20:]}")
    else:
        print("❌ DATABASE_URL not found in environment variables!")
        print("   Make sure .env file exists in the project root")
        return
    
    # Initialize database connection
    success = await init_database()
    
    if not success:
        print("❌ Failed to connect to database")
        return
    
    print("\n✅ All tables created successfully!")
    print(f"📊 Tables: {list(Base.metadata.tables.keys())}")
    print("\n📝 Tables created:")
    print("   - users (for authentication)")
    print("   - articles (for news storage)")
    
    # Close connection
    if engine:
        await engine.dispose()
    
    print("\n✅ Database is ready for user authentication!")

if __name__ == "__main__":
    asyncio.run(create_tables())