"""主窗口 - 应用程序主界面"""

import asyncio
import logging
from functools import partial
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QMenuBar,
    QMenu,
    QToolBar,
    QMessageBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QLabel,
    QStatusBar,
    QProgressDialog,
    QComboBox,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread, QObject, QEvent
from PyQt6.QtGui import QAction, QIcon, QKeySequence

from ..core.config import settings
from ..core.database import DatabaseManager
from ..core.project_cache import ProjectCache
from ..gitlab.client import GitLabClient
from ..gitlab.models import MergeRequestInfo, DiffFile, MRState
from ..ai.reviewer import create_reviewer, ReviewIssue
from .mr_list_widget import MRListWidget
from .diff_viewer import DiffViewerPanel
from .comment_panel import CommentPanel
from .related_mr_dialog import RelatedMRDialog

logger = logging.getLogger(__name__)


class AIReviewWorker(QObject):
    """AI审查工作线程"""

    # 信号：审查完成、审查失败
    review_completed = pyqtSignal(list)  # ai_comments
    review_failed = pyqtSignal(str)  # error_message

    def __init__(self, mr, diff_files, review_config):
        super().__init__()
        self.mr = mr
        self.diff_files = diff_files
        self.review_config = review_config

    def run_review(self):
        """执行AI审查（在子线程中运行）"""
        try:
            # 创建AI审查器
            provider = self.review_config.get("provider", "openai")
            reviewer_kwargs = {
                "temperature": self.review_config.get("temperature", 0.3),
                "max_tokens": self.review_config.get("max_tokens", 2000),
            }

            if provider == "openai":
                reviewer_kwargs.update({
                    "api_key": self.review_config.get("api_key", ""),
                    "model": self.review_config.get("model", "gpt-3.5-turbo"),
                    "base_url": self.review_config.get("base_url"),
                })
            elif provider == "ollama":
                reviewer_kwargs.update({
                    "base_url": self.review_config.get("base_url", "http://localhost:11434"),
                    "model": self.review_config.get("model", "codellama"),
                })

            reviewer = create_reviewer(provider, **reviewer_kwargs)

            # 执行审查
            review_rules = self.review_config.get("review_rules", [])
            result = reviewer.review_merge_request(
                mr=self.mr,
                diff_files=self.diff_files,
                review_rules=review_rules,
                quick_mode=False,
            )

            # 将AIReviewResult转换为评论列表
            ai_comments = self._convert_result_to_comments(result)
            self.review_completed.emit(ai_comments)

        except Exception as e:
            logger.error(f"AI审查失败: {e}", exc_info=True)
            self.review_failed.emit(str(e))

    def _convert_result_to_comments(self, result) -> list:
        """将AIReviewResult转换为评论列表"""
        comments = []

        # 从file_reviews中提取评论（每个文件的详细审查结果）
        for file_path, file_review_list in result.file_reviews.items():
            if isinstance(file_review_list, list):
                for review_item in file_review_list:
                    if isinstance(review_item, dict):
                        line_number = review_item.get("line_number")
                        description = review_item.get("description", "")
                        severity = review_item.get("severity", "suggestion")

                        # 构建评论内容，包含严重程度
                        if description:
                            content = f"{severity.capitalize()}: {description}"
                            comments.append({
                                "file_path": file_path,
                                "line_number": line_number,
                                "content": content,
                            })

        # 如果file_reviews为空，从critical_issues/warnings/suggestions提取
        if not comments:
            # 这些已经包含了文件路径和行号信息
            all_items = []

            for issue in result.critical_issues:
                all_items.append(("warning", issue))

            for warning in result.warnings:
                all_items.append(("warning", warning))

            for suggestion in result.suggestions:
                all_items.append(("suggestion", suggestion))

            # 解析每个条目，提取文件路径和行号
            for severity, full_desc in all_items[:20]:  # 限制最多20条
                # 格式: "file_path:line_number - description" 或 "file_path - description"
                parts = full_desc.split(" - ", 1)
                if len(parts) >= 2:
                    location_part = parts[0]
                    description_part = parts[1]

                    # 尝试解析文件路径和行号
                    file_path = location_part
                    line_number = None

                    if ":" in location_part:
                        path_parts = location_part.rsplit(":", 1)
                        if path_parts[-1].isdigit():
                            file_path = path_parts[0]
                            line_number = int(path_parts[-1])

                    comments.append({
                        "file_path": file_path,
                        "line_number": line_number,
                        "content": f"{severity.capitalize()}: {description_part}",
                    })

        return comments


class ConfigDialog(QDialog):
    """配置对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("配置")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QFormLayout(self)

        # GitLab配置
        self.gitlab_url_input = QLineEdit(settings.gitlab.url)
        layout.addRow("GitLab URL:", self.gitlab_url_input)

        self.gitlab_token_input = QLineEdit(settings.gitlab.token)
        self.gitlab_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("GitLab Token:", self.gitlab_token_input)

        self.project_id_input = QLineEdit(settings.gitlab.default_project_id or "")
        layout.addRow("默认项目ID:", self.project_id_input)

        # AI配置
        ai_provider = settings.ai.provider
        self.ai_provider_input = QLineEdit(ai_provider)
        layout.addRow("AI提供商:", self.ai_provider_input)

        if ai_provider == "openai":
            self.openai_key_input = QLineEdit(settings.ai.openai.api_key)
            self.openai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addRow("OpenAI API Key:", self.openai_key_input)

            self.openai_model_input = QLineEdit(settings.ai.openai.model)
            layout.addRow("OpenAI 模型:", self.openai_model_input)

        # 按钮
        buttons = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addRow(buttons)

    def get_config(self) -> dict:
        """获取配置"""
        return {
            "gitlab_url": self.gitlab_url_input.text(),
            "gitlab_token": self.gitlab_token_input.text(),
            "project_id": self.project_id_input.text() or None,
            "ai_provider": self.ai_provider_input.text(),
            "openai_key": self.openai_key_input.text() if hasattr(self, 'openai_key_input') else "",
            "openai_model": self.openai_model_input.text() if hasattr(self, 'openai_model_input') else "",
        }


class ProjectSelectDialog(QDialog):
    """项目选择对话框 - 使用下拉框选择项目"""

    def __init__(self, gitlab_client, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.gitlab_client = gitlab_client
        self.selected_project = None
        self.projects = []
        self._setup_ui()
        self._load_projects()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题和说明
        title_label = QLabel("选择项目")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        desc_label = QLabel("请从下拉列表中选择一个项目:")
        layout.addWidget(desc_label)

        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入项目名称或路径进行筛选...")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # 项目下拉框
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(400)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        layout.addWidget(self.project_combo)

        # 项目详情区域
        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        self.details_label.setStyleSheet("color: #666; padding: 8px; background: #f5f5f5; border-radius: 4px;")
        layout.addWidget(self.details_label)

        layout.addStretch()

        # 按钮
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setEnabled(False)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

    def _load_projects(self):
        """加载项目列表"""
        try:
            self.project_combo.addItem("正在加载项目...")
            self.project_combo.setEnabled(False)

            # 获取所有项目（用户成员的项目）
            self.projects = self.gitlab_client.list_projects(
                membership=True,
                per_page=100,
            )

            # 清空并重新填充下拉框
            self.project_combo.clear()
            self.project_combo.setEnabled(True)

            if not self.projects:
                self.project_combo.addItem("暂无可用项目")
                self.project_combo.setEnabled(False)
                self.details_label.setText("未找到您可以访问的项目。")
            else:
                self.project_combo.addItem("-- 请选择项目 --")
                for project in self.projects:
                    # 显示格式: 项目名称 (路径)
                    display_text = f"{project.name} ({project.path_with_namespace})"
                    self.project_combo.addItem(display_text, project)

                self.project_combo.setCurrentIndex(0)
                self.details_label.setText(f"共找到 {len(self.projects)} 个项目")

        except Exception as e:
            self.project_combo.clear()
            self.project_combo.addItem("加载失败")
            self.project_combo.setEnabled(False)
            self.details_label.setText(f"加载项目列表失败: {e}")

    def _on_project_changed(self, index: int):
        """当项目选择改变时"""
        if index <= 0 or not self.projects:
            self.selected_project = None
            self.ok_btn.setEnabled(False)
            self.details_label.setText("请选择一个项目")
            return

        project = self.project_combo.currentData()
        if project:
            self.selected_project = project
            self.ok_btn.setEnabled(True)
            # 显示项目详情
            details = f"<b>{project.name}</b><br>"
            details += f"路径: {project.path_with_namespace}<br>"
            details += f"ID: {project.id}<br>"
            if project.description:
                details += f"描述: {project.description}"
            self.details_label.setText(details)

    def _on_search_changed(self, text: str):
        """当搜索文本改变时"""
        search_text = text.lower().strip()
        current_project = self.project_combo.currentData()

        self.project_combo.clear()

        if not self.projects:
            return

        # 过滤项目
        filtered_projects = []
        for project in self.projects:
            if (search_text in project.name.lower() or
                search_text in project.path_with_namespace.lower()):
                filtered_projects.append(project)

        self.project_combo.addItem("-- 请选择项目 --")
        for project in filtered_projects:
            display_text = f"{project.name} ({project.path_with_namespace})"
            self.project_combo.addItem(display_text, project)

        # 尝试恢复之前的选择
        if current_project:
            for i in range(1, self.project_combo.count()):
                if self.project_combo.itemData(i) and self.project_combo.itemData(i).id == current_project.id:
                    self.project_combo.setCurrentIndex(i)
                    break
        else:
            self.project_combo.setCurrentIndex(0)

    def get_selected_project(self):
        """获取选中的项目"""
        return self.selected_project


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()

        # 核心组件
        self.gitlab_client: Optional[GitLabClient] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.ai_reviewer = None

        # 项目缓存
        self.project_cache = ProjectCache()

        # AI审查线程
        self.ai_review_thread: Optional[QThread] = None
        self.ai_review_worker: Optional[AIReviewWorker] = None

        # 当前状态
        self.current_project_id: Optional[str] = None
        self.current_mr: Optional[MergeRequestInfo] = None
        self.current_diff_files: list[DiffFile] = []

        # 设置UI
        self._setup_ui()

        # 确保目录存在
        settings.ensure_directories()

        # 初始化数据库
        self._init_database()

        # 自动刷新定时器
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self._on_auto_refresh)

        # 检查配置
        self._check_config()

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("GitLab AI Review")
        self.setMinimumSize(1200, 800)

        # 应用配置中的窗口大小
        self.resize(settings.app.ui.window_width, settings.app.ui.window_height)

        # 创建菜单栏
        self._create_menu_bar()

        # 创建工具栏
        self._create_tool_bar()

        # 创建中央组件
        central_widget = self._create_central_widget()
        self.setCentralWidget(central_widget)

        # 创建状态栏
        self._create_status_bar()

    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        # 连接GitLab
        connect_action = QAction("连接GitLab(&C)", self)
        connect_action.setShortcut("Ctrl+Shift+C")
        connect_action.triggered.connect(self._on_connect_gitlab)
        file_menu.addAction(connect_action)

        # 选择项目
        select_project_action = QAction("选择项目(&P)", self)
        select_project_action.setShortcut("Ctrl+Shift+P")
        select_project_action.triggered.connect(self._on_select_project)
        file_menu.addAction(select_project_action)

        # 打开最近项目（子菜单）
        self.recent_projects_menu = file_menu.addMenu("打开最近项目(&R)")
        self._update_recent_projects_menu()

        file_menu.addSeparator()

        # 配置
        config_action = QAction("配置(&S)", self)
        config_action.setShortcut("Ctrl+,")
        config_action.triggered.connect(self._on_config)
        file_menu.addAction(config_action)

        file_menu.addSeparator()

        # 退出
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")

        # 刷新
        refresh_action = QAction("刷新(&R)", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._on_refresh)
        view_menu.addAction(refresh_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        # 关于
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _create_tool_bar(self):
        """创建工具栏"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # 连接GitLab
        self.connect_action = QAction("连接", self)
        self.connect_action.triggered.connect(self._on_connect_gitlab)
        toolbar.addAction(self.connect_action)

        # 选择项目
        self.project_action = QAction("选择项目", self)
        self.project_action.triggered.connect(self._on_select_project)
        toolbar.addAction(self.project_action)

        toolbar.addSeparator()

        # 刷新MR列表
        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self._on_refresh)
        toolbar.addAction(refresh_action)

        # 与我相关的MR
        self.related_mr_action = QAction("与我相关的MR", self)
        self.related_mr_action.triggered.connect(self._on_show_related_mr)
        toolbar.addAction(self.related_mr_action)

        toolbar.addSeparator()

        # 开始AI审查
        # self.review_action = QAction("AI审查", self)
        # self.review_action.setEnabled(False)
        # self.review_action.triggered.connect(self._on_start_review)
        # toolbar.addAction(self.review_action)

        toolbar.addSeparator()

        # 项目显示
        self.project_label = QLabel()
        self.project_label.setStyleSheet("padding: 4px; color: #495057;")
        toolbar.addWidget(self.project_label)

    def _create_central_widget(self) -> QWidget:
        """创建中央组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：MR列表
        self.mr_list_widget = MRListWidget()
        self.mr_list_widget.setMinimumWidth(300)
        self.mr_list_widget.mr_selected.connect(self._on_mr_selected)
        self.mr_list_widget.refresh_requested.connect(self._on_refresh)
        splitter.addWidget(self.mr_list_widget)

        # 中间：Diff查看器
        self.diff_viewer = DiffViewerPanel()
        self.diff_viewer.setMinimumWidth(400)
        self.diff_viewer.line_clicked.connect(self._on_diff_line_clicked)
        self.diff_viewer.ai_review_current_file_requested.connect(self._on_ai_review_current_file)
        splitter.addWidget(self.diff_viewer)

        # 右侧：评论面板
        self.comment_panel = CommentPanel()
        self.comment_panel.setMinimumWidth(350)
        self.comment_panel.publish_comment_requested.connect(self._on_publish_comment)
        self.comment_panel.ai_review_requested.connect(self._on_ai_review)
        self.comment_panel.jump_to_comment_requested.connect(self._on_jump_to_comment)
        splitter.addWidget(self.comment_panel)

        # 设置分割器比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        # 设置初始分割位置
        splitter.setSizes([
            settings.app.ui.split_left,
            settings.app.ui.window_width - settings.app.ui.split_left - settings.app.ui.split_right,
            settings.app.ui.split_right,
        ])

        layout.addWidget(splitter)

        return widget

    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def _init_database(self):
        """初始化数据库"""
        try:
            self.db_manager = DatabaseManager(settings.app.database_path)
            logger.info(f"数据库初始化成功: {settings.app.database_path}")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            self.status_bar.showMessage(f"数据库初始化失败: {e}")

    def _check_config(self):
        """检查配置"""
        if not settings.gitlab.url or not settings.gitlab.token:
            QMessageBox.warning(
                self,
                "配置未完成",
                "请先配置GitLab连接信息。\n\n点击\"确定\"打开配置对话框。",
            )
            self._on_config()

    def showEvent(self, event):
        """窗口显示事件 - 自动连接GitLab"""
        super().showEvent(event)
        # 只在第一次显示时自动连接
        if not self.gitlab_client and settings.gitlab.url and settings.gitlab.token:
            QTimer.singleShot(100, self._auto_connect_gitlab)

    def _auto_connect_gitlab(self):
        """自动连接GitLab"""
        if self.gitlab_client:
            return  # 已经连接

        try:
            self.status_bar.showMessage("正在自动连接GitLab...")

            # 创建GitLab客户端
            self.gitlab_client = GitLabClient(
                url=settings.gitlab.url,
                token=settings.gitlab.token,
                db_manager=self.db_manager,
            )

            self.status_bar.showMessage("已连接到GitLab")
            self.connect_action.setText("已连接")
            self.connect_action.setEnabled(False)

            # 更新最近项目菜单
            self._update_recent_projects_menu()

            # 尝试加载最近的项目
            # last_project = self.project_cache.get_last_project()
            # if last_project:
                # project_id = last_project.get("project_id")
                # project_name = last_project.get("project_name", "")

                # if project_id:
                    # self.current_project_id = project_id
                    # display_name = f"{project_name} ({project_id})" if project_name else project_id
                    # self.project_label.setText(f"项目: {display_name}")
                    # self._load_merge_requests()
                    # self.status_bar.showMessage(f"已自动加载最近项目: {display_name}")
            # elif settings.gitlab.default_project_id:
                # 如果没有最近项目，使用默认项目
                # self.current_project_id = settings.gitlab.default_project_id
                # self.project_label.setText(f"项目: {self.current_project_id}")
                # self._load_merge_requests()

            # 启用自动刷新
            if settings.app.auto_refresh.enabled:
                self.auto_refresh_timer.start(settings.app.auto_refresh.interval * 1000)

        except Exception as e:
            logger.warning(f"自动连接GitLab失败: {e}")
            self.status_bar.showMessage("自动连接失败，请手动连接")

    def _on_connect_gitlab(self):
        """连接GitLab"""
        if not settings.gitlab.url or not settings.gitlab.token:
            QMessageBox.warning(self, "配置错误", "请先配置GitLab URL和Token")
            self._on_config()
            return

        try:
            self.status_bar.showMessage("正在连接GitLab...")

            # 创建GitLab客户端
            self.gitlab_client = GitLabClient(
                url=settings.gitlab.url,
                token=settings.gitlab.token,
                db_manager=self.db_manager,
            )

            self.status_bar.showMessage("已连接到GitLab")
            self.connect_action.setText("已连接")
            self.connect_action.setEnabled(False)

            # 更新最近项目菜单
            self._update_recent_projects_menu()

            # 尝试加载最近的项目
            last_project = self.project_cache.get_last_project()
            if last_project:
                project_id = last_project.get("project_id")
                project_name = last_project.get("project_name", "")

                if project_id:
                    self.current_project_id = project_id
                    display_name = f"{project_name} ({project_id})" if project_name else project_id
                    self.project_label.setText(f"项目: {display_name}")
                    self._load_merge_requests()
            elif settings.gitlab.default_project_id:
                # 如果没有最近项目，使用默认项目
                self.current_project_id = settings.gitlab.default_project_id
                self.project_label.setText(f"项目: {self.current_project_id}")
                self._load_merge_requests()

            # 启用自动刷新
            if settings.app.auto_refresh.enabled:
                self.auto_refresh_timer.start(settings.app.auto_refresh.interval * 1000)

        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"无法连接到GitLab:\n\n{e}")
            self.status_bar.showMessage("连接失败")

    def _on_select_project(self):
        """选择项目"""
        if not self.gitlab_client:
            QMessageBox.warning(self, "未连接", "请先连接到GitLab")
            return

        dialog = ProjectSelectDialog(self.gitlab_client, self)
        if dialog.exec():
            selected_project = dialog.get_selected_project()
            if selected_project:
                self.current_project_id = str(selected_project.id)
                project_name = selected_project.path_with_namespace
                display_name = f"{selected_project.name} ({selected_project.id})"
                self.project_label.setText(f"项目: {display_name}")

                # 保存到最近项目缓存
                self.project_cache.add_recent_project(self.current_project_id, project_name)

                # 更新最近项目菜单
                self._update_recent_projects_menu()

                # 加载MR列表
                self._load_merge_requests()

    def _update_recent_projects_menu(self):
        """更新最近项目菜单"""
        # 清空菜单
        self.recent_projects_menu.clear()

        # 获取最近项目列表
        recent_projects = self.project_cache.get_recent_projects()

        if not recent_projects:
            # 没有最近项目
            no_recent_action = QAction("暂无最近项目", self)
            no_recent_action.setEnabled(False)
            self.recent_projects_menu.addAction(no_recent_action)
        else:
            # 添加每个项目到菜单
            for project in recent_projects:
                project_id = project.get("project_id", "")
                project_name = project.get("project_name", "")

                # 显示名称：优先使用项目名称，如果没有则使用项目ID
                display_name = project_name if project_name else project_id
                if project_name and project_id != project_name:
                    # 如果名称和ID不同，显示 ID 作为补充
                    action_text = f"{display_name} ({project_id})"
                else:
                    action_text = display_name

                action = QAction(action_text, self)
                # 使用 functools.partial 传递 project_id 参数
                action.triggered.connect(partial(self._on_open_recent_project, project_id))
                self.recent_projects_menu.addAction(action)

            # 添加分隔线和清除选项
            self.recent_projects_menu.addSeparator()
            clear_recent_action = QAction("清除最近项目列表", self)
            clear_recent_action.triggered.connect(self._on_clear_recent_projects)
            self.recent_projects_menu.addAction(clear_recent_action)

    def _on_open_recent_project(self, project_id: str):
        """打开最近项目"""
        if not self.gitlab_client:
            QMessageBox.warning(self, "未连接", "请先连接到GitLab")
            return

        # 设置当前项目
        self.current_project_id = project_id
        self.project_label.setText(f"项目: {project_id}")

        # 重新添加到缓存（更新访问时间）
        project_info = self.gitlab_client.get_project(project_id)
        project_name = project_info.path_with_namespace if project_info else ""
        self.project_cache.add_recent_project(project_id, project_name)

        # 更新菜单
        self._update_recent_projects_menu()

        # 加载MR列表
        self._load_merge_requests()

    def _on_clear_recent_projects(self):
        """清除最近项目列表"""
        reply = QMessageBox.question(
            self,
            "确认清除",
            "确定要清除最近项目列表吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.project_cache.clear_cache()
            self._update_recent_projects_menu()

    def _load_merge_requests(self):
        """加载MR列表"""
        if not self.gitlab_client or not self.current_project_id:
            return

        try:
            self.status_bar.showMessage("正在加载MR列表...")
            self.mr_list_widget.set_loading(True)

            # 根据"与我相关的MR"按钮状态选择获取方式
            if self.related_mr_action.isChecked():
                # 只获取与当前用户相关的MR
                mr_list = self.gitlab_client.list_merge_requests_related_to_me(
                    project_id=self.current_project_id,
                    state="all",
                )
            else:
                # 获取所有MR
                mr_list = self.gitlab_client.list_merge_requests(
                    project_id=self.current_project_id,
                    state="all",
                )

            self.mr_list_widget.load_merge_requests(mr_list)
            self.status_bar.showMessage(f"已加载 {len(mr_list)} 个MR")

        except Exception as e:
            logger.error(f"加载MR列表失败: {e}")
            QMessageBox.critical(self, "加载失败", f"无法加载MR列表:\n\n{e}")
            self.status_bar.showMessage("加载失败")
        finally:
            self.mr_list_widget.set_loading(False)

    def _on_mr_selected(self, mr: MergeRequestInfo):
        """处理MR选中"""
        self.current_mr = mr

        try:
            # 获取MR详情和Diff
            self.status_bar.showMessage(f"正在加载MR !{mr.iid}的详情...")

            # 获取diff文件
            self.current_diff_files = self.gitlab_client.get_merge_request_diffs(
                project_id=self.current_project_id,
                mr_iid=mr.iid,
            )

            # 显示diff
            self.diff_viewer.load_diffs(self.current_diff_files)

            # 清空评论面板并传递diff文件
            self.comment_panel._on_clear()
            self.comment_panel.set_diff_files(self.current_diff_files)

            self.status_bar.showMessage(f"已加载MR !{mr.iid} - {mr.title}")

        except Exception as e:
            logger.error(f"加载MR详情失败: {e}")
            self.status_bar.showMessage(f"加载失败: {e}")

    def _on_diff_line_clicked(self, line_number: int, line_type: str, file_path: str):
        """处理diff行点击"""
        # 将位置信息传递给评论面板
        self.comment_panel.set_code_location(file_path, line_number, line_type)
        self.status_bar.showMessage(f"已选择: {file_path}:{line_number}")

    def _on_publish_comment(self, file_path: str, content: str, line_number: object, line_type: str):
        """处理发布评论到GitLab"""
        if not self.gitlab_client or not self.current_mr:
            QMessageBox.warning(self, "错误", "未连接到GitLab或未选择MR")
            return

        try:
            # 如果没有行号或行号为0，发布为普通MR评论
            if line_number is None or line_number == 0:
                success = self.gitlab_client.create_merge_request_note(
                    project_id=self.current_project_id,
                    mr_iid=self.current_mr.iid,
                    body=content,
                )

                if success:
                    self.status_bar.showMessage("评论已发布")
                else:
                    QMessageBox.warning(self, "发布失败", "评论发布失败，请检查权限")
            else:
                # 有行号，发布为行评论
                # 确定line_type对应的GitLab参数
                # "new" -> 新增行, "old" -> 删除行, "context" -> 上下文行
                position_type = "new" if line_type == "addition" else "old" if line_type == "deletion" else "new"

                success = self.gitlab_client.create_merge_request_discussion(
                    project_id=self.current_project_id,
                    mr_iid=self.current_mr.iid,
                    body=content,
                    file_path=file_path,
                    line_number=int(line_number),
                    line_type=position_type,
                )

                if success:
                    self.status_bar.showMessage(f"评论已发布到 {file_path}:{line_number}")
                else:
                    QMessageBox.warning(self, "发布失败", "评论发布失败，请检查权限")

        except Exception as e:
            logger.error(f"发布评论失败: {e}")
            QMessageBox.critical(self, "发布失败", f"发布评论时发生错误:\n\n{e}")

    def _on_refresh(self):
        """刷新"""
        if self.current_project_id:
            self._load_merge_requests()

    def _on_show_related_mr(self):
        """显示所有项目中与我相关的MR"""
        if not self.gitlab_client:
            QMessageBox.warning(self, "错误", "请先配置GitLab连接")
            return

        # 创建对话框
        dialog = RelatedMRDialog(self)
        dialog.set_loading(True, "正在加载MR...")

        # 设置数据加载回调函数
        def load_mr_data():
            return self.gitlab_client.list_all_merge_requests_related_to_me()

        dialog.set_load_data_callback(load_mr_data)

        # 设置当前用户ID用于角色筛选
        current_user = self.gitlab_client.get_current_user()
        if current_user:
            dialog.set_current_user_id(current_user.get("id"))

        # 加载初始数据
        try:
            mr_list = load_mr_data()
            dialog.load_merge_requests(mr_list)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载MR失败: {e}")
            dialog.reject()
            return
        finally:
            dialog.set_loading(False)

        # 显示对话框
        dialog.exec()

    def _on_auto_refresh(self):
        """自动刷新"""
        self._on_refresh()

    def _on_config(self):
        """打开配置对话框"""
        dialog = ConfigDialog(self)
        if dialog.exec():
            config = dialog.get_config()

            # 更新配置（这里简化处理，实际应该更新配置文件）
            settings.gitlab.url = config["gitlab_url"]
            settings.gitlab.token = config["gitlab_token"]
            if config["project_id"]:
                settings.gitlab.default_project_id = config["project_id"]

            QMessageBox.information(self, "配置已保存", "配置已保存，请重启应用生效")

    def _on_about(self):
        """关于对话框"""
        QMessageBox.about(
            self,
            "关于 GitLab AI Review",
            "<h3>GitLab AI Review</h3>"
            "<p>AI驱动的GitLab代码审查工具</p>"
            "<p>版本: 0.1.0</p>"
            "<p>使用PyQt6构建</p>"
        )

    def closeEvent(self, event):
        """关闭事件"""
        # 停止定时器
        if self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()

        # 等待AI审查线程结束
        if self.ai_review_thread and self.ai_review_thread.isRunning():
            self.ai_review_thread.quit()
            self.ai_review_thread.wait()

        event.accept()

    def _on_ai_review(self):
        """处理AI审查请求"""
        if not self.current_mr:
            QMessageBox.warning(self, "提示", "请先选择一个Merge Request")
            return

        if not self.current_diff_files:
            QMessageBox.warning(self, "提示", "没有可审查的代码变更")
            return

        # 检查AI配置
        provider = settings.ai.provider
        if provider == "openai" and not settings.ai.openai.api_key:
            QMessageBox.warning(
                self,
                "配置错误",
                "请先配置OpenAI API Key\n\n可以在配置中设置或使用.env文件配置OPENAI_API_KEY"
            )
            return

        if provider == "ollama":
            # Ollama可以继续，因为它使用本地服务
            pass

        try:
            # 停止之前的审查线程
            if self.ai_review_thread and self.ai_review_thread.isRunning():
                self.ai_review_thread.quit()
                self.ai_review_thread.wait()

            # 准备审查配置
            review_config = {
                "provider": provider,
                "temperature": settings.ai.openai.temperature if provider == "openai" else 0.3,
                "max_tokens": settings.ai.openai.max_tokens if provider == "openai" else 2000,
                "review_rules": settings.ai.review_rules,
            }

            if provider == "openai":
                review_config.update({
                    "api_key": settings.ai.openai.api_key,
                    "model": settings.ai.openai.model,
                    "base_url": settings.ai.openai.base_url,
                })
            elif provider == "ollama":
                review_config.update({
                    "base_url": settings.ai.ollama.base_url,
                    "model": settings.ai.ollama.model,
                })

            # 创建工作线程
            self.ai_review_thread = QThread()
            self.ai_review_worker = AIReviewWorker(
                self.current_mr,
                self.current_diff_files,
                review_config
            )
            self.ai_review_worker.moveToThread(self.ai_review_thread)

            # 连接信号
            self.ai_review_thread.started.connect(self.ai_review_worker.run_review)
            self.ai_review_worker.review_completed.connect(self._on_ai_review_completed)
            self.ai_review_worker.review_failed.connect(self._on_ai_review_failed)
            self.ai_review_worker.review_completed.connect(self.ai_review_thread.quit)
            self.ai_review_worker.review_failed.connect(self.ai_review_thread.quit)

            # 更新状态
            self.status_bar.showMessage("正在进行AI审查...")
            self.comment_panel.ai_review_btn.setEnabled(False)
            self.comment_panel.ai_review_btn.setText("AI审查中...")

            # 启动线程
            self.ai_review_thread.start()

        except Exception as e:
            logger.error(f"启动AI审查失败: {e}", exc_info=True)
            self.comment_panel.on_ai_review_error(str(e))
            self.status_bar.showMessage("AI审查失败")

    def _on_ai_review_completed(self, ai_comments: list):
        """AI审查完成回调"""
        self.comment_panel.on_ai_review_complete(ai_comments)
        self.status_bar.showMessage(f"AI审查完成，生成 {len(ai_comments)} 条评论")
        # 恢复diff viewer上的按钮状态
        self.diff_viewer.ai_review_file_btn.setEnabled(True)
        self.diff_viewer.ai_review_file_btn.setText("AI评论当前文件")

    def _on_ai_review_failed(self, error_msg: str):
        """AI审查失败回调"""
        self.comment_panel.on_ai_review_error(error_msg)
        self.status_bar.showMessage("AI审查失败")
        # 恢复diff viewer上的按钮状态
        self.diff_viewer.ai_review_file_btn.setEnabled(True)
        self.diff_viewer.ai_review_file_btn.setText("AI评论当前文件")

    def _on_ai_review_current_file(self, diff_file):
        """处理AI审查当前文件请求"""
        if not self.current_mr:
            QMessageBox.warning(self, "提示", "请先选择一个Merge Request")
            return

        if not diff_file:
            QMessageBox.warning(self, "提示", "没有可审查的文件")
            return

        # 检查AI配置
        provider = settings.ai.provider
        if provider == "openai" and not settings.ai.openai.api_key:
            QMessageBox.warning(
                self,
                "配置错误",
                "请先配置OpenAI API Key\n\n可以在配置中设置或使用.env文件配置OPENAI_API_KEY"
            )
            return

        try:
            # 停止之前的审查线程
            if self.ai_review_thread and self.ai_review_thread.isRunning():
                self.ai_review_thread.quit()
                self.ai_review_thread.wait()

            # 准备审查配置
            review_config = {
                "provider": provider,
                "temperature": settings.ai.openai.temperature if provider == "openai" else 0.3,
                "max_tokens": settings.ai.openai.max_tokens if provider == "openai" else 2000,
                "review_rules": settings.ai.review_rules,
            }

            if provider == "openai":
                review_config.update({
                    "api_key": settings.ai.openai.api_key,
                    "model": settings.ai.openai.model,
                    "base_url": settings.ai.openai.base_url,
                })
            elif provider == "ollama":
                review_config.update({
                    "base_url": settings.ai.ollama.base_url,
                    "model": settings.ai.ollama.model,
                })

            # 创建工作线程
            self.ai_review_thread = QThread()
            self.ai_review_worker = AIReviewWorker(
                self.current_mr,
                [diff_file],  # 只审查当前选中的文件
                review_config
            )
            self.ai_review_worker.moveToThread(self.ai_review_thread)

            # 连接信号
            self.ai_review_thread.started.connect(self.ai_review_worker.run_review)
            self.ai_review_worker.review_completed.connect(self._on_ai_review_completed)
            self.ai_review_worker.review_failed.connect(self._on_ai_review_failed)
            self.ai_review_worker.review_completed.connect(self.ai_review_thread.quit)
            self.ai_review_worker.review_failed.connect(self.ai_review_thread.quit)

            # 更新状态
            file_path = diff_file.get_display_path()
            self.status_bar.showMessage(f"正在进行AI审查: {file_path}...")
            self.diff_viewer.ai_review_file_btn.setEnabled(False)
            self.diff_viewer.ai_review_file_btn.setText("AI审查中...")

            # 启动线程
            self.ai_review_thread.start()

        except Exception as e:
            logger.error(f"启动AI审查失败: {e}", exc_info=True)
            self.comment_panel.on_ai_review_error(str(e))
            self.status_bar.showMessage("AI审查失败")
            self.diff_viewer.ai_review_file_btn.setEnabled(True)
            self.diff_viewer.ai_review_file_btn.setText("AI评论当前文件")

    def _on_jump_to_comment(self, file_path: str, line_number: int):
        """处理跳转到评论位置"""
        self.diff_viewer.jump_to_file_and_line(file_path, line_number)
        self.status_bar.showMessage(f"已跳转到 {file_path}:{line_number}")
