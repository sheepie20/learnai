import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel
from models import User
from database import DatabaseService

# Security settings
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30  # For refresh tokens

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None  # Optional for backward compatibility
    expires_in: Optional[int] = None  # Optional for backward compatibility

class TokenData(BaseModel):
    username: Optional[str] = None
    token_type: Optional[str] = None
    exp: Optional[int] = None

class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Password hashing

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# JWT creation

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None, token_type: str = "access"):
    to_encode = data.copy()
    # Add token_type to the payload
    to_encode.update({"token_type": token_type})
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# User lookup (replace with DB)
async def get_user(username: str) -> Optional[User]:
    return await DatabaseService.get_user_by_username(username)

# Authentication dependencies
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Print token for debugging
        print(f"[DEBUG] Token received: {token[:20]}...")
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            print("[DEBUG] No username in token")
            raise credentials_exception
            
        print(f"[DEBUG] Username from token: {username}")
    except JWTError as e:
        print(f"[DEBUG] JWT Error: {str(e)}")
        raise credentials_exception
        
    user = await get_user(username)
    if user is None:
        print(f"[DEBUG] User not found: {username}")
        raise credentials_exception
        
    print(f"[DEBUG] User authenticated: {username}")
    return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user

# Classes already defined above

# User lookup - use DatabaseService directly
async def get_user(username: str) -> Optional[User]:
    """Get user by username"""
    return await DatabaseService.get_user_by_username(username)

async def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password"""
    user = await get_user(username)
    if not user or not User.verify_password(password, user.hashed_password):
        return None
    return user

def create_token(data: dict, token_type: str = "access", expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT token with specified type and expiration"""
    to_encode = data.copy()
    to_encode.update({"token_type": token_type})
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        if token_type == "access":
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        else:  # refresh token
            expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_tokens(username: str) -> dict:
    """Create both access and refresh tokens"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    access_token = create_token(
        data={"sub": username},
        token_type="access",
        expires_delta=access_token_expires
    )
    
    refresh_token = create_token(
        data={"sub": username},
        token_type="refresh",
        expires_delta=refresh_token_expires
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

class TokenError(Exception):
    """Base class for token-related errors"""
    pass

class TokenExpiredError(TokenError):
    """Raised when token has expired"""
    pass

class InvalidTokenError(TokenError):
    """Raised when token is invalid"""
    pass

async def decode_token(token: str, required_type: str = None) -> TokenData:
    """Decode and validate JWT token"""
    try:
        # Let PyJWT handle expiration validation
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM],
            options={"verify_exp": True}  # Verify expiration
        )
        
        # Extract claims
        username: str = payload.get("sub")
        token_type: str = payload.get("token_type")
        exp: int = payload.get("exp")
        
        # Debug info
        now = datetime.now(timezone.utc)
        if exp:
            exp_time = datetime.fromtimestamp(exp, tz=timezone.utc)
            print(f"[DEBUG] Token expires at: {exp_time}, Current time: {now}, Delta: {exp_time - now}")
        
        if username is None:
            raise InvalidTokenError("Token missing username")
            
        if required_type and token_type != required_type:
            raise InvalidTokenError(f"Expected {required_type} token but got {token_type}")
            
        # We don't need to check expiration here as PyJWT already did it
        # But we'll keep the exp field in the returned data
        return TokenData(username=username, token_type=token_type, exp=exp)
        
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except jwt.JWTError:
        raise InvalidTokenError("Could not validate token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    print(f"[AUTH DEBUG] Received token: {token}")
    """Get current authenticated user from JWT token"""
    try:
        token_data = await decode_token(token, required_type="access")
    except TokenExpiredError as e:
        print(f"[AUTH DEBUG] TokenExpiredError: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except TokenError as e:
        print(f"[AUTH DEBUG] TokenError: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_user(token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
