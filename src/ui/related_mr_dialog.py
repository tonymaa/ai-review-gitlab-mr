"""与我相关的MR对话框 - 显示所有项目中assignee或reviewer为我的MR"""

from typing import Optional, List, Callable
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QLabel,
    QPushButton,
    QProgressBar,
    QLineEdit,
    QFrame,
    QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QClipboard
from ..gitlab.models import MergeRequestInfo, ProjectInfo, MRState
from .theme import Theme


class RelatedMRDialog(QDialog):
    """与我相关的MR对话框"""

    def __init__(self, parent: Optional[QDialog] = None):
        super().__init__(parent)
        self.setWindowTitle("与我相关的MR")
        self.setMinimumSize(900, 600)

        # 存储所有MR数据
        self.all_mr_list: List[tuple[MergeRequestInfo, ProjectInfo]] = []

        # 数据加载回调函数
        self._load_data_callback: Optional[Callable[[], List[tuple[MergeRequestInfo, ProjectInfo]]]] = None

        # MR打开回调函数
        self._open_mr_callback: Optional[Callable[[MergeRequestInfo, ProjectInfo], None]] = None

        # MR详情回调函数
        self._show_mr_detail_callback: Optional[Callable[[MergeRequestInfo, ProjectInfo], None]] = None

        # MR approve/unapprove 回调函数
        self._approve_callback: Optional[Callable[[MergeRequestInfo, ProjectInfo], None]] = None
        self._unapprove_callback: Optional[Callable[[MergeRequestInfo, ProjectInfo], None]] = None

        # 保存 GitLabClient 引用和当前用户ID
        self._gitlab_client = None
        self._current_user_id = None

        self._setup_ui()

    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setSpacing(Theme.PADDING_MD_INT)
        layout.setContentsMargins(Theme.PADDING_XL_INT, Theme.PADDING_XL_INT, Theme.PADDING_XL_INT, Theme.PADDING_XL_INT)

        # 标题说明
        title_label = QLabel("所有项目中assignee或reviewer为我的Merge Request")
        layout.addWidget(title_label)

        # 筛选栏
        filter_bar = self._create_filter_bar()
        layout.addWidget(filter_bar)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # MR列表树
        self.mr_tree = self._create_mr_tree()
        layout.addWidget(self.mr_tree)

        # 状态栏
        self.status_label = QLabel()
        self.status_label.setProperty("class", "status-bar")
        layout.addWidget(self.status_label)

        # 按钮栏
        button_layout = QHBoxLayout()
        button_layout.setSpacing(Theme.PADDING_SM_INT)
        button_layout.addStretch()

        self.approve_btn = QPushButton("同意")
        self.approve_btn.setProperty("class", "success")
        self.approve_btn.setEnabled(False)
        self.approve_btn.clicked.connect(self._on_approve_clicked)
        button_layout.addWidget(self.approve_btn)

        self.copy_link_btn = QPushButton("复制链接")
        self.copy_link_btn.setProperty("class", "default")
        self.copy_link_btn.setEnabled(False)
        self.copy_link_btn.clicked.connect(self._on_copy_link_clicked)
        button_layout.addWidget(self.copy_link_btn)

        self.detail_btn = QPushButton("查看详情")
        self.detail_btn.setProperty("class", "default")
        self.detail_btn.setEnabled(False)
        self.detail_btn.clicked.connect(self._on_detail_clicked)
        button_layout.addWidget(self.detail_btn)

        self.open_btn = QPushButton("打开")
        self.open_btn.setProperty("class", "primary")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._on_open_clicked)
        button_layout.addWidget(self.open_btn)

        self.close_btn = QPushButton("关闭")
        self.close_btn.setProperty("class", "default")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def _create_filter_bar(self) -> QFrame:
        """创建筛选栏"""
        filter_bar = QFrame()

        layout = QHBoxLayout(filter_bar)
        layout.setContentsMargins(Theme.PADDING_SM_INT, Theme.PADDING_XS_INT, Theme.PADDING_SM_INT, Theme.PADDING_XS_INT)
        layout.setSpacing(Theme.PADDING_XS_INT)

        # 搜索框
        search_label = QLabel("搜索:")
        layout.addWidget(search_label)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索标题、作者、项目...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self.search_input)

        return filter_bar

    def _create_mr_tree(self) -> QTreeWidget:
        """创建MR列表树"""
        tree = QTreeWidget()
        tree.setHeaderLabels(["项目", "!MR", "标题", "作者", "评论", "已批准", "状态", "更新时间"])
        tree.setAlternatingRowColors(True)
        tree.setRootIsDecorated(False)
        tree.setSortingEnabled(True)
        tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        tree.itemSelectionChanged.connect(self._on_selection_changed)

        # 设置列宽
        header = tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

        return tree

    def set_load_data_callback(self, callback: Callable[[], List[tuple[MergeRequestInfo, ProjectInfo]]]):
        """设置数据加载回调函数

        Args:
            callback: 返回MR列表的回调函数
        """
        self._load_data_callback = callback

    def set_open_mr_callback(self, callback: Callable[[MergeRequestInfo, ProjectInfo], None]):
        """设置MR打开回调函数

        Args:
            callback: 接收MR和项目信息的回调函数，用于打开MR
        """
        self._open_mr_callback = callback

    def set_approve_callbacks(
        self,
        approve_callback: Callable[[MergeRequestInfo, ProjectInfo], None],
        unapprove_callback: Callable[[MergeRequestInfo, ProjectInfo], None],
    ):
        """设置approve/unapprove回调函数

        Args:
            approve_callback: 同意MR的回调函数
            unapprove_callback: 取消同意MR的回调函数
        """
        self._approve_callback = approve_callback
        self._unapprove_callback = unapprove_callback

    def set_show_mr_detail_callback(self, callback: Callable[[MergeRequestInfo, ProjectInfo], None]):
        """设置显示MR详情回调函数

        Args:
            callback: 接收MR和项目信息的回调函数，用于显示MR详情
        """
        self._show_mr_detail_callback = callback

    def set_gitlab_client(self, client):
        """设置GitLab客户端

        Args:
            client: GitLabClient实例
        """
        self._gitlab_client = client

    def load_merge_requests(self, mr_list):
        """
        加载MR列表

        Args:
            mr_list: (MergeRequestInfo, ProjectInfo) 元组列表，或兼容格式的数据
        """
        # 数据兼容处理
        self.all_mr_list = self._normalize_mr_list(mr_list)
        self._refresh_display()

    def _normalize_mr_list(self, mr_list) -> List[tuple[MergeRequestInfo, ProjectInfo]]:
        """
        标准化MR列表数据，处理各种可能的输入格式

        Args:
            mr_list: 原始MR列表

        Returns:
            标准化的 (MergeRequestInfo, ProjectInfo) 元组列表
        """
        normalized = []

        for item in mr_list:
            if isinstance(item, tuple) and len(item) == 2:
                mr_info, project_info = item

                # 兼容 GitLab RESTObject 直接返回的情况
                if hasattr(mr_info, 'asdict'):
                    try:
                        mr_info = MergeRequestInfo.from_dict(mr_info.asdict())
                    except Exception:
                        continue

                # 兼容 project_info 同样是 RESTObject 的情况
                if project_info is not None and hasattr(project_info, 'asdict'):
                    try:
                        project_info = ProjectInfo.from_dict(project_info.asdict())
                    except Exception:
                        project_info = None

                # 确保类型正确
                if isinstance(mr_info, MergeRequestInfo):
                    if project_info is None or isinstance(project_info, ProjectInfo):
                        normalized.append((mr_info, project_info))
                elif isinstance(mr_info, dict):
                    # 处理字典格式
                    try:
                        mr_obj = MergeRequestInfo.from_dict(mr_info)
                        proj_obj = ProjectInfo.from_dict(project_info) if isinstance(project_info, dict) else None
                        normalized.append((mr_obj, proj_obj))
                    except Exception:
                        pass

        return normalized

    def _refresh_display(self):
        """刷新显示（本地筛选）"""
        # 获取筛选条件
        search_text = self.search_input.text().lower()

        # 清空列表
        self.mr_tree.clear()

        # 筛选并添加MR
        filtered_count = 0
        for mr_info, project_info in self.all_mr_list:
            # 应用搜索筛选
            if search_text:
                title_match = search_text in mr_info.title.lower()
                author_match = search_text in mr_info.author.username.lower() if mr_info.author else False
                project_match = search_text in project_info.name.lower() if project_info else False
                if not (title_match or author_match or project_match):
                    continue

            filtered_count += 1
            self._add_mr_item(mr_info, project_info)

        # 更新状态栏
        self.status_label.setText(f"共 {filtered_count} 个MR (总计 {len(self.all_mr_list)})")

    def _add_mr_item(self, mr: MergeRequestInfo, project: ProjectInfo):
        """添加MR项到树"""
        # 格式化时间
        if mr.updated_at:
            time_str = self._format_time(mr.updated_at)
        else:
            time_str = "-"

        # 状态文本和图标
        state_text = self._get_state_text(mr.state)
        state_color = self._get_state_color(mr.state)

        # 创建项目
        approved_text = "✓" if mr.approved_by_current_user else ""
        item = QTreeWidgetItem([
            project.name if project else "未知",
            f"!{mr.iid}",
            mr.title,
            mr.author.name if mr.author else "未知",
            str(mr.user_notes_count),
            approved_text,
            state_text,
            time_str,
        ])

        # 设置状态颜色
        item.setForeground(6, QColor(state_color))

        # 设置已批准颜色
        if mr.approved_by_current_user:
            item.setForeground(5, QColor(Theme.SUCCESS))

        # 存储MR和项目对象
        item.setData(0, Qt.ItemDataRole.UserRole, (mr, project))

        # WIP标记
        if mr.work_in_progress:
            item.setText(1, f"[WIP] !{mr.iid}")
            item.setForeground(1, QColor("#868e96"))

        # 添加到树
        self.mr_tree.addTopLevelItem(item)

    def _on_search_text_changed(self, _text: str) -> None:
        """处理搜索文本变化"""
        self._refresh_display()

    def _on_selection_changed(self):
        """处理选择变化"""
        has_selection = bool(self.mr_tree.selectedItems())
        self.open_btn.setEnabled(has_selection)
        self.approve_btn.setEnabled(has_selection)
        self.copy_link_btn.setEnabled(has_selection)
        self.detail_btn.setEnabled(has_selection)

        # 更新approve按钮文本
        if has_selection:
            item = self.mr_tree.selectedItems()[0]
            mr, project = item.data(0, Qt.ItemDataRole.UserRole)
            if mr.approved_by_current_user:
                self.approve_btn.setText("取消同意")
            else:
                self.approve_btn.setText("同意")
        else:
            self.approve_btn.setText("同意")

    def _on_copy_link_clicked(self):
        """处理复制链接按钮点击"""
        selected_items = self.mr_tree.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        mr, _ = item.data(0, Qt.ItemDataRole.UserRole)

        # 获取MR的web_url
        if mr.web_url:
            # 复制到剪切板
            clipboard = QApplication.clipboard()
            clipboard.setText(mr.web_url)
            # 显示提示
            self.status_label.setText(f"已复制链接: {mr.web_url}")
        else:
            self.status_label.setText("该MR没有链接")

    def _on_detail_clicked(self):
        """处理查看详情按钮点击"""
        selected_items = self.mr_tree.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        mr, project = item.data(0, Qt.ItemDataRole.UserRole)

        if self._show_mr_detail_callback:
            self._show_mr_detail_callback(mr, project)

    def _on_approve_clicked(self):
        """处理同意/取消同意按钮点击"""
        selected_items = self.mr_tree.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        mr, project = item.data(0, Qt.ItemDataRole.UserRole)

        if mr.approved_by_current_user:
            # 取消同意
            if self._unapprove_callback:
                self._unapprove_callback(mr, project)
                # 更新本地状态
                mr.approved_by_current_user = False
                self._update_mr_item_display(item, mr)
        else:
            # 同意
            if self._approve_callback:
                self._approve_callback(mr, project)
                # 更新本地状态
                mr.approved_by_current_user = True
                self._update_mr_item_display(item, mr)

    def _update_mr_item_display(self, item: QTreeWidgetItem, mr: MergeRequestInfo):
        """更新MR项的显示"""
        # 更新已批准列
        approved_text = "✓" if mr.approved_by_current_user else ""
        item.setText(5, approved_text)
        if mr.approved_by_current_user:
            item.setForeground(5, QColor(Theme.SUCCESS))
        else:
            item.setForeground(5, QColor())

        # 更新按钮文本
        if mr.approved_by_current_user:
            self.approve_btn.setText("取消同意")
        else:
            self.approve_btn.setText("同意")

    def _on_open_clicked(self):
        """处理打开按钮点击"""
        selected_items = self.mr_tree.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        mr, project = item.data(0, Qt.ItemDataRole.UserRole)

        if self._open_mr_callback:
            self._open_mr_callback(mr, project)
            # 打开后关闭对话框
            self.accept()


    def set_current_user_id(self, user_id: int):
        """设置当前用户ID（用于角色筛选）"""
        self._current_user_id = user_id

    def _format_time(self, dt: datetime) -> str:
        """格式化时间"""
        from datetime import timezone

        # 处理带时区和不带时区的时间
        if dt.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.now()

        delta = now - dt

        if delta.days > 7:
            return dt.strftime("%Y-%m-%d")
        elif delta.days > 0:
            return f"{delta.days}天前"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours}小时前"
        elif delta.seconds >= 60:
            minutes = delta.seconds // 60
            return f"{minutes}分钟前"
        else:
            return "刚刚"

    def _get_state_text(self, state: MRState) -> str:
        """获取状态文本"""
        state_map = {
            MRState.OPENED: "已打开",
            MRState.MERGED: "已合并",
            MRState.CLOSED: "已关闭",
            MRState.LOCKED: "已锁定",
        }
        return state_map.get(state, str(state.value))

    def _get_state_color(self, state: MRState) -> str:
        """获取状态颜色"""
        color_map = {
            MRState.OPENED: Theme.PRIMARY,  # 蓝色
            MRState.MERGED: Theme.SUCCESS,  # 绿色
            MRState.CLOSED: Theme.TEXT_TERTIARY,  # 灰色
            MRState.LOCKED: Theme.ERROR,  # 红色
        }
        return color_map.get(state, Theme.TEXT_PRIMARY)

    def set_loading(self, loading: bool, text: str = ""):
        """设置加载状态"""
        if loading:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # 不确定进度
            if text:
                self.progress_bar.setTextVisible(True)
                self.progress_bar.setFormat(text)
        else:
            self.progress_bar.setVisible(False)
