from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QFrame,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextEdit,
    QSizeGrip,
)
from PySide6.QtCore import Qt, QPoint, QBuffer, QIODevice
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from osdagbridge_desktop.ui.dialogs.tabs.common import apply_field_style
from osdagbridge_desktop.ui.utils.styled_scroll_area import StyledScrollArea
from osdagbridge_desktop.ui.utils.custom_titlebar import CustomTitleBar
from osdagbridge_desktop.ui.dialogs.tabs.steel_design_check import StatusBadge
from osdagbridge_desktop.ui.utils.custom_widgets import PercentBarWidget

# Import the schema
from osdagbridge_core.core.bridge_types.plate_girder.ui_fields_additional_input import DECK_DESIGN_SUMMARY_SCHEMA


class NoScrollTable(QTableWidget):
    """Passes wheel events to parent scroll area — table never scrolls."""
    def wheelEvent(self, event):
        event.ignore()


class DeckReinforcementCADWidget(QWidget):
    """Responsive schematic of deck reinforcement and girder position."""

    _CACHE_SCALE = 3
    _CAD_ROW_IDENTIFIERS = {
        "T1": ("Transverse", "Interior", "Top"),
        "T2": ("Transverse", "Overhang", "Top"),
        "T3": ("Longitudinal", "Full deck", "Top"),
        "B1": ("Longitudinal", "Full deck", "Bottom"),
        "B2": ("Transverse", "Full deck", "Bottom"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict = {}
        self._cached_data = None
        self._cached_size = None
        self._cached_image = None
        self._cached_png_bytes = None
        self.setMinimumSize(300, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, data: dict) -> None:
        new_data = dict(data or {})
        if new_data != self._data:
            self._data = new_data
            self._invalidate_cache()
            self.update()

    def _invalidate_cache(self) -> None:
        self._cached_data = None
        self._cached_size = None
        self._cached_image = None
        self._cached_png_bytes = None

    def resizeEvent(self, event) -> None:
        if self._cached_size != self._expected_cache_size():
            self._invalidate_cache()
        super().resizeEvent(event)

    def _expected_cache_size(self):
        return (
            self.width() * self._CACHE_SCALE,
            self.height() * self._CACHE_SCALE,
        )

    def _cache_is_valid(self) -> bool:
        return (
            self._cached_png_bytes is not None
            and self._cached_data == self._data
            and self._cached_size == self._expected_cache_size()
            and self._cached_image is not None
            and (
                self._cached_image.width(),
                self._cached_image.height(),
            ) == self._cached_size
        )

    def _ensure_cache(self) -> None:
        if self._cache_is_valid():
            return

        image = QImage(
            *self._expected_cache_size(),
            QImage.Format_ARGB32_Premultiplied,
        )
        image.fill(QColor("#ffffff"))
        painter = QPainter(image)
        painter.scale(self._CACHE_SCALE, self._CACHE_SCALE)
        self._draw_cad(painter)
        painter.end()

        buffer = QBuffer()
        if not buffer.open(QIODevice.WriteOnly):
            raise RuntimeError("Could not open deck reinforcement image buffer")
        try:
            if not image.save(buffer, "PNG"):
                raise RuntimeError("Could not encode deck reinforcement CAD")
            self._cached_data = dict(self._data)
            self._cached_size = self._expected_cache_size()
            self._cached_image = image
            self._cached_png_bytes = bytes(buffer.data())
        finally:
            buffer.close()

    def cached_png(self, data: dict = None) -> bytes:
        if data is not None and dict(data or {}) != self._data:
            self.set_data(data)
        self._ensure_cache()
        return self._cached_png_bytes

    @staticmethod
    def _number(value, default=0.0) -> float:
        try:
            return float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return default

    def _value(self, key: str, default="") -> str:
        value = self._data.get(key, default)
        return str(value) if value not in (None, "") else default

    def _property_value(self, label: str, default="") -> str:
        fields = DECK_DESIGN_SUMMARY_SCHEMA.get(
            "properties_card", {}
        ).get("fields", [])

        data_key = next(
            (
                field.get("data_key")
                for field in fields
                if field.get("label") == label
            ),
            None,
        )

        if not data_key:
            return default

        return self._value(data_key, default)

    def _map_reinforcement_data(self, designation: str):
        identifiers = self._CAD_ROW_IDENTIFIERS.get(designation)
        if not identifiers:
            return {}

        direction, zone, face = identifiers
        rows = DECK_DESIGN_SUMMARY_SCHEMA.get("reinforcement_table", {}).get(
            "rows", []
        )
        return next(
            (
                row
                for row in rows
                if (
                    row.get("direction") == direction
                    and row.get("zone") == zone
                    and row.get("face") == face
                )
            ),
            {},
        )
    @staticmethod
    def _schema_key_map(row: dict) -> dict:
        """Resolve schema field roles to their actual data keys."""
        return {
            field_name[:-4]: data_key
            for field_name, data_key in row.items()
            if (
                isinstance(field_name, str)
                and field_name.endswith("_key")
                and isinstance(data_key, str)
                and data_key
            )
        }
    def _reinforcement_data(self) -> dict:
        rows = DECK_DESIGN_SUMMARY_SCHEMA.get(
            "reinforcement_table", {}
        ).get("rows", [])

        required_keys = {
            data_key
            for row in rows
            for data_key in self._schema_key_map(row).values()
        }
        return {
            key: self._data[key]
            for key in self._data
            if key in required_keys
        }

    def _reinforcement_value(
        self, designation: str, data_field: str, default=""
    ) -> str:
        row = self._map_reinforcement_data(designation)
        data_key = self._schema_key_map(row).get(data_field)

        if not data_key:
            return default

        return str(
            self._reinforcement_data().get(data_key, default)
        )


    def _reinforcement_info(self, designation: str):
        if not self._map_reinforcement_data(designation):
            return None

        dia = self._number(
            self._reinforcement_value(designation, "bar"), 0.0
        )
        spacing = self._number(
            self._reinforcement_value(designation, "spacing"), 0.0
        )

        if dia <= 0 or spacing <= 0:
            return None

        return {
            "details": f"{dia:g} mm @ {spacing:g} mm",
        }

    def _dimension(
        self,
        painter,
        x1,
        y1,
        x2,
        y2,
        label,
        vertical=False,
    ):
        color = QColor("#709900")
        painter.setPen(QPen(color, 1))
        painter.setBrush(color)

        painter.drawLine(
            int(x1), int(y1),
            int(x2), int(y2),
        )

        span = abs(y2 - y1) if vertical else abs(x2 - x1)
        arrow_size = max(1, min(6, span / 3))
        arrow_half_width = 2

        if vertical:
            # Top arrow points downward into the measured span.
            painter.drawPolygon([
                QPoint(int(x1), int(y1)),
                QPoint(
                    int(x1 - arrow_half_width),
                    int(y1 + arrow_size),
                ),
                QPoint(
                    int(x1 + arrow_half_width),
                    int(y1 + arrow_size),
                ),
            ])

            # Bottom arrow points upward into the measured span.
            painter.drawPolygon([
                QPoint(int(x2), int(y2)),
                QPoint(
                    int(x2 - arrow_half_width),
                    int(y2 - arrow_size),
                ),
                QPoint(
                    int(x2 + arrow_half_width),
                    int(y2 - arrow_size),
                ),
            ])

            painter.setPen(color)
            painter.drawText(
                int(x1 + 6),
                int((y1 + y2) / 2 - 9),
                76,
                18,
                Qt.AlignLeft | Qt.AlignVCenter,
                label,
            )
        else:
            # Left arrow points right, into the measured span.
            painter.drawPolygon([
                QPoint(int(x1), int(y1)),
                QPoint(
                    int(x1 + arrow_size),
                    int(y1 - arrow_half_width),
                ),
                QPoint(
                    int(x1 + arrow_size),
                    int(y1 + arrow_half_width),
                ),
            ])

            # Right arrow points left, into the measured span.
            painter.drawPolygon([
                QPoint(int(x2), int(y2)),
                QPoint(
                    int(x2 - arrow_size),
                    int(y2 - arrow_half_width),
                ),
                QPoint(
                    int(x2 - arrow_size),
                    int(y2 + arrow_half_width),
                ),
            ])

            painter.setPen(color)
            painter.drawText(
                int(x1),
                int(y1 + 2),
                int(x2 - x1),
                18,
                Qt.AlignCenter,
                label,
            )

    def _draw_vertical_dimension_arrows(
        self, painter, x, y_top, y_bottom
    ):
        arrow_size = 7
        arrow_half_width = 2

        painter.setBrush(QColor("#709900"))

        # Top arrowhead
        painter.drawPolygon([
            QPoint(int(x), int(y_top)),
            QPoint(
                int(x - arrow_half_width),
                int(y_top + arrow_size),
            ),
            QPoint(
                int(x + arrow_half_width),
                int(y_top + arrow_size),
            ),
        ])

        # Bottom arrowhead
        painter.drawPolygon([
            QPoint(int(x), int(y_bottom)),
            QPoint(
                int(x - arrow_half_width),
                int(y_bottom - arrow_size),
            ),
            QPoint(
                int(x + arrow_half_width),
                int(y_bottom - arrow_size),
            ),
        ])


    def _draw_reinforcement_label(self, painter, designation, pos):
        info = self._reinforcement_info(designation)
        if not info:
            return

        painter.setFont(QFont("Arial", 8))
        painter.setPen(QColor("#709900"))

        text = info["details"]
        metrics = painter.fontMetrics()

        # Keep the label within the CAD widget's horizontal bounds.
        margin = 8
        available_width = self.width() - 2 * margin
        text_width = metrics.horizontalAdvance(text)

        # Prefer one line unless the complete label would be clipped.
        if text_width <= available_width:
            lines = [text]
        else:
            parts = text.split("@", 1)
            if len(parts) == 2:
                lines = [
                    parts[0].strip() + " @",
                    parts[1].strip(),
                ]
            else:
                lines = [text]

        line_height = metrics.height()
        total_height = line_height * len(lines)

        # Centre the label around its anchor, then clamp it to the widget.
        text_x = pos.x() - max(
            metrics.horizontalAdvance(line) for line in lines
        ) // 2
        text_x = max(
            margin,
            min(text_x, self.width() - margin - max(
                metrics.horizontalAdvance(line) for line in lines
            )),
        )

        if designation in ("T1", "T2", "T3"):
            text_y = pos.y() - 14 - total_height
        else:
            text_y = pos.y() + 14

        # Prevent vertical clipping at the widget edges.
        text_y = max(
            line_height,
            min(text_y, self.height() - total_height),
        )

        for index, line in enumerate(lines):
            painter.drawText(
                text_x,
                text_y + (index + 1) * line_height,
                line,
            )
    def paintEvent(self, _event):
        self._ensure_cache()
        painter = QPainter(self)
        painter.drawImage(self.rect(), self._cached_image)
        painter.end()

    def _draw_cad(self, painter):
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setRenderHint(QPainter.Antialiasing)

        bounds = self.rect().adjusted(10, 10, -10, -10)
        painter.setPen(QPen(QColor("#202020")))
        painter.setFont(QFont("Arial", 11, QFont.Bold))
        painter.setPen(QColor("#111111"))
        painter.drawText(
            bounds.left(), bounds.top(), bounds.width(), 24,
            Qt.AlignHCenter | Qt.AlignTop, "Deck Reinforcement"
        )
        overhang_mm = self._number(
            self._property_value("Deck Overhang (mm):"), 0.0
        )
        thickness = self._number(
            self._property_value("Thickness (mm):"), 0.0
        )
        if thickness <= 0:
            painter.setFont(QFont("Arial", 9))
            painter.drawText(
                bounds.adjusted(0, 30, 0, 0), Qt.AlignCenter,
                "Deck thickness unavailable"
            )
            return

        cover_top = self._number(
            self._reinforcement_value("T1", "cover"), 50.0
        )
        cover_bottom = self._number(
            self._reinforcement_value("B2", "cover"), 50.0
        )
        top_dia = self._number(
            self._reinforcement_value("T1", "bar"), 0.0
        )
        bottom_dia = self._number(
            self._reinforcement_value("B2", "bar"), 0.0
        )
        # Use the effective depths calculated by the Core design.
        # B2: transverse bottom reinforcement.
        # T1: transverse top reinforcement in the interior zone.
        d_bottom = self._number(
            self._reinforcement_value("B2", "depth"),
            0.0,
        )
        d_top = self._number(
            self._reinforcement_value("T1", "depth"),
            0.0,
        )

        left = bounds.left() + 22
        right = bounds.right() - 100
        top = bounds.top() + 106
        available_width = max(120, right - left)
        available_height = max(70, bounds.bottom() - top - 42)
        slab_height = min(available_height * 0.62, 82)
        slab_bottom = top + slab_height
        slab_right = right
        support_x = left + available_width * 0.28

        # Fill the concrete slab without drawing its right border.
        painter.setPen(QPen(QColor("#4c4c4c"), 1))
        painter.setBrush(QColor("#e8e8e8"))
        painter.drawRect(
            int(left), int(top),
            int(slab_right - left), int(slab_height)
        )

        # Cover only the unwanted straight right border with concrete fill.
        painter.setPen(QPen(QColor("#e8e8e8"), 3))
        painter.drawLine(
            int(slab_right), int(top + 1),
            int(slab_right), int(slab_bottom - 1)
        )

        # Zigzag break forming the actual right boundary of the slab.
        painter.setPen(QPen(QColor("#4c4c4c"), 1))


        # Short vertical zigzag break at the right end of the slab
        # Upper zigzag break at the right end of the slab.
        painter.setPen(QPen(QColor("#4c4c4c"), 1))

        zigzag = [
            (slab_right, top),
            (slab_right, top + slab_height * 0.38),
            (slab_right + 7, top + slab_height * 0.50),
            (slab_right - 5, top + slab_height * 0.62),
            (slab_right, top + slab_height * 0.70),
        ]

        for index in range(len(zigzag) - 1):
            x1, y1 = zigzag[index]
            x2, y2 = zigzag[index + 1]
            painter.drawLine(
                int(x1), int(y1),
                int(x2), int(y2)
            )

        # Straight lower boundary of the slab.
        painter.drawLine(
            int(slab_right), int(top + slab_height * 0.70),
            int(slab_right), int(slab_bottom)
        )
        top_offset = max(
            8,
            min(
                slab_height * 0.28,
                (cover_top + top_dia / 2.0) / thickness * slab_height,
            ),
        )
        bottom_offset = max(
            8,
            min(
                slab_height * 0.28,
                (cover_bottom + bottom_dia / 2.0) / thickness * slab_height,
            ),
        )
        top_y = top + top_offset
        bottom_y = slab_bottom - bottom_offset

            # Draw reinforcement bars with a visible central gap.
        bar_start_x = left + 10
        bar_end_x = slab_right - 10
        bend_x = bar_start_x

        leg_length = min(12, slab_height * 0.15)

        painter.setPen(QPen(QColor("#85877A"), 3))

        # Top horizontal reinforcement bar.
        painter.drawLine(
            int(bar_start_x),
            int(top_y),
            int(bar_end_x),
            int(top_y),
        )

        # Top vertical leg, contained within the slab.
        painter.drawLine(
            int(bend_x),
            int(top_y),
            int(bend_x),
            int(top_y + leg_length),
        )

        # Bottom horizontal reinforcement bar.
        painter.drawLine(
            int(bar_start_x),
            int(bottom_y),
            int(bar_end_x),
            int(bottom_y),
        )

        # Bottom vertical leg, contained within the slab.
        painter.drawLine(
            int(bend_x),
            int(bottom_y - leg_length),
            int(bend_x),
            int(bottom_y),
        )
        # Draw reinforcement markers using input-dependent spacing.
        marker_color = QColor("#99A850")
        painter.setPen(QPen(marker_color, 1))
        painter.setBrush(marker_color)

        top_spacing = self._number(
            self._reinforcement_value("T1", "spacing"), 200.0
        )
        overhang_spacing = self._number(
            self._reinforcement_value("T2", "spacing"), top_spacing
        )
        bottom_spacing = self._number(
            self._reinforcement_value("B2", "spacing"), 200.0
        )

        def draw_markers(
            x_start,
            x_end,
            y,
            spacing,
        ):
            points = []

            if x_end <= x_start:
                return points

            # Keep the schematic marker positions fixed,
            # regardless of the reinforcement spacing input.
            count = 4

            for index in range(count):
                x = x_start + index * (x_end - x_start) / (count - 1)
                px, py = int(x), int(y)

                # Keep original coordinates for callout calculations.
                points.append((px, py))

                # Shift only the selected green dot visually.
                marker_x = px
                dot_diameter = 4.5

                if y == top_y:
                    painter.drawEllipse(
                        int(marker_x - dot_diameter // 2),
                        py,
                        int(dot_diameter),
                        int(dot_diameter),
                    )
                else:
                    painter.drawEllipse(
                        int(marker_x - dot_diameter // 2),
                        int(py - dot_diameter),
                        int(dot_diameter),
                        int(dot_diameter),
                    )

            return points

        # Draw top markers at uniform intervals, matching the bottom row.
        # The callout labels still display the actual reinforcement spacing.
        top_points = draw_markers(
            bar_start_x + 10,
            bar_end_x,
            top_y,
            bottom_spacing,
        )

        # Split the points at the girder so callouts keep their correct zones.
        top_overhang_points = [
            point for point in top_points
            if point[0] < support_x
        ]
        top_interior_points = [
            point for point in top_points
            if point[0] >= support_x
        ]

        bottom_points = draw_markers(
            bar_start_x + 10,
            bar_end_x,
            bottom_y,
            bottom_spacing,
        )
        # T1: interior top; T2: overhang top (replacement for T1 there).
        # T3: longitudinal top; B1: longitudinal bottom;
        # B2: transverse bottom.
        def nearest_point(points, target_x):
            if not points:
                return (int(target_x), int(top_y))

            return min(points, key=lambda point: abs(point[0] - target_x))
        # Fixed callout anchors: independent of input values and marker count.
        # Reinforcement labels remain dynamically mapped to the UI data.
        pointer_points = {
            "T1": (
                int(left + available_width * 0.36),
                int(top_y),
            ),
            "T2": (
                int(left + available_width * 0.10),
                int(top_y),
            ),
            "T3": (
                int(left + available_width * 0.73),
                int(top_y),
            ),
            "B1": (
                int(left + available_width * 0.67),
                int(bottom_y),
            ),
            "B2": (
                int(left + available_width * 0.45),
                int(bottom_y),
            ),
        }
        # Exterior girder: top flange attached to slab, stem below.
        
        stem_height = 26
        flange_width = 64
        flange_height = 5

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#666666"))

        # Horizontal flange attached to the underside of the slab.
        painter.drawRect(
            int(support_x - flange_width / 2),
            int(slab_bottom),
            flange_width,
            flange_height,
        )

        # Vertical girder stem
        stem_center_x = int(support_x)
        stem_top_y = int(slab_bottom + flange_height)
        stem_bottom_y = int(stem_top_y + stem_height)

        painter.setPen(QPen(QColor("#666666"), 5))
        painter.drawLine(
            stem_center_x,
            stem_top_y,
            stem_center_x,
            stem_bottom_y,
        )

        # Thin zigzag symbol attached to the bottom of the stem
        painter.setPen(QPen(QColor("#393333"), 1))

        zigzag_shift_y = 5

        zigzag_points = [
            QPoint(stem_center_x - 14, stem_bottom_y + 2 + zigzag_shift_y),
            QPoint(stem_center_x - 5, stem_bottom_y + 2 + zigzag_shift_y),
            QPoint(stem_center_x + 1, stem_bottom_y - 6 + zigzag_shift_y),
            QPoint(stem_center_x + 6, stem_bottom_y + 7 + zigzag_shift_y),
            QPoint(stem_center_x + 15, stem_bottom_y + 2 + zigzag_shift_y),
        ]

        for index in range(len(zigzag_points) - 1):
            painter.drawLine(
                zigzag_points[index],
                zigzag_points[index + 1],
            )

        painter.setPen(QPen(QColor("#000000"), 1, Qt.DashLine))
        painter.drawLine(
            int(support_x),
            int(top - 15),
            int(support_x),
            int(stem_bottom_y - 30),
        )
        painter.setPen(QPen(QColor("#000000"), 1))
        painter.setFont(QFont("Arial", 7))
        painter.drawText(
            int(support_x - 32), int(top - 27), 64, 12,
            Qt.AlignCenter, "Girder CL"
    )
        # Right-end clear-cover annotations
        cover_color = QColor("#709900")
        painter.setPen(QPen(cover_color, 1))
        painter.setBrush(cover_color)
        painter.setFont(QFont("Arial", 7))

        cover_x = slab_right - 72
        cover_arrow_x = slab_right - 18

        cover_arrow_half_width = 2
        bottom_cover_arrow_half_width = 1

        top_cover_arrow_size = min(8, max(1, (top_y - top) / 2))
        bottom_cover_arrow_size = min(
            6, max(1, (slab_bottom - bottom_y) / 2)
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#709900"))

        # Top cover: arrowheads point inward towards each other.
        # Upper arrow points down.
        painter.drawPolygon([
            QPoint(
                int(cover_arrow_x),
                int(top),
            ),
            QPoint(
                int(cover_arrow_x - cover_arrow_half_width),
                int(top - 5),
            ),
            QPoint(
                int(cover_arrow_x + cover_arrow_half_width),
                int(top - 5),
            ),
        ])
        # Lower arrow points up.
        painter.drawPolygon([
            QPoint(
                int(cover_arrow_x),
                int(top_y),
            ),
            QPoint(
                int(cover_arrow_x - cover_arrow_half_width),
                int(top_y + 6),
            ),
            QPoint(
                int(cover_arrow_x + cover_arrow_half_width),
                int(top_y + 6),
            ),
        ])

        painter.setPen(QColor("#709900"))
        painter.setFont(QFont("Arial", 7))
        painter.drawText(
            int(cover_x - 4),
            int((top + top_y) / 2 - 6),
            52,
            12,
            Qt.AlignRight | Qt.AlignVCenter,
            f"{cover_top:g} mm",
        )

        # Bottom cover: arrowheads point inward towards each other.
        # Upper arrow points down.
        painter.drawPolygon([
            QPoint(
                int(cover_arrow_x),
                int(bottom_y),
            ),
            QPoint(
                int(cover_arrow_x - bottom_cover_arrow_half_width),
                int(bottom_y - 5),
            ),
            QPoint(
                int(cover_arrow_x + bottom_cover_arrow_half_width),
                int(bottom_y - 5),
            ),
        ])

        # Lower arrow points up.
        painter.drawPolygon([
            QPoint(
                int(cover_arrow_x),
                int(slab_bottom),
            ),
            QPoint(
                int(cover_arrow_x - bottom_cover_arrow_half_width),
                int(slab_bottom + 5),
            ),
            QPoint(
                int(cover_arrow_x + bottom_cover_arrow_half_width),
                int(slab_bottom + 5),
            ),
        ])
        painter.drawText(
            int(cover_x - 4),
            int((bottom_y + slab_bottom) / 2 - 6),
            52,
            12,
            Qt.AlignRight | Qt.AlignVCenter,
            f"{cover_bottom:g} mm",
        )

        # Short extension strokes beyond the four cover arrowheads.
        painter.setPen(QPen(cover_color, 1))

        # Above the upper top-cover arrow.
        painter.drawLine(
            int(cover_arrow_x), int(top - 5),
            int(cover_arrow_x), int(top - 10),
        )

        # Below the lower top-cover arrow.
        painter.drawLine(
            int(cover_arrow_x), int(top_y + 6),
            int(cover_arrow_x), int(top_y + 11),
        )

        # Above the upper bottom-cover arrow.
        painter.drawLine(
            int(cover_arrow_x), int(bottom_y - 5),
            int(cover_arrow_x), int(bottom_y - 10),
        )

        # Below the lower bottom-cover arrow.
        painter.drawLine(
            int(cover_arrow_x), int(slab_bottom + 5),
            int(cover_arrow_x), int(slab_bottom + 11),
        )

        # Effective-depth dimensions at the right end
        depth_x1 = slab_right + 28
        depth_x2 = slab_right + 70

        painter.setPen(QPen(QColor("#709900"), 1))
        painter.setFont(QFont("Arial", 8))

        # Bottom transverse effective depth.
        painter.drawLine(
            int(slab_right), int(top),
            int(depth_x1), int(top),
        )
        painter.drawLine(
            int(slab_right), int(bottom_y),
            int(depth_x1), int(bottom_y),
        )

        # Bottom transverse effective depth: vertical dimension line
        painter.drawLine(
            int(depth_x1), int(top),
            int(depth_x1), int(bottom_y),
        )
        # Bottom transverse effective depth: filled arrowheads pointing outward.
        painter.setBrush(QColor("#709900"))
        self._draw_vertical_dimension_arrows(
            painter, depth_x1, top, bottom_y
        )
        # Top transverse effective depth: horizontal extension lines begin at slab edge
        painter.drawLine(
            int(slab_right), int(top_y),
            int(depth_x2), int(top_y),
        )
        painter.drawLine(
            int(slab_right), int(slab_bottom),
            int(depth_x2), int(slab_bottom),
        )

        # Top transverse effective depth: vertical dimension line
        painter.drawLine(
            int(depth_x2), int(top_y),
            int(depth_x2), int(slab_bottom),
        )
        # Top transverse effective depth: filled arrowheads pointing outward.
        painter.setBrush(QColor("#709900"))
        self._draw_vertical_dimension_arrows(
            painter, depth_x2, top_y, slab_bottom
        )
        # Effective-depth values below their dimension lines
        painter.setFont(QFont("Arial", 7))

        painter.drawText(
            int(depth_x1 - 30),
            int(top - 14),
            60,
            14,
            Qt.AlignHCenter | Qt.AlignVCenter,
            f"{d_bottom:g} mm",
        )

        painter.drawText(
            int(depth_x2 - 30),
            int(slab_bottom + 6),
            60,
            14,
            Qt.AlignHCenter | Qt.AlignVCenter,
            f"{d_top:g} mm",
        )
        if overhang_mm > 0:
            dimension_y = slab_bottom + 63

            painter.setPen(QPen(QColor("#709900"), 1))

            # Left extension line: deck bottom-left corner to dimension line.
            painter.drawLine(
                int(left),
                int(slab_bottom),
                int(left),
                int(dimension_y),
            )

            # Right extension line: deck bottom at the girder centre.
            painter.drawLine(
                int(support_x),
                int(slab_bottom + 37),
                int(support_x),
                int(dimension_y),
            )

            # Horizontal overhang dimension.
            self._dimension(
                painter,
                left,
                dimension_y,
                support_x,
                dimension_y,
                f"{overhang_mm:g} mm",
            )

        # Draw permanent reinforcement callout lines and labels.
        label_offsets = {
            "T1": 35,
            "T2": 55,
            "T3": 35,
            "B1": 35,
            "B2": 35,
        }

        for name, (px, py) in pointer_points.items():
            is_top = name in ("T1", "T2", "T3")

            # Keep reinforcement dots fixed; adjust callout lines only.
            pointer_x = px
            if is_top:
                outside_y = int(top - label_offsets[name])
            elif name == "B2":
                outside_y = int(slab_bottom + 25)
            else:
                outside_y = int(
                    slab_bottom + label_offsets[name]
                )

            pointer_color = QColor("#777777")
            painter.setPen(
                QPen(pointer_color, 1, Qt.DashLine)
            )
            painter.setBrush(pointer_color)

            line_start_y = (
                int(top_y) if is_top else int(bottom_y)
            )

            # Draw the dashed callout line.
            painter.drawLine(
                pointer_x,
                line_start_y,
                pointer_x,
                outside_y,
            )

            # Draw the callout anchor circle.
            painter.drawEllipse(
                pointer_x - 3,
                outside_y - 3,
                6,
                6,
            )

            label_pos = QPoint(pointer_x, outside_y)

            if name in ("T1"):
                label_pos = QPoint(pointer_x + 40, outside_y + 4)
            elif name == "T2":
                label_pos = QPoint(pointer_x, outside_y + 4)
            elif name == "T3":
                label_pos = QPoint(pointer_x + 20, outside_y + 4)
            elif name == "B2":
                label_pos = QPoint(pointer_x + 21 , outside_y - 10)
            elif name == "B1":
                label_pos = QPoint(pointer_x, outside_y - 10)
            else:
                label_pos = QPoint(pointer_x, outside_y)

            # Draw reinforcement details permanently.
            self._draw_reinforcement_label(
                painter,
                name,
                label_pos,
            )



class DeckReinforcementCADCard(QFrame):
    """Card that owns the deck reinforcement CAD preview and its styling."""

    CARD_HEIGHT = 260

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("deckReinforcementCADCard")
        self.setStyleSheet(
            "QFrame#deckReinforcementCADCard {"
            "  background-color: white;"
            "  border: 1px solid #b0b0b0;"
            "  border-radius: 6px;"
            "}"
        )

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )
        self.setFixedHeight(self.CARD_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self.cad_widget = DeckReinforcementCADWidget(self)
        self.cad_widget.setMinimumSize(300, 240)
        self.cad_widget.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        layout.addWidget(self.cad_widget)

    def set_data(self, data: dict) -> None:
        """Pass deck design results to the CAD drawing widget."""
        self.cad_widget.set_data(data)

class DeckDesign(QDialog):
    """
    Deck Design dialog — schema-driven dialog that displays deck properties, 
    reinforcement details, utilization ratios, and design check results.
    """

    _REBAR_ROW_HEIGHT  = 50
    _REBAR_HEADER_HEIGHT = 48

    def __init__(self, parent=None):
        super().__init__(None)
        self._main_window = parent
        self.setObjectName("DeckDesign")
        self.resize(1024, 720)
        self.setMinimumSize(900, 520)
        self.schema = DECK_DESIGN_SUMMARY_SCHEMA
        self.init_ui()

        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border: 1px solid #90AF13;
            }
        """)

    def setupWrapper(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.Window
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)

        self.title_bar = CustomTitleBar()
        self.title_bar.setTitle("Deck Design")
        main_layout.addWidget(self.title_bar)

        self.content_widget = QWidget(self)
        main_layout.addWidget(self.content_widget, 1)

        size_grip = QSizeGrip(self)
        size_grip.setFixedSize(16, 16)

        overlay = QHBoxLayout()
        overlay.setContentsMargins(0, 0, 4, 4)
        overlay.addStretch(1)
        overlay.addWidget(size_grip, 0, Qt.AlignBottom | Qt.AlignRight)
        main_layout.addLayout(overlay)

    def init_ui(self):
        self.setupWrapper()

        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)

        scroll_area = StyledScrollArea()

        container = QWidget()
        container.setStyleSheet("background-color: white;")

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.setSpacing(8)

        self.reinforcement_cad_card = DeckReinforcementCADCard(container)

        # Deck Properties and CAD preview share the top row.
        props_row = QHBoxLayout()
        props_row.setContentsMargins(0, 0, 0, 0)
        props_row.setSpacing(12)

        properties_card = self._build_properties_section()
        properties_card.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )
        properties_card.setFixedHeight(260)

        props_row.addWidget(properties_card, 2, Qt.AlignTop)
        props_row.addWidget(self.reinforcement_cad_card, 3, Qt.AlignTop)
        container_layout.addLayout(props_row)

        container_layout.addWidget(self._build_reinforcement_section())
        container_layout.addWidget(self._build_utilization_section())
        container_layout.addWidget(self._build_design_check_section())
        container_layout.addStretch()

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        backend = getattr(self._main_window, "backend", None)
        if backend is not None and getattr(backend, "grillage_geometry", None) is not None:
            try:
                result = backend.output_dict.get("deck_design_results")
                self.load_data(result)
            except Exception:
                self.design_check_text.setHtml(
                    "<p style='color:#c0392b;font-size:11px;padding:12px;'>"
                    "Deck design could not be computed. Check inputs and try again."
                    "</p>"
                )
        else:
            self.design_check_text.setHtml(
                "<p style='color:#888888;font-size:11px;padding:16px;'>"
                "Click <b>Design</b> in the Input panel to run the analysis, "
                "then re-open this dialog to see deck design results."
                "</p>"
            )

    def _create_card_frame(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("girderCard")
        frame.setStyleSheet(
            "QFrame#girderCard {"
            "  background-color: white;"
            "  border: 1px solid #b0b0b0;"
            "  border-radius: 6px;"
            "}"
        )
        return frame

    def _create_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            "font-size: 13px; color: #2B2B2B; font-weight: bold;"
            " background: transparent; border: none;"
        )
        label.setAutoFillBackground(False)
        return label

    def _create_small_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setTextFormat(Qt.RichText)
        label.setStyleSheet(
            "font-size: 11px; color: #333333;"
            " background: transparent; border: none;"
        )
        label.setAutoFillBackground(False)
        return label

    def _readonly_field(self) -> QLineEdit:
        field = QLineEdit()
        field.setReadOnly(True)
        field.setMinimumWidth(80)
        field.setMinimumHeight(28)
        field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        apply_field_style(field)
        return field

    def _make_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        grid.setColumnMinimumWidth(0, 230)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        return grid

    def _add_row(self, grid, row, text, widget):
        grid.addWidget(
            self._create_small_label(text), row, 0,
            Qt.AlignLeft | Qt.AlignVCenter,
        )
        grid.addWidget(widget, row, 1)
        return row + 1

    def _build_properties_section(self) -> QFrame:
        prop_schema = self.schema.get("properties_card", {})
        card = self._create_card_frame()

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 12, 18, 12)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignTop)

        card_layout.addWidget(
            self._create_label(
                prop_schema.get("title", "Deck Properties:")
            ),
            alignment=Qt.AlignTop,
        )

        grid = self._make_grid()
        self._prop_fields = {}

        row = 0
        for field_def in prop_schema.get("fields", []):
            field = self._readonly_field()
            data_key = field_def.get("data_key")

            if data_key:
                self._prop_fields[data_key] = field

            row = self._add_row(
                grid,
                row,
                field_def.get("label", ""),
                field,
            )

        card_layout.addLayout(grid)
        card_layout.addStretch(1)

        return card

    def _build_reinforcement_section(self) -> QFrame:
        reinf_schema = self.schema.get("reinforcement_table", {})
        card = self._create_card_frame()
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)
        card_layout.addWidget(self._create_label(reinf_schema.get("title", "Reinforcement Details:")))

        rows_def = reinf_schema.get("rows", [])
        headers = reinf_schema.get("columns", [])
        num_rows = len(rows_def)
        num_cols = len(headers)

        overhang_row = next(
            (row for row, definition in enumerate(rows_def)
             if definition.get("is_overhang")),
            None,
        )
        self.rebar_table = NoScrollTable()
        self.rebar_table.setRowCount(num_rows)
        self.rebar_table.setColumnCount(num_cols)
        self.rebar_table.setHorizontalHeaderLabels(headers)

        for row, row_def in enumerate(rows_def):
            row_labels = (
                row_def.get("direction", ""),
                row_def.get("zone", ""),
                row_def.get("face", ""),
            )
            for col, label in enumerate(row_labels):
                item = QTableWidgetItem(label)
                item.setFlags(Qt.ItemIsEnabled)
                item.setTextAlignment(Qt.AlignCenter)
                self.rebar_table.setItem(row, col, item)

            for col in range(3, num_cols):
                cell = QTableWidgetItem("")
                cell.setFlags(Qt.ItemIsEnabled)
                cell.setTextAlignment(Qt.AlignCenter)
                self.rebar_table.setItem(row, col, cell)

        if overhang_row is not None:
            self.rebar_table.setRowHidden(overhang_row, True)

        h_header = self.rebar_table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.Stretch)
        h_header.setSectionResizeMode(num_cols - 1, QHeaderView.Fixed)
        h_header.resizeSection(num_cols - 1, 135)
        h_header.setDefaultAlignment(Qt.AlignCenter)

        v_header = self.rebar_table.verticalHeader()
        v_header.setVisible(False)
        v_header.setDefaultSectionSize(self._REBAR_ROW_HEIGHT)
        v_header.setSectionResizeMode(QHeaderView.Stretch)

        self.rebar_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rebar_table.setSelectionMode(QTableWidget.NoSelection)
        self.rebar_table.setFocusPolicy(Qt.NoFocus)
        self.rebar_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.rebar_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.rebar_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.rebar_table.setAlternatingRowColors(True)

        visible_rows = sum(
            not row.get("is_overhang", False) for row in rows_def
        )
        self.rebar_table.setFixedHeight(
            self._REBAR_HEADER_HEIGHT + visible_rows * self._REBAR_ROW_HEIGHT + 2
        )

        self.rebar_table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f9f9f9;
                gridline-color: #e0e0e0;
                border: 1px solid #e0e0e0;
                color: #333333;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e0e0e0;
                color: #333333;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #333333;
                padding: 8px;
                border: 1px solid #e0e0e0;
                font-weight: bold;
                font-size: 11px;
            }
        """)

        reinforcement_row = QHBoxLayout()
        reinforcement_row.setContentsMargins(0, 0, 0, 0)
        reinforcement_row.setSpacing(12)

        table_column = QVBoxLayout()
        table_column.setContentsMargins(0, 0, 0, 0)
        table_column.addWidget(self.rebar_table)

        self._overhang_note = QLabel(reinf_schema.get("overhang_note", ""))
        self._overhang_note.setStyleSheet(
            "font-size: 10px; color: #666666; background: transparent; border: none;"
        )
        self._overhang_note.setVisible(False)
        table_column.addWidget(self._overhang_note)

        table_container = QWidget()
        table_container.setLayout(table_column)
        reinforcement_row.addWidget(table_container, 1)
        card_layout.addLayout(reinforcement_row)
        return card

    def _build_utilization_section(self) -> QFrame:
        util_schema = self.schema.get("utilization_card", {})
        card = self._create_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)
        card_layout.addWidget(self._create_label(util_schema.get("title", "Utilization Summary:")))

        self._ur_widgets: dict = {}

        for check_def in util_schema.get("checks", []):
            key = check_def.get("key")
            label = check_def.get("label", "")
            is_overhang = check_def.get("is_overhang", False)
            
            bar = PercentBarWidget(label=label, value=0.0, parent=self)
            
            card_layout.addWidget(bar)
            bar.setVisible(not is_overhang)

            self._ur_widgets[key] = {
                "bar":   bar,
                "is_overhang": is_overhang,
            }

        return card

    def _build_design_check_section(self) -> QFrame:
        dc_schema = self.schema.get("design_check_card", {})
        card = self._create_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)
        card_layout.addWidget(self._create_label(dc_schema.get("title", "Design Check:")))

        self.design_check_text = QTextEdit()
        self.design_check_text.setReadOnly(True)
        self.design_check_text.setMinimumHeight(200)
        self.design_check_text.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding,
        )
        self.design_check_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: none;
                font-size: 11px;
                color: #333333;
            }
        """)
        card_layout.addWidget(self.design_check_text)
        return card

    @staticmethod
    def _text_to_html(text: str) -> str:
        lines = []
        for line in text.split("\n"):
            esc = (line
                   .replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;"))
            esc = esc.replace(
                "PASS",
                '<span style="color:#1a7a4a;font-weight:bold">PASS</span>',
            )
            esc = esc.replace(
                "FAIL",
                '<span style="color:#8b0000;font-weight:bold">FAIL</span>',
            )
            esc = esc.replace("&lt;sub&gt;", "<sub>")
            esc = esc.replace("&lt;/sub&gt;", "</sub>")
            
            lines.append(esc)
        return (
            "<pre style='font-family:monospace;font-size:11px;"
            "color:#333333;line-height:1.55;margin:0;'>"
            + "<br>".join(lines)
            + "</pre>"
        )

    def load_data(self, output_dict: dict) -> None:
        if not output_dict:
            return

        # ── Properties ───────────────────────────────────────────────────────
        prop_schema = self.schema.get("properties_card", {})
        for field_def in prop_schema.get("fields", []):
            data_key = field_def.get("data_key")
            if data_key and data_key in self._prop_fields:
                self._prop_fields[data_key].setText(str(output_dict.get(data_key, "")))

        # ── Reinforcement table ───────────────────────────────────────────────
        self.reinforcement_cad_card.set_data(output_dict)

        reinf_schema = self.schema.get("reinforcement_table", {})
        rows_def = reinf_schema.get("rows", [])
        cover_face = {"Bottom": " (bottom)", "Top": " (top)"}
        depth_face = {"Bottom": " (top)", "Top": " (bottom)"}
        has_overhang = False

        for row, row_def in enumerate(rows_def):
            is_overhang = row_def.get("is_overhang", False)

            field_keys = DeckReinforcementCADWidget._schema_key_map(
                row_def
            )

            if is_overhang:
                bar_data_key = field_keys.get("bar")
                has_overhang = (
                    bool(output_dict.get(bar_data_key, ""))
                    if bar_data_key
                    else False
                )

                self.rebar_table.setRowHidden(
                    row, not has_overhang
                )

                if not has_overhang:
                    continue

            for col, (field_role, data_key) in enumerate(
                field_keys.items(), start=3
            ):
                value = output_dict.get(data_key, "")

                if value and field_role == "cover":
                    value = (
                        f"{value}"
                        f"{cover_face.get(row_def.get('face', ''), '')}"
                    )
                elif value and field_role == "depth":
                    value = (
                        f"{value}"
                        f"{depth_face.get(row_def.get('face', ''), '')}"
                    )

                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled)
                item.setTextAlignment(Qt.AlignCenter)
                self.rebar_table.setItem(row, col, item)

        n_visible = sum(
            not row.get("is_overhang", False) for row in rows_def
        ) + int(has_overhang)
        self.rebar_table.setFixedHeight(
            self._REBAR_HEADER_HEIGHT + n_visible * self._REBAR_ROW_HEIGHT + 2
        )
        self._overhang_note.setVisible(has_overhang)
        # Update utilization bars.
        for key, widgets in self._ur_widgets.items():
            if widgets["is_overhang"]:
                widgets["bar"].setVisible(has_overhang)

            raw = output_dict.get(key)
            if raw is None:
                widgets["bar"].set_value(0.0)
            else:
                widgets["bar"].set_value(float(raw) * 100.0)

        # Update design-check text.
        dc_schema = self.schema.get("design_check_card", {})
        dc_key = dc_schema.get("data_key", "deck_design_check")
        raw_text = str(output_dict.get(dc_key, ""))

        if raw_text:
            self.design_check_text.setHtml(self._text_to_html(raw_text))
        else:
            self.design_check_text.clear()
