# app/services/auth_service.py

import os
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

class AuthService:
    """Authentication service for user management"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password for storing"""
        # FIXED: Bcrypt has 72 byte limit - truncate BEFORE hashing
        if len(password.encode('utf-8')) > 72:
            password = password[:72]
        
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        # FIXED: Truncate password before verification too
        if len(plain_password.encode('utf-8')) > 72:
            plain_password = plain_password[:72]
        
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        
        return encoded_jwt
    
    @staticmethod
    def decode_access_token(token: str) -> Optional[dict]:
        """Decode and verify a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    @staticmethod
    async def create_user(
        session: AsyncSession,
        email: str,
        password: str,
        selected_categories: list,
        full_name: Optional[str] = None
    ) -> Optional[User]:
        """Create a new user account"""
        
        # Check if user already exists
        result = await session.execute(
            select(User).where(User.email == email)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            return None  # User already exists
        
        # Create new user - hash_password now handles truncation
        hashed_password = AuthService.hash_password(password)
        
        new_user = User(
            email=email,
            password_hash=hashed_password,
            full_name=full_name,
            selected_categories=selected_categories,
            is_active=True,
            is_verified=False
        )
        
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        
        return new_user
    
    @staticmethod
    async def authenticate_user(
        session: AsyncSession,
        email: str,
        password: str
    ) -> Optional[User]:
        """Authenticate a user by email and password"""
        
        # Find user by email
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Verify password - verify_password now handles truncation
        if not AuthService.verify_password(password, user.password_hash):
            return None
        
        # Update last login
        user.last_login = datetime.now()
        await session.commit()
        
        return user
    
    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
        """Get user by ID"""
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
        """Get user by email"""
        result = await session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_user_categories(
        session: AsyncSession,
        user_id: int,
        categories: list
    ) -> Optional[User]:
        """Update user's selected categories"""
        user = await AuthService.get_user_by_id(session, user_id)
        
        if not user:
            return None
        
        user.selected_categories = categories
        user.updated_at = datetime.now()
        await session.commit()
        await session.refresh(user)
        
        return user

# Global auth service instance
auth_service = AuthService()