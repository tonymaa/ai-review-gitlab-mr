"""自动审查配置和状态管理 API

提供自动审查配置、状态查询和手动触发等 REST API 接口
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import DatabaseManager
from src.core.auth import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()

# HTTP Bearer 认证
security = HTTPBearer()


# ==================== 依赖注入 ====================

def get_db() -> DatabaseManager:
    """获取数据库管理器"""
    from server.main import app
    db: DatabaseManager = app.state.db
    return db


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: DatabaseManager = Depends(get_db),
) -> int:
    """从 token 获取当前用户 ID"""
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=401,
            detail="Token 中没有用户信息",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Token 中的用户 ID 格式无效",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==================== Request/Response 模型 ====================

class AutoReviewConfigRequest(BaseModel):
    """自动审查配置请求"""
    enabled: bool = Field(default=False, description="是否启用自动审查")
    interval_seconds: int = Field(default=120, ge=10, le=3600, description="检查间隔（秒）")
    target_creators: List[str] = Field(default_factory=list, description="MR创建者用户名列表")
    target_projects: List[str] = Field(default_factory=list, description="目标项目ID列表")
    auto_approve_keywords: List[str] = Field(default_factory=list, description="自动批准关键词列表")
    auto_approve_mode: str = Field(default="always", description="自动批准模式: always, keyword_only, never")
    add_as_comment: bool = Field(default=True, description="是否将总结添加为MR评论")


class AutoReviewConfigResponse(BaseModel):
    """自动审查配置响应"""
    enabled: bool
    interval_seconds: int
    target_creators: List[str]
    target_projects: List[str]
    auto_approve_keywords: List[str]
    auto_approve_mode: str
    add_as_comment: bool
    is_running: bool = Field(default=False, description="当前任务是否运行中")
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None


class AutoReviewStatusResponse(BaseModel):
    """自动审查状态响应"""
    is_enabled: bool
    is_running: bool
    last_run_at: Optional[str]
    next_run_at: Optional[str]
    processed_count: int = Field(default=0, description="已处理的MR数量")
    last_processed_mr: Optional[dict] = None


# ==================== 全局状态管理 ====================

# 存储每个用户的任务运行状态
_user_task_status: dict[int, dict] = {}


def get_user_task_status(user_id: int) -> dict:
    """获取用户任务状态"""
    if user_id not in _user_task_status:
        _user_task_status[user_id] = {
            "is_running": False,
            "last_run_at": None,
            "next_run_at": None,
        }
    return _user_task_status[user_id]


def update_user_task_status(user_id: int, **kwargs):
    """更新用户任务状态"""
    if user_id not in _user_task_status:
        _user_task_status[user_id] = {
            "is_running": False,
            "last_run_at": None,
            "next_run_at": None,
        }
    _user_task_status[user_id].update(kwargs)


# ==================== API 端点 ====================

@router.get("/config", response_model=AutoReviewConfigResponse)
async def get_auto_review_config(
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """获取自动审查配置"""
    config = db.get_auto_review_config(user_id)

    # 如果没有配置，返回默认配置
    if not config:
        config = {
            "enabled": False,
            "interval_seconds": 120,
            "target_creators": [],
            "target_projects": [],
            "auto_approve_keywords": [],
            "auto_approve_mode": "always",
            "add_as_comment": True,
        }

    # 获取任务状态
    task_status = get_user_task_status(user_id)

    return AutoReviewConfigResponse(
        **config,
        is_running=task_status["is_running"],
        last_run_at=task_status["last_run_at"],
        next_run_at=task_status["next_run_at"],
    )


@router.post("/config")
async def update_auto_review_config(
    request: AutoReviewConfigRequest,
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """更新自动审查配置"""
    # 保存配置到数据库
    db.upsert_auto_review_config(
        user_id=user_id,
        enabled=request.enabled,
        interval_seconds=request.interval_seconds,
        target_creators=request.target_creators,
        target_projects=request.target_projects,
        auto_approve_keywords=request.auto_approve_keywords,
        auto_approve_mode=request.auto_approve_mode,
        add_as_comment=request.add_as_comment,
    )

    logger.info(f"用户 {user_id} 更新了自动审查配置: enabled={request.enabled}")

    # 获取调度器
    scheduler = getattr(get_db().engine, "auto_review_scheduler", None)
    if scheduler:
        if request.enabled:
            # 检查任务是否已在运行
            if user_id in scheduler._tasks and not scheduler._tasks[user_id].done():
                # 任务已在运行，需要重启以应用新配置
                await scheduler.restart_user_task(user_id, request.interval_seconds)
                logger.info(f"用户 {user_id} 的自动审查任务已重启")
            else:
                # 任务未运行，直接启动
                await scheduler.start_user_task(user_id)
                logger.info(f"用户 {user_id} 的自动审查任务已启动")
        else:
            # 禁用，停止任务
            await scheduler.stop_user_task(user_id)
            logger.info(f"用户 {user_id} 的自动审查任务已停止")

    return {"status": "ok", "message": "配置已更新"}


@router.get("/status", response_model=AutoReviewStatusResponse)
async def get_auto_review_status(
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """获取自动审查运行状态"""
    config = db.get_auto_review_config(user_id)
    task_status = get_user_task_status(user_id)

    # 获取已处理的 MR 数量
    processed_count = db.get_processed_mr_count(user_id)

    return AutoReviewStatusResponse(
        is_enabled=config["enabled"] if config else False,
        is_running=task_status["is_running"],
        last_run_at=task_status["last_run_at"],
        next_run_at=task_status["next_run_at"],
        processed_count=processed_count,
    )


@router.post("/run-now")
async def run_auto_review_now(
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """立即执行一次自动审查"""
    config = db.get_auto_review_config(user_id)
    if not config or not config["enabled"]:
        raise HTTPException(status_code=400, detail="自动审查未启用")

    # 获取调度器并触发一次运行
    scheduler = getattr(get_db().engine, "auto_review_scheduler", None)
    if not scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")

    # 在后台执行
    background_tasks.add_task(scheduler.trigger_single_run, user_id)

    return {"status": "ok", "message": "已触发自动审查任务"}
