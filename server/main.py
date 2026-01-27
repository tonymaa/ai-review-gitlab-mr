"""FastAPI 主应用程序"""

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.database import DatabaseManager
from server.api import gitlab, ai, config, health, auth
from server.models.session import SessionManager


logger = logging.getLogger(__name__)

# 全局数据库管理器
db_manager: DatabaseManager | None = None
session_manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    global db_manager
    logger.info("启动 FastAPI 服务器...")

    # 确保必要目录存在
    settings.ensure_directories()

    # 初始化数据库
    try:
        db_manager = DatabaseManager(settings.app.database_path)
        logger.info(f"数据库初始化成功: {settings.app.database_path}")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")

    # 将数据库管理器注入到路由中
    app.state.db = db_manager
    app.state.session_manager = session_manager

    yield

    # 关闭时清理
    logger.info("关闭 FastAPI 服务器...")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = FastAPI(
        title="GitLab AI Review API",
        description="AI驱动的GitLab代码审查工具",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(health.router, prefix="/api", tags=["Health"])
    app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
    app.include_router(config.router, prefix="/api/config", tags=["Config"])
    app.include_router(gitlab.router, prefix="/api/gitlab", tags=["GitLab"])
    app.include_router(ai.router, prefix="/api/ai", tags=["AI"])

    # 静态文件服务 (React 构建产物)
    web_dist = Path(__file__).parent.parent / "web" / "dist"
    if web_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(web_dist / "assets")), name="assets")
        # 为 index.html 和其他静态文件提供通配符路由
        @app.get("/{path:path}")
        async def serve_static(path: str):
            file_path = web_dist / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(web_dist / "index.html")

    return app


# 创建应用实例
app = create_app()


def run_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """运行服务器"""
    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
