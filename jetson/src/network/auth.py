"""
Authentication and Authorization Module

Implements JWT-based authentication and role-based access control.
Validates: Requirements 9.5
"""

import jwt
import hashlib
import secrets
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles for access control"""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(Enum):
    """System permissions"""
    VIEW_CAMERA = "view_camera"
    CONTROL_POSITION = "control_position"
    CAPTURE_IMAGE = "capture_image"
    CONFIGURE_SYSTEM = "configure_system"
    MANAGE_USERS = "manage_users"
    VIEW_LOGS = "view_logs"


# Role-based permissions mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.VIEW_CAMERA,
        Permission.CONTROL_POSITION,
        Permission.CAPTURE_IMAGE,
        Permission.CONFIGURE_SYSTEM,
        Permission.MANAGE_USERS,
        Permission.VIEW_LOGS,
    ],
    UserRole.OPERATOR: [
        Permission.VIEW_CAMERA,
        Permission.CONTROL_POSITION,
        Permission.CAPTURE_IMAGE,
        Permission.VIEW_LOGS,
    ],
    UserRole.VIEWER: [
        Permission.VIEW_CAMERA,
    ],
}


@dataclass
class User:
    """User account"""
    username: str
    password_hash: str
    role: UserRole
    created_at: float = field(default_factory=time.time)
    last_login: Optional[float] = None
    enabled: bool = True


@dataclass
class Session:
    """User session"""
    token: str
    username: str
    role: UserRole
    created_at: float
    expires_at: float
    ip_address: Optional[str] = None


class AuthManager:
    """Authentication and authorization manager"""
    
    def __init__(self, secret_key: Optional[str] = None, token_expiry_hours: int = 24):
        """
        Initialize auth manager
        
        Args:
            secret_key: JWT secret key (generated if not provided)
            token_expiry_hours: Token expiration time in hours
        """
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.token_expiry_hours = token_expiry_hours
        
        # In-memory user storage (in production, use database)
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        
        # Create default admin user
        self._create_default_admin()
    
    def _create_default_admin(self):
        """Create default admin user"""
        default_password = "admin123"  # Should be changed on first login
        password_hash = self._hash_password(default_password)
        
        admin = User(
            username="admin",
            password_hash=password_hash,
            role=UserRole.ADMIN
        )
        
        self.users["admin"] = admin
        logger.info("Default admin user created (username: admin, password: admin123)")
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username: str, password: str, role: UserRole) -> bool:
        """
        Create a new user
        
        Args:
            username: Username
            password: Plain text password
            role: User role
            
        Returns:
            True if user created successfully
        """
        try:
            if username in self.users:
                logger.warning(f"User {username} already exists")
                return False
            
            password_hash = self._hash_password(password)
            
            user = User(
                username=username,
                password_hash=password_hash,
                role=role
            )
            
            self.users[username] = user
            logger.info(f"User {username} created with role {role.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return False
    
    def delete_user(self, username: str) -> bool:
        """
        Delete a user
        
        Args:
            username: Username to delete
            
        Returns:
            True if user deleted successfully
        """
        try:
            if username == "admin":
                logger.error("Cannot delete admin user")
                return False
            
            if username not in self.users:
                logger.warning(f"User {username} not found")
                return False
            
            del self.users[username]
            
            # Invalidate all sessions for this user
            self.sessions = {
                token: session for token, session in self.sessions.items()
                if session.username != username
            }
            
            logger.info(f"User {username} deleted")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete user: {e}")
            return False
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """
        Change user password
        
        Args:
            username: Username
            old_password: Current password
            new_password: New password
            
        Returns:
            True if password changed successfully
        """
        try:
            if username not in self.users:
                logger.warning(f"User {username} not found")
                return False
            
            user = self.users[username]
            old_hash = self._hash_password(old_password)
            
            if user.password_hash != old_hash:
                logger.warning(f"Invalid old password for user {username}")
                return False
            
            user.password_hash = self._hash_password(new_password)
            logger.info(f"Password changed for user {username}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to change password: {e}")
            return False
    
    def login(self, username: str, password: str, ip_address: Optional[str] = None) -> Optional[str]:
        """
        Authenticate user and create session
        
        Args:
            username: Username
            password: Password
            ip_address: Client IP address
            
        Returns:
            JWT token if authentication successful, None otherwise
        """
        try:
            if username not in self.users:
                logger.warning(f"Login failed: user {username} not found")
                return None
            
            user = self.users[username]
            
            if not user.enabled:
                logger.warning(f"Login failed: user {username} is disabled")
                return None
            
            password_hash = self._hash_password(password)
            
            if user.password_hash != password_hash:
                logger.warning(f"Login failed: invalid password for user {username}")
                return None
            
            # Create JWT token
            now = time.time()
            expires_at = now + (self.token_expiry_hours * 3600)
            
            payload = {
                "username": username,
                "role": user.role.value,
                "iat": now,
                "exp": expires_at
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm="HS256")
            
            # Create session
            session = Session(
                token=token,
                username=username,
                role=user.role,
                created_at=now,
                expires_at=expires_at,
                ip_address=ip_address
            )
            
            self.sessions[token] = session
            
            # Update last login
            user.last_login = now
            
            logger.info(f"User {username} logged in from {ip_address}")
            return token
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return None
    
    def logout(self, token: str) -> bool:
        """
        Logout user and invalidate session
        
        Args:
            token: JWT token
            
        Returns:
            True if logout successful
        """
        try:
            if token in self.sessions:
                username = self.sessions[token].username
                del self.sessions[token]
                logger.info(f"User {username} logged out")
                return True
            else:
                logger.warning("Invalid token for logout")
                return False
                
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token and return payload
        
        Args:
            token: JWT token
            
        Returns:
            Token payload if valid, None otherwise
        """
        try:
            # Check if session exists
            if token not in self.sessions:
                logger.warning("Token not found in active sessions")
                return None
            
            session = self.sessions[token]
            
            # Check if expired
            if time.time() > session.expires_at:
                logger.warning("Token expired")
                del self.sessions[token]
                return None
            
            # Verify JWT
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            if token in self.sessions:
                del self.sessions[token]
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None
    
    def check_permission(self, token: str, permission: Permission) -> bool:
        """
        Check if user has permission
        
        Args:
            token: JWT token
            permission: Required permission
            
        Returns:
            True if user has permission
        """
        try:
            payload = self.verify_token(token)
            if not payload:
                return False
            
            role = UserRole(payload["role"])
            
            return permission in ROLE_PERMISSIONS.get(role, [])
            
        except Exception as e:
            logger.error(f"Permission check error: {e}")
            return False
    
    def get_user_role(self, token: str) -> Optional[UserRole]:
        """
        Get user role from token
        
        Args:
            token: JWT token
            
        Returns:
            User role if token valid
        """
        try:
            payload = self.verify_token(token)
            if payload:
                return UserRole(payload["role"])
            return None
        except Exception as e:
            logger.error(f"Get role error: {e}")
            return None
    
    def list_users(self) -> List[Dict[str, Any]]:
        """
        List all users (excluding password hashes)
        
        Returns:
            List of user information
        """
        return [
            {
                "username": user.username,
                "role": user.role.value,
                "created_at": user.created_at,
                "last_login": user.last_login,
                "enabled": user.enabled
            }
            for user in self.users.values()
        ]
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """
        Get list of active sessions
        
        Returns:
            List of active session information
        """
        now = time.time()
        
        # Clean up expired sessions
        expired = [token for token, session in self.sessions.items() if session.expires_at < now]
        for token in expired:
            del self.sessions[token]
        
        return [
            {
                "username": session.username,
                "role": session.role.value,
                "created_at": session.created_at,
                "expires_at": session.expires_at,
                "ip_address": session.ip_address
            }
            for session in self.sessions.values()
        ]


# Decorator for route protection
def require_auth(permission: Optional[Permission] = None):
    """
    Decorator to require authentication and optional permission
    
    Args:
        permission: Required permission (None means just authentication)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # This is a placeholder - actual implementation would integrate with Flask
            # and extract token from request headers
            pass
        return wrapper
    return decorator
