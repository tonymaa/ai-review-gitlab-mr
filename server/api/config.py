"""配置管理 API"""

import logging
import sys
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import DatabaseManager
from src.core.auth import verify_token
from src.core.config import settings

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

class GitLabConfigModel(BaseModel):
    """GitLab 配置模型"""
    url: str = Field(..., description="GitLab 服务器地址")
    token: str = Field(..., description="个人访问令牌")
    default_project_id: Optional[str] = Field(None, description="默认项目 ID 或路径")


class OpenAIConfigModel(BaseModel):
    """OpenAI 配置模型"""
    api_key: str = Field(..., description="OpenAI API 密钥")
    base_url: Optional[str] = Field(None, description="自定义 API 端点")
    model: str = Field(default="gpt-4", description="使用的模型")
    temperature: float = Field(default=0.3, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=4000, ge=1, description="最大 token 数")


class OllamaConfigModel(BaseModel):
    """Ollama 配置模型"""
    base_url: str = Field(default="http://localhost:11434", description="Ollama 服务地址")
    model: str = Field(default="codellama", description="使用的模型")


class AIConfigModel(BaseModel):
    """AI 配置模型"""
    provider: str = Field(default="openai", description="AI 服务提供商")
    openai: OpenAIConfigModel
    ollama: OllamaConfigModel
    review_rules: list[str] = Field(
        default=[
            "检查代码是否符合PEP8规范",
            "检查是否有潜在的安全漏洞",
            "检查是否有性能优化空间",
            "检查代码可读性和可维护性",
            "检查错误处理是否完善",
            "检查是否有重复代码",
            "检查是否缺少必要的注释和文档",
        ],
        description="审查规则列表",
    )


class ConfigResponse(BaseModel):
    """配置响应"""
    gitlab: Optional[GitLabConfigModel] = None
    ai: Optional[AIConfigModel] = None
    allow_registration: bool = Field(default=True, description="是否允许用户注册")


class UpdateConfigRequest(BaseModel):
    """更新配置请求"""
    gitlab: Optional[GitLabConfigModel] = None
    ai: Optional[AIConfigModel] = None


# ==================== API 端点 ====================

@router.get("/config", response_model=ConfigResponse)
async def get_config(
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """
    获取当前用户配置
    """
    # 获取应用配置
    allow_registration = settings.app.allow_registration

    # 获取 GitLab 配置
    gitlab_config = db.get_gitlab_config(user_id)
    gitlab_response = None
    if gitlab_config:
        gitlab_response = GitLabConfigModel(
            url=gitlab_config["url"],
            token=gitlab_config["token"],
            default_project_id=gitlab_config["default_project_id"],
        )

    # 获取 AI 配置
    ai_config = db.get_ai_config(user_id)
    ai_response = None
    if ai_config:
        ai_response = AIConfigModel(
            provider=ai_config["provider"],
            openai=OpenAIConfigModel(
                api_key=ai_config["openai_api_key"] or "",
                base_url=ai_config["openai_base_url"],
                model=ai_config["openai_model"],
                temperature=ai_config["openai_temperature"],
                max_tokens=ai_config["openai_max_tokens"],
            ),
            ollama=OllamaConfigModel(
                base_url=ai_config["ollama_base_url"],
                model=ai_config["ollama_model"],
            ),
            review_rules=ai_config["review_rules"] or [],
        )

    return ConfigResponse(
        gitlab=gitlab_response,
        ai=ai_response,
        allow_registration=allow_registration
    )


@router.post("/config")
async def update_config(
    request: UpdateConfigRequest,
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """
    更新配置（需要认证）
    """
    # 更新 GitLab 配置
    if request.gitlab:
        db.upsert_gitlab_config(
            user_id=user_id,
            url=request.gitlab.url,
            token=request.gitlab.token,
            default_project_id=request.gitlab.default_project_id,
        )
        logger.info(f"用户 {user_id} 更新了 GitLab 配置")

    # 更新 AI 配置
    if request.ai:
        db.upsert_ai_config(
            user_id=user_id,
            provider=request.ai.provider,
            openai_api_key=request.ai.openai.api_key,
            openai_base_url=request.ai.openai.base_url,
            openai_model=request.ai.openai.model,
            openai_temperature=request.ai.openai.temperature,
            openai_max_tokens=request.ai.openai.max_tokens,
            ollama_base_url=request.ai.ollama.base_url,
            ollama_model=request.ai.ollama.model,
            review_rules=request.ai.review_rules,
        )
        logger.info(f"用户 {user_id} 更新了 AI 配置")

    return {"status": "ok", "message": "配置已更新"}
