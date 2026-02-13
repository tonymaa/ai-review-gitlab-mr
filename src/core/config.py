"""配置管理模块 - 使用Pydantic进行类型安全的配置管理"""

import os
from pathlib import Path
from typing import Optional, List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class GitLabConfig(BaseSettings):
    """GitLab配置"""

    model_config = SettingsConfigDict(env_prefix="GITLAB_")

    url: str = Field(default="", description="GitLab服务器地址")
    token: str = Field(default="", description="个人访问令牌")
    default_project_id: Optional[str] = Field(
        default=None, description="默认项目ID或路径"
    )


class OpenAIConfig(BaseSettings):
    """OpenAI配置"""

    model_config = SettingsConfigDict(env_prefix="OPENAI_")

    api_key: str = Field(default="", description="OpenAI API密钥")
    base_url: Optional[str] = Field(default=None, description="自定义API端点")
    model: str = Field(default="gpt-4", description="使用的模型")
    temperature: float = Field(default=0.3, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=4000, ge=1, description="最大token数")


class OllamaConfig(BaseSettings):
    """Ollama配置"""

    base_url: str = Field(default="http://localhost:11434", description="Ollama服务地址")
    model: str = Field(default="codellama", description="使用的模型")


class AIConfig(BaseSettings):
    """AI审查配置"""

    provider: str = Field(default="openai", description="AI服务提供商")
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    review_rules: List[str] = Field(
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


class UIConfig(BaseSettings):
    """UI配置"""

    theme: str = Field(default="default", description="界面主题")
    window_width: int = Field(default=1400, ge=800, description="窗口宽度")
    window_height: int = Field(default=900, ge=600, description="窗口高度")
    split_left: int = Field(default=300, ge=200, description="左侧面板宽度")
    split_right: int = Field(default=400, ge=200, description="右侧面板宽度")


class AutoRefreshConfig(BaseSettings):
    """自动刷新配置"""

    enabled: bool = Field(default=True, description="是否启用自动刷新")
    interval: int = Field(default=300, ge=10, description="刷新间隔(秒)")


class LoggingConfig(BaseSettings):
    """日志配置"""

    level: str = Field(default="INFO", description="日志级别")
    file: str = Field(default="./logs/app.log", description="日志文件路径")


class JWTConfig(BaseSettings):
    """JWT配置"""

    model_config = SettingsConfigDict(env_prefix="JWT_")

    secret_key: str = Field(
        default="your-secret-key-change-this-in-production",
        description="JWT签名密钥"
    )
    algorithm: str = Field(default="HS256", description="JWT算法")
    expire_minutes: int = Field(default=60 * 24 * 180, description="Token过期时间(分钟)")


class AppConfig(BaseSettings):
    """应用配置"""

    cache_dir: str = Field(default="./cache", description="缓存目录")
    database_path: str = Field(default="./data/review.db", description="数据库路径")
    allow_registration: bool = Field(default=True, description="是否允许用户注册")
    ui: UIConfig = Field(default_factory=UIConfig)
    auto_refresh: AutoRefreshConfig = Field(default_factory=AutoRefreshConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class Settings:
    """全局配置管理器"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置

        Args:
            config_path: 配置文件路径，默认为项目根目录的config.yaml
        """
        self._config_path = config_path or self._find_config_path()
        self._gitlab: Optional[GitLabConfig] = None
        self._ai: Optional[AIConfig] = None
        self._app: Optional[AppConfig] = None
        self._jwt: Optional[JWTConfig] = None

    @staticmethod
    def _find_config_path() -> str:
        """查找配置文件路径"""
        possible_paths = [
            "config.yaml",
            "config.local.yaml",
            "../config.yaml",
            "../config.local.yaml",
        ]

        for path in possible_paths:
            full_path = Path(path).resolve()
            if full_path.exists():
                return str(full_path)

        # 如果找不到配置文件，返回默认路径
        return "config.yaml"

    def load_yaml(self) -> dict:
        """从YAML文件加载配置"""
        config_file = Path(self._config_path)
        if not config_file.exists():
            return {}

        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @property
    def gitlab(self) -> GitLabConfig:
        """获取GitLab配置"""
        if self._gitlab is None:
            # 优先从环境变量加载，再从YAML文件加载
            self._gitlab = GitLabConfig()
            yaml_config = self.load_yaml()
            if "gitlab" in yaml_config:
                gitlab_config = yaml_config["gitlab"]
                # 如果环境变量为空，从YAML配置补充
                if not self._gitlab.url and gitlab_config.get("url"):
                    self._gitlab.url = gitlab_config["url"]
                if not self._gitlab.token and gitlab_config.get("token"):
                    self._gitlab.token = gitlab_config["token"]
                if gitlab_config.get("default_project_id"):
                    self._gitlab.default_project_id = gitlab_config[
                        "default_project_id"
                    ]
        return self._gitlab

    @property
    def ai(self) -> AIConfig:
        """获取AI配置"""
        if self._ai is None:
            self._ai = AIConfig()
            yaml_config = self.load_yaml()
            if "ai" in yaml_config:
                ai_config = yaml_config["ai"]
                if ai_config.get("provider"):
                    self._ai.provider = ai_config["provider"]
                if "openai" in ai_config:
                    openai_config = ai_config["openai"]
                    if openai_config.get("api_key"):
                        self._ai.openai.api_key = openai_config["api_key"]
                    if openai_config.get("base_url"):
                        self._ai.openai.base_url = openai_config["base_url"]
                    if openai_config.get("model"):
                        self._ai.openai.model = openai_config["model"]
                    if openai_config.get("temperature") is not None:
                        self._ai.openai.temperature = openai_config["temperature"]
                    if openai_config.get("max_tokens"):
                        self._ai.openai.max_tokens = openai_config["max_tokens"]
                if "ollama" in ai_config:
                    ollama_config = ai_config["ollama"]
                    if ollama_config.get("base_url"):
                        self._ai.ollama.base_url = ollama_config["base_url"]
                    if ollama_config.get("model"):
                        self._ai.ollama.model = ollama_config["model"]
                if ai_config.get("review_rules"):
                    self._ai.review_rules = ai_config["review_rules"]
        return self._ai

    @property
    def app(self) -> AppConfig:
        """获取应用配置"""
        if self._app is None:
            self._app = AppConfig()
            yaml_config = self.load_yaml()
            if "app" in yaml_config:
                app_config = yaml_config["app"]
                if app_config.get("cache_dir"):
                    self._app.cache_dir = app_config["cache_dir"]
                if app_config.get("database_path"):
                    self._app.database_path = app_config["database_path"]
                if app_config.get("allow_registration") is not None:
                    self._app.allow_registration = app_config["allow_registration"]
                if "ui" in app_config:
                    ui_config = app_config["ui"]
                    if ui_config.get("theme"):
                        self._app.ui.theme = ui_config["theme"]
                    if ui_config.get("window_width"):
                        self._app.ui.window_width = ui_config["window_width"]
                    if ui_config.get("window_height"):
                        self._app.ui.window_height = ui_config["window_height"]
                    if ui_config.get("split_left"):
                        self._app.ui.split_left = ui_config["split_left"]
                    if ui_config.get("split_right"):
                        self._app.ui.split_right = ui_config["split_right"]
                if "auto_refresh" in app_config:
                    refresh_config = app_config["auto_refresh"]
                    if refresh_config.get("enabled") is not None:
                        self._app.auto_refresh.enabled = refresh_config["enabled"]
                    if refresh_config.get("interval"):
                        self._app.auto_refresh.interval = refresh_config["interval"]
                if "logging" in app_config:
                    logging_config = app_config["logging"]
                    if logging_config.get("level"):
                        self._app.logging.level = logging_config["level"]
                    if logging_config.get("file"):
                        self._app.logging.file = logging_config["file"]
        return self._app

    @property
    def jwt(self) -> JWTConfig:
        """获取JWT配置"""
        if self._jwt is None:
            # 优先从环境变量加载
            self._jwt = JWTConfig()
            yaml_config = self.load_yaml()
            if "jwt" in yaml_config:
                jwt_config = yaml_config["jwt"]
                # 如果环境变量为默认值，从YAML配置补充
                if jwt_config.get("secret_key") and self._jwt.secret_key == "your-secret-key-change-this-in-production":
                    self._jwt.secret_key = jwt_config["secret_key"]
                if jwt_config.get("algorithm"):
                    self._jwt.algorithm = jwt_config["algorithm"]
                if jwt_config.get("expire_minutes"):
                    self._jwt.expire_minutes = jwt_config["expire_minutes"]
        return self._jwt

    def ensure_directories(self) -> None:
        """确保必要的目录存在"""
        directories = [
            self.app.cache_dir,
            Path(self.app.database_path).parent,
            Path(self.app.logging.file).parent,
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def validate(self) -> bool:
        """验证配置是否有效"""
        errors = []

        # 验证GitLab配置
        if not self.gitlab.url:
            errors.append("GitLab URL未配置")
        if not self.gitlab.token:
            errors.append("GitLab Token未配置")

        # 验证AI配置
        if self.ai.provider == "openai" and not self.ai.openai.api_key:
            errors.append("OpenAI API Key未配置")

        if errors:
            print("配置验证失败:")
            for error in errors:
                print(f"  - {error}")
            return False

        return True


# 全局配置实例
settings = Settings()
