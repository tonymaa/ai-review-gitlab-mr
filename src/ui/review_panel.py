"""审查意见面板 - 显示AI审查结果"""

import json
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLabel,
    QPushButton,
    QTabWidget,
    QScrollArea,
    QFrame,
    QProgressBar,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QTextDocument, QFont

from ..gitlab.models import AIReviewResult, ReviewComment
from ..ai.reviewer import AIReviewer, ReviewIssue
from .theme import Theme, load_qss_stylesheet


class ReviewWorkerThread(QThread):
    """AI审查工作线程"""

    # 信号：审查完成
    review_finished = pyqtSignal(object)  # AIReviewResult
    # 信号：审查失败
    review_failed = pyqtSignal(str)  # error_message
    # 信号：进度更新
    progress_updated = pyqtSignal(str)  # status_message

    def __init__(
        self,
        reviewer: AIReviewer,
        mr: "MergeRequestInfo",
        diff_files: List,
        review_rules: List[str],
    ):
        super().__init__()
        self.reviewer = reviewer
        self.mr = mr
        self.diff_files = diff_files
        self.review_rules = review_rules

    def run(self):
        """运行审查"""
        try:
            self.progress_updated.emit("正在进行AI审查...")
            result = self.reviewer.review_merge_request(
                mr=self.mr,
                diff_files=self.diff_files,
                review_rules=self.review_rules,
                quick_mode=False,
            )
            self.review_finished.emit(result)
        except Exception as e:
            self.review_failed.emit(str(e))


class IssueWidget(QFrame):
    """单个问题显示组件"""

    def __init__(self, issue: ReviewIssue, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.issue = issue
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.PADDING_MD_INT, Theme.PADDING_MD_INT, Theme.PADDING_MD_INT, Theme.PADDING_MD_INT)
        layout.setSpacing(Theme.PADDING_XS_INT)

        # 根据严重程度设置颜色
        severity_colors = {
            "critical": Theme.ERROR,
            "warning": Theme.WARNING,
            "suggestion": Theme.SUCCESS,
        }
        severity_labels = {
            "critical": "严重",
            "warning": "警告",
            "suggestion": "建议",
        }
        color = severity_colors.get(self.issue.severity, Theme.TEXT_TERTIARY)
        label = severity_labels.get(self.issue.severity, "其他")

        # 设置样式
        self.setStyleSheet(f"""
            background-color: {Theme.BG_BASE};
            border: 1px solid {Theme.BORDER_COLOR};
            border-radius: {Theme.RADIUS_BASE};
            border-left: 3px solid {color};
            margin: {Theme.PADDING_XS};
        """)

        # 标题栏
        title_layout = QHBoxLayout()
        title_layout.setSpacing(Theme.PADDING_XS_INT)

        # 严重程度标签
        severity_label = QLabel(f"[{label}]")
        severity_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        title_layout.addWidget(severity_label)

        # 位置信息
        if self.issue.file_path:
            location = self.issue.file_path
            if self.issue.line_number:
                location += f":{self.issue.line_number}"
            location_label = QLabel(location)
            location_label.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 10px;")
            title_layout.addWidget(location_label)

        title_layout.addStretch()
        layout.addLayout(title_layout)

        # 描述
        desc_label = QLabel(self.issue.description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"padding: {Theme.PADDING_XS}; color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(desc_label)


class ReviewPanel(QWidget):
    """审查意见面板"""

    # 信号：需要发布评论到GitLab
    publish_comment_requested = pyqtSignal(str, str, int, str)  # (file_path, content, line, type)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.current_review_result: Optional[AIReviewResult] = None
        self.review_thread: Optional[ReviewWorkerThread] = None

        self._setup_ui()

    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        title_bar = self._create_title_bar()
        layout.addWidget(title_bar)

        # 主内容区域（使用Tab）
        self.tab_widget = QTabWidget()
        load_qss_stylesheet(self.tab_widget)

        # 摘要Tab
        self.summary_tab = self._create_summary_tab()
        self.tab_widget.addTab(self.summary_tab, "摘要")

        # 问题Tab
        self.issues_tab = self._create_issues_tab()
        self.tab_widget.addTab(self.issues_tab, "问题")

        # 警告Tab
        self.warnings_tab = self._create_warnings_tab()
        self.tab_widget.addTab(self.warnings_tab, "警告")

        # 建议Tab
        self.suggestions_tab = self._create_suggestions_tab()
        self.tab_widget.addTab(self.suggestions_tab, "建议")

        layout.addWidget(self.tab_widget)

    def _create_title_bar(self) -> QFrame:
        """创建标题栏"""
        title_bar = QFrame()
        load_qss_stylesheet(title_bar)

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(Theme.PADDING_MD_INT, Theme.PADDING_SM_INT, Theme.PADDING_MD_INT, Theme.PADDING_SM_INT)
        layout.setSpacing(Theme.PADDING_SM_INT)

        # 标题
        title = QLabel("AI审查意见")
        title.setStyleSheet(f"font-weight: 600; font-size: 14px; color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(title)

        layout.addStretch()

        # 开始审查按钮
        self.start_review_btn = QPushButton("开始审查")
        self.start_review_btn.setProperty("class", "primary")
        self.start_review_btn.clicked.connect(self._on_start_review)
        layout.addWidget(self.start_review_btn)

        return title_bar

    def _create_summary_tab(self) -> QWidget:
        """创建摘要Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT, Theme.PADDING_LG_INT)
        layout.setSpacing(Theme.PADDING_MD_INT)

        # 评分
        score_layout = QHBoxLayout()
        score_label = QLabel("整体评分:")
        score_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        score_layout.addWidget(score_label)
        self.score_label = QLabel("-")
        self.score_label.setStyleSheet(f"font-size: 24px; font-weight: 600; color: {Theme.PRIMARY};")
        score_layout.addWidget(self.score_label)
        max_score_label = QLabel("/ 10")
        max_score_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        score_layout.addWidget(max_score_label)
        score_layout.addStretch()
        layout.addLayout(score_layout)

        # 摘要文本
        summary_title = QLabel("审查摘要:")
        summary_title.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(summary_title)
        self.summary_text = QTextEdit()
        self.summary_text.setProperty("class", "input")
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(150)
        layout.addWidget(self.summary_text)

        # 统计信息
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(Theme.PADDING_MD_INT)
        stats_layout.addWidget(QLabel("问题:"))
        self.issues_count_label = QLabel("0")
        self.issues_count_label.setStyleSheet(f"color: {Theme.ERROR}; font-weight: 600;")
        stats_layout.addWidget(self.issues_count_label)

        stats_layout.addWidget(QLabel("| 警告:"))
        self.warnings_count_label = QLabel("0")
        self.warnings_count_label.setStyleSheet(f"color: {Theme.WARNING}; font-weight: 600;")
        stats_layout.addWidget(self.warnings_count_label)

        stats_layout.addWidget(QLabel("| 建议:"))
        self.suggestions_count_label = QLabel("0")
        self.suggestions_count_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-weight: 600;")
        stats_layout.addWidget(self.suggestions_count_label)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        layout.addStretch()
        return widget

    def _create_issues_tab(self) -> QScrollArea:
        """创建问题Tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self.issues_layout = QVBoxLayout(container)
        self.issues_layout.addStretch()
        scroll.setWidget(container)

        return scroll

    def _create_warnings_tab(self) -> QScrollArea:
        """创建警告Tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self.warnings_layout = QVBoxLayout(container)
        self.warnings_layout.addStretch()
        scroll.setWidget(container)

        return scroll

    def _create_suggestions_tab(self) -> QScrollArea:
        """创建建议Tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self.suggestions_layout = QVBoxLayout(container)
        self.suggestions_layout.addStretch()
        scroll.setWidget(container)

        return scroll

    def start_review(
        self,
        reviewer: AIReviewer,
        mr: "MergeRequestInfo",
        diff_files: List,
        review_rules: List[str],
    ):
        """
        开始AI审查

        Args:
            reviewer: AI审查器
            mr: Merge Request信息
            diff_files: Diff文件列表
            review_rules: 审查规则列表
        """
        # 停止之前的审查
        if self.review_thread and self.review_thread.isRunning():
            self.review_thread.quit()
            self.review_thread.wait()

        # 创建新的审查线程
        self.review_thread = ReviewWorkerThread(
            reviewer=reviewer,
            mr=mr,
            diff_files=diff_files,
            review_rules=review_rules,
        )
        self.review_thread.review_finished.connect(self._on_review_finished)
        self.review_thread.review_failed.connect(self._on_review_failed)
        self.review_thread.progress_updated.connect(self._on_progress_updated)

        # 更新UI状态
        self.start_review_btn.setEnabled(False)
        self.start_review_btn.setText("审查中...")
        self._clear_all_tabs()

        # 启动线程
        self.review_thread.start()

    def _on_review_finished(self, result: AIReviewResult):
        """处理审查完成"""
        self.current_review_result = result
        self._display_review_result(result)

        # 恢复按钮
        self.start_review_btn.setEnabled(True)
        self.start_review_btn.setText("重新审查")

    def _on_review_failed(self, error_message: str):
        """处理审查失败"""
        QMessageBox.critical(self, "审查失败", f"AI审查过程中发生错误:\n\n{error_message}")

        # 恢复按钮
        self.start_review_btn.setEnabled(True)
        self.start_review_btn.setText("开始审查")

    def _on_progress_updated(self, message: str):
        """处理进度更新"""
        self.start_review_btn.setText(message)

    def _display_review_result(self, result: AIReviewResult):
        """显示审查结果"""
        # 更新摘要
        self.score_label.setText(str(result.overall_score))
        self.summary_text.setPlainText(result.summary)
        self.issues_count_label.setText(str(result.issues_count))
        self.warnings_count_label.setText(str(len(result.warnings)))
        self.suggestions_count_label.setText(str(result.suggestions_count))

        # 更新问题列表
        for issue_text in result.critical_issues:
            self._add_issue_widget(self.issues_layout, issue_text, "critical")

        # 更新警告列表
        for warning_text in result.warnings:
            self._add_issue_widget(self.warnings_layout, warning_text, "warning")

        # 更新建议列表
        for suggestion_text in result.suggestions:
            self._add_issue_widget(self.suggestions_layout, suggestion_text, "suggestion")

    def _add_issue_widget(self, layout: QVBoxLayout, text: str, severity: str):
        """添加问题组件"""
        issue = ReviewIssue(
            file_path="",
            line_number=None,
            description=text,
            severity=severity,
        )
        widget = IssueWidget(issue)
        layout.insertWidget(layout.count() - 1, widget)

    def _clear_all_tabs(self):
        """清空所有Tab"""
        # 清空问题Tab
        while self.issues_layout.count() > 1:
            item = self.issues_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 清空警告Tab
        while self.warnings_layout.count() > 1:
            item = self.warnings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 清空建议Tab
        while self.suggestions_layout.count() > 1:
            item = self.suggestions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 重置摘要
        self.score_label.setText("-")
        self.summary_text.clear()
        self.issues_count_label.setText("0")
        self.warnings_count_label.setText("0")
        self.suggestions_count_label.setText("0")

    def _on_start_review(self):
        """处理开始审查按钮点击"""
        # 这个方法由主窗口连接
        pass

    def clear(self):
        """清空显示"""
        self.current_review_result = None
        self._clear_all_tabs()

    def get_current_result(self) -> Optional[AIReviewResult]:
        """获取当前审查结果"""
        return self.current_review_result
