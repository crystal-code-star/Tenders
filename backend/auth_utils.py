"""
Authentication utilities for single-user login system.
Handles password hashing and JWT token generation/verification.
"""

import os
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Single user credentials (stored in environment variables)
AUTHORIZED_EMAIL = os.getenv("AUTHORIZED_EMAIL", "user@example.com")
AUTHORIZED_PASSWORD_HASH = os.getenv("AUTHORIZED_PASSWORD_HASH", "")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(email: str, expires_delta: timedelta = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        email: User email
        expires_delta: Optional expiration time delta
        
    Returns:
        JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.utcnow() + expires_delta
    to_encode = {"sub": email, "exp": expire}
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        jwt.InvalidTokenError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise jwt.InvalidTokenError("Invalid token")
        return {"email": email}
    except jwt.ExpiredSignatureError:
        raise jwt.InvalidTokenError("Token has expired")
    except jwt.InvalidTokenError:
        raise jwt.InvalidTokenError("Invalid token")


def generate_password_hash(password: str) -> str:
    """
    Generate a password hash for setup purposes.
    Use this to create the AUTHORIZED_PASSWORD_HASH for .env file.
    """
    return hash_password(password)
