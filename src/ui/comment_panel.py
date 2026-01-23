"""评论面板 - 允许用户手动添加行评论"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLabel,
    QPushButton,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QInputDialog,
    QAbstractItemView,
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QColor

from ..gitlab.models import ReviewComment


class CommentListItem(QWidget):
    """评论列表项 - 自定义widget以提供更好的UI"""

    # 信号：发布、编辑、删除
    publish_requested = pyqtSignal()
    edit_requested = pyqtSignal()
    delete_requested = pyqtSignal()
    jump_requested = pyqtSignal()

    def __init__(self, comment: ReviewComment, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.comment = comment
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setFixedHeight(70)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(4)

        # 顶部：文件路径、行号、类型标签
        header = QHBoxLayout()
        header.setSpacing(6)

        # 文件路径标签
        file_label = QLabel(self._get_display_path())
        file_label.setStyleSheet("color: #495057; font-size: 11px; font-weight: 600;")
        header.addWidget(file_label)

        # 行号标签
        if self.comment.line_number:
            line_label = QLabel(f":{self.comment.line_number}")
            line_label.setStyleSheet("""
                QLabel {
                    background-color: #e7f5ff;
                    color: #1971c2;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 10px;
                    font-weight: 600;
                }
            """)
            header.addWidget(line_label)

        header.addStretch()

        # 评论类型标签
        type_text = "AI" if self.comment.comment_type == "ai_comment" else "手动"
        type_color = "#7c4dff" if self.comment.comment_type == "ai_comment" else "#228be6"
        type_label = QLabel(type_text)
        type_label.setStyleSheet(f"""
            QLabel {{
                background-color: {type_color};
                color: white;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 9px;
                font-weight: 600;
            }}
        """)
        header.addWidget(type_label)

        layout.addLayout(header)

        # 中部：评论内容
        content = self.comment.content
        if len(content) > 80:
            content = content[:80] + "..."

        content_label = QLabel(content)
        content_label.setStyleSheet("color: #212529; font-size: 12px;")
        content_label.setWordWrap(True)
        content_label.setMaximumHeight(36)
        layout.addWidget(content_label)

    def _get_display_path(self) -> str:
        """获取显示的文件路径"""
        path = self.comment.file_path or ""
        if len(path) > 40:
            return "..." + path[-37:]
        return path

    def enterEvent(self, event):
        """鼠标进入事件"""
        self.setStyleSheet("background-color: #f8f9fa; border-radius: 4px;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.setStyleSheet("")
        super().leaveEvent(event)


class CommentEditor(QWidget):
    """评论编辑器"""

    # 信号：评论提交
    comment_submitted = pyqtSignal(str)  # content
    # 信号：取消
    comment_cancelled = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        self.title_label = QLabel("添加评论")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 4px;")
        layout.addWidget(self.title_label)

        # 位置信息
        self.location_label = QLabel("位置: -")
        self.location_label.setStyleSheet("color: #868e96; font-size: 11px; padding: 4px;")
        layout.addWidget(self.location_label)

        # 评论内容
        layout.addWidget(QLabel("评论内容:"))
        self.comment_text = QTextEdit()
        self.comment_text.setPlaceholderText("输入你的评论...")
        self.comment_text.setMaximumHeight(120)
        layout.addWidget(self.comment_text)

        # 按钮
        buttons = QHBoxLayout()
        self.submit_btn = QPushButton("发布评论")
        self.submit_btn.clicked.connect(self._on_submit)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self._on_cancel)
        buttons.addWidget(self.submit_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

    def set_location(self, file_path: str, line_number: int, line_type: str):
        """设置评论位置"""
        line_label = {"new": "新", "old": "旧", "context": "上下文"}.get(line_type, line_type)
        self.location_label.setText(f"文件: {file_path}\n行号: {line_number} ({line_label})")

    def set_title(self, title: str):
        """设置标题"""
        self.title_label.setText(title)

    def _on_submit(self):
        """提交评论"""
        content = self.comment_text.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "提示", "请输入评论内容")
            return
        self.comment_submitted.emit(content)
        self.comment_text.clear()

    def _on_cancel(self):
        """取消评论"""
        self.comment_text.clear()
        self.comment_cancelled.emit()

    def clear(self):
        """清空"""
        self.comment_text.clear()
        self.location_label.setText("位置: -")
        self.set_title("添加评论")


class CommentListWidget(QListWidget):
    """评论列表组件"""

    # 信号：删除评论、编辑评论、跳转到评论位置、发布单个评论、项被选中
    delete_requested = pyqtSignal(int)  # index
    edit_requested = pyqtSignal(int)  # index
    jump_to_comment = pyqtSignal(str, int)  # (file_path, line_number)
    publish_requested = pyqtSignal(int)  # index - 发布单个评论
    item_clicked = pyqtSignal(int)  # index - 单击选中

    # SelectionMode设为SingleSelection
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setStyleSheet("""
            QListWidget {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                background-color: #ffffff;
                outline: none;
            }
            QListWidget::item {
                border: none;
                border-bottom: 1px solid #f1f3f5;
                padding: 10px 12px;
                color: #212529;
                background-color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
            }
            QListWidget::item:selected {
                background-color: #e7f5ff;
                color: #212529;
            }
        """)

        # 启用右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 连接单击和双击事件
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _on_item_clicked(self, item: QListWidgetItem):
        """处理单击事件 - 选中并准备编辑"""
        if not item:
            return

        # 获取评论索引
        list_index = self.row(item)
        self.item_clicked.emit(list_index)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """处理双击事件 - 跳转到代码位置"""
        if not item:
            return

        # 获取评论索引
        comment_index = item.data(Qt.ItemDataRole.UserRole)
        if comment_index is None:
            return

        # 从父级获取评论对象
        parent_panel = self.parent()
        while parent_panel and not isinstance(parent_panel, CommentPanel):
            parent_panel = parent_panel.parent()

        if parent_panel and 0 <= comment_index < len(parent_panel.local_comments):
            comment = parent_panel.local_comments[comment_index]
            if comment.file_path and comment.line_number:
                self.jump_to_comment.emit(comment.file_path, comment.line_number)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        from PyQt6.QtWidgets import QMenu

        item = self.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        publish_action = menu.addAction("发布")
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")

        # 菜单操作
        action = menu.exec(self.mapToGlobal(pos))
        if action == publish_action:
            index = self.row(item)
            self.publish_requested.emit(index)
        elif action == edit_action:
            index = self.row(item)
            self.edit_requested.emit(index)
        elif action == delete_action:
            index = self.row(item)
            self.delete_requested.emit(index)

    def add_comment(self, comment: ReviewComment, index: int = -1):
        """
        添加评论

        Args:
            comment: 评论对象
            index: 索引位置，用于关联删除
        """
        # 创建列表项
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, index)

        # 设置item大小以适应自定义widget
        item.setSizeHint(QSize(0, 70))

        # 创建自定义widget
        widget = CommentListItem(comment, self)

        self.addItem(item)
        self.setItemWidget(item, widget)

        # 滚动到底部
        self.scrollToBottom()

    def remove_comment_at(self, index: int):
        """删除指定位置的评论"""
        # 查找对应索引的item
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == index:
                self.takeItem(i)
                return

    def clear_comments(self):
        """清空评论"""
        self.clear()


class CommentPanel(QWidget):
    """评论面板 - 允许用户添加和管理评论"""

    # 信号：发布评论到GitLab
    publish_comment_requested = pyqtSignal(str, str, object, str)  # (file_path, content, line, line_type) - line用object以支持None
    # 信号：请求AI审查
    ai_review_requested = pyqtSignal()  # 无参数，审查当前MR的diff
    # 信号：跳转到指定评论位置
    jump_to_comment_requested = pyqtSignal(str, int)  # (file_path, line_number)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # 当前选中的位置
        self.current_file_path: Optional[str] = None
        self.current_line_number: Optional[int] = None
        self.current_line_type: Optional[str] = None

        # 本地评论列表
        self.local_comments: list[ReviewComment] = []

        # 当前正在编辑的评论索引（None表示新建评论）
        self._editing_index: Optional[int] = None

        # 当前MR的diff文件（用于AI审查）
        self.current_diff_files: list = []

        self._setup_ui()

    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        title_bar = self._create_title_bar()
        layout.addWidget(title_bar)

        # 评论编辑器
        self.comment_editor = CommentEditor()
        self.comment_editor.comment_submitted.connect(self._on_comment_submitted)
        self.comment_editor.comment_cancelled.connect(self._on_comment_cancelled)
        layout.addWidget(self.comment_editor)

        # 已添加的评论列表
        comments_group = QGroupBox("待发布评论")
        comments_layout = QVBoxLayout(comments_group)

        self.comment_list = CommentListWidget()
        self.comment_list.delete_requested.connect(self._on_delete_comment)
        self.comment_list.edit_requested.connect(self._on_edit_comment)
        self.comment_list.jump_to_comment.connect(self._on_jump_to_comment)
        self.comment_list.publish_requested.connect(self._on_publish_single)
        self.comment_list.item_clicked.connect(self._on_item_clicked)
        comments_layout.addWidget(self.comment_list)

        # 发布全部按钮
        publish_all_btn = QPushButton("发布全部评论到GitLab")
        publish_all_btn.clicked.connect(self._on_publish_all)
        comments_layout.addWidget(publish_all_btn)

        layout.addWidget(comments_group)

    def _create_title_bar(self) -> QWidget:
        """创建标题栏"""
        from PyQt6.QtWidgets import QFrame, QHBoxLayout

        title_bar = QFrame()
        title_bar.setStyleSheet("background-color: #f8f9fa; border-bottom: 1px solid #dee2e6; padding: 8px;")

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(8, 4, 8, 4)

        # 标题
        title = QLabel("评论")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        layout.addStretch()

        # AI 评论按钮
        self.ai_review_btn = QPushButton("AI 评论")
        self.ai_review_btn.setMaximumWidth(80)
        self.ai_review_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c4dff;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6200ea;
            }
            QPushButton:pressed {
                background-color: #5200cc;
            }
            QPushButton:disabled {
                background-color: #b0a0ff;
            }
        """)
        self.ai_review_btn.clicked.connect(self._on_ai_review)
        layout.addWidget(self.ai_review_btn)

        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setMaximumWidth(60)
        clear_btn.clicked.connect(self._on_clear)
        layout.addWidget(clear_btn)

        return title_bar

    def set_code_location(self, file_path: str, line_number: int, line_type: str):
        """
        设置代码位置（当用户点击diff行时调用）

        Args:
            file_path: 文件路径
            line_number: 行号
            line_type: 行类型 (new/old/context)
        """
        self.current_file_path = file_path
        self.current_line_number = line_number
        self.current_line_type = line_type

        # 重置为添加评论模式
        self._editing_index = None

        # 设置标题为"添加评论"
        self.comment_editor.set_title("添加评论")
        self.comment_editor.set_location(file_path, line_number, line_type)

        # 清空评论内容
        self.comment_editor.comment_text.clear()
        self.comment_text.setFocus()

    def _on_comment_submitted(self, content: str):
        """处理评论提交"""
        # 检查是否是编辑模式
        if self._editing_index is not None:
            # 编辑现有评论
            if 0 <= self._editing_index < len(self.local_comments):
                self.local_comments[self._editing_index].content = content
                self._refresh_comment_list()
            # 重置编辑模式
            self._editing_index = None
        else:
            # 创建新评论（允许没有行号的普通评论）
            comment = ReviewComment(
                id=None,
                content=content,
                line_number=self.current_line_number,  # 可以为 None
                file_path=self.current_file_path or "",  # 可以为空字符串
                comment_type="user_comment",
            )

            # 使用当前列表长度作为索引
            index = len(self.local_comments)
            self.local_comments.append(comment)
            self.comment_list.add_comment(comment, index)

        # 清空编辑器
        self.comment_editor.clear()

    def _on_delete_comment(self, list_index: int):
        """处理删除评论"""
        # 获取实际的评论索引
        item = self.comment_list.item(list_index)
        if item:
            comment_index = item.data(Qt.ItemDataRole.UserRole)
            if 0 <= comment_index < len(self.local_comments):
                # 如果正在编辑的是被删除的评论，重置编辑模式
                if self._editing_index == comment_index:
                    self._editing_index = None
                    self.comment_editor.clear()

                # 删除评论
                del self.local_comments[comment_index]
                self.comment_list.takeItem(list_index)

                # 重新构建列表以更新索引
                self._refresh_comment_list()

    def _on_edit_comment(self, list_index: int):
        """处理编辑评论"""
        # 获取实际的评论索引
        item = self.comment_list.item(list_index)
        if item:
            comment_index = item.data(Qt.ItemDataRole.UserRole)
            if 0 <= comment_index < len(self.local_comments):
                comment = self.local_comments[comment_index]

                # 设置编辑模式
                self._editing_index = comment_index

                # 将评论内容加载到编辑器
                self.current_file_path = comment.file_path
                self.current_line_number = comment.line_number
                self.current_line_type = "new"  # 默认为新行

                # 更新编辑器标题为编辑模式
                self.comment_editor.set_title("编辑评论")

                # 根据是否有行号显示不同的位置信息
                if comment.file_path and comment.line_number:
                    self.comment_editor.location_label.setText(f"编辑评论 - {comment.file_path}:{comment.line_number}")
                elif comment.file_path:
                    self.comment_editor.location_label.setText(f"编辑评论 - {comment.file_path}")
                else:
                    self.comment_editor.location_label.setText("编辑评论 - 普通评论")

                self.comment_editor.comment_text.setPlainText(comment.content)

                # 聚焦到编辑器
                self.comment_text.setFocus()

    def _on_item_clicked(self, list_index: int):
        """处理单击评论项 - 加载到编辑器准备编辑"""
        # 获取实际的评论索引
        item = self.comment_list.item(list_index)
        if not item:
            return

        comment_index = item.data(Qt.ItemDataRole.UserRole)
        if comment_index is None or comment_index < 0 or comment_index >= len(self.local_comments):
            return

        comment = self.local_comments[comment_index]

        # 设置编辑模式
        self._editing_index = comment_index

        # 将评论内容加载到编辑器
        self.current_file_path = comment.file_path
        self.current_line_number = comment.line_number
        self.current_line_type = "new"  # 默认为新行

        # 更新编辑器标题为编辑模式
        self.comment_editor.set_title("编辑评论")

        # 根据是否有行号显示不同的位置信息
        if comment.file_path and comment.line_number:
            self.comment_editor.location_label.setText(f"编辑评论 - {comment.file_path}:{comment.line_number}")
        elif comment.file_path:
            self.comment_editor.location_label.setText(f"编辑评论 - {comment.file_path}")
        else:
            self.comment_editor.location_label.setText("编辑评论 - 普通评论")

        self.comment_editor.comment_text.setPlainText(comment.content)

        # 聚焦到编辑器
        self.comment_text.setFocus()

    def _refresh_comment_list(self):
        """刷新评论列表（更新索引）"""
        self.comment_list.clear()
        for i, comment in enumerate(self.local_comments):
            self.comment_list.add_comment(comment, i)

    def _on_comment_cancelled(self):
        """处理取消评论"""
        self.current_file_path = None
        self.current_line_number = None
        self.current_line_type = None
        self._editing_index = None  # 重置编辑模式
        self.comment_editor.clear()

    def _on_publish_all(self):
        """发布全部评论到GitLab"""
        if not self.local_comments:
            QMessageBox.information(self, "提示", "没有待发布的评论")
            return

        # 确认发布
        reply = QMessageBox.question(
            self,
            "确认发布",
            f"确定要发布 {len(self.local_comments)} 条评论到GitLab吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            for comment in self.local_comments:
                # 确定行类型
                line_type = self.current_line_type or "new"
                self.publish_comment_requested.emit(
                    comment.file_path,
                    comment.content,
                    comment.line_number,
                    line_type,
                )

            # 清空本地评论
            self.local_comments.clear()
            self.comment_list.clear_comments()
            QMessageBox.information(self, "成功", "评论已发布")

    def _on_publish_single(self, list_index: int):
        """发布单条评论到GitLab"""
        # 获取实际的评论索引
        item = self.comment_list.item(list_index)
        if not item:
            return

        comment_index = item.data(Qt.ItemDataRole.UserRole)
        if comment_index is None or comment_index < 0 or comment_index >= len(self.local_comments):
            return

        comment = self.local_comments[comment_index]

        # 确定行类型
        line_type = self.current_line_type or "new"

        # 发布评论
        self.publish_comment_requested.emit(
            comment.file_path,
            comment.content,
            comment.line_number,
            line_type,
        )

        # 从本地列表中删除已发布的评论
        del self.local_comments[comment_index]
        self.comment_list.takeItem(list_index)

        # 重新构建列表以更新索引
        self._refresh_comment_list()

    def _on_clear(self):
        """清空所有评论"""
        self.local_comments.clear()
        self.comment_list.clear_comments()
        self.comment_editor.clear()

    @property
    def comment_text(self):
        """获取评论文本输入框"""
        return self.comment_editor.comment_text

    def set_diff_files(self, diff_files: list):
        """设置当前MR的diff文件（用于AI审查）"""
        self.current_diff_files = diff_files

    def _on_ai_review(self):
        """处理AI评论按钮点击"""
        if not self.current_diff_files:
            QMessageBox.information(self, "提示", "请先选择一个Merge Request")
            return

        # 禁用按钮，显示正在审查
        self.ai_review_btn.setEnabled(False)
        self.ai_review_btn.setText("AI审查中...")

        # 发射AI审查请求信号
        self.ai_review_requested.emit()

    def on_ai_review_complete(self, ai_comments: list[dict]):
        """AI审查完成回调（由主窗口调用）"""
        # 启用按钮
        self.ai_review_btn.setEnabled(True)
        self.ai_review_btn.setText("AI 评论")

        # 添加AI生成的评论到待发布列表
        for comment_data in ai_comments:
            comment = ReviewComment(
                id=None,
                content=comment_data.get("content", ""),
                line_number=comment_data.get("line_number"),
                file_path=comment_data.get("file_path", ""),
                comment_type="ai_comment",
            )
            index = len(self.local_comments)
            self.local_comments.append(comment)
            self.comment_list.add_comment(comment, index)

        # 显示结果
        if ai_comments:
            QMessageBox.information(
                self,
                "AI审查完成",
                f"AI已生成 {len(ai_comments)} 条评论，已添加到待发布评论列表"
            )
        else:
            QMessageBox.information(
                self,
                "AI审查完成",
                "未发现明显问题"
            )

    def on_ai_review_error(self, error_msg: str):
        """AI审查错误回调"""
        self.ai_review_btn.setEnabled(True)
        self.ai_review_btn.setText("AI 评论")
        QMessageBox.critical(self, "AI审查失败", f"AI审查失败:\n\n{error_msg}")

    def _on_jump_to_comment(self, file_path: str, line_number: int):
        """处理跳转到评论位置"""
        # 发射信号给主窗口处理
        self.jump_to_comment_requested.emit(file_path, line_number)
