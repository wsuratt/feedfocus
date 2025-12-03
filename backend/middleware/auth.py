"""
Authentication middleware for Supabase JWT verification
"""
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import os
from typing import Optional

# Security scheme for Bearer tokens
security = HTTPBearer(auto_error=False)

def get_jwt_secret() -> str:
    """Get JWT secret from environment"""
    secret = os.getenv('SUPABASE_JWT_SECRET')
    if not secret:
        raise ValueError("SUPABASE_JWT_SECRET not configured")
    return secret


def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> str:
    """
    Verify Supabase JWT token and return user_id.
    
    This middleware:
    1. Extracts Bearer token from Authorization header
    2. Verifies JWT signature using Supabase JWT secret
    3. Returns user_id from token payload
    
    Args:
        credentials: HTTP Bearer token from Authorization header
        
    Returns:
        user_id (str): Supabase user ID from token's 'sub' claim
        
    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    # Check if token was provided
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing. Please provide a Bearer token."
        )
    
    token = credentials.credentials
    
    try:
        # Decode and verify JWT token
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=['HS256'],
            audience='authenticated',  # Supabase uses 'authenticated' as audience
            options={"verify_aud": True}
        )
        
        # Extract user ID from 'sub' claim (Supabase standard)
        user_id = payload.get('sub')
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: no user ID found in token payload"
            )
        
        return user_id
        
    except JWTError as e:
        # Token is invalid, expired, or signature doesn't match
        raise HTTPException(
            status_code=401,
            detail=f"Invalid authentication token: {str(e)}"
        )
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Authentication error: {str(e)}"
        )


def optional_verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[str]:
    """
    Optional authentication - returns user_id if token provided, None otherwise.
    Useful for endpoints that work both authenticated and unauthenticated.
    
    Args:
        credentials: HTTP Bearer token from Authorization header
        
    Returns:
        user_id (str) if authenticated, None if not
    """
    if not credentials:
        return None
    
    try:
        return verify_token(credentials)
    except HTTPException:
        return None
