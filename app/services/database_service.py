from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.models.database import Article, get_db_session
from typing import List, Optional
import datetime

class DatabaseService:
    """Service for database operations"""
    
    async def save_article(self, article_data: dict) -> bool:
        """Save article to database"""
        try:
            # FIXED: Use async with properly
            async with get_db_session() as session:
                # Check if article already exists (by title and category)
                existing = await session.execute(
                    select(Article).where(
                        and_(
                            Article.title == article_data['naslov'],
                            Article.category == article_data.get('category', 'Unknown')
                        )
                    )
                )
                
                if existing.scalar_one_or_none():
                    print(f"📰 Article already exists: {article_data['naslov'][:50]}...")
                    return True
                
                # Create new article
                article = Article(
                    title=article_data['naslov'],
                    preview_text=article_data['tekst'],
                    ai_enhanced_content=article_data.get('ai_enhanced_content', ''),
                    original_link=article_data.get('original_link'),
                    source_name=article_data.get('izvor', ''),
                    category=article_data.get('category', 'Unknown'),
                    language='hr'
                )
                
                session.add(article)
                # No need to commit - handled by context manager
                
                print(f"✅ Saved article: {article_data['naslov'][:50]}...")
                return True
                
        except Exception as e:
            print(f"❌ Failed to save article: {e}")
            return False
    
    async def save_articles_batch(self, articles: List[dict], category: str) -> int:
        """Save multiple articles for a category"""
        saved_count = 0
        
        for article in articles:
            article['category'] = category
            if await self.save_article(article):
                saved_count += 1
        
        print(f"✅ Saved {saved_count}/{len(articles)} articles for {category}")
        return saved_count
    
    async def search_articles(self, query: str, category: Optional[str] = None, limit: int = 20) -> List[dict]:
        """Search articles by text query"""
        try:
            async with get_db_session() as session:
                # Build search conditions
                search_conditions = []
                
                if query:
                    # Simple text search across title, preview, and AI content
                    search_text = f"%{query.lower()}%"
                    search_conditions.append(
                        or_(
                            func.lower(Article.title).like(search_text),
                            func.lower(Article.preview_text).like(search_text),
                            func.lower(Article.ai_enhanced_content).like(search_text)
                        )
                    )
                
                if category:
                    search_conditions.append(Article.category == category)
                
                # Build query
                stmt = select(Article)
                if search_conditions:
                    stmt = stmt.where(and_(*search_conditions))
                
                stmt = stmt.order_by(Article.created_at.desc()).limit(limit)
                
                # Execute query
                result = await session.execute(stmt)
                articles = result.scalars().all()
                
                # Convert to dict format
                return [
                    {
                        'id': article.id,
                        'naslov': article.title,
                        'tekst': article.preview_text,
                        'ai_enhanced_content': article.ai_enhanced_content,
                        'original_link': article.original_link,
                        'izvor': article.source_name,
                        'category': article.category,
                        'created_at': article.created_at.isoformat() if article.created_at else None
                    }
                    for article in articles
                ]
                
        except Exception as e:
            print(f"❌ Search failed: {e}")
            return []
    
    async def get_articles_by_category(self, category: str, limit: int = 20) -> List[dict]:
        """Get recent articles for a category"""
        try:
            async with get_db_session() as session:
                stmt = (
                    select(Article)
                    .where(Article.category == category)
                    .order_by(Article.created_at.desc())
                    .limit(limit)
                )
                
                result = await session.execute(stmt)
                articles = result.scalars().all()
                
                return [
                    {
                        'id': article.id,
                        'naslov': article.title,
                        'tekst': article.preview_text,
                        'ai_enhanced_content': article.ai_enhanced_content,
                        'original_link': article.original_link,
                        'izvor': article.source_name,
                        'category': article.category,
                        'created_at': article.created_at.isoformat() if article.created_at else None
                    }
                    for article in articles
                ]
                
        except Exception as e:
            print(f"❌ Failed to get articles for {category}: {e}")
            return []
    
    async def get_database_stats(self) -> dict:
        """Get database statistics"""
        try:
            async with get_db_session() as session:
                # Total articles
                total_result = await session.execute(select(func.count(Article.id)))
                total_articles = total_result.scalar()
                
                # Articles by category
                category_result = await session.execute(
                    select(Article.category, func.count(Article.id))
                    .group_by(Article.category)
                )
                
                categories = {}
                for category, count in category_result.all():
                    categories[category] = count
                
                return {
                    'total_articles': total_articles,
                    'categories': categories,
                    'database_connected': True
                }
                
        except Exception as e:
            print(f"❌ Failed to get database stats: {e}")
            return {
                'total_articles': 0,
                'categories': {},
                'database_connected': False,
                'error': str(e)
            }

# Global database service instance
db_service = DatabaseService()