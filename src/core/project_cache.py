"""项目缓存管理器 - 用于持久化存储最近打开的项目"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ProjectCache:
    """项目缓存管理器"""

    CACHE_FILE = "recent_projects.json"
    MAX_RECENT_PROJECTS = 10

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        初始化项目缓存

        Args:
            cache_dir: 缓存目录路径，默认为用户数据目录
        """
        if cache_dir is None:
            # 使用用户主目录下的 .gitlab-ai-review 目录
            home = Path.home()
            cache_dir = home / ".gitlab-ai-review"

        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / self.CACHE_FILE

        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> Dict[str, Any]:
        """加载缓存数据"""
        if not self.cache_file.exists():
            return {}

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"加载缓存文件失败: {e}")
            return {}

    def _save_cache(self, data: Dict[str, Any]) -> bool:
        """保存缓存数据"""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            logger.error(f"保存缓存文件失败: {e}")
            return False

    def get_recent_projects(self) -> List[Dict[str, Any]]:
        """
        获取最近打开的项目列表

        Returns:
            项目信息列表，按最近访问时间排序
        """
        cache = self._load_cache()
        projects = cache.get("recent_projects", [])
        return projects[:self.MAX_RECENT_PROJECTS]

    def add_recent_project(self, project_id: str, project_name: str = "") -> bool:
        """
        添加或更新最近打开的项目

        Args:
            project_id: 项目ID或路径
            project_name: 项目名称（可选）

        Returns:
            是否成功保存
        """
        cache = self._load_cache()
        projects = cache.get("recent_projects", [])

        # 移除已存在的相同项目
        projects = [p for p in projects if p.get("project_id") != project_id]

        # 添加到列表开头
        new_project = {
            "project_id": project_id,
            "project_name": project_name,
            "last_accessed": datetime.now().isoformat(),
        }
        projects.insert(0, new_project)

        # 只保留最近的项目
        cache["recent_projects"] = projects[:self.MAX_RECENT_PROJECTS]

        return self._save_cache(cache)

    def get_last_project(self) -> Optional[Dict[str, Any]]:
        """
        获取最近打开的项目

        Returns:
            项目信息，如果没有则返回None
        """
        projects = self.get_recent_projects()
        return projects[0] if projects else None

    def clear_cache(self) -> bool:
        """
        清空缓存

        Returns:
            是否成功
        """
        return self._save_cache({"recent_projects": []})
