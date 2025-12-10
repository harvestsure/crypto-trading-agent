"""
Authentication API Routes
Handles user registration, login, logout, and profile management
"""

import uuid
import traceback
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field

from auth import (
    UserRepository,
    SessionRepository,
    authenticate_user,
    create_access_token,
    get_current_user
)
from logger_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# Request/Response Models
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str]
    created_at: str
    last_login: Optional[str]


@router.post("/register", response_model=LoginResponse)
async def register(request: RegisterRequest):
    """Register a new user"""
    # Check if username already exists
    existing_user = UserRepository.get_by_username(request.username)
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    
    # Check if email already exists
    existing_email = UserRepository.get_by_email(request.email)
    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create new user
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    user_data = {
        'id': user_id,
        'username': request.username,
        'email': request.email,
        'password': request.password,
        'full_name': request.full_name or request.username
    }
    
    try:
        user = UserRepository.create(user_data)
        
        # Create access token
        access_token = create_access_token(user['id'], user['username'])
        
        # Create session
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        expires_at = datetime.now() + timedelta(days=7)
        SessionRepository.create({
            'id': session_id,
            'user_id': user['id'],
            'token': access_token,
            'expires_at': expires_at.isoformat()
        })
        
        # Update last login
        UserRepository.update_last_login(user['id'])
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user['id'],
                "username": user['username'],
                "email": user['email'],
                "full_name": user.get('full_name'),
                "created_at": user.get('created_at', ''),
                "last_login": user.get('last_login')
            }
        }
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create user: {str(e)}"
        )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login with username and password"""
    user = authenticate_user(request.username, request.password)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )
    
    if not user.get('is_active'):
        raise HTTPException(
            status_code=401,
            detail="User account is inactive"
        )
    
    # Create access token
    access_token = create_access_token(user['id'], user['username'])
    
    # Create session
    session_id = f"session_{uuid.uuid4().hex[:12]}"
    expires_at = datetime.now() + timedelta(days=7)
    SessionRepository.create({
        'id': session_id,
        'user_id': user['id'],
        'token': access_token,
        'expires_at': expires_at.isoformat()
    })
    
    # Update last login
    UserRepository.update_last_login(user['id'])
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "full_name": user.get('full_name'),
            "created_at": user.get('created_at', ''),
            "last_login": user.get('last_login')
        }
    }


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout current user (invalidate all sessions)"""
    SessionRepository.delete_by_user(current_user['id'])
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    return current_user


@router.get("/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """Verify if token is valid"""
    return {
        "valid": True,
        "user": {
            "id": current_user['id'],
            "username": current_user['username']
        }
    }
