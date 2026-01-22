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
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect
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
    """行号区域组件 - 可点击选择行"""

    # 信号：行被点击
    line_clicked = pyqtSignal(int, str)  # (line_number, line_type)

    # 图标区域宽度
    ICON_WIDTH = 20

    def __init__(self, editor: "CodeDiffViewer"):
        super().__init__(editor)
        self.editor = editor
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # 当前悬停的行号
        self._hovered_line = None

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        """绘制行号"""
        from PyQt6.QtGui import QPainter, QPainterPath, QPen, QFontMetricsF
        from PyQt6.QtCore import QPointF, QRectF

        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#f1f3f5"))

        # 获取文档和布局
        document = self.editor.document()
        layout = document.documentLayout()

        # 计算滚动偏移（使用 scrollbar 的位置）
        scrollbar = self.editor.verticalScrollBar()
        offset_y = -scrollbar.value()
        offset = QPointF(0, offset_y)

        # 从文档开始查找第一个可见块
        block = document.begin()
        block_number = 0

        # 找到第一个可见的块（在视口上方的块跳过）
        while block.isValid():
            block_rect = layout.blockBoundingRect(block).translated(offset)
            if block_rect.bottom() >= 0:
                # 找到了第一个可见块
                break
            block = block.next()
            block_number += 1
        else:
            return  # 没有可见块

        # 绘制可见的行号
        font = QFont("Consolas", 9)
        painter.setFont(font)

        while block.isValid():
            block_rect = layout.blockBoundingRect(block).translated(offset)

            if block_rect.top() > event.rect().bottom():
                break  # 超出可见区域

            if block.isVisible() and block_rect.bottom() >= event.rect().top():
                # 获取行信息
                line_info = self.editor.line_info.get(block_number)
                if line_info:
                    old_line, new_line, line_type = line_info

                    # 根据行类型选择颜色
                    if line_type == "addition":
                        bg_color = QColor("#d4edda")
                        text_color = QColor("#155724")
                    elif line_type == "deletion":
                        bg_color = QColor("#f8d7da")
                        text_color = QColor("#721c24")
                    elif line_type == "header":
                        bg_color = QColor("#e2e3e5")
                        text_color = QColor("#383d41")
                    else:
                        bg_color = QColor("#ffffff")
                        text_color = QColor("#6c757d")

                    # 绘制背景
                    painter.fillRect(0, int(block_rect.top()), self.width(), int(block_rect.height()), bg_color)

                    # 绘制评论图标（仅当鼠标悬停在该行时）
                    if block_number == self._hovered_line:
                        self._draw_comment_icon(painter, block_rect)

                    # 显示行号（在图标右侧）
                    if new_line is not None:
                        line_num = str(new_line)
                    elif old_line is not None:
                        line_num = str(old_line)
                    else:
                        line_num = " "

                    painter.setPen(text_color)
                    painter.drawText(
                        self.ICON_WIDTH,  # 从图标区域后开始
                        int(block_rect.top()),
                        self.width() - self.ICON_WIDTH - 5,
                        int(block_rect.height()),
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        line_num,
                    )

            block = block.next()
            block_number += 1

    def _draw_comment_icon(self, painter, block_rect):
        """绘制评论图标（气泡样式）"""
        from PyQt6.QtGui import QPainterPath, QPen
        from PyQt6.QtCore import QRectF

        # 图标区域
        icon_size = 14
        x = (self.ICON_WIDTH - icon_size) / 2
        y = block_rect.top() + (block_rect.height() - icon_size) / 2
        rect = QRectF(x, y, icon_size, icon_size)

        # 创建气泡路径
        path = QPainterPath()

        # 气泡主体（圆角矩形）
        radius = 3
        path.addRoundedRect(rect, radius, radius)

        # 气泡尾巴（小三角形）
        tail_size = 4
        tail_x = rect.right() - 2
        tail_y = rect.center().y()
        path.moveTo(tail_x, tail_y - tail_size / 2)
        path.lineTo(tail_x + tail_size, tail_y)
        path.lineTo(tail_x, tail_y + tail_size / 2)

        # 填充气泡
        painter.setPen(QPen(QColor("#6c757d"), 1.5))
        painter.setBrush(QColor("#f8f9fa"))
        painter.drawPath(path)

        # 绘制三个小点表示评论
        dot_color = QColor("#6c757d")
        dot_radius = 1.2
        center_y = rect.center().y()

        for i in range(3):
            dot_x = rect.left() + 3 + i * 4
            painter.setPen(dot_color)
            painter.setBrush(dot_color)
            painter.drawEllipse(QRectF(dot_x - dot_radius, center_y - dot_radius,
                                       dot_radius * 2, dot_radius * 2))

    def mouseMoveEvent(self, event):
        """处理鼠标移动（用于悬停效果）"""
        from PyQt6.QtCore import QPointF

        document = self.editor.document()
        layout = document.documentLayout()
        scrollbar = self.editor.verticalScrollBar()
        offset_y = -scrollbar.value()
        offset = QPointF(0, offset_y)

        # 查找鼠标悬停的行
        block = document.begin()
        block_number = 0
        mouse_y = event.position().y()

        old_hovered = self._hovered_line
        self._hovered_line = None

        while block.isValid():
            block_rect = layout.blockBoundingRect(block).translated(offset)
            if block_rect.top() <= mouse_y <= block_rect.bottom():
                if block_number in self.editor.line_info:
                    self._hovered_line = block_number
                break
            block = block.next()
            block_number += 1

        # 更新光标样式
        if self._hovered_line is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        # 如果悬停行改变，重绘
        if old_hovered != self._hovered_line:
            self.update()

    def mousePressEvent(self, event):
        """处理鼠标点击"""
        from PyQt6.QtCore import QPointF

        document = self.editor.document()
        layout = document.documentLayout()

        # 计算滚动偏移（使用 scrollbar 的位置）
        scrollbar = self.editor.verticalScrollBar()
        offset_y = -scrollbar.value()
        offset = QPointF(0, offset_y)

        # 从文档开始查找被点击的块
        block = document.begin()
        block_number = 0
        click_y = event.position().y()
        click_x = event.position().x()

        while block.isValid():
            block_rect = layout.blockBoundingRect(block).translated(offset)
            if block_rect.top() <= click_y <= block_rect.bottom():
                # 找到了点击的块
                if block_number in self.editor.line_info:
                    # 只有点击在图标区域内才触发
                    if click_x <= self.ICON_WIDTH:
                        old_line, new_line, line_type = self.editor.line_info[block_number]
                        line_num = new_line if new_line is not None else old_line
                        if line_num:
                            self.line_clicked.emit(line_num, line_type)
                break
            block = block.next()
            block_number += 1

        super().mousePressEvent(event)


class CodeDiffViewer(QTextEdit):
    """代码Diff查看器"""

    # 信号：行被点击 (从行号区域点击触发)
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
                border-right: none;
                border-radius: 4px 0 0 4px;
                padding: 0px;
            }
        """)

        # 当前显示的diff文件
        self.current_diff_file: Optional[DiffFile] = None

        # 行信息映射 (block_number -> (old_line, new_line, line_type))
        self.line_info: dict[int, Tuple[Optional[int], Optional[int], str]] = {}

        # 创建行号区域
        self.line_number_area = LineNumberArea(self)
        self.line_number_area.line_clicked.connect(self.line_clicked.emit)

        # 连接信号 - 使用QTextEdit的信号
        self.textChanged.connect(self.update_line_number_area_width)
        # 注意：QTextEdit没有updateRequest信号，我们需要通过其他方式更新行号区域
        # 使用scrollbar的信号来更新
        self.verticalScrollBar().valueChanged.connect(self.line_number_area.update)

        # 获取document的blockCountChanged信号
        self.document().blockCountChanged.connect(self.update_line_number_area_width)

        # 设置高亮器
        self.highlighter = DiffHighlighter(self.document())

        # 设置边距为行号区域宽度
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

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

    def line_number_area_width(self) -> int:
        """计算行号区域宽度"""
        # 包含图标宽度 + 行号宽度
        icon_width = LineNumberArea.ICON_WIDTH
        digits = len(str(max(1, self.document().blockCount())))
        return icon_width + 40 + digits * self.fontMetrics().horizontalAdvance("9")

    def update_line_number_area_width(self):
        """更新行号区域宽度"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int):
        """更新行号区域"""
        if dy:
            self.line_number_area.scroll(0, dy)
        self.line_number_area.update()

        if rect.contains(self.viewport().rect()):
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

    def resizeEvent(self, event):
        """处理窗口大小改变"""
        super().resizeEvent(event)

        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            cr.left(),
            cr.top(),
            self.line_number_area_width(),
            cr.height(),
        )

    def jump_to_line(self, line_number: int):
        """
        跳转到指定行号

        Args:
            line_number: 目标行号
        """
        # 查找包含该行号的块
        document = self.document()
        block = document.begin()
        block_number = 0

        while block.isValid():
            if block_number in self.line_info:
                old_line, new_line, line_type = self.line_info[block_number]
                # 检查是否匹配目标行号
                if new_line == line_number or old_line == line_number:
                    # 找到了，滚动到该位置
                    cursor = QTextCursor(block)
                    self.setTextCursor(cursor)
                    # 手动滚动使该行居中
                    self._center_cursor_on_line(cursor.block())
                    # 高亮显示该行
                    self._highlight_line(cursor)
                    return
            block = block.next()
            block_number += 1

    def _center_cursor_on_line(self, block):
        """手动滚动使指定块居中"""
        # 获取块的几何信息
        layout = self.document().documentLayout()
        block_rect = layout.blockBoundingRect(block)

        # 计算滚动位置使块居中
        scrollbar = self.verticalScrollBar()
        viewport_height = self.viewport().height()

        # 当前滚动位置
        current_scroll = scrollbar.value()
        # 块相对于文档顶部的位置
        block_top = int(block_rect.top())

        # 计算新的滚动位置使块居中
        new_scroll = block_top - viewport_height // 2 + int(block_rect.height()) // 2

        # 设置滚动位置
        scrollbar.setValue(new_scroll)

    def _highlight_line(self, cursor: QTextCursor):
        """临时高亮显示当前行"""
        # 保存原始光标位置
        original_position = cursor.position()

        # 选择整行
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)

        # 创建选区（额外格式）
        extra_selections = self.extraSelections()

        # 创建高亮格式
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor("#fff3cd"))  # 黄色高亮

        # 创建高亮选区
        highlight = QTextEdit.ExtraSelection()
        highlight.cursor = cursor
        highlight.format = highlight_format

        # 添加高亮
        extra_selections.append(highlight)
        self.setExtraSelections(extra_selections)

        # 1秒后清除高亮
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, lambda: self._clear_highlight())

    def _clear_highlight(self):
        """清除行高亮"""
        self.setExtraSelections([])


class DiffViewerPanel(QWidget):
    """Diff查看器面板 - 包含文件选择和代码显示"""

    # 信号：文件被选中
    file_selected = pyqtSignal(int)  # file_index
    # 信号：代码行被点击
    line_clicked = pyqtSignal(int, str, str)  # (line_number, line_type, file_path)
    # 信号：AI审查当前文件请求
    ai_review_current_file_requested = pyqtSignal(object)  # diff_file (DiffFile对象)

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

        # AI评论当前文件按钮
        self.ai_review_file_btn = QPushButton("AI评论当前文件")
        self.ai_review_file_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c4dff;
                color: white;
                border: none;
                padding: 6px 12px;
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
        self.ai_review_file_btn.clicked.connect(self._on_ai_review_current_file)
        file_selector_layout.addWidget(self.ai_review_file_btn)

        file_selector_layout.addStretch()
        layout.addLayout(file_selector_layout)

        # 代码查看器容器（包含行号条和代码区域）
        viewer_container = QWidget()
        viewer_container.setStyleSheet("background-color: #ffffff;")
        viewer_layout = QHBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(0)

        # 创建代码查看器
        self.diff_viewer = CodeDiffViewer()
        self.diff_viewer.line_clicked.connect(self._on_line_clicked)

        # 添加行号区域和编辑器
        viewer_layout.addWidget(self.diff_viewer.line_number_area)
        viewer_layout.addWidget(self.diff_viewer)

        layout.addWidget(viewer_container)

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

    def _on_ai_review_current_file(self):
        """处理AI评论当前文件按钮点击"""
        current_file = self.get_current_diff_file()
        if current_file:
            self.ai_review_current_file_requested.emit(current_file)
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请先选择一个文件")

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

    def jump_to_file_and_line(self, file_path: str, line_number: int):
        """
        跳转到指定文件和行号

        Args:
            file_path: 文件路径
            line_number: 行号
        """
        # 查找匹配的文件
        target_index = -1
        for i, diff_file in enumerate(self.diff_files):
            # 检查 old_path 和 new_path 是否匹配
            if file_path in (diff_file.old_path, diff_file.new_path):
                target_index = i
                break

        if target_index < 0:
            # 未找到匹配文件
            return

        # 切换到目标文件
        self.file_combo.setCurrentIndex(target_index)

        # 跳转到指定行
        self.diff_viewer.jump_to_line(line_number)
