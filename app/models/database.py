# app/models/database.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import func
from contextlib import asynccontextmanager
import os
import sys
import asyncio

# Windows async fix
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

Base = declarative_base()

class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    preview_text = Column(Text, nullable=False)
    ai_enhanced_content = Column(Text, nullable=False)
    original_link = Column(String(1000))
    source_name = Column(String(200))
    category = Column(String(50), nullable=False)
    language = Column(String(10), default='hr')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('articles_search_title_idx', 'title'),
        Index('articles_search_content_idx', 'preview_text'),
        Index('articles_category_idx', 'category'),
        Index('articles_created_idx', 'created_at'),
        Index('articles_category_created_idx', 'category', 'created_at'),
    )

# Database engine and session
engine = None
async_session_maker = None

async def init_database():
    """Initialize database connection"""
    global engine, async_session_maker
    
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL not found, skipping database initialization")
        return False
    
    try:
        print(f"🔗 Connecting to database...")
        engine = create_async_engine(
            DATABASE_URL, 
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True
        )
        
        # FIXED: Use async_sessionmaker instead of sessionmaker
        async_session_maker = async_sessionmaker(
            engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ Database initialized successfully")
        print(f"📊 Tables created: {list(Base.metadata.tables.keys())}")
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

async def close_database():
    """Close database connection"""
    global engine
    if engine:
        await engine.dispose()
        print("✅ Database connection closed")

# FIXED: Proper async context manager
@asynccontextmanager
async def get_db_session():
    """Get database session - FIXED async context manager"""
    if async_session_maker is None:
        raise Exception("Database not initialized")
    
    session = async_session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()