"""现代化UI主题配置 - 使用 #1677ff 作为主题色"""

import os
from pathlib import Path
from PyQt6.QtGui import QColor, QPalette, QPixmap, QPainter, QPen
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtWidgets import QApplication


class Theme:
    """现代化主题配置"""

    # 主题色
    PRIMARY = "#1677ff"
    PRIMARY_HOVER = "#4096ff"
    PRIMARY_ACTIVE = "#0958d9"
    PRIMARY_DISABLED = "#8c8c8c"

    # 功能色
    SUCCESS = "#52c41a"
    WARNING = "#faad14"
    ERROR = "#ff4d4f"
    INFO = "#1677ff"

    # 中性色
    TEXT_PRIMARY = "#262626"
    TEXT_SECONDARY = "#595959"
    TEXT_TERTIARY = "#8c8c8c"
    TEXT_QUATERNARY = "#bfbfbf"

    # 背景色
    BG_LAYOUT = "#f5f5f5"
    BG_BASE = "#ffffff"
    BG_ELEVATED = "#ffffff"
    BG_SPOTLIGHT = "#ffffff"
    BG_MASK = "rgba(0, 0, 0, 0.45)"

    # 边框色
    BORDER_COLOR = "#d9d9d9"
    BORDER_COLOR_SPLIT = "#f0f0f0"

    # 阴影
    SHADOW_1 = "0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02)"
    SHADOW_2 = "0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)"

    # 圆角
    RADIUS_SMALL = "4px"
    RADIUS_BASE = "6px"
    RADIUS_LARGE = "8px"

    # 间距 (CSS字符串版本，用于样式表)
    PADDING_XS = "4px"
    PADDING_SM = "8px"
    PADDING_MD = "12px"
    PADDING_LG = "16px"
    PADDING_XL = "24px"

    # 间距数值版本，用于 setContentsMargins, setSpacing 等
    PADDING_XS_INT = 4
    PADDING_SM_INT = 8
    PADDING_MD_INT = 12
    PADDING_LG_INT = 16
    PADDING_XL_INT = 24

    # 圆角数值版本
    RADIUS_SMALL_INT = 4
    RADIUS_BASE_INT = 6
    RADIUS_LARGE_INT = 8

    # Diff 专用色
    DIFF_ADD_BG = "#f6ffed"
    DIFF_ADD_TEXT = "#52c41a"
    DIFF_DELETE_BG = "#fff2f0"
    DIFF_DELETE_TEXT = "#ff4d4f"
    DIFF_HEADER_BG = "#f0f0f0"
    DIFF_HEADER_TEXT = "#595959"
    DIFF_CONTEXT_TEXT = "#8c8c8c"

    # 评论类型色
    COMMENT_AI_BADGE = "#1677ff"
    COMMENT_USER_BADGE = "#52c41a"

    @classmethod
    def apply_to_app(cls, app: QApplication):
        """应用主题到应用程序"""
        palette = app.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(cls.BG_BASE))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.Base, QColor(cls.BG_BASE))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(cls.BG_LAYOUT))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.Text, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.Button, QColor(cls.BG_BASE))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Link, QColor(cls.PRIMARY))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(cls.PRIMARY))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        app.setPalette(palette)


# 通用样式
STYLES = {
    # 按钮样式
    "button_primary": f"""
        QPushButton {{
            background-color: {Theme.PRIMARY};
            color: #ffffff;
            border: none;
            border-radius: {Theme.RADIUS_BASE};
            padding: {Theme.PADDING_SM} {Theme.PADDING_MD};
            font-weight: 500;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {Theme.PRIMARY_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {Theme.PRIMARY_ACTIVE};
        }}
        QPushButton:disabled {{
            background-color: {Theme.BG_LAYOUT};
            color: {Theme.TEXT_TERTIARY};
        }}
    """,

    "button_default": f"""
        QPushButton {{
            background-color: {Theme.BG_BASE};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER_COLOR};
            border-radius: {Theme.RADIUS_BASE};
            padding: {Theme.PADDING_SM} {Theme.PADDING_MD};
            font-weight: 500;
            font-size: 13px;
        }}
        QPushButton:hover {{
            color: {Theme.PRIMARY};
            border-color: {Theme.PRIMARY};
        }}
        QPushButton:pressed {{
            background-color: {Theme.BG_LAYOUT};
        }}
        QPushButton:disabled {{
            background-color: {Theme.BG_BASE};
            color: {Theme.TEXT_TERTIARY};
            border-color: {Theme.BORDER_COLOR};
        }}
    """,

    "button_text": f"""
        QPushButton {{
            background-color: transparent;
            color: {Theme.TEXT_PRIMARY};
            border: none;
            padding: {Theme.PADDING_XS} {Theme.PADDING_SM};
            font-weight: 500;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {Theme.BG_LAYOUT};
            color: {Theme.PRIMARY};
        }}
        QPushButton:pressed {{
            background-color: {Theme.BG_LAYOUT};
        }}
        QPushButton:disabled {{
            color: {Theme.TEXT_TERTIARY};
        }}
    """,

    # 输入框样式
    "input": f"""
        QLineEdit {{
            background-color: {Theme.BG_BASE};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER_COLOR};
            border-radius: {Theme.RADIUS_BASE};
            padding: {Theme.PADDING_SM};
            selection-background-color: {Theme.PRIMARY};
            selection-color: #ffffff;
        }}
        QTextEdit {{
            background-color: {Theme.BG_BASE};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER_COLOR};
            border-radius: {Theme.RADIUS_BASE};
            padding: {Theme.PADDING_SM};
            selection-background-color: {Theme.PRIMARY};
            selection-color: #ffffff;
        }}
        QPlainTextEdit {{
            background-color: {Theme.BG_BASE};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER_COLOR};
            border-radius: {Theme.RADIUS_BASE};
            padding: {Theme.PADDING_SM};
            selection-background-color: {Theme.PRIMARY};
            selection-color: #ffffff;
        }}
        QLineEdit:hover {{
            border-color: {Theme.PRIMARY_HOVER};
        }}
        QTextEdit:hover {{
            border-color: {Theme.PRIMARY_HOVER};
        }}
        QPlainTextEdit:hover {{
            border-color: {Theme.PRIMARY_HOVER};
        }}
        QLineEdit:focus {{
            border-color: {Theme.PRIMARY};
            outline: none;
        }}
        QTextEdit:focus {{
            border-color: {Theme.PRIMARY};
            outline: none;
        }}
        QPlainTextEdit:focus {{
            border-color: {Theme.PRIMARY};
            outline: none;
        }}
        QLineEdit:disabled {{
            background-color: {Theme.BG_LAYOUT};
            color: {Theme.TEXT_TERTIARY};
        }}
        QTextEdit:disabled {{
            background-color: {Theme.BG_LAYOUT};
            color: {Theme.TEXT_TERTIARY};
        }}
        QPlainTextEdit:disabled {{
            background-color: {Theme.BG_LAYOUT};
            color: {Theme.TEXT_TERTIARY};
        }}
    """,

    # 组合框样式
    "combobox": f"""
        QComboBox {{
            background-color: {Theme.BG_BASE};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER_COLOR};
            border-radius: {Theme.RADIUS_BASE};
            padding: {Theme.PADDING_XS} {Theme.PADDING_SM};
            min-height: 20px;
        }}
        QComboBox:hover {{
            border-color: {Theme.PRIMARY_HOVER};
        }}
        QComboBox:focus {{
            border-color: {Theme.PRIMARY};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: right center;
            width: 20px;
            border-left: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: {Theme.BG_BASE};
            border: 1px solid {Theme.BORDER_COLOR};
            border-radius: {Theme.RADIUS_BASE};
            selection-background-color: {Theme.BG_LAYOUT};
            selection-color: {Theme.TEXT_PRIMARY};
            padding: {Theme.PADDING_XS};
        }}
        QComboBox QAbstractItemView::item {{
            padding: {Theme.PADDING_XS} {Theme.PADDING_SM};
            border-radius: {Theme.RADIUS_SMALL};
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {Theme.BG_LAYOUT};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {Theme.BG_LAYOUT};
            color: {Theme.PRIMARY};
        }}
    """,

    # 树形控件样式
    "tree": f"""
        QTreeWidget {{
            background-color: {Theme.BG_BASE};
            border: 1px solid {Theme.BORDER_COLOR};
            border-radius: {Theme.RADIUS_BASE};
            outline: none;
            font-size: 12px;
        }}
        QTreeWidget::item {{
            padding: {Theme.PADDING_SM} {Theme.PADDING_SM};
            border-bottom: 1px solid {Theme.BORDER_COLOR_SPLIT};
            color: {Theme.TEXT_PRIMARY};
        }}
        QTreeWidget::item:hover {{
            background-color: {Theme.BG_LAYOUT};
        }}
        QTreeWidget::item:selected {{
            background-color: rgba(22, 119, 255, 0.1);
            color: {Theme.PRIMARY};
        }}
        QTreeWidget::branch {{
            background-color: {Theme.BG_BASE};
        }}
        QTreeWidget::branch:has-children:closed {{
            image: none;
            border: none;
        }}
        QTreeWidget::branch:has-children:open {{
            image: none;
            border: none;
        }}
        QTreeWidget::header {{
            background-color: {Theme.BG_LAYOUT};
            border: none;
            border-bottom: 1px solid {Theme.BORDER_COLOR};
            padding: {Theme.PADDING_SM};
        }}
        QTreeWidget::header::section {{
            background-color: {Theme.BG_LAYOUT};
            color: {Theme.TEXT_SECONDARY};
            border: none;
            border-right: 1px solid {Theme.BORDER_COLOR_SPLIT};
            padding: {Theme.PADDING_XS} {Theme.PADDING_SM};
            font-weight: 600;
            font-size: 11px;
        }}
    """,

    # 列表控件样式
    "list": f"""
        QListWidget {{
            background-color: {Theme.BG_BASE};
            border: 1px solid {Theme.BORDER_COLOR};
            border-radius: {Theme.RADIUS_BASE};
            outline: none;
        }}
        QListWidget::item {{
            padding: {Theme.PADDING_SM} {Theme.PADDING_MD};
            border-bottom: 1px solid {Theme.BORDER_COLOR_SPLIT};
            color: {Theme.TEXT_PRIMARY};
        }}
        QListWidget::item:hover {{
            background-color: {Theme.BG_LAYOUT};
        }}
        QListWidget::item:selected {{
            background-color: rgba(22, 119, 255, 0.1);
            color: {Theme.PRIMARY};
        }}
    """,

    # 标签页样式
    "tab": f"""
        QTabWidget::pane {{
            border: 1px solid {Theme.BORDER_COLOR};
            background-color: {Theme.BG_BASE};
            border-radius: {Theme.RADIUS_BASE};
            top: -1px;
        }}
        QTabBar::tab {{
            background-color: {Theme.BG_LAYOUT};
            color: {Theme.TEXT_SECONDARY};
            border: 1px solid {Theme.BORDER_COLOR};
            border-bottom: none;
            padding: {Theme.PADDING_SM} {Theme.PADDING_MD};
            margin-right: 2px;
            border-top-left-radius: {Theme.RADIUS_BASE};
            border-top-right-radius: {Theme.RADIUS_BASE};
            font-size: 12px;
        }}
        QTabBar::tab:hover {{
            color: {Theme.PRIMARY};
            background-color: {Theme.BG_BASE};
        }}
        QTabBar::tab:selected {{
            background-color: {Theme.BG_BASE};
            color: {Theme.PRIMARY};
            border-bottom: 2px solid {Theme.PRIMARY};
            font-weight: 600;
        }}
    """,

    # 分组框样式
    "groupbox": f"""
        QGroupBox {{
            background-color: {Theme.BG_BASE};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER_COLOR};
            border-radius: {Theme.RADIUS_BASE};
            margin-top: {Theme.PADDING_SM};
            padding-top: {Theme.PADDING_SM};
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: {Theme.PADDING_MD};
            padding: 0 {Theme.PADDING_XS};
        }}
    """,

    # 滚动条样式
    "scrollbar": f"""
        QScrollBar:vertical {{
            background-color: {Theme.BG_LAYOUT};
            width: 10px;
            border-radius: 5px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {Theme.TEXT_TERTIARY};
            min-height: 20px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {Theme.TEXT_SECONDARY};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QScrollBar:horizontal {{
            background-color: {Theme.BG_LAYOUT};
            height: 10px;
            border-radius: 5px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {Theme.TEXT_TERTIARY};
            min-width: 20px;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {Theme.TEXT_SECONDARY};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
    """,

    # 标题栏样式
    "title_bar": f"""
        QFrame {{
            background-color: {Theme.BG_BASE};
            border-bottom: 1px solid {Theme.BORDER_COLOR_SPLIT};
            padding: {Theme.PADDING_MD};
        }}
    """,

    # 状态栏样式
    "status_bar": f"""
        QFrame {{
            background-color: {Theme.BG_LAYOUT};
            color: {Theme.TEXT_SECONDARY};
            border-top: 1px solid {Theme.BORDER_COLOR_SPLIT};
            padding: {Theme.PADDING_XS} {Theme.PADDING_SM};
            font-size: 11px;
        }}
        QLabel {{
            background-color: {Theme.BG_LAYOUT};
            color: {Theme.TEXT_SECONDARY};
            border-top: 1px solid {Theme.BORDER_COLOR_SPLIT};
            padding: {Theme.PADDING_XS} {Theme.PADDING_SM};
            font-size: 11px;
        }}
    """,

    # 工具栏样式
    "toolbar": f"""
        QFrame {{
            background-color: {Theme.BG_LAYOUT};
            border-bottom: 1px solid {Theme.BORDER_COLOR_SPLIT};
            padding: {Theme.PADDING_SM};
        }}
    """,

    # 对话框样式
    "dialog": f"""
        QDialog {{
            background-color: {Theme.BG_BASE};
        }}
    """,

    # 主窗口样式
    "main_window": f"""
        QMainWindow {{
            background-color: {Theme.BG_LAYOUT};
        }}
        QMainWindow::separator {{
            background-color: {Theme.BORDER_COLOR_SPLIT};
            width: 1px;
            height: 1px;
        }}
        QMainWindow::separator:hover {{
            background-color: {Theme.PRIMARY};
        }}
    """,
}


def get_button_style(variant: str = "primary") -> str:
    """获取按钮样式

    Args:
        variant: primary | default | text
    """
    return STYLES.get(f"button_{variant}", STYLES["button_primary"])


def get_input_style() -> str:
    """获取输入框样式"""
    return STYLES["input"]


def get_combobox_style() -> str:
    """获取组合框样式"""
    return STYLES["combobox"]


def get_tree_style() -> str:
    """获取树形控件样式"""
    return STYLES["tree"]


def get_list_style() -> str:
    """获取列表控件样式"""
    return STYLES["list"]


def get_tab_style() -> str:
    """获取标签页样式"""
    return STYLES["tab"]


def get_groupbox_style() -> str:
    """获取分组框样式"""
    return STYLES["groupbox"]


def get_scrollbar_style() -> str:
    """获取滚动条样式"""
    return STYLES["scrollbar"]


def get_title_bar_style() -> str:
    """获取标题栏样式"""
    return STYLES["title_bar"]


def get_status_bar_style() -> str:
    """获取状态栏样式"""
    return STYLES["status_bar"]


def get_toolbar_style() -> str:
    """获取工具栏样式"""
    return STYLES["toolbar"]


def get_dialog_style() -> str:
    """获取对话框样式"""
    return STYLES["dialog"]


def get_main_window_style() -> str:
    """获取主窗口样式"""
    return STYLES["main_window"]


def get_qss_file_path() -> str:
    """获取 QSS 样式文件的路径"""
    # 获取当前文件所在目录
    current_dir = Path(__file__).parent
    return str(current_dir / "styles.qss")


def _ensure_down_arrow_icon():
    """确保下拉箭头图标存在"""
    icon_path = Path(__file__).parent / "images" / "down_arrow.png"
    if not icon_path.exists():
        # 创建图标
        size = 16
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 设置画笔颜色 - 深灰色
        color = QColor(Theme.TEXT_SECONDARY)
        pen = QPen(color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        # 绘制 V 形箭头
        center_x = size / 2
        center_y = size / 2
        offset = size / 4

        # 左上到中心
        painter.drawLine(QPointF(center_x - offset, center_y - offset/2),
                         QPointF(center_x, center_y + offset/2))
        # 中心到右上
        painter.drawLine(QPointF(center_x, center_y + offset/2),
                         QPointF(center_x + offset, center_y - offset/2))

        painter.end()

        # 确保目录存在
        icon_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存为 PNG
        pixmap.save(str(icon_path))

    return str(icon_path)


def load_qss_stylesheet(widget=None) -> str:
    """
    从外部 QSS 文件加载样式表

    Args:
        widget: 可选，要应用样式的组件。如果为 None，则只返回样式表字符串

    Returns:
        样式表字符串
    """
    # 确保箭头图标存在并获取路径
    icon_path = _ensure_down_arrow_icon()

    qss_path = get_qss_file_path()

    try:
        with open(qss_path, 'r', encoding='utf-8') as f:
            stylesheet = f.read()

        # 替换图片路径为绝对路径 (Windows 兼容)
        abs_path = str(Path(icon_path).absolute()).replace(os.sep, '/')
        stylesheet = stylesheet.replace("url(src/images/down_arrow.png)", f"url(file:///{abs_path})")

        # 如果提供了 widget，则应用样式
        if widget:
            widget.setStyleSheet(stylesheet)

        return stylesheet
    except FileNotFoundError:
        logger = __import__('logging').getLogger(__name__)
        logger.warning(f"QSS样式文件未找到: {qss_path}，将使用内联样式")
        return ""
    except Exception as e:
        logger = __import__('logging').getLogger(__name__)
        logger.error(f"加载QSS样式文件失败: {e}")
        return ""


def apply_stylesheet_to_widget(widget, style_type: str = "full"):
    """
    应用样式到组件

    Args:
        widget: 要应用样式的组件
        style_type: 样式类型 ("full" 加载完整QSS, "minimal" 只应用基本样式)
    """
    if style_type == "full":
        # 加载外部QSS文件
        qss_style = load_qss_stylesheet()
        if qss_style:
            current_style = widget.styleSheet() or ""
            widget.setStyleSheet(current_style + qss_style)
        else:
            # 如果外部文件不存在，使用内联样式作为后备
            widget.setStyleSheet(get_main_window_style())
    else:
        # 使用内联样式
        widget.setStyleSheet(get_main_window_style())


# 便捷函数：为不同组件应用样式
def apply_button_style(button, variant: str = "primary"):
    """应用按钮样式"""
    button.setProperty("class", variant)
    style = load_qss_stylesheet()
    if style:
        button.setStyleSheet(button.styleSheet() + style)


def apply_input_style(widget):
    """应用输入框样式"""
    style = load_qss_stylesheet()
    if style:
        widget.setStyleSheet(widget.styleSheet() + style)


def apply_combobox_style(widget):
    """应用下拉框样式"""
    style = load_qss_stylesheet()
    if style:
        widget.setStyleSheet(widget.styleSheet() + style)


def apply_tree_style(widget):
    """应用树形控件样式"""
    style = load_qss_stylesheet()
    if style:
        widget.setStyleSheet(widget.styleSheet() + style)


def apply_list_style(widget):
    """应用列表控件样式"""
    style = load_qss_stylesheet()
    if style:
        widget.setStyleSheet(widget.styleSheet() + style)


def apply_tab_style(widget):
    """应用标签页样式"""
    style = load_qss_stylesheet()
    if style:
        widget.setStyleSheet(widget.styleSheet() + style)


def apply_scrollbar_style(widget):
    """应用滚动条样式"""
    style = load_qss_stylesheet()
    if style:
        widget.setStyleSheet(widget.styleSheet() + style)
