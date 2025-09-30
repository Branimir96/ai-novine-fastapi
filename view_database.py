# view_database.py

import asyncio
import sys
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import os

# Windows async fix
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

async def view_database():
    """View all database contents"""
    
    print("=" * 70)
    print("🔍 AI NOVINE - DATABASE VIEWER")
    print("=" * 70)
    
    # Get DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found")
        return
    
    # Convert URL format
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    
    # Create engine directly
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True
    )
    
    try:
        async with engine.connect() as conn:
            
            # 1. List all tables
            print("\n📊 TABLES IN DATABASE:")
            print("-" * 70)
            
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            
            tables = result.fetchall()
            if tables:
                for table in tables:
                    print(f"   ✅ {table[0]}")
            else:
                print("   ℹ️  No tables found")
                return
            
            # 2. Check USERS table
            print("\n" + "=" * 70)
            print("👥 USERS TABLE")
            print("=" * 70)
            
            # Check if users table exists
            has_users_table = any(table[0] == 'users' for table in tables)
            
            if has_users_table:
                result = await conn.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar()
                print(f"\n📊 Total users: {user_count}")
                
                if user_count > 0:
                    print("\n👤 User Details:")
                    print("-" * 70)
                    result = await conn.execute(text("""
                        SELECT id, email, full_name, selected_categories, 
                               is_active, is_verified, created_at, last_login
                        FROM users
                        ORDER BY created_at DESC
                    """))
                    
                    users = result.fetchall()
                    for user in users:
                        print(f"\n   ID: {user[0]}")
                        print(f"   Email: {user[1]}")
                        print(f"   Name: {user[2] or 'Not set'}")
                        print(f"   Categories: {user[3]}")
                        print(f"   Active: {user[4]}")
                        print(f"   Verified: {user[5]}")
                        print(f"   Created: {user[6]}")
                        print(f"   Last Login: {user[7] or 'Never'}")
                        print("-" * 70)
                else:
                    print("   ℹ️  No users registered yet")
            else:
                print("   ⚠️  Users table does not exist")
                print("   Run: python init_tables.py")
            
            # 3. Check ARTICLES table
            print("\n" + "=" * 70)
            print("📰 ARTICLES TABLE")
            print("=" * 70)
            
            # Check if articles table exists
            has_articles_table = any(table[0] == 'articles' for table in tables)
            
            if has_articles_table:
                result = await conn.execute(text("SELECT COUNT(*) FROM articles"))
                article_count = result.scalar()
                print(f"\n📊 Total articles: {article_count}")
                
                if article_count > 0:
                    # Articles by category
                    print("\n📊 Articles by Category:")
                    print("-" * 70)
                    result = await conn.execute(text("""
                        SELECT category, COUNT(*) as count
                        FROM articles
                        GROUP BY category
                        ORDER BY count DESC
                    """))
                    
                    categories = result.fetchall()
                    for cat in categories:
                        print(f"   {cat[0]}: {cat[1]} articles")
                    
                    # Recent articles
                    print("\n📰 5 Most Recent Articles:")
                    print("-" * 70)
                    result = await conn.execute(text("""
                        SELECT title, category, source_name, created_at
                        FROM articles
                        ORDER BY created_at DESC
                        LIMIT 5
                    """))
                    
                    articles = result.fetchall()
                    for i, article in enumerate(articles, 1):
                        print(f"\n   {i}. {article[0][:60]}...")
                        print(f"      Category: {article[1]} | Source: {article[2]}")
                        print(f"      Created: {article[3]}")
                else:
                    print("   ℹ️  No articles in database yet")
            else:
                print("   ⚠️  Articles table does not exist")
                print("   Run: python init_tables.py")
            
            # 4. Database size info
            print("\n" + "=" * 70)
            print("💾 DATABASE INFORMATION")
            print("=" * 70)
            
            result = await conn.execute(text("""
                SELECT 
                    pg_size_pretty(pg_database_size(current_database())) as size,
                    current_database() as name
            """))
            
            db_info = result.fetchone()
            print(f"\n   Database Name: {db_info[1]}")
            print(f"   Database Size: {db_info[0]}")
            
    except Exception as e:
        print(f"\n❌ Error viewing database: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if engine:
            await engine.dispose()
        print("\n" + "=" * 70)
        print("✅ Database viewer closed")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(view_database())