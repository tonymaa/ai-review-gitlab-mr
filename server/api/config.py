"""配置管理 API"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class GitLabConfigModel(BaseModel):
    """GitLab 配置模型"""
    url: str
    token: str
    default_project_id: str | None = None


class AIConfigModel(BaseModel):
    """AI 配置模型"""
    provider: str
    openai_api_key: str
    openai_base_url: str | None = None
    openai_model: str
    openai_temperature: float
    openai_max_tokens: int
    ollama_base_url: str
    ollama_model: str
    review_rules: list[str]


class ConfigResponse(BaseModel):
    """配置响应"""
    gitlab: GitLabConfigModel
    ai: AIConfigModel


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """获取当前配置"""
    return ConfigResponse(
        gitlab=GitLabConfigModel(
            url=settings.gitlab.url,
            token=settings.gitlab.token,
            default_project_id=settings.gitlab.default_project_id,
        ),
        ai=AIConfigModel(
            provider=settings.ai.provider,
            openai_api_key=settings.ai.openai.api_key,
            openai_base_url=settings.ai.openai.base_url,
            openai_model=settings.ai.openai.model,
            openai_temperature=settings.ai.openai.temperature,
            openai_max_tokens=settings.ai.openai.max_tokens,
            ollama_base_url=settings.ai.ollama.base_url,
            ollama_model=settings.ai.ollama.model,
            review_rules=settings.ai.review_rules,
        ),
    )


class UpdateConfigRequest(BaseModel):
    """更新配置请求"""
    gitlab: GitLabConfigModel | None = None
    ai: AIConfigModel | None = None


@router.post("/config")
async def update_config(request: UpdateConfigRequest):
    """更新配置 (注意：这只是临时更新，不会保存到文件)"""
    # 更新 GitLab 配置
    if request.gitlab:
        settings.gitlab.url = request.gitlab.url
        settings.gitlab.token = request.gitlab.token
        settings.gitlab.default_project_id = request.gitlab.default_project_id

    # 更新 AI 配置
    if request.ai:
        settings.ai.provider = request.ai.provider
        settings.ai.openai.api_key = request.ai.openai_api_key
        settings.ai.openai.base_url = request.ai.openai_base_url
        settings.ai.openai.model = request.ai.openai_model
        settings.ai.openai.temperature = request.ai.openai_temperature
        settings.ai.openai.max_tokens = request.ai.openai_max_tokens
        settings.ai.ollama.base_url = request.ai.ollama_base_url
        settings.ai.ollama.model = request.ai.ollama_model
        settings.ai.review_rules = request.ai.review_rules

    return {"status": "ok", "message": "配置已更新"}
