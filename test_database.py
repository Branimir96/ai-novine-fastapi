# test_database.py (WINDOWS COMPATIBLE VERSION)

import asyncio
import os
import sys
import selectors
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Windows-specific fix - MUST be at the top
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

async def test_database_connection():
    """Comprehensive database connection test"""
    
    print("=" * 60)
    print("🔍 AI NOVINE - DATABASE CONNECTION TEST")
    print("=" * 60)
    
    # Step 1: Check if DATABASE_URL exists
    print("\n📋 Step 1: Checking DATABASE_URL environment variable...")
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment variables!")
        print("   Check your .env file")
        return False
    
    print(f"✅ DATABASE_URL found")
    print(f"   URL (masked): {database_url[:20]}...{database_url[-20:]}")
    
    # Step 2: Check URL format and convert if needed
    print("\n📋 Step 2: Validating DATABASE_URL format...")
    
    if database_url.startswith("postgresql://"):
        original_url = database_url
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        print(f"✅ Converted URL from 'postgresql://' to 'postgresql+psycopg://'")
    elif database_url.startswith("postgresql+psycopg://"):
        print(f"✅ URL already in correct format (postgresql+psycopg://)")
    else:
        print(f"❌ ERROR: Unknown database URL format: {database_url[:30]}...")
        return False
    
    # Step 3: Try to create engine
    print("\n📋 Step 3: Creating database engine...")
    
    try:
        engine = create_async_engine(
    database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)
        print("✅ Database engine created successfully")
    except Exception as e:
        print(f"❌ ERROR creating engine: {e}")
        return False
    
    # Step 4: Test actual connection
    print("\n📋 Step 4: Testing actual database connection...")
    
    try:
        async with engine.connect() as conn:
            print("✅ Successfully connected to database!")
            
            # Step 5: Test basic query
            print("\n📋 Step 5: Running test query (SELECT 1)...")
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar()
            
            if value == 1:
                print("✅ Test query successful!")
            else:
                print(f"⚠️  Unexpected result: {value}")
            
            # Step 6: Check database version
            print("\n📋 Step 6: Checking PostgreSQL version...")
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ PostgreSQL Version:")
            print(f"   {version[:80]}...")
            
            # Step 7: Check if our tables exist
            print("\n📋 Step 7: Checking existing tables...")
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            
            tables = result.fetchall()
            
            if tables:
                print(f"✅ Found {len(tables)} table(s):")
                for table in tables:
                    print(f"   - {table[0]}")
            else:
                print("⚠️  No tables found (database is empty)")
            
            # Step 8: Check if 'articles' table exists
            print("\n📋 Step 8: Checking 'articles' table specifically...")
            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'articles'
                )
            """))
            
            articles_exists = result.scalar()
            
            if articles_exists:
                print("✅ 'articles' table exists!")
                
                # Count articles
                result = await conn.execute(text("SELECT COUNT(*) FROM articles"))
                count = result.scalar()
                print(f"   Articles in database: {count}")
                
                if count > 0:
                    # Show sample article
                    result = await conn.execute(text("""
                        SELECT title, category, created_at 
                        FROM articles 
                        ORDER BY created_at DESC 
                        LIMIT 1
                    """))
                    article = result.fetchone()
                    if article:
                        print(f"\n   Latest article:")
                        print(f"   - Title: {article[0][:60]}...")
                        print(f"   - Category: {article[1]}")
                        print(f"   - Created: {article[2]}")
            else:
                print("⚠️  'articles' table does NOT exist")
                print("   Run database initialization to create it")
            
    except Exception as e:
        print(f"❌ ERROR during connection test: {e}")
        print(f"\n💡 Error details:")
        print(f"   Type: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        return False
    
    finally:
        await engine.dispose()
        print("\n📋 Step 9: Closing database connection...")
        print("✅ Connection closed")
    
    # Final summary
    print("\n" + "=" * 60)
    print("✅ DATABASE CONNECTION TEST COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("\n💡 Your database is working correctly!")
    print("   You can now use it for user authentication.")
    
    return True


async def test_database_operations():
    """Test actual database operations"""
    
    print("\n" + "=" * 60)
    print("🧪 TESTING DATABASE OPERATIONS")
    print("=" * 60)
    
    database_url = os.getenv("DATABASE_URL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        # Test creating a table
        print("\n📋 Test 1: Creating test table...")
        
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        print("✅ Test table created")
        
        # Test inserting data
        print("\n📋 Test 2: Inserting test data...")
        
        async with async_session() as session:
            await session.execute(text("""
                INSERT INTO test_table (name) 
                VALUES ('Test Entry 1'), ('Test Entry 2')
            """))
            await session.commit()
        print("✅ Test data inserted")
        
        # Test reading data
        print("\n📋 Test 3: Reading test data...")
        
        async with async_session() as session:
            result = await session.execute(text("SELECT * FROM test_table"))
            rows = result.fetchall()
            print(f"✅ Found {len(rows)} row(s)")
            for row in rows:
                print(f"   - ID: {row[0]}, Name: {row[1]}, Created: {row[2]}")
        
        # Clean up test table
        print("\n📋 Test 4: Cleaning up test table...")
        
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS test_table"))
        print("✅ Test table removed")
        
        print("\n✅ ALL DATABASE OPERATIONS SUCCESSFUL!")
        
    except Exception as e:
        print(f"❌ ERROR during operations test: {e}")
        return False
    
    finally:
        await engine.dispose()
    
    return True


async def main():
    """Run all tests"""
    
    print("\n🚀 Starting comprehensive database tests...\n")
    print("💻 Platform: Windows")
    print("🔧 Event Loop: WindowsSelectorEventLoop\n")
    
    # Test 1: Connection
    connection_ok = await test_database_connection()
    
    if not connection_ok:
        print("\n❌ Connection test failed. Fix connection issues first.")
        return
    
    # Test 2: Operations
    print("\n" + "=" * 60)
    input("Press ENTER to run database operations test...")
    
    operations_ok = await test_database_operations()
    
    if operations_ok:
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("\n✅ Your PostgreSQL database is fully functional!")
        print("✅ You can proceed with user authentication implementation.")
        print("\n📝 Next steps:")
        print("   1. Keep your DATABASE_URL in .env")
        print("   2. Create User model")
        print("   3. Implement authentication")
    else:
        print("\n❌ Operations test failed.")
        print("   Check error messages above for details.")


if __name__ == "__main__":
    # Windows compatibility fix
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())