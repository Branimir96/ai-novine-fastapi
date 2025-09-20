from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import func
import os

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

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
    
    # Search index on title and content
    __table_args__ = (
        Index('articles_search_idx', 'title', 'preview_text', 'ai_enhanced_content'),
        Index('articles_category_idx', 'category'),
        Index('articles_created_idx', 'created_at'),
    )

# Database engine and session
engine = None
async_session = None

async def init_database():
    """Initialize database connection"""
    global engine, async_session
    
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL not found, skipping database initialization")
        return False
    
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ Database initialized successfully")
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

async def get_db_session():
    """Get database session"""
    if async_session is None:
        raise Exception("Database not initialized")
    return async_session()