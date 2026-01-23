"""MR列表组件 - 显示Merge Request列表"""

from typing import Optional, List
from datetime import datetime, timezone
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QLineEdit,
    QLabel,
    QPushButton,
    QComboBox,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon

from ..gitlab.models import MergeRequestInfo, MRState
from .theme import Theme


class MRListWidget(QWidget):
    """Merge Request列表组件"""

    # 信号：MR被选中
    mr_selected = pyqtSignal(object)  # MergeRequestInfo
    # 信号：需要刷新
    refresh_requested = pyqtSignal()
    # 信号：状态筛选改变
    state_filter_changed = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.mr_list: List[MergeRequestInfo] = []
        self.current_mr: Optional[MergeRequestInfo] = None

        self._setup_ui()

    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        title_bar = self._create_title_bar()
        layout.addWidget(title_bar)

        # 搜索和筛选栏
        filter_bar = self._create_filter_bar()
        layout.addWidget(filter_bar)

        # MR列表树
        self.mr_tree = self._create_mr_tree()
        layout.addWidget(self.mr_tree)

        # 状态栏
        self.status_label = QLabel()
        self.status_label.setProperty("class", "status-bar")
        layout.addWidget(self.status_label)

    def _create_title_bar(self) -> QFrame:
        """创建标题栏"""
        title_bar = QFrame()

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(Theme.PADDING_MD_INT, Theme.PADDING_SM_INT, Theme.PADDING_MD_INT, Theme.PADDING_SM_INT)
        layout.setSpacing(Theme.PADDING_SM_INT)

        # 标题
        title = QLabel("Merge Requests")
        layout.addWidget(title)

        layout.addStretch()

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setMaximumWidth(60)
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        layout.addWidget(self.refresh_btn)

        return title_bar

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
        self.search_input.setPlaceholderText("搜索标题、作者...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self.search_input)

        # 状态筛选
        state_label = QLabel("状态:")
        layout.addWidget(state_label)
        self.state_combo = QComboBox()
        self.state_combo.addItems(["全部", "已打开", "已合并", "已关闭"])
        self.state_combo.currentTextChanged.connect(self._on_state_filter_changed)
        layout.addWidget(self.state_combo)

        return filter_bar

    def _create_mr_tree(self) -> QTreeWidget:
        """创建MR列表树"""
        tree = QTreeWidget()
        tree.setHeaderLabels(["!MR", "标题", "作者", "状态", "更新时间"])
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
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        return tree

    def load_merge_requests(self, mr_list: List[MergeRequestInfo]):
        """
        加载MR列表

        Args:
            mr_list: MergeRequestInfo列表
        """
        self.mr_list = mr_list
        self._refresh_display()

    def _refresh_display(self):
        """刷新显示"""
        # 获取筛选条件
        search_text = self.search_input.text().lower()
        state_filter = self.state_combo.currentText()

        # 映射状态筛选
        state_map = {
            "全部": None,
            "已打开": MRState.OPENED,
            "已合并": MRState.MERGED,
            "已关闭": MRState.CLOSED,
        }
        filter_state = state_map.get(state_filter)

        # 清空列表
        self.mr_tree.clear()

        # 筛选并添加MR
        filtered_count = 0
        for mr in self.mr_list:
            # 应用筛选
            if search_text:
                title_match = search_text in mr.title.lower()
                author_match = search_text in mr.author.username.lower() if mr.author else False
                if not (title_match or author_match):
                    continue

            if filter_state and mr.state != filter_state:
                continue

            filtered_count += 1
            self._add_mr_item(mr)

        # 更新状态栏
        self.status_label.setText(f"共 {filtered_count} 个MR (总计 {len(self.mr_list)})")

    def _add_mr_item(self, mr: MergeRequestInfo):
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
        item = QTreeWidgetItem([
            f"!{mr.iid}",
            mr.title,
            mr.author.name if mr.author else "未知",
            state_text,
            time_str,
        ])

        # 设置状态颜色
        item.setForeground(3, QColor(state_color))

        # 存储MR对象
        item.setData(0, Qt.ItemDataRole.UserRole, mr)

        # WIP标记
        if mr.work_in_progress:
            item.setText(0, f"[WIP] !{mr.iid}")
            item.setForeground(0, QColor("#868e96"))

        # 添加到树
        self.mr_tree.addTopLevelItem(item)

    def _format_time(self, dt: datetime) -> str:
        """格式化时间"""
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

    def _on_selection_changed(self):
        """处理选择变化"""
        selected_items = self.mr_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            mr = item.data(0, Qt.ItemDataRole.UserRole)
            if mr:
                self.current_mr = mr
                self.mr_selected.emit(mr)

    def _on_search_text_changed(self, text: str):
        """处理搜索文本变化"""
        self._refresh_display()

    def _on_state_filter_changed(self, state: str):
        """处理状态筛选变化"""
        self.state_filter_changed.emit(state)
        self._refresh_display()

    def _on_refresh_clicked(self):
        """处理刷新按钮点击"""
        self.refresh_requested.emit()

    def get_selected_mr(self) -> Optional[MergeRequestInfo]:
        """获取当前选中的MR"""
        return self.current_mr

    def clear(self):
        """清空列表"""
        self.mr_list.clear()
        self.mr_tree.clear()
        self.current_mr = None
        self.status_label.setText("无MR")

    def set_loading(self, loading: bool):
        """设置加载状态"""
        if loading:
            self.status_label.setText("加载中...")
            self.refresh_btn.setEnabled(False)
        else:
            self.refresh_btn.setEnabled(True)
