"""AI 审查 API 路由

提供 AI 代码审查相关的 REST API 接口
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.gitlab.client import GitLabClient
from src.gitlab.models import MergeRequestInfo, DiffFile
from src.ai.reviewer import create_reviewer
from src.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# 全局 GitLab 客户端引用 (从 gitlab 模块共享)
from server.api import gitlab
_gitlab_client = lambda: gitlab._gitlab_client


# ==================== Request/Response 模型 ====================

class ReviewRequest(BaseModel):
    """AI 审查请求"""
    project_id: str
    mr_iid: int
    provider: str = "openai"
    quick_mode: bool = False


class FileReviewRequest(BaseModel):
    """单文件审查请求"""
    project_id: str
    mr_iid: int
    file_path: str
    provider: str = "openai"


class ReviewComment(BaseModel):
    """审查评论"""
    file_path: str
    line_number: int | None = None
    content: str
    severity: str = "suggestion"  # critical, warning, suggestion


class ReviewResponse(BaseModel):
    """审查响应"""
    status: str
    summary: str
    overall_score: int
    issues_count: int
    suggestions_count: int
    comments: List[ReviewComment]


# ==================== 全局状态管理 ====================

# 存储正在进行的审查任务
_review_tasks: dict = {}


# ==================== 辅助函数 ====================

def _build_review_config(provider: str) -> dict:
    """构建审查配置"""
    config = {
        "provider": provider,
        "temperature": 0.3,
        "max_tokens": 2000,
        "review_rules": settings.ai.review_rules,
    }

    if provider == "openai":
        config.update({
            "api_key": settings.ai.openai.api_key,
            "model": settings.ai.openai.model,
            "base_url": settings.ai.openai.base_url,
            "temperature": settings.ai.openai.temperature,
            "max_tokens": settings.ai.openai.max_tokens,
        })
    elif provider == "ollama":
        config.update({
            "base_url": settings.ai.ollama.base_url,
            "model": settings.ai.ollama.model,
        })

    return config


def _convert_result_to_comments(result, mr_title: str = "") -> List[ReviewComment]:
    """将 AIReviewResult 转换为评论列表"""
    comments = []

    # 从 file_reviews 中提取评论
    for file_path, file_review_list in result.file_reviews.items():
        if isinstance(file_review_list, list):
            for review_item in file_review_list:
                if isinstance(review_item, dict):
                    line_number = review_item.get("line_number")
                    description = review_item.get("description", "")
                    severity = review_item.get("severity", "suggestion")

                    if description:
                        content = f"{severity.capitalize()}: {description}"
                        comments.append(ReviewComment(
                            file_path=file_path,
                            line_number=line_number,
                            content=content,
                            severity=severity,
                        ))

    # 如果 file_reviews 为空，从 critical_issues/warnings/suggestions 提取
    if not comments:
        all_items = []

        for issue in result.critical_issues:
            all_items.append(("critical", issue))

        for warning in result.warnings:
            all_items.append(("warning", warning))

        for suggestion in result.suggestions:
            all_items.append(("suggestion", suggestion))

        # 解析每个条目
        for severity, full_desc in all_items[:20]:
            parts = full_desc.split(" - ", 1)
            if len(parts) >= 2:
                location_part = parts[0]
                description_part = parts[1]

                file_path = location_part
                line_number = None

                if ":" in location_part:
                    path_parts = location_part.rsplit(":", 1)
                    if path_parts[-1].isdigit():
                        file_path = path_parts[0]
                        line_number = int(path_parts[-1])

                comments.append(ReviewComment(
                    file_path=file_path,
                    line_number=line_number,
                    content=f"{severity.capitalize()}: {description_part}",
                    severity=severity,
                ))

    return comments


def _run_review(task_id: str, client: GitLabClient, project_id: str, mr_iid: int, config: dict, quick_mode: bool = False):
    """后台执行审查任务"""
    try:
        # 获取 MR 信息
        mr = client.get_merge_request(project_id, mr_iid)
        if not mr:
            _review_tasks[task_id] = {
                "status": "error",
                "error": "MR 不存在",
            }
            return

        # 获取 Diff
        diff_files = client.get_merge_request_diffs(project_id, mr_iid)

        # 创建审查器
        reviewer = create_reviewer(config["provider"], **config)

        # 执行审查
        result = reviewer.review_merge_request(
            mr=mr,
            diff_files=diff_files,
            review_rules=config["review_rules"],
            quick_mode=quick_mode,
        )

        # 转换结果
        comments = _convert_result_to_comments(result, mr.title)

        _review_tasks[task_id] = {
            "status": "completed",
            "result": ReviewResponse(
                status="completed",
                summary=result.summary,
                overall_score=result.overall_score,
                issues_count=result.issues_count,
                suggestions_count=result.suggestions_count,
                comments=comments,
            ),
        }

    except Exception as e:
        logger.error(f"审查任务失败: {e}", exc_info=True)
        _review_tasks[task_id] = {
            "status": "error",
            "error": str(e),
        }


# ==================== API 端点 ====================

@router.post("/review", response_model=dict)
async def start_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    """启动 AI 审查任务"""
    client = _gitlab_client()
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

    # 检查 AI 配置
    provider = request.provider or settings.ai.provider
    if provider == "openai" and not settings.ai.openai.api_key:
        raise HTTPException(status_code=400, detail="OpenAI API Key 未配置")

    # 生成任务 ID
    import uuid
    task_id = str(uuid.uuid4())

    # 初始化任务状态
    _review_tasks[task_id] = {
        "status": "running",
    }

    # 构建配置
    config = _build_review_config(provider)

    # 启动后台任务
    background_tasks.add_task(
        _run_review,
        task_id,
        client,
        request.project_id,
        request.mr_iid,
        config,
        request.quick_mode,
    )

    return {
        "status": "started",
        "task_id": task_id,
    }


@router.get("/review/{task_id}")
async def get_review_status(task_id: str):
    """获取审查任务状态"""
    if task_id not in _review_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = _review_tasks[task_id]

    if task["status"] == "completed":
        return task["result"]
    elif task["status"] == "error":
        raise HTTPException(status_code=500, detail=task.get("error", "审查失败"))
    else:
        return {"status": "running"}


@router.post("/review/file", response_model=ReviewResponse)
async def review_single_file(request: FileReviewRequest):
    """审查单个文件"""
    client = _gitlab_client()
    if not client:
        raise HTTPException(status_code=401, detail="未连接到 GitLab")

    # 检查 AI 配置
    provider = request.provider or settings.ai.provider
    if provider == "openai" and not settings.ai.openai.api_key:
        raise HTTPException(status_code=400, detail="OpenAI API Key 未配置")

    try:
        # 获取 MR 信息
        mr = client.get_merge_request(request.project_id, request.mr_iid)
        if not mr:
            raise HTTPException(status_code=404, detail="MR 不存在")

        # 获取所有 Diff
        all_diffs = client.get_merge_request_diffs(request.project_id, request.mr_iid)

        # 找到指定文件
        target_diff = None
        for diff in all_diffs:
            if diff.new_path == request.file_path or diff.old_path == request.file_path:
                target_diff = diff
                break

        if not target_diff:
            raise HTTPException(status_code=404, detail="文件不存在")

        # 创建审查器
        config = _build_review_config(provider)
        reviewer = create_reviewer(provider, **config)

        # 执行审查
        result = reviewer.review_merge_request(
            mr=mr,
            diff_files=[target_diff],
            review_rules=config["review_rules"],
            quick_mode=False,
        )

        # 转换结果
        comments = _convert_result_to_comments(result, mr.title)

        return ReviewResponse(
            status="completed",
            summary=result.summary,
            overall_score=result.overall_score,
            issues_count=result.issues_count,
            suggestions_count=result.suggestions_count,
            comments=comments,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件审查失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_ai_config():
    """获取 AI 配置"""
    return {
        "provider": settings.ai.provider,
        "openai": {
            "model": settings.ai.openai.model,
            "base_url": settings.ai.openai.base_url,
            "api_key": "***",  # 不返回完整 key
            "temperature": settings.ai.openai.temperature,
            "max_tokens": settings.ai.openai.max_tokens,
        },
        "ollama": {
            "base_url": settings.ai.ollama.base_url,
            "model": settings.ai.ollama.model,
        },
        "review_rules": settings.ai.review_rules,
    }
