"""Diff代码查看器 - 支持语法高亮和行号显示"""

import re
from typing import Optional, List, Tuple
from PyQt6.QtWidgets import (
    QTextEdit,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QSplitter,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import (
    QTextCursor,
    QTextCharFormat,
    QColor,
    QFont,
    QTextBlockFormat,
    QSyntaxHighlighter,
    QTextDocument,
)
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.token import Token
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

from ..gitlab.models import DiffFile


class DiffHighlighter(QSyntaxHighlighter):
    """Diff语法高亮器"""

    def __init__(self, document: QTextDocument):
        super().__init__(document)

        # 定义颜色方案
        self.addition_format = QTextCharFormat()
        self.addition_format.setBackground(QColor("#d4edda"))
        self.addition_format.setForeground(QColor("#155724"))

        self.deletion_format = QTextCharFormat()
        self.deletion_format.setBackground(QColor("#f8d7da"))
        self.deletion_format.setForeground(QColor("#721c24"))

        self.header_format = QTextCharFormat()
        self.header_format.setBackground(QColor("#e2e3e5"))
        self.header_format.setForeground(QColor("#383d41"))
        self.header_format.setFontWeight(QFont.Weight.Bold)

        self.context_format = QTextCharFormat()
        self.context_format.setForeground(QColor("#6c757d"))

    def highlightBlock(self, text: str):
        """高亮文本块"""
        if text.startswith("@@"):
            # Diff header
            self.setFormat(0, len(text), self.header_format)
        elif text.startswith("+") and not text.startswith("+++"):
            # 添加的行
            self.setFormat(0, len(text), self.addition_format)
        elif text.startswith("-") and not text.startswith("---"):
            # 删除的行
            self.setFormat(0, len(text), self.deletion_format)
        else:
            # 上下文行
            self.setFormat(0, len(text), self.context_format)


class LineNumberArea(QWidget):
    """行号区域组件"""

    def __init__(self, editor: "CodeDiffViewer"):
        super().__init__(editor)
        self.editor = editor
        self.setFixedWidth(80)

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        """绘制行号"""
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#f8f9fa"))

        block = self.editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
        bottom = top + self.editor.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#6c757d"))
                painter.setFont(QFont("Consolas", 9))
                painter.drawText(
                    0,
                    int(top),
                    self.width() - 5,
                    self.editor.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + self.editor.blockBoundingRect(block).height()
            block_number += 1


from PyQt6.QtGui import QPainter


class CodeDiffViewer(QTextEdit):
    """代码Diff查看器"""

    # 信号：行被点击
    line_clicked = pyqtSignal(int, str)  # (line_number, line_type)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # 设置字体
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        # 设置只读
        self.setReadOnly(True)

        # 设置样式
        self.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
            }
        """)

        # 当前显示的diff文件
        self.current_diff_file: Optional[DiffFile] = None

        # 行信息映射 (block_number -> (old_line, new_line, line_type))
        self.line_info: dict[int, Tuple[Optional[int], Optional[int], str]] = {}

        # 安装事件过滤器
        self.viewport().installEventFilter(self)

        # 设置高亮器
        self.highlighter = DiffHighlighter(self.document())

    def load_diff_file(self, diff_file: DiffFile):
        """
        加载并显示diff文件

        Args:
            diff_file: DiffFile对象
        """
        self.current_diff_file = diff_file
        self.line_info.clear()

        # 解析diff内容
        lines = diff_file.diff.split("\n")

        # 构建显示内容
        display_lines = []
        old_line_num = 0
        new_line_num = 0

        for line in lines:
            if line.startswith("@@"):
                # 解析hunk头部
                # 格式: @@ -old_start,old_lines +new_start,new_lines @@
                match = re.match(r"@@\s+-(\d+),?\d*\s+\+(\d+),?\d*\s+@@", line)
                if match:
                    old_line_num = int(match.group(1)) - 1
                    new_line_num = int(match.group(2)) - 1
                line_type = "header"
            elif line.startswith("+") and not line.startswith("+++"):
                new_line_num += 1
                line_type = "addition"
            elif line.startswith("-") and not line.startswith("---"):
                old_line_num += 1
                line_type = "deletion"
            else:
                # 上下文行
                old_line_num += 1
                new_line_num += 1
                line_type = "context"

            display_lines.append(line)

            # 保存行信息
            block_num = len(display_lines) - 1
            if line_type == "addition":
                self.line_info[block_num] = (None, new_line_num, line_type)
            elif line_type == "deletion":
                self.line_info[block_num] = (old_line_num, None, line_type)
            elif line_type == "context":
                self.line_info[block_num] = (old_line_num, new_line_num, line_type)
            else:
                self.line_info[block_num] = (None, None, line_type)

        # 显示内容
        self.setPlainText("\n".join(display_lines))

    def mousePressEvent(self, event):
        """处理鼠标点击事件"""
        super().mousePressEvent(event)

        # 获取点击的行
        cursor = self.cursorForPosition(event.pos())
        block_number = cursor.blockNumber()

        # 获取行信息
        if block_number in self.line_info:
            old_line, new_line, line_type = self.line_info[block_number]
            # 发射信号
            line_num = new_line if new_line is not None else old_line
            if line_num:
                self.line_clicked.emit(line_num, line_type)

    def line_number_area_width(self) -> int:
        """计算行号区域宽度"""
        digits = len(str(max(1, self.document().blockCount())))
        space = 20
        return 50 + digits * self.fontMetrics().horizontalAdvance("9")

    def update_line_number_area(self, rect: int, dy: int):
        """更新行号区域"""
        if dy:
            self.scroll(0, dy)
        else:
            self.viewport().update(0, rect, self.width(), rect)
            self.update()

    def resizeEvent(self, event):
        """处理窗口大小改变"""
        super().resizeEvent(event)
        # 更新布局


class DiffViewerPanel(QWidget):
    """Diff查看器面板 - 包含文件选择和代码显示"""

    # 信号：文件被选中
    file_selected = pyqtSignal(int)  # file_index
    # 信号：代码行被点击
    line_clicked = pyqtSignal(int, str, str)  # (line_number, line_type, file_path)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.diff_files: List[DiffFile] = []
        self.current_file_index: int = -1

        self._setup_ui()

    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # 文件选择下拉框
        file_selector_layout = QHBoxLayout()
        file_selector_layout.addWidget(QLabel("文件:"))

        self.file_combo = QComboBox()
        self.file_combo.setMinimumWidth(400)
        self.file_combo.currentIndexChanged.connect(self._on_file_changed)
        file_selector_layout.addWidget(self.file_combo)

        file_selector_layout.addStretch()
        layout.addLayout(file_selector_layout)

        # 代码查看器
        self.diff_viewer = CodeDiffViewer()
        self.diff_viewer.line_clicked.connect(self._on_line_clicked)
        layout.addWidget(self.diff_viewer)

        # 状态栏
        self.status_label = QLabel()
        self.status_label.setStyleSheet("padding: 4px; background-color: #f8f9fa; border-top: 1px solid #dee2e6;")
        layout.addWidget(self.status_label)

    def _create_toolbar(self) -> QFrame:
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #f8f9fa; border-bottom: 1px solid #dee2e6; padding: 4px;")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 4, 8, 4)

        # 统计标签
        self.stats_label = QLabel()
        layout.addWidget(self.stats_label)

        layout.addStretch()

        return toolbar

    def load_diffs(self, diff_files: List[DiffFile]):
        """
        加载diff文件列表

        Args:
            diff_files: DiffFile列表
        """
        self.diff_files = diff_files
        self.file_combo.clear()

        if not diff_files:
            self.file_combo.addItem("(无文件变更)")
            self.stats_label.setText("无文件变更")
            return

        # 添加文件到下拉框
        for i, diff_file in enumerate(diff_files):
            display_text = diff_file.get_display_path()
            # 添加统计信息
            stats = f" (+{diff_file.additions}, -{diff_file.deletions})"
            self.file_combo.addItem(f"{display_text}{stats}", i)

        # 更新统计
        total_additions = sum(df.additions for df in diff_files)
        total_deletions = sum(df.deletions for df in diff_files)
        self.stats_label.setText(
            f"共 {len(diff_files)} 个文件, "
            f"+{total_additions} 行, -{total_deletions} 行"
        )

        # 选择第一个文件
        if diff_files:
            self.file_combo.setCurrentIndex(0)

    def _on_file_changed(self, index: int):
        """处理文件选择变化"""
        if index < 0 or index >= len(self.diff_files):
            return

        self.current_file_index = index
        diff_file = self.diff_files[index]
        self.diff_viewer.load_diff_file(diff_file)

        # 更新状态栏
        change_type = "新增" if diff_file.new_file else "删除" if diff_file.deleted_file else "修改"
        self.status_label.setText(
            f"{change_type} | {diff_file.old_path} → {diff_file.new_path}"
        )

        # 发射信号
        self.file_selected.emit(index)

    def _on_line_clicked(self, line_number: int, line_type: str):
        """处理代码行点击"""
        if self.current_file_index >= 0 and self.current_file_index < len(self.diff_files):
            file_path = self.diff_files[self.current_file_index].get_display_path()
            self.line_clicked.emit(line_number, line_type, file_path)

    def get_current_diff_file(self) -> Optional[DiffFile]:
        """获取当前显示的diff文件"""
        if 0 <= self.current_file_index < len(self.diff_files):
            return self.diff_files[self.current_file_index]
        return None

    def clear(self):
        """清空显示"""
        self.diff_files.clear()
        self.file_combo.clear()
        self.diff_viewer.clear()
        self.current_file_index = -1
        self.stats_label.setText("无文件变更")
        self.status_label.clear()
