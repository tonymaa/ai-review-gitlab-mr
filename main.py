"""GitLab AI Review - 应用入口

主应用程序启动文件
"""

import sys
import logging
from pathlib import Path

# 加载环境变量（必须在导入settings之前）
from dotenv import load_dotenv
load_dotenv()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

import qdarktheme

from src.core.config import settings
from src.ui.main_window import MainWindow


def setup_logging():
    """设置日志"""
    # 确保日志目录存在
    log_file = Path(settings.app.logging.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 配置日志
    logging.basicConfig(
        level=getattr(logging, settings.app.logging.level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # 减少第三方库的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def main():
    """主函数"""
    # PyQt6默认已启用高DPI支持，无需额外设置

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("GitLab AI Review")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("GitLab AI Review")

    # 应用 qdarktheme 主题（自动跟随系统，自定义 primary color）
    qdarktheme.setup_theme(
        theme="auto",
        custom_colors={"primary": "#1677ff"}
    )

    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("启动 GitLab AI Review")

    # 确保必要目录存在
    settings.ensure_directories()

    # 创建并显示主窗口
    try:
        window = MainWindow()
        window.show()

        logger.info("应用程序已启动")

        # 运行应用
        sys.exit(app.exec())

    except Exception as e:
        logger.error(f"启动失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
