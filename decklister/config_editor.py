"""
Config Editor for DeckLister.

A visual editor for creating and editing deck image config files.
Allows drawing, moving, and resizing card areas on a background,
managing layers (including text and csv_field), and previewing the final output.
"""
import json
import os
import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QGroupBox, QSpinBox,
    QCheckBox, QComboBox, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsPixmapItem, QListWidget, QListWidgetItem, QSplitter,
    QToolBar, QStatusBar, QColorDialog, QFormLayout, QScrollArea,
    QSizePolicy, QAbstractItemView, QMessageBox, QDialog, QDialogButtonBox,
    QFontDialog, QDoubleSpinBox, QTabWidget,
)
from PySide6.QtCore import Qt, QRectF, Signal, QPointF
from PySide6.QtGui import (
    QPixmap, QColor, QPen, QBrush, QAction, QImage, QPainter, QFont,
)

try:
    from .config import Config
    from .deck import Deck
    from .deck_image_generator import DeckImageGenerator
except ImportError:
    from decklister.config import Config
    from decklister.deck import Deck
    from decklister.deck_image_generator import DeckImageGenerator


# ── Area colors (semi-transparent) ──────────────────────────────────────
AREA_COLORS = {
    "leader_area":  QColor(220, 60, 60, 80),
    "base_area":    QColor(60, 100, 220, 80),
    "deck_area":    QColor(60, 180, 60, 80),
    "sb_area":      QColor(220, 180, 40, 80),
    "misc_area":    QColor(180, 80, 220, 80),
}
AREA_BORDER_COLORS = {
    "leader_area":  QColor(220, 60, 60, 200),
    "base_area":    QColor(60, 100, 220, 200),
    "deck_area":    QColor(60, 180, 60, 200),
    "sb_area":      QColor(220, 180, 40, 200),
    "misc_area":    QColor(180, 80, 220, 200),
}
AREA_LABELS = {
    "leader_area":  "Leader",
    "base_area":    "Base",
    "deck_area":    "Deck",
    "sb_area":      "Sideboard",
    "misc_area":    "Misc",
}

FONT_FILTER = "Font Files (*.ttf *.otf *.TTF *.OTF);;All Files (*)"


# ── Resizable/draggable rectangle ───────────────────────────────────────
class ResizableRect(QGraphicsRectItem):
    """A rectangle that can be moved and resized by dragging edges/corners."""

    HANDLE_SIZE = 8

    def __init__(self, x, y, w, h, area_type, label="", parent_editor=None):
        super().__init__(x, y, w, h)
        self.area_type = area_type
        self.label = label
        self.parent_editor = parent_editor
        self._resizing = None
        self._drag_start = None

        fill = AREA_COLORS.get(area_type, QColor(128, 128, 128, 80))
        border = AREA_BORDER_COLORS.get(area_type, QColor(128, 128, 128, 200))
        self.setBrush(QBrush(fill))
        self.setPen(QPen(border, 2))
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    def get_coords(self):
        """Return [x0, y0, x1, y1] in scene coordinates."""
        r = self.rect()
        pos = self.pos()
        return [
            int(pos.x() + r.x()),
            int(pos.y() + r.y()),
            int(pos.x() + r.x() + r.width()),
            int(pos.y() + r.y() + r.height()),
        ]

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        r = self.rect()
        painter.setPen(QPen(Qt.white))
        font = QFont("Arial", 10, QFont.Bold)
        painter.setFont(font)
        display = self.label or AREA_LABELS.get(self.area_type, self.area_type)
        painter.drawText(r, Qt.AlignCenter, display)

    def _edge_at(self, pos):
        r = self.rect()
        hs = self.HANDLE_SIZE
        left = abs(pos.x() - r.left()) < hs
        right = abs(pos.x() - r.right()) < hs
        top = abs(pos.y() - r.top()) < hs
        bottom = abs(pos.y() - r.bottom()) < hs
        if top and left: return "tl"
        if top and right: return "tr"
        if bottom and left: return "bl"
        if bottom and right: return "br"
        if left: return "l"
        if right: return "r"
        if top: return "t"
        if bottom: return "b"
        return None

    def hoverMoveEvent(self, event):
        edge = self._edge_at(event.pos())
        cursors = {
            "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
            "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
            "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
            "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
        }
        self.setCursor(cursors.get(edge, Qt.SizeAllCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edge = self._edge_at(event.pos())
            if edge:
                self._resizing = edge
                self._drag_start = event.pos()
            else:
                self._resizing = None
                self._drag_start = event.scenePos() - self.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            r = self.rect()
            pos = event.pos()
            new_rect = QRectF(r)
            if "l" in self._resizing: new_rect.setLeft(pos.x())
            if "r" in self._resizing: new_rect.setRight(pos.x())
            if "t" in self._resizing: new_rect.setTop(pos.y())
            if "b" in self._resizing: new_rect.setBottom(pos.y())
            if new_rect.width() >= 20 and new_rect.height() >= 20:
                self.setRect(new_rect.normalized())
        elif self._drag_start is not None:
            self.setPos(event.scenePos() - self._drag_start)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._resizing = None
        self._drag_start = None
        if self.parent_editor:
            self.parent_editor._on_area_changed()
        event.accept()


# ── Text layer dialog ───────────────────────────────────────────────────
class TextLayerDialog(QDialog):
    """Dialog for editing a text or csv_field layer."""

    def __init__(self, parent=None, layer_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Text Layer")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Layer type
        self._type_combo = QComboBox()
        self._type_combo.addItems(["text", "csv_field"])
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        form.addRow("Type:", self._type_combo)

        # Text content (for type=text)
        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("Text to display")
        form.addRow("Text:", self._text_input)

        # Column name (for type=csv_field)
        self._column_input = QLineEdit()
        self._column_input.setPlaceholderText("e.g., DeckName, OwnerDisplayName")
        form.addRow("CSV Column:", self._column_input)

        # Font
        self._font_path = None
        font_row = QHBoxLayout()
        self._font_label = QLineEdit()
        self._font_label.setReadOnly(True)
        self._font_label.setPlaceholderText("System default")
        font_row.addWidget(self._font_label)
        font_browse = QPushButton("Browse")
        font_browse.clicked.connect(self._browse_font)
        font_row.addWidget(font_browse)
        font_clear = QPushButton("Clear")
        font_clear.clicked.connect(self._clear_font)
        font_row.addWidget(font_clear)
        form.addRow("Font:", font_row)

        # Size
        self._size_spin = QSpinBox()
        self._size_spin.setRange(6, 500)
        self._size_spin.setValue(48)
        form.addRow("Size:", self._size_spin)

        # Color
        self._color = [255, 255, 255, 255]
        self._color_btn = QPushButton("Pick Color")
        self._color_btn.clicked.connect(self._pick_color)
        self._color_preview = QLabel()
        self._update_color_preview()
        color_row = QHBoxLayout()
        color_row.addWidget(self._color_btn)
        color_row.addWidget(self._color_preview)
        form.addRow("Color:", color_row)

        # Alignment
        self._align_combo = QComboBox()
        self._align_combo.addItems(["left", "center", "right"])
        form.addRow("Align:", self._align_combo)

        # Position: area or point
        self._pos_mode_combo = QComboBox()
        self._pos_mode_combo.addItems(["area", "position"])
        self._pos_mode_combo.currentTextChanged.connect(self._on_pos_mode_changed)
        form.addRow("Placement:", self._pos_mode_combo)

        # Area coordinates
        area_row = QHBoxLayout()
        self._area_x0 = QSpinBox(); self._area_x0.setRange(0, 9999)
        self._area_y0 = QSpinBox(); self._area_y0.setRange(0, 9999)
        self._area_x1 = QSpinBox(); self._area_x1.setRange(0, 9999); self._area_x1.setValue(500)
        self._area_y1 = QSpinBox(); self._area_y1.setRange(0, 9999); self._area_y1.setValue(100)
        for lbl, spin in [("X0:", self._area_x0), ("Y0:", self._area_y0),
                          ("X1:", self._area_x1), ("Y1:", self._area_y1)]:
            area_row.addWidget(QLabel(lbl))
            area_row.addWidget(spin)
        self._area_widget = QWidget()
        self._area_widget.setLayout(area_row)
        form.addRow("Area:", self._area_widget)

        # Point position
        pos_row = QHBoxLayout()
        self._pos_x = QSpinBox(); self._pos_x.setRange(0, 9999)
        self._pos_y = QSpinBox(); self._pos_y.setRange(0, 9999)
        pos_row.addWidget(QLabel("X:"))
        pos_row.addWidget(self._pos_x)
        pos_row.addWidget(QLabel("Y:"))
        pos_row.addWidget(self._pos_y)
        self._pos_widget = QWidget()
        self._pos_widget.setLayout(pos_row)
        form.addRow("Position:", self._pos_widget)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Initialize visibility
        self._on_type_changed(self._type_combo.currentText())
        self._on_pos_mode_changed(self._pos_mode_combo.currentText())

        # Load existing data
        if layer_data:
            self._load_data(layer_data)

    def _on_type_changed(self, text):
        self._text_input.setVisible(text == "text")
        self._column_input.setVisible(text == "csv_field")

    def _on_pos_mode_changed(self, text):
        self._area_widget.setVisible(text == "area")
        self._pos_widget.setVisible(text == "position")

    def _browse_font(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Font", "", FONT_FILTER)
        if path:
            self._font_path = path
            self._font_label.setText(os.path.basename(path))

    def _clear_font(self):
        self._font_path = None
        self._font_label.setText("")

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(*self._color[:3]), self)
        if color.isValid():
            self._color = [color.red(), color.green(), color.blue(), 255]
            self._update_color_preview()

    def _update_color_preview(self):
        r, g, b = self._color[:3]
        self._color_preview.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); min-width: 40px; min-height: 20px; border: 1px solid gray;"
        )
        self._color_preview.setText(f"  ({r}, {g}, {b})")

    def _load_data(self, data):
        layer_type = data.get("type", "text")
        self._type_combo.setCurrentText(layer_type)
        self._text_input.setText(data.get("text", ""))
        self._column_input.setText(data.get("column", ""))
        self._size_spin.setValue(data.get("size", 48))
        if data.get("color"):
            self._color = list(data["color"])
            if len(self._color) == 3:
                self._color.append(255)
            self._update_color_preview()
        self._align_combo.setCurrentText(data.get("align", "left"))
        if data.get("font"):
            self._font_path = data["font"]
            self._font_label.setText(os.path.basename(data["font"]))

        if data.get("area"):
            self._pos_mode_combo.setCurrentText("area")
            a = data["area"]
            self._area_x0.setValue(a[0])
            self._area_y0.setValue(a[1])
            self._area_x1.setValue(a[2])
            self._area_y1.setValue(a[3])
        elif data.get("position"):
            self._pos_mode_combo.setCurrentText("position")
            p = data["position"]
            self._pos_x.setValue(p[0])
            self._pos_y.setValue(p[1])

    def get_data(self):
        """Return the layer dict."""
        layer_type = self._type_combo.currentText()
        data = {
            "type": layer_type,
            "size": self._size_spin.value(),
            "color": self._color[:3],
            "align": self._align_combo.currentText(),
        }
        if layer_type == "text":
            data["text"] = self._text_input.text()
        else:
            data["column"] = self._column_input.text()

        if self._font_path:
            data["font"] = self._font_path

        if self._pos_mode_combo.currentText() == "area":
            data["area"] = [
                self._area_x0.value(), self._area_y0.value(),
                self._area_x1.value(), self._area_y1.value(),
            ]
        else:
            data["position"] = [self._pos_x.value(), self._pos_y.value()]

        return data


# ── Main editor window ──────────────────────────────────────────────────
class ConfigEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeckLister Config Editor")
        self.setMinimumSize(1200, 700)

        self._config_path = None
        self._deck_path = None
        self._bg_path = None
        self._fg_path = None
        self._count_bg_path = None
        self._count_font_path = None
        self._areas = []
        self._text_layers = []  # list of layer dicts (text/csv_field)
        self._resolution = (1920, 1080)

        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()
        self._update_canvas_size()

    # ── Toolbar ─────────────────────────────────────────────────────────
    def _setup_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        for label, slot in [
            ("New", self._new_config),
            ("Open", self._open_config),
            ("Save", self._save_config),
            ("Save As", self._save_config_as),
        ]:
            act = QAction(label, self)
            act.triggered.connect(slot)
            tb.addAction(act)

        tb.addSeparator()
        preview_act = QAction("Preview Deck", self)
        preview_act.triggered.connect(self._preview_deck)
        tb.addAction(preview_act)

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready")

    # ── Main UI ─────────────────────────────────────────────────────────
    def _setup_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        # Left: Canvas
        canvas_widget = QWidget()
        canvas_layout = QVBoxLayout(canvas_widget)
        canvas_layout.setContentsMargins(0, 0, 0, 0)

        self._scene = QGraphicsScene()
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setDragMode(QGraphicsView.NoDrag)
        self._view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        canvas_layout.addWidget(self._view)

        self._bg_item = None
        self._fg_item = None
        self._preview_item = None

        splitter.addWidget(canvas_widget)

        # Right: Tabbed properties panel
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(340)
        scroll.setMaximumWidth(480)

        props = QWidget()
        props_layout = QVBoxLayout(props)
        props_layout.setAlignment(Qt.AlignTop)

        tabs = QTabWidget()

        # ── Tab 1: Layout ───────────────────────────────────────────────
        layout_tab = QWidget()
        layout_layout = QVBoxLayout(layout_tab)
        layout_layout.setAlignment(Qt.AlignTop)

        # Resolution
        res_group = QGroupBox("Resolution")
        res_layout = QVBoxLayout(res_group)
        res_form = QFormLayout()
        self._width_spin = QSpinBox()
        self._width_spin.setRange(100, 7680)
        self._width_spin.setValue(1920)
        self._width_spin.valueChanged.connect(self._on_resolution_changed)
        res_form.addRow("Width:", self._width_spin)
        self._height_spin = QSpinBox()
        self._height_spin.setRange(100, 4320)
        self._height_spin.setValue(1080)
        self._height_spin.valueChanged.connect(self._on_resolution_changed)
        res_form.addRow("Height:", self._height_spin)
        res_layout.addLayout(res_form)

        res_from_bg_btn = QPushButton("Set from Background Image")
        res_from_bg_btn.setToolTip("Set resolution to match the background image dimensions")
        res_from_bg_btn.clicked.connect(self._resolution_from_background)
        res_layout.addWidget(res_from_bg_btn)
        layout_layout.addWidget(res_group)

        # Background
        bg_group = QGroupBox("Background")
        bg_layout = QVBoxLayout(bg_group)
        bg_row = QHBoxLayout()
        self._bg_input = QLineEdit()
        self._bg_input.setPlaceholderText("Image path or leave empty for solid color")
        self._bg_input.setReadOnly(True)
        bg_row.addWidget(self._bg_input)
        bg_browse = QPushButton("Browse")
        bg_browse.clicked.connect(self._browse_background)
        bg_row.addWidget(bg_browse)
        bg_clear = QPushButton("Clear")
        bg_clear.clicked.connect(self._clear_background)
        bg_row.addWidget(bg_clear)
        bg_layout.addLayout(bg_row)

        bg_color_row = QHBoxLayout()
        bg_color_row.addWidget(QLabel("Or solid color:"))
        self._bg_color_btn = QPushButton("Pick Color")
        self._bg_color_btn.clicked.connect(self._pick_bg_color)
        bg_color_row.addWidget(self._bg_color_btn)
        self._bg_color_label = QLabel("(30, 30, 30)")
        bg_color_row.addWidget(self._bg_color_label)
        bg_layout.addLayout(bg_color_row)
        self._bg_color = None
        layout_layout.addWidget(bg_group)

        # Foreground
        fg_group = QGroupBox("Foreground")
        fg_row = QHBoxLayout(fg_group)
        self._fg_input = QLineEdit()
        self._fg_input.setPlaceholderText("Foreground overlay image (RGBA)")
        self._fg_input.setReadOnly(True)
        fg_row.addWidget(self._fg_input)
        fg_browse = QPushButton("Browse")
        fg_browse.clicked.connect(self._browse_foreground)
        fg_row.addWidget(fg_browse)
        fg_clear = QPushButton("Clear")
        fg_clear.clicked.connect(self._clear_foreground)
        fg_row.addWidget(fg_clear)
        layout_layout.addWidget(fg_group)

        # Areas
        area_group = QGroupBox("Areas")
        area_layout = QVBoxLayout(area_group)

        add_area_row = QHBoxLayout()
        self._area_type_combo = QComboBox()
        self._area_type_combo.addItems(["leader_area", "base_area", "deck_area", "sb_area", "misc_area"])
        add_area_row.addWidget(self._area_type_combo)
        add_btn = QPushButton("Add Area")
        add_btn.clicked.connect(self._add_area)
        add_area_row.addWidget(add_btn)
        area_layout.addLayout(add_area_row)

        self._area_list = QListWidget()
        self._area_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._area_list.currentRowChanged.connect(self._on_area_selected)
        area_layout.addWidget(self._area_list)

        del_area_btn = QPushButton("Delete Selected Area")
        del_area_btn.clicked.connect(self._delete_area)
        area_layout.addWidget(del_area_btn)

        coord_group = QGroupBox("Selected Area Coordinates")
        coord_form = QFormLayout(coord_group)
        self._coord_x0 = QSpinBox(); self._coord_x0.setRange(0, 9999)
        self._coord_y0 = QSpinBox(); self._coord_y0.setRange(0, 9999)
        self._coord_x1 = QSpinBox(); self._coord_x1.setRange(0, 9999)
        self._coord_y1 = QSpinBox(); self._coord_y1.setRange(0, 9999)
        for spin in (self._coord_x0, self._coord_y0, self._coord_x1, self._coord_y1):
            spin.valueChanged.connect(self._on_coord_spin_changed)
        coord_form.addRow("X0:", self._coord_x0)
        coord_form.addRow("Y0:", self._coord_y0)
        coord_form.addRow("X1:", self._coord_x1)
        coord_form.addRow("Y1:", self._coord_y1)
        area_layout.addWidget(coord_group)
        layout_layout.addWidget(area_group)

        layout_layout.addStretch()
        tabs.addTab(layout_tab, "Layout")

        # ── Tab 2: Cards & Text ─────────────────────────────────────────
        cards_tab = QWidget()
        cards_layout = QVBoxLayout(cards_tab)
        cards_layout.setAlignment(Qt.AlignTop)

        # Card settings
        card_group = QGroupBox("Card Settings")
        card_form = QFormLayout(card_group)
        self._padding_spin = QSpinBox()
        self._padding_spin.setRange(0, 50)
        self._padding_spin.setValue(3)
        card_form.addRow("Padding:", self._padding_spin)
        self._uniform_check = QCheckBox("Uniform card size")
        self._uniform_check.setChecked(True)
        card_form.addRow(self._uniform_check)

        # Count background
        count_bg_row = QHBoxLayout()
        self._count_bg_input = QLineEdit()
        self._count_bg_input.setPlaceholderText("Count background image")
        self._count_bg_input.setReadOnly(True)
        count_bg_row.addWidget(self._count_bg_input)
        count_bg_browse = QPushButton("Browse")
        count_bg_browse.clicked.connect(self._browse_count_bg)
        count_bg_row.addWidget(count_bg_browse)
        count_bg_clear = QPushButton("Clear")
        count_bg_clear.clicked.connect(lambda: (setattr(self, '_count_bg_path', None), self._count_bg_input.setText("")))
        count_bg_row.addWidget(count_bg_clear)
        card_form.addRow("Count BG:", count_bg_row)

        # Count font
        count_font_row = QHBoxLayout()
        self._count_font_input = QLineEdit()
        self._count_font_input.setPlaceholderText("Font for card count overlay")
        self._count_font_input.setReadOnly(True)
        count_font_row.addWidget(self._count_font_input)
        count_font_browse = QPushButton("Browse")
        count_font_browse.clicked.connect(self._browse_count_font)
        count_font_row.addWidget(count_font_browse)
        count_font_clear = QPushButton("Clear")
        count_font_clear.clicked.connect(lambda: (setattr(self, '_count_font_path', None), self._count_font_input.setText("")))
        count_font_row.addWidget(count_font_clear)
        card_form.addRow("Count Font:", count_font_row)

        cards_layout.addWidget(card_group)

        # Text layers
        text_group = QGroupBox("Text Layers")
        text_layout = QVBoxLayout(text_group)

        text_btn_row = QHBoxLayout()
        add_text_btn = QPushButton("Add Text Layer")
        add_text_btn.clicked.connect(self._add_text_layer)
        text_btn_row.addWidget(add_text_btn)
        edit_text_btn = QPushButton("Edit")
        edit_text_btn.clicked.connect(self._edit_text_layer)
        text_btn_row.addWidget(edit_text_btn)
        del_text_btn = QPushButton("Delete")
        del_text_btn.clicked.connect(self._delete_text_layer)
        text_btn_row.addWidget(del_text_btn)
        text_layout.addLayout(text_btn_row)

        move_btn_row = QHBoxLayout()
        up_btn = QPushButton("Move Up")
        up_btn.clicked.connect(self._move_text_layer_up)
        move_btn_row.addWidget(up_btn)
        down_btn = QPushButton("Move Down")
        down_btn.clicked.connect(self._move_text_layer_down)
        move_btn_row.addWidget(down_btn)
        text_layout.addLayout(move_btn_row)

        self._text_list = QListWidget()
        self._text_list.setSelectionMode(QAbstractItemView.SingleSelection)
        text_layout.addWidget(self._text_list)
        cards_layout.addWidget(text_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QHBoxLayout(preview_group)
        self._deck_input = QLineEdit()
        self._deck_input.setPlaceholderText("Deck file for preview")
        preview_layout.addWidget(self._deck_input)
        deck_browse = QPushButton("Browse")
        deck_browse.clicked.connect(self._browse_deck)
        preview_layout.addWidget(deck_browse)
        cards_layout.addWidget(preview_group)

        cards_layout.addStretch()
        tabs.addTab(cards_tab, "Cards & Text")

        props_layout.addWidget(tabs)
        scroll.setWidget(props)
        splitter.addWidget(scroll)
        splitter.setSizes([800, 400])

    # ── Canvas management ───────────────────────────────────────────────
    def _update_canvas_size(self):
        w, h = self._resolution
        self._scene.setSceneRect(0, 0, w, h)
        self._draw_background()
        self._draw_foreground()

    def _draw_background(self):
        if self._bg_item:
            self._scene.removeItem(self._bg_item)
            self._bg_item = None
        w, h = self._resolution
        if self._bg_path and os.path.isfile(self._bg_path):
            pixmap = QPixmap(self._bg_path).scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        elif self._bg_color:
            img = QImage(w, h, QImage.Format_RGB32)
            img.fill(QColor(*self._bg_color))
            pixmap = QPixmap.fromImage(img)
        else:
            img = QImage(w, h, QImage.Format_RGB32)
            img.fill(QColor(30, 30, 30))
            pixmap = QPixmap.fromImage(img)
        self._bg_item = QGraphicsPixmapItem(pixmap)
        self._bg_item.setZValue(0)
        self._scene.addItem(self._bg_item)

    def _draw_foreground(self):
        if self._fg_item:
            self._scene.removeItem(self._fg_item)
            self._fg_item = None
        if self._fg_path and os.path.isfile(self._fg_path):
            w, h = self._resolution
            pixmap = QPixmap(self._fg_path).scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self._fg_item = QGraphicsPixmapItem(pixmap)
            self._fg_item.setZValue(50)
            self._scene.addItem(self._fg_item)

    def _clear_preview(self):
        if self._preview_item:
            self._scene.removeItem(self._preview_item)
            self._preview_item = None

    # ── Resolution ──────────────────────────────────────────────────────
    def _on_resolution_changed(self):
        self._resolution = (self._width_spin.value(), self._height_spin.value())
        self._update_canvas_size()

    def _resolution_from_background(self):
        """Set resolution to match the background image dimensions."""
        if not self._bg_path or not os.path.isfile(self._bg_path):
            self._statusbar.showMessage("No background image loaded.")
            return
        pixmap = QPixmap(self._bg_path)
        if pixmap.isNull():
            self._statusbar.showMessage("Could not read background image dimensions.")
            return
        self._width_spin.setValue(pixmap.width())
        self._height_spin.setValue(pixmap.height())
        self._statusbar.showMessage(f"Resolution set to {pixmap.width()}x{pixmap.height()} from background image.")

    # ── Background ──────────────────────────────────────────────────────
    def _browse_background(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )
        if path:
            self._bg_path = path
            self._bg_color = None
            self._bg_input.setText(path)
            self._bg_color_label.setText("(using image)")
            self._draw_background()

    def _clear_background(self):
        self._bg_path = None
        self._bg_input.setText("")
        self._bg_color_label.setText("(30, 30, 30)")
        self._draw_background()

    def _pick_bg_color(self):
        color = QColorDialog.getColor(QColor(30, 30, 30), self)
        if color.isValid():
            self._bg_color = (color.red(), color.green(), color.blue())
            self._bg_path = None
            self._bg_input.setText("")
            self._bg_color_label.setText(f"({color.red()}, {color.green()}, {color.blue()})")
            self._draw_background()

    # ── Foreground ──────────────────────────────────────────────────────
    def _browse_foreground(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Foreground Image", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )
        if path:
            self._fg_path = path
            self._fg_input.setText(path)
            self._draw_foreground()

    def _clear_foreground(self):
        self._fg_path = None
        self._fg_input.setText("")
        self._draw_foreground()

    # ── Count background / font ─────────────────────────────────────────
    def _browse_count_bg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Count Background", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )
        if path:
            self._count_bg_path = path
            self._count_bg_input.setText(path)

    def _browse_count_font(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Count Font", "", FONT_FILTER
        )
        if path:
            self._count_font_path = path
            self._count_font_input.setText(os.path.basename(path))

    # ── Areas ───────────────────────────────────────────────────────────
    def _add_area(self):
        area_type = self._area_type_combo.currentText()
        w, h = self._resolution
        rect = ResizableRect(0, 0, 200, 200, area_type, parent_editor=self)
        rect.setPos(w // 2 - 100, h // 2 - 100)
        self._scene.addItem(rect)
        self._areas.append(rect)
        self._refresh_area_list()

    def _delete_area(self):
        row = self._area_list.currentRow()
        if 0 <= row < len(self._areas):
            self._scene.removeItem(self._areas.pop(row))
            self._refresh_area_list()

    def _refresh_area_list(self):
        self._area_list.clear()
        for rect in self._areas:
            coords = rect.get_coords()
            label = AREA_LABELS.get(rect.area_type, rect.area_type)
            self._area_list.addItem(f"{label}: [{coords[0]}, {coords[1]}, {coords[2]}, {coords[3]}]")

    def _on_area_selected(self, row):
        for rect in self._areas:
            rect.setSelected(False)
        if 0 <= row < len(self._areas):
            self._areas[row].setSelected(True)
            coords = self._areas[row].get_coords()
            self._updating_coords = True
            self._coord_x0.setValue(coords[0])
            self._coord_y0.setValue(coords[1])
            self._coord_x1.setValue(coords[2])
            self._coord_y1.setValue(coords[3])
            self._updating_coords = False

    def _on_coord_spin_changed(self):
        if getattr(self, '_updating_coords', False):
            return
        row = self._area_list.currentRow()
        if 0 <= row < len(self._areas):
            rect = self._areas[row]
            x0 = self._coord_x0.value()
            y0 = self._coord_y0.value()
            x1 = self._coord_x1.value()
            y1 = self._coord_y1.value()
            rect.setPos(x0, y0)
            rect.setRect(0, 0, max(20, x1 - x0), max(20, y1 - y0))
            self._refresh_area_list()

    def _on_area_changed(self):
        self._refresh_area_list()
        row = self._area_list.currentRow()
        if 0 <= row < len(self._areas):
            coords = self._areas[row].get_coords()
            self._updating_coords = True
            self._coord_x0.setValue(coords[0])
            self._coord_y0.setValue(coords[1])
            self._coord_x1.setValue(coords[2])
            self._coord_y1.setValue(coords[3])
            self._updating_coords = False

    # ── Text layers ─────────────────────────────────────────────────────
    def _add_text_layer(self):
        dlg = TextLayerDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self._text_layers.append(data)
            self._refresh_text_list()

    def _edit_text_layer(self):
        row = self._text_list.currentRow()
        if 0 <= row < len(self._text_layers):
            dlg = TextLayerDialog(self, layer_data=self._text_layers[row])
            if dlg.exec() == QDialog.Accepted:
                self._text_layers[row] = dlg.get_data()
                self._refresh_text_list()

    def _delete_text_layer(self):
        row = self._text_list.currentRow()
        if 0 <= row < len(self._text_layers):
            self._text_layers.pop(row)
            self._refresh_text_list()

    def _move_text_layer_up(self):
        row = self._text_list.currentRow()
        if row > 0:
            self._text_layers[row], self._text_layers[row - 1] = self._text_layers[row - 1], self._text_layers[row]
            self._refresh_text_list()
            self._text_list.setCurrentRow(row - 1)

    def _move_text_layer_down(self):
        row = self._text_list.currentRow()
        if 0 <= row < len(self._text_layers) - 1:
            self._text_layers[row], self._text_layers[row + 1] = self._text_layers[row + 1], self._text_layers[row]
            self._refresh_text_list()
            self._text_list.setCurrentRow(row + 1)

    def _refresh_text_list(self):
        self._text_list.clear()
        for layer in self._text_layers:
            lt = layer.get("type", "text")
            if lt == "text":
                preview = layer.get("text", "")[:40]
                self._text_list.addItem(f"[text] \"{preview}\"")
            else:
                col = layer.get("column", "")
                self._text_list.addItem(f"[csv] {col}")

    # ── Deck preview ────────────────────────────────────────────────────
    def _browse_deck(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Deck File", "",
            "Deck Files (*.json *.csv);;All Files (*)"
        )
        if path:
            self._deck_input.setText(path)

    def _preview_deck(self):
        deck_path = self._deck_input.text().strip()
        if not deck_path:
            self._statusbar.showMessage("No deck file selected for preview.")
            return

        self._clear_preview()
        self._statusbar.showMessage("Generating preview...")
        QApplication.processEvents()

        try:
            config = self._build_config()
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                tmp_output = f.name
            try:
                generator = DeckImageGenerator(config=config)
                generator.run(deck_path, output_path=tmp_output)
                pixmap = QPixmap(tmp_output)
                if not pixmap.isNull():
                    self._preview_item = QGraphicsPixmapItem(pixmap)
                    self._preview_item.setZValue(5)
                    self._scene.addItem(self._preview_item)
                    self._statusbar.showMessage("Preview rendered.")
                else:
                    self._statusbar.showMessage("Preview failed.")
            finally:
                if os.path.exists(tmp_output):
                    os.unlink(tmp_output)
        except Exception as e:
            self._statusbar.showMessage(f"Preview error: {e}")

    # ── Config building ─────────────────────────────────────────────────
    def _build_config(self):
        leader_areas = []
        base_areas = []
        deck_area = None
        sb_area = None
        misc_area = None

        for rect in self._areas:
            coords = rect.get_coords()
            if rect.area_type == "leader_area":
                leader_areas.append(coords)
            elif rect.area_type == "base_area":
                base_areas.append(coords)
            elif rect.area_type == "deck_area":
                deck_area = coords
            elif rect.area_type == "sb_area":
                sb_area = coords
            elif rect.area_type == "misc_area":
                misc_area = coords

        layers = []
        if self._bg_path:
            layers.append({"type": "image", "path": self._bg_path})
        elif self._bg_color:
            layers.append({"type": "color", "color": list(self._bg_color)})
        layers.append({"type": "cards"})
        # Text layers go after cards but before foreground
        for tl in self._text_layers:
            layers.append(tl)
        if self._fg_path:
            layers.append({"type": "image", "path": self._fg_path})

        return Config(
            resolution=self._resolution,
            layers=layers,
            leader_areas=leader_areas,
            base_areas=base_areas,
            deck_area=deck_area,
            sb_area=sb_area,
            misc_area=misc_area,
            count_background=self._count_bg_path,
            count_font=self._count_font_path,
            padding=self._padding_spin.value(),
            uniform_card_size=self._uniform_check.isChecked(),
        )

    def _config_to_dict(self, config=None):
        if config is None:
            config = self._build_config()
        data = {
            "resolution": list(config.resolution),
            "padding": config.padding,
            "uniform_card_size": config.uniform_card_size,
        }
        if config.layers:
            data["layers"] = config.layers
        if config.leader_areas:
            data["leader_areas"] = config.leader_areas
        if config.base_areas:
            data["base_areas"] = config.base_areas
        if config.deck_area:
            data["deck_area"] = config.deck_area
        if config.sb_area:
            data["sb_area"] = config.sb_area
        if config.misc_area:
            data["misc_area"] = config.misc_area
        if config.count_background:
            data["count_background"] = config.count_background
        if config.count_font:
            data["count_font"] = config.count_font
        return data

    # ── File operations ─────────────────────────────────────────────────
    def _new_config(self):
        self._config_path = None
        self._bg_path = None
        self._fg_path = None
        self._count_bg_path = None
        self._count_font_path = None
        self._bg_color = None
        self._bg_input.setText("")
        self._fg_input.setText("")
        self._count_bg_input.setText("")
        self._count_font_input.setText("")
        self._bg_color_label.setText("(30, 30, 30)")
        self._width_spin.setValue(1920)
        self._height_spin.setValue(1080)
        self._padding_spin.setValue(3)
        self._uniform_check.setChecked(True)
        self._deck_input.setText("")

        for rect in self._areas:
            self._scene.removeItem(rect)
        self._areas.clear()
        self._text_layers.clear()
        self._refresh_area_list()
        self._refresh_text_list()
        self._clear_preview()
        self._update_canvas_size()
        self._statusbar.showMessage("New config created.")

    def _open_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Config File", "", "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self._statusbar.showMessage(f"Error loading config: {e}")
            return

        self._config_path = path
        config_dir = os.path.dirname(path)

        # Clear
        for rect in self._areas:
            self._scene.removeItem(rect)
        self._areas.clear()
        self._text_layers.clear()
        self._clear_preview()

        # Resolution
        res = data.get("resolution", [1920, 1080])
        self._resolution = (res[0], res[1])
        self._width_spin.setValue(res[0])
        self._height_spin.setValue(res[1])

        # Layers
        self._bg_path = None
        self._fg_path = None
        self._bg_color = None

        layers = data.get("layers")
        if layers:
            found_cards = False
            for layer in layers:
                if isinstance(layer, str):
                    if not self._bg_path:
                        self._bg_path = self._resolve_path(layer, config_dir)
                    else:
                        self._fg_path = self._resolve_path(layer, config_dir)
                elif isinstance(layer, (list, tuple)) and len(layer) >= 3:
                    self._bg_color = tuple(layer[:3])
                elif isinstance(layer, dict):
                    lt = layer.get("type")
                    if lt == "image":
                        lp = self._resolve_path(layer["path"], config_dir)
                        if not found_cards and not self._bg_path:
                            self._bg_path = lp
                        else:
                            self._fg_path = lp
                    elif lt == "color":
                        self._bg_color = tuple(layer["color"][:3])
                    elif lt == "cards":
                        found_cards = True
                    elif lt in ("text", "csv_field"):
                        self._text_layers.append(layer)
        else:
            bg = data.get("background")
            if isinstance(bg, str):
                self._bg_path = self._resolve_path(bg, config_dir)
            elif isinstance(bg, (list, tuple)):
                self._bg_color = tuple(bg[:3])
            fg = data.get("foreground")
            if isinstance(fg, str):
                self._fg_path = self._resolve_path(fg, config_dir)

        self._bg_input.setText(self._bg_path or "")
        self._bg_color_label.setText(str(self._bg_color) if self._bg_color else "(30, 30, 30)")
        self._fg_input.setText(self._fg_path or "")

        # Card settings
        self._padding_spin.setValue(data.get("padding", 3))
        self._uniform_check.setChecked(data.get("uniform_card_size", True))

        self._count_bg_path = data.get("count_background")
        if self._count_bg_path:
            self._count_bg_path = self._resolve_path(self._count_bg_path, config_dir)
        self._count_bg_input.setText(self._count_bg_path or "")

        self._count_font_path = data.get("count_font")
        if self._count_font_path:
            self._count_font_path = self._resolve_path(self._count_font_path, config_dir)
        self._count_font_input.setText(os.path.basename(self._count_font_path) if self._count_font_path else "")

        # Areas
        self._update_canvas_size()
        for coords in data.get("leader_areas", []):
            self._add_area_from_coords("leader_area", coords)
        for coords in data.get("base_areas", []):
            self._add_area_from_coords("base_area", coords)
        if data.get("deck_area"):
            self._add_area_from_coords("deck_area", data["deck_area"])
        if data.get("sb_area"):
            self._add_area_from_coords("sb_area", data["sb_area"])
        if data.get("misc_area"):
            self._add_area_from_coords("misc_area", data["misc_area"])

        self._refresh_area_list()
        self._refresh_text_list()
        self._statusbar.showMessage(f"Loaded: {path}")

    def _resolve_path(self, path, config_dir):
        if os.path.isabs(path):
            return path
        resolved = os.path.join(config_dir, path)
        if os.path.exists(resolved):
            return resolved
        return path

    def _add_area_from_coords(self, area_type, coords):
        x0, y0, x1, y1 = coords
        rect = ResizableRect(0, 0, x1 - x0, y1 - y0, area_type, parent_editor=self)
        rect.setPos(x0, y0)
        self._scene.addItem(rect)
        self._areas.append(rect)

    def _save_config(self):
        if self._config_path:
            self._write_config(self._config_path)
        else:
            self._save_config_as()

    def _save_config_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Config", "", "JSON Files (*.json);;All Files (*)"
        )
        if path:
            self._config_path = path
            self._write_config(path)

    def _write_config(self, path):
        try:
            data = self._config_to_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._statusbar.showMessage(f"Saved: {path}")
        except Exception as e:
            self._statusbar.showMessage(f"Error saving: {e}")


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    window = ConfigEditor()
    window.show()
    if not app.property("_decklister_running"):
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
