"""What's New API - 从 GitHub Releases 拉取最新发布信息"""

import logging
import os
import time

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

logger = logging.getLogger(__name__)

# GitHub API 配置
GITHUB_API_BASE = "https://api.github.com"
GITHUB_REPO_ENV = "WHATS_NEW_REPO"
# 内存缓存：5 分钟避免频繁打 GitHub
CACHE_TTL_SECONDS = 300
_cache: dict[str, object] = {"data": None, "fetched_at": 0.0}


class WhatsNewResponse(BaseModel):
    """最新发布信息"""
    id: int
    tag_name: str
    name: str
    published_at: str
    body: str
    html_url: str


def _get_repo() -> str | None:
    """从环境变量读取 GitHub 仓库路径，格式 owner/repo"""
    repo = os.environ.get(GITHUB_REPO_ENV, "").strip()
    if not repo:
        return None
    # 简单校验格式
    if "/" not in repo:
        logger.warning(f"环境变量 {GITHUB_REPO_ENV} 格式错误，应为 owner/repo: {repo}")
        return None
    return repo


@router.get("/whats-new/latest", response_model=WhatsNewResponse | None)
async def get_latest_release():
    """获取最新正式 release 信息（跳过 prerelease 和 draft）

    环境变量未配置时返回 null，前端静默不弹窗。
    """
    repo = _get_repo()
    if repo is None:
        return None

    # 缓存命中直接返回
    now = time.time()
    cached = _cache.get("data")
    if cached is not None and now - float(_cache.get("fetched_at", 0.0)) < CACHE_TTL_SECONDS:
        return cached

    url = f"{GITHUB_API_BASE}/repos/{repo}/releases/latest"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        if resp.status_code == 404:
            # 没有任何 release，缓存空结果
            _cache["data"] = None
            _cache["fetched_at"] = now
            return None
        resp.raise_for_status()
        data = resp.json()
        # releases/latest 本身就跳过 prerelease/draft
        result = WhatsNewResponse(
            id=data["id"],
            tag_name=data["tag_name"],
            name=data.get("name") or data["tag_name"],
            published_at=data["published_at"],
            body=data.get("body") or "",
            html_url=data["html_url"],
        )
        _cache["data"] = result
        _cache["fetched_at"] = now
        return result
    except httpx.HTTPError as e:
        logger.warning(f"获取 GitHub release 失败: {e}")
        # 网络错误时返回上次缓存（如果有），否则 502
        if cached is not None:
            return cached
        raise HTTPException(status_code=502, detail=f"获取 release 失败: {e}")
    except Exception as e:
        logger.error(f"获取 release 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))
