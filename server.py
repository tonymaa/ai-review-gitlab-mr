"""GitLab AI Review - Web Server

Web 服务器启动文件
"""

import sys
import logging
from pathlib import Path

# 加载环境变量（必须在导入settings之前）
from dotenv import load_dotenv
load_dotenv()

from server.main import run_server

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def main():
    """启动 Web 服务器"""
    import argparse

    parser = argparse.ArgumentParser(description="GitLab AI Review Web Server")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="绑定的主机地址 (默认: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=19000,
        help="绑定的端口 (默认: 19000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="启用自动重载（开发模式）"
    )

    args = parser.parse_args()

    logger.info("启动 GitLab AI Review Web 服务器...")
    logger.info(f"访问地址: http://{args.host}:{args.port}")

    try:
        run_server(host=args.host, port=args.port, reload=args.reload)
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
