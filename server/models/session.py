"""会话管理模块

管理客户端连接状态和会话数据
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器"""

    def __init__(self):
        """初始化会话管理器"""
        # 存储会话数据: session_id -> session_data
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, session_id: str) -> Dict[str, Any]:
        """创建新会话"""
        session = {
            "id": session_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "gitlab_connected": False,
            "gitlab_url": None,
            "current_project_id": None,
        }
        self._sessions[session_id] = session
        logger.info(f"创建会话: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        return self._sessions.get(session_id)

    def update_session(self, session_id: str, **kwargs):
        """更新会话数据"""
        if session_id in self._sessions:
            self._sessions[session_id].update(kwargs)
            self._sessions[session_id]["last_activity"] = datetime.now()

    def delete_session(self, session_id: str):
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"删除会话: {session_id}")

    def cleanup_expired_sessions(self, max_age_hours: int = 24):
        """清理过期会话"""
        now = datetime.now()
        expired_sessions = []

        for session_id, session in self._sessions.items():
            last_activity = session.get("last_activity", session["created_at"])
            if now - last_activity > timedelta(hours=max_age_hours):
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            self.delete_session(session_id)

        if expired_sessions:
            logger.info(f"清理了 {len(expired_sessions)} 个过期会话")
