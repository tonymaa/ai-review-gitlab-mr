"""主窗口 - 应用程序主界面"""

import logging
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
    QInputDialog,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QLabel,
    QStatusBar,
    QProgressDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon, QKeySequence

from ..core.config import settings
from ..core.database import DatabaseManager
from ..gitlab.client import GitLabClient
from ..gitlab.models import MergeRequestInfo, DiffFile, MRState
from ..ai.reviewer import create_reviewer
from .mr_list_widget import MRListWidget
from .diff_viewer import DiffViewerPanel
from .review_panel import ReviewPanel

logger = logging.getLogger(__name__)


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


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()

        # 核心组件
        self.gitlab_client: Optional[GitLabClient] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.ai_reviewer = None

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

        # 开始AI审查
        self.review_action = QAction("AI审查", self)
        self.review_action.setEnabled(False)
        self.review_action.triggered.connect(self._on_start_review)
        toolbar.addAction(self.review_action)

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
        splitter.addWidget(self.diff_viewer)

        # 右侧：审查面板
        self.review_panel = ReviewPanel()
        self.review_panel.setMinimumWidth(350)
        splitter.addWidget(self.review_panel)

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

            # 如果有默认项目，自动选择
            if settings.gitlab.default_project_id:
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

        project_id, ok = QInputDialog.getText(
            self,
            "选择项目",
            "请输入项目ID或路径:\n(如: 123 或 group/project)",
            text=settings.gitlab.default_project_id or "",
        )

        if ok and project_id:
            self.current_project_id = project_id
            self.project_label.setText(f"项目: {project_id}")
            self._load_merge_requests()

    def _load_merge_requests(self):
        """加载MR列表"""
        if not self.gitlab_client or not self.current_project_id:
            return

        try:
            self.status_bar.showMessage("正在加载MR列表...")
            self.mr_list_widget.set_loading(True)

            # 获取MR列表 (默认获取全部，让用户自己筛选)
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
        self.review_action.setEnabled(True)

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

            # 清空审查面板
            self.review_panel.clear()

            self.status_bar.showMessage(f"已加载MR !{mr.iid} - {mr.title}")

        except Exception as e:
            logger.error(f"加载MR详情失败: {e}")
            self.status_bar.showMessage(f"加载失败: {e}")

    def _on_start_review(self):
        """开始AI审查"""
        if not self.current_mr or not self.current_diff_files:
            return

        if not settings.ai.openai.api_key and settings.ai.provider == "openai":
            QMessageBox.warning(self, "配置错误", "请先配置OpenAI API Key")
            return

        try:
            # 创建AI审查器
            self.ai_reviewer = create_reviewer(
                provider=settings.ai.provider,
                api_key=settings.ai.openai.api_key,
                model=settings.ai.openai.model,
                base_url=settings.ai.openai.base_url,
                temperature=settings.ai.openai.temperature,
                max_tokens=settings.ai.openai.max_tokens,
            )

            # 开始审查
            self.review_panel.start_review(
                reviewer=self.ai_reviewer,
                mr=self.current_mr,
                diff_files=self.current_diff_files,
                review_rules=settings.ai.review_rules,
            )

        except Exception as e:
            logger.error(f"启动AI审查失败: {e}")
            QMessageBox.critical(self, "审查失败", f"无法启动AI审查:\n\n{e}")

    def _on_refresh(self):
        """刷新"""
        if self.current_project_id:
            self._load_merge_requests()

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

        # 等待审查线程结束
        if hasattr(self.review_panel, 'review_thread') and self.review_panel.review_thread:
            if self.review_panel.review_thread.isRunning():
                self.review_panel.review_thread.quit()
                self.review_panel.review_thread.wait()

        event.accept()
