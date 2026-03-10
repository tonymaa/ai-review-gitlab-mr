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
from server.api import gitlab, ai, config, health, auth, auto_review
from server.models.session import SessionManager
from src.scheduler.auto_review_scheduler import AutoReviewScheduler


logger = logging.getLogger(__name__)

# 全局数据库管理器
db_manager: DatabaseManager | None = None
session_manager = SessionManager()
auto_review_scheduler: AutoReviewScheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    global db_manager, auto_review_scheduler
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

    # 初始化自动审查调度器
    try:
        auto_review_scheduler = AutoReviewScheduler(db_manager)
        app.state.auto_review_scheduler = auto_review_scheduler

        # 将调度器注入到数据库引擎（方便API访问）
        db_manager.engine.auto_review_scheduler = auto_review_scheduler

        # 启动所有已启用自动审查的用户任务
        await _start_enabled_auto_review_tasks(db_manager, auto_review_scheduler)

        logger.info("自动审查调度器初始化成功")
    except Exception as e:
        logger.error(f"自动审查调度器初始化失败: {e}")

    yield

    # 关闭时清理
    logger.info("关闭 FastAPI 服务器...")

    # 停止所有自动审查任务
    if auto_review_scheduler:
        await auto_review_scheduler.stop_all()
        logger.info("自动审查任务已全部停止")


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
    app.include_router(auto_review.router, prefix="/api/auto-review", tags=["AutoReview"])

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


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """运行服务器"""
    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


async def _start_enabled_auto_review_tasks(
    db: DatabaseManager,
    scheduler: "AutoReviewScheduler",
):
    """启动所有已启用自动审查的用户任务"""
    try:
        enabled_configs = db.list_enabled_auto_review_configs()
        for config in enabled_configs:
            user_id = config["user_id"]
            try:
                await scheduler.start_user_task(user_id)
                logger.info(f"已启动用户 {user_id} 的自动审查任务")
            except Exception as e:
                logger.error(f"启动用户 {user_id} 的自动审查任务失败: {e}")
    except Exception as e:
        logger.error(f"获取已启用自动审查配置失败: {e}")


if __name__ == "__main__":
    run_server()
