# app/models/user.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Index
from sqlalchemy.sql import func
from app.models.database import Base

class User(Base):
    """User model for authentication and personalization"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    
    # User's selected news categories (stored as JSON array)
    selected_categories = Column(JSON, default=list, nullable=False)
    # Example: ["Hrvatska", "Tehnologija", "Sport"]
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Indexes for performance
    __table_args__ = (
        Index('users_email_idx', 'email'),
        Index('users_active_idx', 'is_active'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, categories={len(self.selected_categories)})>"