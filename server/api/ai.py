"""AI 审查 API 路由

提供 AI 代码审查相关的 REST API 接口
"""

import logging
import sys
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.gitlab.client import GitLabClient
from src.gitlab.models import MergeRequestInfo, DiffFile
from src.ai.reviewer import create_reviewer
from src.core.database import DatabaseManager
from src.core.auth import verify_token
from src.core.exceptions import (
    GitLabException,
    GitLabNotFoundError,
    AIException,
    AIConnectionError,
    AIAuthError,
    AIQuotaError,
    AIModelNotFoundError,
)

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


def get_gitlab_client(
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
) -> GitLabClient:
    """获取当前用户的 GitLab 客户端"""
    config = db.get_gitlab_config(user_id)
    if not config:
        raise HTTPException(
            status_code=400,
            detail="请先连接到 GitLab",
        )

    return GitLabClient(
        url=config["url"],
        token=config["token"],
    )


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

def _build_review_config(ai_config: dict, provider: str) -> dict:
    """构建审查配置"""
    config = {
        "provider": provider,
        "temperature": 0.3,
        "max_tokens": 2000,
        "review_rules": ai_config.get("review_rules", []),
    }

    if provider == "openai":
        config.update({
            "api_key": ai_config.get("openai_api_key", ""),
            "model": ai_config.get("openai_model", "gpt-4"),
            "base_url": ai_config.get("openai_base_url"),
            "temperature": ai_config.get("openai_temperature", 0.3),
            "max_tokens": ai_config.get("openai_max_tokens", 2000),
        })
    elif provider == "ollama":
        config.update({
            "base_url": ai_config.get("ollama_base_url", "http://localhost:11434"),
            "model": ai_config.get("ollama_model", "codellama"),
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

        # 获取 Diff
        diff_files = client.get_merge_request_diffs(project_id, mr_iid)

        # 创建审查器
        reviewer = create_reviewer(**config)

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

    except GitLabException as e:
        logger.error(f"审查任务失败 (GitLab错误): {e}")
        _review_tasks[task_id] = {
            "status": "error",
            "error": str(e),
        }
    except AIAuthError as e:
        logger.error(f"审查任务失败 (AI认证错误): {e}")
        _review_tasks[task_id] = {
            "status": "error",
            "error": str(e),
        }
    except AIQuotaError as e:
        logger.error(f"审查任务失败 (AI配额错误): {e}")
        _review_tasks[task_id] = {
            "status": "error",
            "error": str(e),
        }
    except AIModelNotFoundError as e:
        logger.error(f"审查任务失败 (AI模型错误): {e}")
        _review_tasks[task_id] = {
            "status": "error",
            "error": str(e),
        }
    except AIConnectionError as e:
        logger.error(f"审查任务失败 (AI连接错误): {e}")
        _review_tasks[task_id] = {
            "status": "error",
            "error": str(e),
        }
    except AIException as e:
        logger.error(f"审查任务失败 (AI错误): {e}")
        _review_tasks[task_id] = {
            "status": "error",
            "error": str(e),
        }
    except Exception as e:
        logger.error(f"审查任务失败 (未知错误): {e}", exc_info=True)
        _review_tasks[task_id] = {
            "status": "error",
            "error": f"审查失败: {str(e)}",
        }


# ==================== API 端点 ====================

@router.post("/review", response_model=dict)
async def start_review(
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
    client: GitLabClient = Depends(get_gitlab_client),
):
    """启动 AI 审查任务"""
    # 获取用户的 AI 配置
    ai_config = db.get_ai_config(user_id)
    if not ai_config:
        raise HTTPException(status_code=400, detail="请先配置 AI")

    provider = request.provider or ai_config.get("provider", "openai")
    if provider == "openai" and not ai_config.get("openai_api_key"):
        raise HTTPException(status_code=400, detail="OpenAI API Key 未配置")

    # 生成任务 ID
    import uuid
    task_id = str(uuid.uuid4())

    # 初始化任务状态
    _review_tasks[task_id] = {
        "status": "running",
    }

    # 构建配置
    config = _build_review_config(ai_config, provider)

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
async def review_single_file(
    request: FileReviewRequest,
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
    client: GitLabClient = Depends(get_gitlab_client),
):
    """审查单个文件"""
    # 获取用户的 AI 配置
    ai_config = db.get_ai_config(user_id)
    if not ai_config:
        raise HTTPException(status_code=400, detail="请先配置 AI")

    provider = request.provider or ai_config.get("provider", "openai")
    if provider == "openai" and not ai_config.get("openai_api_key"):
        raise HTTPException(status_code=400, detail="OpenAI API Key 未配置")

    try:
        # 获取 MR 信息
        mr = client.get_merge_request(request.project_id, request.mr_iid)

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
        config = _build_review_config(ai_config, provider)
        reviewer = create_reviewer(**config)

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

    except GitLabNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitLabException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except AIAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except AIQuotaError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except AIModelNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AIConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except AIException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件审查失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"审查失败: {str(e)}")


@router.get("/config")
async def get_ai_config(
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """获取当前用户的 AI 配置"""
    ai_config = db.get_ai_config(user_id)
    if not ai_config:
        raise HTTPException(status_code=404, detail="AI 配置不存在")

    return {
        "provider": ai_config.get("provider"),
        "openai": {
            "model": ai_config.get("openai_model"),
            "base_url": ai_config.get("openai_base_url"),
            "api_key": "***",  # 不返回完整 key
            "temperature": ai_config.get("openai_temperature"),
            "max_tokens": ai_config.get("openai_max_tokens"),
        },
        "ollama": {
            "base_url": ai_config.get("ollama_base_url"),
            "model": ai_config.get("ollama_model"),
        },
        "review_rules": ai_config.get("review_rules", []),
    }
