"""认证 API 路由

提供用户注册、登录、登出等认证相关的 REST API 接口
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import DatabaseManager, User
from src.core.auth import create_access_token, verify_token
from src.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# HTTP Bearer 认证
security = HTTPBearer()


# ==================== 依赖注入 ====================

def get_db() -> DatabaseManager:
    """获取数据库管理器"""
    # 从应用状态中获取
    from server.main import app
    db: DatabaseManager = app.state.db
    return db


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: DatabaseManager = Depends(get_db),
) -> dict:
    """
    获取当前登录用户

    Args:
        credentials: HTTP Bearer 认证凭据
        db: 数据库管理器

    Returns:
        当前用户数据字典

    Raises:
        HTTPException: 认证失败时抛出 401 错误
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    logger.info(f"[get_current_user] Received token, length: {len(token) if token else 0}")

    payload = verify_token(token)
    if payload is None:
        logger.warning("[get_current_user] Token verification failed")
        raise credentials_exception

    user_id_str: str = payload.get("sub")
    logger.info(f"[get_current_user] Token payload user_id (str): {user_id_str}")
    if user_id_str is None:
        logger.warning("[get_current_user] No user_id in token payload")
        raise credentials_exception

    # 将字符串转换为整数
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        logger.warning(f"[get_current_user] Invalid user_id format: {user_id_str}")
        raise credentials_exception

    user_data = db.get_user_data(user_id)
    if user_data is None:
        logger.warning(f"[get_current_user] User not found in database: {user_id}")
        raise credentials_exception

    logger.info(f"[get_current_user] User authenticated successfully: {user_data.get('username')}")
    return user_data


async def get_current_active_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    获取当前活跃用户

    Args:
        current_user: 当前用户数据字典

    Returns:
        当前活跃用户数据字典

    Raises:
        HTTPException: 用户未激活时抛出 400 错误
    """
    if not current_user.get("is_active", False):
        raise HTTPException(status_code=400, detail="用户未激活")
    return current_user


# ==================== Request/Response 模型 ====================

class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户响应"""
    id: int
    username: str
    created_at: str
    is_active: bool

    @classmethod
    def from_dict(cls, data: dict) -> "UserResponse":
        return cls(
            id=data["id"],
            username=data["username"],
            created_at=data.get("created_at", ""),
            is_active=data["is_active"],
        )


class RegisterResponse(BaseModel):
    """注册响应"""
    status: str
    message: str
    user: UserResponse
    token: str


class LoginResponse(BaseModel):
    """登录响应"""
    status: str
    message: str
    user: UserResponse
    token: str


# ==================== API 端点 ====================

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: DatabaseManager = Depends(get_db)):
    """
    用户注册

    Args:
        request: 注册请求
        db: 数据库管理器

    Returns:
        注册响应，包含用户信息和 token
    """
    # 检查是否允许注册
    if not settings.app.allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="注册功能已关闭，请联系管理员",
        )

    try:
        # 创建用户 - create_user 已经返回 user_data 字典
        user_data = db.create_user(request.username, request.password)

        # 生成 token
        token_data = {
            "sub": str(user_data["id"]),  # JWT sub 必须是字符串
            "username": user_data["username"],
        }
        access_token = create_access_token(token_data)

        logger.info(f"用户注册成功: {request.username}")

        return RegisterResponse(
            status="ok",
            message="注册成功",
            user=UserResponse.from_dict(user_data),
            token=access_token,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"用户注册失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}",
        )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: DatabaseManager = Depends(get_db)):
    """
    用户登录

    Args:
        request: 登录请求
        db: 数据库管理器

    Returns:
        登录响应，包含用户信息和 token
    """
    try:
        # 验证用户
        user_data = db.verify_user(request.username, request.password)

        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user_data.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户已被禁用",
            )

        # 生成 token
        token_data = {
            "sub": str(user_data["id"]),  # JWT sub 必须是字符串
            "username": user_data["username"],
        }
        access_token = create_access_token(token_data)

        logger.info(f"用户登录成功: {request.username}")

        return LoginResponse(
            status="ok",
            message="登录成功",
            user=UserResponse.from_dict(user_data),
            token=access_token,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录失败: {str(e)}",
        )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_active_user)):
    """
    用户登出

    注：由于使用 JWT 无状态认证，登出主要在前端处理（删除 token）。
    此接口主要用于记录日志或执行其他清理操作。

    Args:
        current_user: 当前用户

    Returns:
        登出响应
    """
    logger.info(f"用户登出: {current_user['username']}")
    return {
        "status": "ok",
        "message": "登出成功",
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """
    获取当前用户信息

    Args:
        current_user: 当前用户数据字典

    Returns:
        当前用户信息
    """
    return UserResponse.from_dict(current_user)


@router.post("/verify-token")
async def verify_token_endpoint(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: DatabaseManager = Depends(get_db),
):
    """
    验证 token 有效性

    Args:
        credentials: HTTP Bearer 认证凭据
        db: 数据库管理器

    Returns:
        验证结果
    """
    payload = verify_token(credentials.credentials)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
        )

    user_id_str: str = payload.get("sub")
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 中的 user_id 格式无效",
        )

    user_data = db.get_user_data(user_id)

    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    return {
        "status": "ok",
        "message": "Token 有效",
        "user": UserResponse.from_dict(user_data),
    }
