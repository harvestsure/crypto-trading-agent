"""
Authentication and Authorization Module
Provides JWT-based authentication for the CryptoAgent platform
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import bcrypt
import jwt
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_db

# Configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

security = HTTPBearer()


class UserRepository:
    """Repository for user data operations"""
    
    @staticmethod
    def create(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Hash the password
            password_hash = bcrypt.hashpw(
                user_data['password'].encode('utf-8'), 
                bcrypt.gensalt()
            ).decode('utf-8')
            
            cursor.execute("""
                INSERT INTO users (id, username, email, password_hash, full_name)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_data['id'],
                user_data['username'],
                user_data['email'],
                password_hash,
                user_data.get('full_name', '')
            ))
            
            # Return the created user data (without password hash for security)
            return {
                'id': user_data['id'],
                'username': user_data['username'],
                'email': user_data['email'],
                'full_name': user_data.get('full_name', ''),
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'is_active': True
            }
    
    @staticmethod
    def get_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, email, full_name, created_at, last_login, is_active
                FROM users WHERE id = ?
            """, (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def get_by_username(username: str) -> Optional[Dict[str, Any]]:
        """Get user by username (includes password hash for authentication)"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def get_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def update_last_login(user_id: str):
        """Update user's last login timestamp"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET last_login = ? WHERE id = ?
            """, (datetime.now().isoformat(), user_id))
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8')
        )


class SessionRepository:
    """Repository for session management"""
    
    @staticmethod
    def create(session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new session"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (id, user_id, token, expires_at)
                VALUES (?, ?, ?, ?)
            """, (
                session_data['id'],
                session_data['user_id'],
                session_data['token'],
                session_data['expires_at']
            ))
            return session_data
    
    @staticmethod
    def get_by_token(token: str) -> Optional[Dict[str, Any]]:
        """Get session by token"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sessions 
                WHERE token = ? AND expires_at > ?
            """, (token, datetime.now().isoformat()))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def delete(session_id: str) -> bool:
        """Delete a session (logout)"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def delete_by_user(user_id: str) -> bool:
        """Delete all sessions for a user"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def cleanup_expired():
        """Remove expired sessions"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM sessions WHERE expires_at <= ?
            """, (datetime.now().isoformat(),))


def create_access_token(user_id: str, username: str) -> str:
    """Create JWT access token"""
    expires = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": user_id,
        "username": username,
        "exp": expires
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidSignatureError:
        return None
    except (jwt.DecodeError, jwt.PyJWTError):
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user
    Use this in protected routes: user = Depends(get_current_user)
    """
    token = credentials.credentials
    
    # Decode the JWT token
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid token payload"
        )
    
    # Get user from database
    user = UserRepository.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )
    
    if not user.get('is_active'):
        raise HTTPException(
            status_code=401,
            detail="User account is inactive"
        )
    
    return user


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user with username and password"""
    user = UserRepository.get_by_username(username)
    if not user:
        return None
    
    if not UserRepository.verify_password(password, user['password_hash']):
        return None
    
    return user
