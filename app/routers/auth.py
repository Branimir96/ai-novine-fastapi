# app/routers/auth.py

from fastapi import APIRouter, HTTPException, Request, Form, Response, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from typing import List, Optional
from pydantic import BaseModel, EmailStr
import sys
import asyncio

# Windows async fix
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.models.database import get_db_session
from app.services.auth_service import auth_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["authentication"])
templates = Jinja2Templates(directory="app/templates")

# Pydantic models for validation
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    selected_categories: List[str]

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Available categories
AVAILABLE_CATEGORIES = [
    "Hrvatska",
    "Svijet", 
    "Ekonomija",
    "Tehnologija",
    "Sport",
    "Regija",
    "Europska_unija"
]

# ============================================================
# HTML PAGES
# ============================================================

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Display registration page"""
    return templates.TemplateResponse("register.html", {
        "request": request,
        "title": "Registracija - AI Novine",
        "categories": AVAILABLE_CATEGORIES
    })

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page"""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "title": "Prijava - AI Novine"
    })

# ============================================================
# API ENDPOINTS
# ============================================================

@router.post("/register")
async def register_user(
    email: str = Form(...),
    password: str = Form(...),
    full_name: Optional[str] = Form(None),
    categories: List[str] = Form(...)
):
    """Register a new user"""
    
    # Validation
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    if not categories or len(categories) < 2:
        raise HTTPException(status_code=400, detail="Please select at least 2 categories")
    
    if len(categories) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 categories allowed")
    
    # Validate categories
    invalid_cats = [cat for cat in categories if cat not in AVAILABLE_CATEGORIES]
    if invalid_cats:
        raise HTTPException(status_code=400, detail=f"Invalid categories: {invalid_cats}")
    
    # Create user - FIXED: Use async with properly
    try:
        async with get_db_session() as session:
            user = await auth_service.create_user(
                session=session,
                email=email,
                password=password,
                selected_categories=categories,
                full_name=full_name
            )
            
            if not user:
                raise HTTPException(status_code=400, detail="User with this email already exists")
            
            # Create JWT token
            token = auth_service.create_access_token(data={"user_id": user.id, "email": user.email})
            
            # Return success with redirect
            response = RedirectResponse(url="/my-news", status_code=303)
            response.set_cookie(
                key="access_token",
                value=f"Bearer {token}",
                httponly=True,
                max_age=60*60*24*7,  # 7 days
                samesite="lax"
            )
            
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@router.post("/login")
async def login_user(
    email: str = Form(...),
    password: str = Form(...)
):
    """Login user"""
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    
    # FIXED: Use async with properly
    try:
        async with get_db_session() as session:
            # Authenticate user
            user = await auth_service.authenticate_user(
                session=session,
                email=email,
                password=password
            )
            
            if not user:
                raise HTTPException(status_code=401, detail="Invalid email or password")
            
            if not user.is_active:
                raise HTTPException(status_code=403, detail="Account is disabled")
            
            # Create JWT token
            token = auth_service.create_access_token(data={"user_id": user.id, "email": user.email})
            
            # Return success with redirect
            response = RedirectResponse(url="/my-news", status_code=303)
            response.set_cookie(
                key="access_token",
                value=f"Bearer {token}",
                httponly=True,
                max_age=60*60*24*7,  # 7 days
                samesite="lax"
            )
            
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@router.post("/logout")
async def logout_user():
    """Logout user"""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="access_token")
    return response

@router.get("/me")
async def get_current_user(request: Request):
    """Get current logged-in user info"""
    
    # Get token from cookie
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Remove "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token[7:]
    
    # Decode token
    payload = auth_service.decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Get user from database - FIXED: Use async with properly
    async with get_db_session() as session:
        user = await auth_service.get_user_by_id(session, user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "selected_categories": user.selected_categories,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None
        }

# ============================================================
# HELPER FUNCTION (Dependency for protected routes)
# ============================================================

async def get_current_user_from_cookie(request: Request):
    """Dependency to get current user from cookie"""
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    if token.startswith("Bearer "):
        token = token[7:]
    
    payload = auth_service.decode_access_token(token)
    if not payload:
        return None
    
    user_id = payload.get("user_id")
    if not user_id:
        return None
    
    # FIXED: Use async with properly
    async with get_db_session() as session:
        user = await auth_service.get_user_by_id(session, user_id)
        return user