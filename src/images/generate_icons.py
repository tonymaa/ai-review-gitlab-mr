"""生成下拉箭头图标"""
from PyQt6.QtGui import QPixmap, QPainter, QPen
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPolygonF
import sys

def create_down_arrow(size: int = 16, output_path: str = "down_arrow.png"):
    """创建下拉箭头图标"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 设置画笔颜色 - 深灰色
    color = Qt.GlobalColor.darkGray
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

    # 保存为 PNG
    pixmap.save(output_path)
    print(f"Arrow icon saved to: {output_path}")

if __name__ == "__main__":
    create_down_arrow(16, "e:/project/gitlab-ai-review/src/images/down_arrow.png")
