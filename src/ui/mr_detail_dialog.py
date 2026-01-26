"""MR详情对话框 - 显示MR的完整信息"""

from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QScrollArea,
    QWidget,
    QFrame,
    QLineEdit,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QColor

from ..gitlab.models import MergeRequestInfo, ProjectInfo, MRState, GitLabUser
from .theme import Theme


class AsyncWorker(QObject):
    """异步工作线程"""

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class CommentItemWidget(QFrame):
    """评论项组件"""

    delete_requested = pyqtSignal(int)  # comment_id

    def __init__(self, comment_data: Dict[str, Any], current_user_id: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.comment_data = comment_data
        self.current_user_id = current_user_id
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setProperty("class", "comment-item")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.PADDING_MD_INT, Theme.PADDING_MD_INT, Theme.PADDING_MD_INT, Theme.PADDING_MD_INT)
        layout.setSpacing(Theme.PADDING_SM_INT)

        # 顶部：作者和时间
        header = QHBoxLayout()
        author_data = self.comment_data.get("author", {})
        author_name = author_data.get("name", "未知")
        created_at = self.comment_data.get("created_at", "")
        time_str = self._format_time(created_at) if created_at else ""

        author_label = QLabel(f"<b>{author_name}</b>")
        header.addWidget(author_label)

        header.addStretch()

        time_label = QLabel(time_str)
        time_label.setProperty("class", "text-secondary")
        header.addWidget(time_label)

        # 删除按钮（只能删除自己的评论）
        if author_data.get("id") == self.current_user_id:
            delete_btn = QPushButton("删除")
            delete_btn.setProperty("class", "danger")
            delete_btn.setMaximumWidth(60)
            delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.comment_data.get("id")))
            header.addWidget(delete_btn)

        layout.addLayout(header)

        # 评论内容
        body = self.comment_data.get("body", "")
        content_label = QLabel(body)
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(content_label)

    def _format_time(self, time_str: str) -> str:
        """格式化时间"""
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            from datetime import timezone
            now = datetime.now(timezone.utc)
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
        except:
            return time_str


class MRDetailDialog(QDialog):
    """MR详情对话框"""

    # 信号：刷新MR列表
    refresh_requested = pyqtSignal()

    def __init__(self, mr: MergeRequestInfo, project: ProjectInfo, gitlab_client, current_user_id: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mr = mr
        self.project = project
        self.gitlab_client = gitlab_client
        self.current_user_id = current_user_id

        self.setWindowTitle(f"MR详情 - {mr.title}")
        self.setMinimumSize(1000, 700)

        self.comments: List[Dict[str, Any]] = []

        # 保存异步线程引用，防止被过早销毁
        self._async_threads = []

        self._setup_ui()
        self._load_comments()

    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setSpacing(Theme.PADDING_MD_INT)
        layout.setContentsMargins(Theme.PADDING_XL_INT, Theme.PADDING_XL_INT, Theme.PADDING_XL_INT, Theme.PADDING_XL_INT)

        # 主内容区域（使用卡片式设计）
        main_content = QWidget()
        main_layout = QVBoxLayout(main_content)
        main_layout.setSpacing(Theme.PADDING_LG_INT)

        # 标题卡片
        title_card = self._create_title_card()
        main_layout.addWidget(title_card)

        # 信息卡片（分支、状态等）
        info_card = self._create_info_card()
        main_layout.addWidget(info_card)

        # 用户卡片（Assignees & Reviewers）
        users_card = self._create_users_card()
        main_layout.addWidget(users_card)

        # 描述卡片
        desc_card = self._create_description_card()
        main_layout.addWidget(desc_card)

        # 评论卡片
        comments_card = self._create_comments_card()
        main_layout.addWidget(comments_card)

        main_layout.addStretch()

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidget(main_content)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setProperty("class", "main-scroll")
        layout.addWidget(scroll)

        # 底部按钮栏
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.approve_btn = QPushButton("同意" if not self.mr.approved_by_current_user else "取消同意")
        self.approve_btn.setProperty("class", "success")
        self.approve_btn.clicked.connect(self._on_approve_clicked)
        button_layout.addWidget(self.approve_btn)

        self.close_btn = QPushButton("关闭")
        self.close_btn.setProperty("class", "default")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def _create_title_card(self) -> QFrame:
        """创建标题卡片"""
        frame = QFrame()
        frame.setProperty("class", "card")
        layout = QVBoxLayout(frame)
        layout.setSpacing(Theme.PADDING_SM_INT)
        layout.setContentsMargins(Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT)

        # 标题
        title_label = QLabel(f"<h2>{self.mr.title}</h2>")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # MR IID 和状态标签
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(Theme.PADDING_MD_INT)

        # IID标签
        iid_label = QLabel(f"!{self.mr.iid}")
        iid_label.setProperty("class", "badge")
        iid_label.setStyleSheet("background-color: #6c757d; color: white; padding: 2px 8px; border-radius: 4px;")
        meta_layout.addWidget(iid_label)

        # 状态标签
        state_text = self._get_state_text(self.mr.state)
        state_color = self._get_state_color(self.mr.state)
        state_label = QLabel(state_text)
        state_label.setStyleSheet(f"background-color: {state_color}; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold;")
        meta_layout.addWidget(state_label)

        # WIP标签
        if self.mr.work_in_progress:
            wip_label = QLabel("WIP")
            wip_label.setStyleSheet("background-color: #ffc107; color: #212529; padding: 2px 8px; border-radius: 4px; font-weight: bold;")
            meta_layout.addWidget(wip_label)

        meta_layout.addStretch()

        # 项目名称
        if self.project:
            project_label = QLabel(f"{self.project.name}")
            project_label.setProperty("class", "text-secondary")
            meta_layout.addWidget(project_label)

        layout.addLayout(meta_layout)

        return frame

    def _create_info_card(self) -> QFrame:
        """创建信息卡片"""
        frame = QFrame()
        frame.setProperty("class", "card")
        layout = QVBoxLayout(frame)
        layout.setSpacing(Theme.PADDING_SM_INT)
        layout.setContentsMargins(Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT)

        # 第一行：作者、时间
        row1 = QHBoxLayout()
        row1.setSpacing(Theme.PADDING_MD_INT)

        # 作者
        author_name = self.mr.author.name if self.mr.author else "未知"
        row1.addWidget(QLabel("<b>作者:</b>"))
        author_label = QLabel(author_name)
        row1.addWidget(author_label)

        row1.addWidget(QLabel("•"))

        # 更新时间
        if self.mr.updated_at:
            time_str = self._format_time(self.mr.updated_at)
            row1.addWidget(QLabel("<b>更新:</b>"))
            row1.addWidget(QLabel(time_str))

        row1.addStretch()
        layout.addLayout(row1)

        # 第二行：分支信息
        row2 = QHBoxLayout()
        row2.setSpacing(Theme.PADDING_SM_INT)

        row2.addWidget(QLabel("<b>分支:</b>"))

        # 源分支
        source_label = QLabel(self.mr.source_branch)
        source_label.setProperty("class", "code")
        source_label.setStyleSheet("background-color: #e9ecef; padding: 2px 6px; border-radius: 3px;")
        row2.addWidget(source_label)

        row2.addWidget(QLabel("→"))

        # 目标分支
        target_label = QLabel(self.mr.target_branch)
        target_label.setProperty("class", "code")
        target_label.setStyleSheet("background-color: #e9ecef; padding: 2px 6px; border-radius: 3px;")
        row2.addWidget(target_label)

        # 变更统计
        if self.mr.additions > 0 or self.mr.deletions > 0:
            stats_text = f"+{self.mr.additions} -{self.mr.deletions}"
            stats_label = QLabel(stats_text)
            stats_label.setStyleSheet("color: #6c757d;")
            row2.addWidget(stats_label)

        row2.addStretch()
        layout.addLayout(row2)

        # 第三行：标签（如果有）
        if self.mr.labels:
            row3 = QHBoxLayout()
            row3.setSpacing(Theme.PADDING_SM_INT)
            row3.addWidget(QLabel("<b>标签:</b>"))

            for label in self.mr.labels:
                tag_label = QLabel(label)
                tag_label.setStyleSheet("background-color: #dee2e6; color: #495057; padding: 2px 8px; border-radius: 12px;")
                row3.addWidget(tag_label)

            row3.addStretch()
            layout.addLayout(row3)

        return frame

    def _create_users_card(self) -> QFrame:
        """创建用户卡片"""
        frame = QFrame()
        frame.setProperty("class", "card")
        layout = QVBoxLayout(frame)
        layout.setSpacing(Theme.PADDING_MD_INT)
        layout.setContentsMargins(Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT)

        header = QLabel("<b>人员</b>")
        layout.addWidget(header)

        # 使用表格布局来显示用户
        from PyQt6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(Theme.PADDING_MD_INT)
        grid.setColumnStretch(1, 1)

        # Assignees 行
        grid.addWidget(QLabel("<b>Assignees:</b>"), 0, 0)
        assignee_widget = QWidget()
        assignee_layout = QHBoxLayout(assignee_widget)
        assignee_layout.setSpacing(Theme.PADDING_SM_INT)
        assignee_layout.setContentsMargins(0, 0, 0, 0)

        if self.mr.assignees:
            for assignee in self.mr.assignees:
                avatar = QLabel(f"@{assignee.username}")
                avatar.setStyleSheet("color: #6c757d;")
                assignee_layout.addWidget(avatar)
        else:
            assignee_layout.addWidget(QLabel("无"))

        assignee_layout.addStretch()
        grid.addWidget(assignee_widget, 0, 1)

        # Reviewers 行
        grid.addWidget(QLabel("<b>Reviewers:</b>"), 1, 0)
        reviewer_widget = QWidget()
        reviewer_layout = QHBoxLayout(reviewer_widget)
        reviewer_layout.setSpacing(Theme.PADDING_SM_INT)
        reviewer_layout.setContentsMargins(0, 0, 0, 0)

        if self.mr.reviewers:
            for reviewer in self.mr.reviewers:
                avatar = QLabel(f"@{reviewer.username}")
                avatar.setStyleSheet("color: #6c757d;")
                reviewer_layout.addWidget(avatar)
        else:
            reviewer_layout.addWidget(QLabel("无"))

        reviewer_layout.addStretch()
        grid.addWidget(reviewer_widget, 1, 1)

        layout.addLayout(grid)

        return frame

    def _create_description_card(self) -> QFrame:
        """创建描述卡片"""
        frame = QFrame()
        frame.setProperty("class", "card")
        layout = QVBoxLayout(frame)
        layout.setSpacing(Theme.PADDING_SM_INT)
        layout.setContentsMargins(Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT)

        header = QLabel("<b>描述</b>")
        layout.addWidget(header)

        if self.mr.description:
            desc_content = QLabel(self.mr.description)
            desc_content.setWordWrap(True)
            desc_content.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(desc_content)
        else:
            layout.addWidget(QLabel("<i>无描述</i>"))

        return frame

    def _create_comments_card(self) -> QFrame:
        """创建评论卡片"""
        frame = QFrame()
        frame.setProperty("class", "card")
        layout = QVBoxLayout(frame)
        layout.setSpacing(Theme.PADDING_MD_INT)
        layout.setContentsMargins(Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT)

        # 标题
        self.comments_count_label = QLabel(f"<b>动态 ({len(self.comments)})</b>")
        layout.addWidget(self.comments_count_label)

        # 添加评论输入框
        input_container = QFrame()
        input_container.setProperty("class", "comment-input-container")
        input_container.setStyleSheet("background-color: #f8f9fa; border-radius: 6px; padding: 8px;")
        input_layout = QVBoxLayout(input_container)
        input_layout.setSpacing(Theme.PADDING_SM_INT)
        input_layout.setContentsMargins(0, 0, 0, 0)

        self.comment_input = QTextEdit()
        self.comment_input.setPlaceholderText("添加评论...")
        self.comment_input.setMaximumHeight(80)
        self.comment_input.setStyleSheet("border: 1px solid #dee2e6; border-radius: 4px; padding: 8px;")
        input_layout.addWidget(self.comment_input)

        add_comment_btn = QPushButton("添加评论")
        add_comment_btn.setProperty("class", "primary")
        add_comment_btn.clicked.connect(self._on_add_comment)
        input_layout.addWidget(add_comment_btn)

        layout.addWidget(input_container)

        # 评论列表
        self.comments_container = QWidget()
        self.comments_layout = QVBoxLayout(self.comments_container)
        self.comments_layout.setSpacing(Theme.PADDING_SM_INT)
        self.comments_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.comments_container)

        return frame

    def _load_comments(self):
        """加载评论（异步）"""
        async_thread = QThread()
        async_worker = AsyncWorker(self.gitlab_client.get_merge_request_notes, self.project.id, self.mr.iid)
        async_worker.moveToThread(async_thread)

        async_thread.started.connect(async_worker.run)
        async_worker.finished.connect(self._on_comments_loaded)
        async_worker.failed.connect(self._on_comments_load_failed)
        async_worker.finished.connect(async_thread.quit)
        async_worker.failed.connect(async_thread.quit)

        # 保存线程引用，防止被过早销毁
        self._async_threads.append((async_thread, async_worker))

        async_thread.start()

    def _on_comments_loaded(self, comments: List[Dict[str, Any]]):
        """评论加载成功回调"""
        self.comments = comments
        self._refresh_comments_display()

    def _on_comments_load_failed(self, error_msg: str):
        """评论加载失败回调"""
        QMessageBox.warning(self, "加载失败", f"加载评论失败: {error_msg}")

    def closeEvent(self, event):
        """对话框关闭事件 - 等待所有异步线程完成"""
        # 等待所有线程完成
        for thread, _ in self._async_threads:
            if thread.isRunning():
                thread.wait()
        super().closeEvent(event)

    def _refresh_comments_display(self):
        """刷新评论显示"""
        # 更新评论数量标签
        if hasattr(self, 'comments_count_label'):
            self.comments_count_label.setText(f"<b>动态 ({len(self.comments)})</b>")

        # 清空现有评论
        while self.comments_layout.count():
            child = self.comments_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 添加评论
        for comment in self.comments:
            comment_widget = CommentItemWidget(comment, self.current_user_id)
            comment_widget.delete_requested.connect(self._on_delete_comment)
            self.comments_layout.addWidget(comment_widget)

    def _on_add_comment(self):
        """添加评论"""
        body = self.comment_input.toPlainText().strip()
        if not body:
            QMessageBox.warning(self, "提示", "请输入评论内容")
            return

        # 调用API添加评论
        success = self.gitlab_client.create_merge_request_note(self.project.id, self.mr.iid, body)
        if success:
            self.comment_input.clear()
            # 重新加载评论
            self._load_comments()
        else:
            QMessageBox.warning(self, "失败", "添加评论失败")

    def _on_delete_comment(self, comment_id: int):
        """删除评论"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这条评论吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.gitlab_client.delete_merge_request_note(self.project.id, self.mr.iid, comment_id)
            if success:
                # 重新加载评论
                self._load_comments()
            else:
                QMessageBox.warning(self, "失败", "删除评论失败")

    def _on_approve_clicked(self):
        """处理同意/取消同意按钮点击"""
        if self.mr.approved_by_current_user:
            # 取消同意
            success = self.gitlab_client.unapprove_merge_request(self.project.id, self.mr.iid)
            if success:
                self.mr.approved_by_current_user = False
                self.approve_btn.setText("同意")
            else:
                QMessageBox.warning(self, "失败", "取消同意失败")
        else:
            # 同意
            success = self.gitlab_client.approve_merge_request(self.project.id, self.mr.iid)
            if success:
                self.mr.approved_by_current_user = True
                self.approve_btn.setText("取消同意")
            else:
                QMessageBox.warning(self, "失败", "同意失败")

    def _format_time(self, dt: datetime) -> str:
        """格式化时间"""
        from datetime import timezone

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
            MRState.OPENED: "Opened",
            MRState.MERGED: "Merged",
            MRState.CLOSED: "Closed",
            MRState.LOCKED: "Locked",
        }
        return state_map.get(state, str(state.value))

    def _get_state_color(self, state: MRState) -> str:
        """获取状态颜色"""
        color_map = {
            MRState.OPENED: Theme.PRIMARY,
            MRState.MERGED: Theme.SUCCESS,
            MRState.CLOSED: Theme.TEXT_TERTIARY,
            MRState.LOCKED: Theme.ERROR,
        }
        return color_map.get(state, Theme.TEXT_PRIMARY)
