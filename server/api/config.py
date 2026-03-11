"""配置管理 API"""

import logging
import sys
from pathlib import Path
from typing import Optional, List
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
    api_key: str = Field(default="", description="OpenAI API 密钥")
    base_url: Optional[str] = Field(None, description="自定义 API 端点")
    model: str = Field(default="gpt-4", description="使用的模型")
    temperature: float = Field(default=0.3, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=4000, ge=1, description="最大 token 数")


class OllamaConfigModel(BaseModel):
    """Ollama 配置模型"""
    base_url: str = Field(default="http://localhost:11434", description="Ollama 服务地址")
    model: str = Field(default="codellama", description="使用的模型")


class AIProviderModel(BaseModel):
    """AI Provider 配置模型"""
    id: Optional[int] = Field(None, description="Provider ID")
    name: str = Field(..., description="Provider 名称")
    provider_type: str = Field(..., description="Provider 类型: openai, ollama")
    openai: Optional[OpenAIConfigModel] = None
    ollama: Optional[OllamaConfigModel] = None


class AIProviderCreateModel(BaseModel):
    """创建 AI Provider 请求模型"""
    name: str = Field(..., description="Provider 名称")
    provider_type: str = Field(..., description="Provider 类型: openai, ollama")
    openai: Optional[OpenAIConfigModel] = None
    ollama: Optional[OllamaConfigModel] = None


class AIProviderUpdateModel(BaseModel):
    """更新 AI Provider 请求模型"""
    name: Optional[str] = Field(None, description="Provider 名称")
    provider_type: Optional[str] = Field(None, description="Provider 类型: openai, ollama")
    openai: Optional[OpenAIConfigModel] = None
    ollama: Optional[OllamaConfigModel] = None


class AIConfigModel(BaseModel):
    """AI 全局配置模型"""
    active_provider_id: Optional[int] = Field(None, description="当前激活的 Provider ID")
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
    summary_prompt: Optional[str] = Field(
        default=None,
        description="AI 总结提示词模板，支持 {mr_title}, {source_branch}, {target_branch}, {description}, {files_changed}, {diff_content} 变量"
    )


class AIProvidersResponse(BaseModel):
    """AI Providers 响应"""
    providers: List[AIProviderModel]
    active_provider_id: Optional[int] = None


class ConfigResponse(BaseModel):
    """配置响应"""
    gitlab: Optional[GitLabConfigModel] = None
    ai: Optional[AIConfigModel] = None
    providers: Optional[AIProvidersResponse] = None
    allow_registration: bool = Field(default=True, description="是否允许用户注册")


class UpdateConfigRequest(BaseModel):
    """更新配置请求"""
    gitlab: Optional[GitLabConfigModel] = None
    ai: Optional[AIConfigModel] = None


# ==================== 辅助函数 ====================

def db_provider_to_model(provider: dict) -> AIProviderModel:
    """将数据库 provider 字典转换为 API 模型"""
    return AIProviderModel(
        id=provider["id"],
        name=provider["name"],
        provider_type=provider["provider_type"],
        openai=OpenAIConfigModel(
            api_key=provider.get("openai_api_key") or "",
            base_url=provider.get("openai_base_url"),
            model=provider.get("openai_model", "gpt-4"),
            temperature=provider.get("openai_temperature", 0.3),
            max_tokens=provider.get("openai_max_tokens", 4000),
        ),
        ollama=OllamaConfigModel(
            base_url=provider.get("ollama_base_url", "http://localhost:11434"),
            model=provider.get("ollama_model", "codellama"),
        ),
    )


# ==================== 配置 API 端点 ====================

@router.get("", response_model=ConfigResponse)
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
            active_provider_id=ai_config.get("active_provider_id"),
            review_rules=ai_config.get("review_rules") or [],
            summary_prompt=ai_config.get("summary_prompt"),
        )

    # 获取 AI Providers
    providers = db.list_ai_providers(user_id)
    providers_response = AIProvidersResponse(
        providers=[db_provider_to_model(p) for p in providers],
        active_provider_id=ai_config.get("active_provider_id") if ai_config else None,
    )

    return ConfigResponse(
        gitlab=gitlab_response,
        ai=ai_response,
        providers=providers_response,
        allow_registration=allow_registration
    )


@router.post("")
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

    # 更新 AI 全局配置
    if request.ai:
        db.upsert_ai_config(
            user_id=user_id,
            active_provider_id=request.ai.active_provider_id,
            review_rules=request.ai.review_rules,
            summary_prompt=request.ai.summary_prompt,
        )
        logger.info(f"用户 {user_id} 更新了 AI 配置")

    return {"status": "ok", "message": "配置已更新"}


# ==================== AI Provider API 端点 ====================

@router.get("/providers")
async def list_providers(
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """
    获取用户的所有 AI Providers
    """
    providers = db.list_ai_providers(user_id)
    ai_config = db.get_ai_config(user_id)

    return {
        "providers": [db_provider_to_model(p).model_dump() for p in providers],
        "active_provider_id": ai_config.get("active_provider_id") if ai_config else None,
    }


@router.post("/providers")
async def create_provider(
    request: AIProviderCreateModel,
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """
    创建新的 AI Provider
    """
    # 验证 provider_type
    if request.provider_type not in ["openai", "ollama"]:
        raise HTTPException(status_code=400, detail="不支持的 provider 类型")

    # 获取配置
    openai_config = request.openai or OpenAIConfigModel()
    ollama_config = request.ollama or OllamaConfigModel()

    provider_id = db.create_ai_provider(
        user_id=user_id,
        name=request.name,
        provider_type=request.provider_type,
        openai_api_key=openai_config.api_key,
        openai_base_url=openai_config.base_url,
        openai_model=openai_config.model,
        openai_temperature=openai_config.temperature,
        openai_max_tokens=openai_config.max_tokens,
        ollama_base_url=ollama_config.base_url,
        ollama_model=ollama_config.model,
    )

    logger.info(f"用户 {user_id} 创建了 AI Provider: {request.name}")

    return {
        "status": "ok",
        "message": "Provider 已创建",
        "provider": db_provider_to_model(db.get_ai_provider(provider_id, user_id)).model_dump(),
    }


@router.get("/providers/{provider_id}")
async def get_provider(
    provider_id: int,
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """
    获取指定的 AI Provider
    """
    provider = db.get_ai_provider(provider_id, user_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider 不存在")

    return db_provider_to_model(provider).model_dump()


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: int,
    request: AIProviderUpdateModel,
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """
    更新 AI Provider
    """
    # 验证 provider 存在
    existing = db.get_ai_provider(provider_id, user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Provider 不存在")

    # 准备更新参数
    update_kwargs = {}
    if request.name is not None:
        update_kwargs["name"] = request.name
    if request.provider_type is not None:
        if request.provider_type not in ["openai", "ollama"]:
            raise HTTPException(status_code=400, detail="不支持的 provider 类型")
        update_kwargs["provider_type"] = request.provider_type

    # 更新 OpenAI 配置
    if request.openai:
        update_kwargs["openai_api_key"] = request.openai.api_key
        update_kwargs["openai_base_url"] = request.openai.base_url
        update_kwargs["openai_model"] = request.openai.model
        update_kwargs["openai_temperature"] = request.openai.temperature
        update_kwargs["openai_max_tokens"] = request.openai.max_tokens

    # 更新 Ollama 配置
    if request.ollama:
        update_kwargs["ollama_base_url"] = request.ollama.base_url
        update_kwargs["ollama_model"] = request.ollama.model

    provider = db.update_ai_provider(provider_id, user_id, **update_kwargs)

    logger.info(f"用户 {user_id} 更新了 AI Provider: {provider_id}")

    return {
        "status": "ok",
        "message": "Provider 已更新",
        "provider": db_provider_to_model(db.get_ai_provider(provider_id, user_id)).model_dump(),
    }


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: int,
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """
    删除 AI Provider
    """
    # 验证 provider 存在
    existing = db.get_ai_provider(provider_id, user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Provider 不存在")

    db.delete_ai_provider(provider_id, user_id)

    logger.info(f"用户 {user_id} 删除了 AI Provider: {provider_id}")

    return {"status": "ok", "message": "Provider 已删除"}


@router.post("/providers/{provider_id}/activate")
async def activate_provider(
    provider_id: int,
    user_id: int = Depends(get_current_user_id),
    db: DatabaseManager = Depends(get_db),
):
    """
    激活指定的 AI Provider
    """
    # 验证 provider 存在
    existing = db.get_ai_provider(provider_id, user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Provider 不存在")

    success = db.set_active_ai_provider(provider_id, user_id)
    if not success:
        raise HTTPException(status_code=500, detail="激活 Provider 失败")

    logger.info(f"用户 {user_id} 激活了 AI Provider: {provider_id}")

    return {"status": "ok", "message": "Provider 已激活"}
