"""
Authentication routes for FastAPI.
Provides login endpoint and token verification.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from auth_utils import (
    verify_password,
    create_access_token,
    verify_token,
    AUTHORIZED_EMAIL,
    AUTHORIZED_PASSWORD_HASH,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


class LoginRequest(BaseModel):
    """Login request model."""
    email: str
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str
    email: str


class UserInfo(BaseModel):
    """User info model."""
    email: str


async def get_current_user(credentials = Depends(security)) -> dict:

    """
    Dependency to verify JWT token and get current user.
    
    Args:
        credentials: HTTP Bearer token from request header
        
    Returns:
        User information dictionary
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    token = credentials.credentials
    try:
        user = verify_token(token)
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login endpoint for single user.
    
    Args:
        request: LoginRequest with email and password
        
    Returns:
        LoginResponse with access token
        
    Raises:
        HTTPException: If credentials are invalid
    """
    # Check if email matches
    if request.email != AUTHORIZED_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Check if password matches
    if not verify_password(request.password, AUTHORIZED_PASSWORD_HASH):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Generate access token
    access_token = create_access_token(email=request.email)
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        email=request.email,
    )


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Get current user information.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        UserInfo with user email
    """
    return UserInfo(email=current_user["email"])


@router.post("/verify-token")
async def verify_token_endpoint(credentials = Depends(security)):

    """
    Verify if a token is valid.
    
    Args:
        credentials: HTTP Bearer token from request header
        
    Returns:
        Dictionary with verification status
    """
    token = credentials.credentials
    try:
        user = verify_token(token)
        return {"valid": True, "email": user["email"]}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )
