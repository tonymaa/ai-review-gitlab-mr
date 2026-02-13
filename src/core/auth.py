"""认证工具模块

提供 JWT token 生成和验证功能
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import JWTError, jwt

logger = logging.getLogger(__name__)


def _get_jwt_config():
    """延迟导入配置，避免循环导入"""
    from src.core.config import settings
    return settings.jwt


# JWT 配置（从配置读取）
def get_secret_key() -> str:
    """获取JWT密钥"""
    return _get_jwt_config().secret_key


def get_algorithm() -> str:
    """获取JWT算法"""
    return _get_jwt_config().algorithm


def get_expire_minutes() -> int:
    """获取Token过期时间（分钟）"""
    return _get_jwt_config().expire_minutes


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问令牌

    Args:
        data: 要编码的数据（通常包含 user_id, username 等）
        expires_delta: 过期时间增量

    Returns:
        JWT token 字符串
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=get_expire_minutes())

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=get_algorithm())

    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    解码访问令牌

    Args:
        token: JWT token 字符串

    Returns:
        解码后的数据，如果 token 无效则返回 None
    """
    try:
        logger.info(f"[decode_access_token] Attempting to decode token, length: {len(token) if token else 0}")
        payload = jwt.decode(token, get_secret_key(), algorithms=[get_algorithm()])
        logger.info(f"[decode_access_token] Token decoded successfully, payload: {payload}")
        return payload
    except JWTError as e:
        logger.warning(f"Token 解码失败: {e}")
        return None


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证 token 有效性

    Args:
        token: JWT token 字符串

    Returns:
        token 数据，验证失败返回 None
    """
    payload = decode_access_token(token)
    if payload is None:
        return None

    # 检查过期时间（虽然 jwt.decode 已经自动检查了）
    expire = payload.get("exp")
    if expire and datetime.utcnow() > datetime.fromtimestamp(expire):
        return None

    return payload
