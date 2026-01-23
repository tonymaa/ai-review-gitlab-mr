"""UI主题配置 - 配合 qdarktheme 使用

qdarktheme 已在 main.py 中通过以下方式设置:
    qdarktheme.setup_theme(
        theme="auto",
        custom_colors={"primary": "#1677ff"}
    )

本模块仅保留必要的颜色常量和间距常量，供代码中动态使用。
所有样式由 qdarktheme 自动处理。
"""


class Theme:
    """主题常量 - 供代码动态使用，样式由 qdarktheme 处理"""

    # 主题色
    PRIMARY = "#1677ff"
    PRIMARY_HOVER = "#4096ff"
    PRIMARY_ACTIVE = "#0958d9"

    # 功能色
    SUCCESS = "#52c41a"
    WARNING = "#faad14"
    ERROR = "#ff4d4f"
    INFO = "#1677ff"

    # 文本色（用于动态设置颜色）
    TEXT_PRIMARY = "#262626"
    TEXT_SECONDARY = "#595959"
    TEXT_TERTIARY = "#8c8c8c"

    # 背景色（用于动态设置背景）
    BG_LAYOUT = "#f5f5f5"
    BG_BASE = "#ffffff"

    # 边框色（用于动态设置边框）
    BORDER_COLOR = "#d9d9d9"

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
