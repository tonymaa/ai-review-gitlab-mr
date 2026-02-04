"""认证工具模块

提供 JWT token 生成和验证功能
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# JWT 配置
SECRET_KEY = "your-secret-key-change-this-in-production"  # 生产环境应该从配置文件读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 180  # 180天


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
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
