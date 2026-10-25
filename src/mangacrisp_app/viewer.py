from __future__ import annotations

import shutil
import sys
import threading
import time
from argparse import ArgumentParser, Namespace
from collections import deque
from collections.abc import Callable, Sequence
from glob import escape as glob_escape
from hashlib import sha1
from html import escape
from math import ceil, isfinite, sqrt
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from mangacrisp_app.archive_utils import discover_samples
from mangacrisp_app.branding import (
    APP_BUNDLE_IDENTIFIER,
    APP_NAME,
    PROJECT_URL,
    SUPPORT_URL,
)
from mangacrisp_app.correction_cache import DEFAULT_UPSCALE_DIR, CorrectionDiskCache
from mangacrisp_app.correction_queue import CorrectionQueue
from mangacrisp_app.cursor_autohide import (
    CURSOR_AUTO_HIDE_DELAY_MS,
    CursorAutoHideState,
    cursor_may_hide,
)
from mangacrisp_app.display_cache import (
    DisplayCache,
    display_image_key,
    display_keys_show_same_image,
)
from mangacrisp_app.engine_utils import (
    PRO_SYNC_GAP,
    realcugan_executable,
    run_realcugan,
)
from mangacrisp_app.i18n import initialize_language, tr
from mangacrisp_app.library import Bookmark, migrate_legacy_application_state
from mangacrisp_app.page_provider import open_pages_for_viewer
from mangacrisp_app.quality_settings import (
    DEFAULT_QUALITY_SETTINGS_PATH,
    load_quality_preferences,
    save_quality_preferences,
    validate_quality_preset,
)
from mangacrisp_app.reader_actions import (
    action_keycap,
    action_label,
    help_entries,
    overlay_action_ids,
    resolve_action,
)

try:
    from PySide6.QtCore import (
        QEvent,
        QObject,
        QRunnable,
        QSize,
        Qt,
        QThreadPool,
        QTimer,
        Signal,
    )
    from PySide6.QtGui import QCursor, QImage, QPixmap
    from PySide6.QtWidgets import (
        QAbstractButton,
        QAbstractSpinBox,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QFormLayout,
        QGridLayout,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    from mangacrisp_app.image_viewport import SpreadViewport
    from mangacrisp_app.reader_widgets import (
        READER_STYLE_SHEET,
        ChoiceButton,
        OverlayPane,
        ShortcutButton,
    )

    PYSIDE_IMPORT_ERROR: ImportError | None = None
except ImportError as exc:
    QEvent = QObject = QRunnable = QSize = QThreadPool = QTimer = Qt = Signal = QCursor = QImage = QPixmap = None
    QApplication = QCheckBox = QComboBox = QDialog = QFormLayout = None
    QHBoxLayout = QInputDialog = QLabel = QMessageBox = QProgressBar = QPushButton = QScrollArea = QSpinBox = QVBoxLayout = QWidget = QFileDialog = None
    SpreadViewport = None
    QMainWindow = object
    PYSIDE_IMPORT_ERROR = exc


ROOT_DIR = Path(__file__).resolve().parents[2]
SAMPLE_DIR = ROOT_DIR / "sample"
DISPLAY_CACHE_DIR = DEFAULT_UPSCALE_DIR / "display_cache"
DEFAULT_FORWARD_PREFETCH_COUNT = 12
DEFAULT_PREVIOUS_PREFETCH_COUNT = 6
MIN_FORWARD_PREFETCH_COUNT = 6
MAX_FORWARD_PREFETCH_COUNT = 24
SLOW_READER_INTERVAL_SECONDS = 8.0
CORRECTION_MISS_WINDOW = 10
CORRECTION_MISS_THRESHOLD = 2
CORRECTION_MISS_LEAD_FACTOR = 1.5
DISPLAY_WARM_AHEAD_COUNT = 4
DISPLAY_WARM_PREVIOUS_COUNT = 4
DISK_PROTECTED_PREVIOUS_COUNT = 12
PREFETCH_DEBOUNCE_MS = 90
DISPLAY_WARM_DEBOUNCE_MS = 180
CACHE_MAINTENANCE_DEBOUNCE_MS = 900
PAGE_STATE_SAVE_DEBOUNCE_MS = 350
CLICK_ZONE_EDGE_FRACTION = 0.4
CLICK_DRAG_TOLERANCE_PX = 12
MAX_DISPLAY_DECODE_PIXELS = 8 * 1024 * 1024
ZOOM_STEP = 1.25
MIN_ZOOM_FACTOR = 0.25
MAX_ZOOM_FACTOR = 8.0
MODEL_NOISE_OPTIONS = {
    "models-pro": ["3"],
    "models-se": ["-1", "0", "1", "2", "3"],
}

PRESETS = [
    {
        "name": "原画",
        "mode": "original",
        "model": "models-se",
        "noise": "0",
        "description": "補正せず最速で表示します。画質比較の基準です。",
    },
    {
        "name": "自然",
        "mode": "corrected",
        "model": "models-se",
        "scale": 2,
        "noise": "0",
        "tile": 0,
        "threshold": 2234,
        "tta": False,
        "description": "se/noise 0。線とトーンを自然に整えます。",
    },
    {
        "name": "クリーニング",
        "mode": "corrected",
        "model": "models-se",
        "scale": 2,
        "noise": "3",
        "tile": 0,
        "threshold": 2234,
        "tta": False,
        "description": "se/noise 3。古いスキャンの荒れを強く抑えます。",
    },
    {
        "name": "高画質",
        "mode": "corrected",
        "model": "models-pro",
        "scale": 3,
        "noise": "3",
        "tile": 0,
        "threshold": 2234,
        "tta": False,
        "description": "pro/noise 3。処理時間より線と質感の仕上がりを優先します。",
    },
]

NOISE_LABELS = {
    "-1": "弱め",
    "0": "自然",
    "1": "標準",
    "2": "やや強め",
    "3": "強め",
}


def viewer_shortcuts_text(
    reading_direction: str,
    available_actions: frozenset[str] = frozenset({"always", "bookmark_add", "bookmark_list"}),
) -> str:
    """Render the registry's help rows using the current application language."""
    return "\n".join(
        tr(entry.template, keys=entry.keys) if entry.keys is not None else tr(entry.template)
        for entry in help_entries(reading_direction, available_actions)
    )


def help_dialog_html(shortcuts_text: str) -> str:
    shortcuts = "<br>".join(escape(line) for line in shortcuts_text.splitlines())
    return (
        f"<p>{shortcuts}</p>"
        f"<hr><p><b>{escape(tr('プロジェクト情報'))}</b><br>"
        f"<a href=\"{PROJECT_URL}\">{escape(tr('ソースコード・不具合報告'))}</a><br>"
        f"<a href=\"{SUPPORT_URL}\">{escape(tr('開発を支援（任意）'))}</a></p>"
    )


def show_help_dialog(parent, shortcuts_text: str) -> None:
    from mangacrisp_app.shortcut_help import ShortcutHelpDialog

    dialog = ShortcutHelpDialog(parent, shortcuts_text)
    try:
        dialog.exec()
    finally:
        dialog.deleteLater()


def display_preset_name(name: str) -> str:
    return tr(name) if name in {preset["name"] for preset in PRESETS} | {"カスタム補正"} else name


def page_progress_text(visible_indexes: list[int], total_pages: int) -> str:
    if not visible_indexes or total_pages <= 0:
        return "0/0"
    if len(visible_indexes) == 1:
        return f"{visible_indexes[0] + 1}/{total_pages}"
    return f"{visible_indexes[0] + 1}-{visible_indexes[-1] + 1}/{total_pages}"


def visible_file_names(pages: Sequence[Path], visible_indexes: list[int]) -> str:
    names = [pages[index].name for index in visible_indexes if 0 <= index < len(pages)]
    return " / ".join(names)


def should_handle_global_shortcut(active_modal_widget: object | None) -> bool:
    return active_modal_widget is None


def reader_click_action(
    x: float,
    width: float,
    reading_direction: str,
    button: str = "left",
) -> str | None:
    if button == "right":
        return "previous"
    if button != "left" or width <= 0 or x < 0 or x > width:
        return None
    position = x / width
    if CLICK_ZONE_EDGE_FRACTION <= position <= 1.0 - CLICK_ZONE_EDGE_FRACTION:
        return "info"
    clicked_left = position < CLICK_ZONE_EDGE_FRACTION
    if reading_direction == "rtl":
        return "next" if clicked_left else "previous"
    return "previous" if clicked_left else "next"


def standard_spread_index(index: int, cover_single: bool) -> int:
    if cover_single:
        if index <= 0:
            return 0
        return 1 + ((index - 1) // 2) * 2
    return max(0, (index // 2) * 2)


def default_spread_order(reading_direction: str) -> str:
    return "rtl" if reading_direction == "rtl" else "ltr"


def display_cache_path_for(display_path: Path) -> Path | None:
    try:
        stat = display_path.stat()
    except OSError:
        return None
    key = sha1(f"{display_path}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()[:16]
    return DISPLAY_CACHE_DIR / f"{key}.png"


def remove_legacy_display_cache() -> None:
    shutil.rmtree(DISPLAY_CACHE_DIR, ignore_errors=True)


def prefetch_window_indexes(
    current_index: int,
    total_pages: int,
    visible_indexes: Sequence[int],
    ahead_count: int,
    previous_count: int = DEFAULT_PREVIOUS_PREFETCH_COUNT,
) -> list[int]:
    indexes = [index for index in visible_indexes if 0 <= index < total_pages]
    start = current_index + len(indexes)
    indexes.extend(range(start, min(total_pages, start + max(0, ahead_count))))
    indexes.extend(range(current_index - 1, max(-1, current_index - previous_count - 1), -1))
    return list(dict.fromkeys(indexes))


def adaptive_forward_prefetch_count(
    intervals_per_page: Sequence[float],
    *,
    base_count: int,
    correction_seconds_per_page: float,
    maximum_count: int = MAX_FORWARD_PREFETCH_COUNT,
    minimum_count: int = MIN_FORWARD_PREFETCH_COUNT,
    slow_interval_seconds: float = SLOW_READER_INTERVAL_SECONDS,
    lead_factor: float = 1.0,
) -> int:
    """Pages to correct ahead of the reader.

    Fast readers get more lead so corrections stay ahead of them; readers who
    linger on a page for ``slow_interval_seconds`` or more drop below the base
    count so the GPU idles instead of correcting pages they will not reach for
    minutes. ``lead_factor`` lets the caller stretch the lead when corrections
    have recently missed the visible spread.
    """
    base_count = max(0, base_count)
    if not intervals_per_page:
        return min(maximum_count, base_count)
    ordered = sorted(intervals_per_page)
    median_interval = ordered[len(ordered) // 2]
    pages_per_second = 1.0 / max(0.05, median_interval)
    lead_seconds = max(12.0, correction_seconds_per_page * 8.0) * max(1.0, lead_factor)
    target = ceil(pages_per_second * lead_seconds) + 4
    floor = min(base_count, minimum_count) if median_interval >= slow_interval_seconds else base_count
    target = max(floor, min(maximum_count, target))
    if target % 2:
        target += 1
    return min(maximum_count, target)


def correction_lead_factor(
    recent_misses: Sequence[bool],
    *,
    threshold: int = CORRECTION_MISS_THRESHOLD,
    factor: float = CORRECTION_MISS_LEAD_FACTOR,
) -> float:
    """Stretch the prefetch lead once the visible spread has been shown uncorrected often enough."""
    return factor if sum(1 for missed in recent_misses if missed) >= threshold else 1.0


def missing_processed_indexes(
    processed_pages: Sequence[Path | None],
    visible_indexes: Sequence[int],
    skipped_indexes: Sequence[int] = (),
) -> list[int]:
    skipped = set(skipped_indexes)
    return [
        index
        for index in visible_indexes
        if 0 <= index < len(processed_pages)
        and index not in skipped
        and (processed_pages[index] is None or not processed_pages[index].is_file())
    ]


class WorkerSignals(QObject):
    upscale_page_done = Signal(int, object, int, object)
    upscale_done = Signal(int, object, object, int, object, bool)
    display_image_done = Signal(object, object, int)


def decode_scaled_display_image(
    display_path: Path,
    target_width: int,
    target_height: int,
    high_quality: bool,
    normalize_color: bool,
) -> QImage:
    image = QImage(str(display_path))
    if image.isNull():
        return image
    if normalize_color:
        target_format = (
            QImage.Format_RGBA8888 if image.hasAlphaChannel() else QImage.Format_RGB888
        )
        image = image.convertToFormat(target_format)
    transform_mode = Qt.SmoothTransformation if high_quality else Qt.FastTransformation
    return image.scaled(
        QSize(target_width, target_height),
        Qt.KeepAspectRatio,
        transform_mode,
    )


def display_decode_target(
    target,
    device_pixel_ratio: float,
    source_size: tuple[int, int] | None = None,
) -> tuple[int, int, float]:
    """Return capped physical decode dimensions and their effective DPR.

    Qt sizes widgets in device-independent pixels.  When a zoomed target
    exceeds the display decode budget, lowering a pixmap's DPR preserves that
    logical size while deliberately reducing only its available detail.
    """
    logical_width = max(1, target.width())
    logical_height = max(1, target.height())
    requested_dpr = max(0.1, float(device_pixel_ratio))
    physical_width = max(1, round(logical_width * requested_dpr))
    physical_height = max(1, round(logical_height * requested_dpr))
    if source_size is not None and source_size[0] > 0 and source_size[1] > 0:
        source_width, source_height = source_size
        fit_scale = min(physical_width / source_width, physical_height / source_height)
        physical_width = max(1, round(source_width * fit_scale))
        physical_height = max(1, round(source_height * fit_scale))
    requested_pixels = physical_width * physical_height
    cap_scale = min(1.0, sqrt(MAX_DISPLAY_DECODE_PIXELS / requested_pixels))
    physical_width = max(1, int(physical_width * cap_scale))
    physical_height = max(1, int(physical_height * cap_scale))
    return physical_width, physical_height, requested_dpr * cap_scale


def display_pixmap_weight(pixmap: QPixmap) -> int:
    """Estimate the resident Qt image backing-store size for the LRU budget."""
    if pixmap.isNull():
        return 1
    return max(1, pixmap.width() * pixmap.height() * max(1, pixmap.depth() // 8))


def target_device_pixel_ratio(target) -> float:
    """Use widget DPR when available; QSize callers retain the DPR-1 contract."""
    getter = getattr(target, "devicePixelRatioF", None)
    return float(getter()) if callable(getter) else 1.0


def actual_size_zoom_factor(image_width: int, fitted_width: float, device_pixel_ratio: float) -> float:
    """Map one original source pixel to one physical screen pixel."""
    if image_width <= 0 or fitted_width <= 0 or device_pixel_ratio <= 0:
        return 1.0
    return image_width / (fitted_width * device_pixel_ratio)


class DisplayRenderTask(QRunnable if QRunnable is not None else object):
    def __init__(
        self,
        signals: WorkerSignals,
        cache_key: tuple,
        display_path: Path,
        target_width: int,
        target_height: int,
        high_quality: bool,
        normalize_color: bool,
    ) -> None:
        super().__init__()
        self.signals = signals
        self.cache_key = cache_key
        self.display_path = display_path
        self.target_width = target_width
        self.target_height = target_height
        self.high_quality = high_quality
        self.normalize_color = normalize_color

    def run(self) -> None:
        started = time.perf_counter()
        image = decode_scaled_display_image(
            self.display_path,
            self.target_width,
            self.target_height,
            self.high_quality,
            self.normalize_color,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        try:
            self.signals.display_image_done.emit(self.cache_key, image, elapsed_ms)
        except RuntimeError:
            pass


class SpreadWindow(QMainWindow):
    def __init__(
        self,
        pages: Sequence[Path],
        title: str,
        cleanup_dir: Path | None = None,
        processed_pages: list[Path | None] | None = None,
        reading_direction: str = "rtl",
        spread_order: str = "rtl",
        cover_single: bool = True,
        auto_prefetch: bool = True,
        prefetch_count: int = DEFAULT_FORWARD_PREFETCH_COUNT,
        previous_prefetch_count: int = DEFAULT_PREVIOUS_PREFETCH_COUNT,
        upscale_height_threshold: int = 2234,
        page_changed_callback: Callable[[int], None] | None = None,
        bookmark_callback: Callable[[int], bool | None] | None = None,
        bookmarks_provider: Callable[[], list[Bookmark]] | None = None,
        bookmark_delete_callback: Callable[[str], bool] | None = None,
        bookmark_edit_callback: Callable[[str, str, str | None], Bookmark | None] | None = None,
        next_book_callback: Callable[[], None] | None = None,
        next_book_label: str | None = None,
        close_callback: Callable[[SpreadWindow], None] | None = None,
        settings_path: Path | None = None,
        embedded: bool = False,
        parent: QWidget | None = None,
        *,
        initial_page_index: int = 0,
        initial_page_layout: str = "spread",
        initial_quality_preset: str | None = None,
    ) -> None:
        super().__init__(parent)
        if embedded:
            self.setWindowFlags(Qt.Widget)
        self.correction_cache = CorrectionDiskCache(DEFAULT_UPSCALE_DIR)
        self.correction_cache.prune()
        self.pages = pages
        self.processed_pages = processed_pages or [None] * len(pages)
        self.reading_direction = reading_direction
        self.spread_order = spread_order
        self.cover_single = cover_single
        self.cleanup_dir = cleanup_dir
        self.auto_prefetch_default = auto_prefetch
        self.prefetch_count_default = prefetch_count
        self.previous_prefetch_count = previous_prefetch_count
        self.prefetch_enabled = auto_prefetch
        self.upscale_height_threshold_default = upscale_height_threshold
        self.page_changed_callback = page_changed_callback
        self.bookmark_callback = bookmark_callback
        self.bookmarks_provider = bookmarks_provider
        self.bookmark_delete_callback = bookmark_delete_callback
        self.bookmark_edit_callback = bookmark_edit_callback
        self.next_book_callback = next_book_callback
        self.next_book_label = next_book_label
        self.close_callback = close_callback
        self.settings_path = settings_path or DEFAULT_QUALITY_SETTINGS_PATH
        self.quality_preferences = load_quality_preferences(self.settings_path)
        self.custom_presets = list(self.quality_preferences["custom_presets"])
        self.settings_ui_mode = self.quality_preferences["ui_mode"]
        self.embedded = embedded
        self.index = min(max(0, initial_page_index), max(0, len(pages) - 1))
        self.is_fullscreen = False
        self.upscale_running = False
        self.prefetch_running = False
        self.prefetch_suspended = False
        self.processing_generation = 0
        self.is_closing = False
        self.prefetch_target_indexes: set[int] = set()
        self.correction_queue = CorrectionQueue()
        self.running_parameter_key: str | None = None
        self.active_output_paths: set[Path] = set()
        self.current_quality_preset = "自然"
        # The current display can be Original while temporarily comparing with
        # O. Keep the durable quality choice separate so that
        # comparison state is never saved for this book or globally.
        self.quality_preset_for_state = "自然"
        self.last_corrected_preset_name = "自然"
        self.navigation_intervals: deque[float] = deque(maxlen=8)
        self.correction_misses: deque[bool] = deque(maxlen=CORRECTION_MISS_WINDOW)
        self.last_navigation_at: float | None = None
        self.correction_seconds_per_page = 1.25
        self.adaptive_prefetch_count = prefetch_count
        self.controls_visible = True
        self.page_layout_mode = "single" if initial_page_layout == "single" else "spread"
        self.initial_quality_preset = initial_quality_preset
        self.reading_info_visible = False
        self.mouse_press_button = None
        self.mouse_press_global_position = None
        self.mouse_last_global_position = None
        self.mouse_dragging = False
        self.suppress_next_mouse_release = False
        self.reading_page_input_dirty = False
        self.viewport_auto_mode_signature: tuple | None = None
        self.pending_auto_page_focus: tuple[float, float] | None = None
        self.image_size_cache: dict[int, tuple[int, int]] = {}
        self.display_pixmap_cache: DisplayCache[tuple, QPixmap] = DisplayCache(
            capacity=18,
            max_bytes=192 * 1024 * 1024,
            weight=display_pixmap_weight,
        )
        self.pending_display_renders: dict[tuple, int] = {}
        self.desired_display_keys: dict[int, tuple | None] = {}
        self.fallback_display_keys: dict[int, tuple | None] = {}
        self.shown_display_keys: dict[int, tuple | None] = {}
        self.display_decode_times_ms: deque[int] = deque(maxlen=32)
        self.visible_display_pool = QThreadPool(self)
        self.visible_display_pool.setMaxThreadCount(2)
        self.warm_display_pool = QThreadPool(self)
        self.warm_display_pool.setMaxThreadCount(2)
        self.last_disk_cache_prune_signature: tuple[str, tuple[int, ...]] | None = None
        self.fast_resize_render = False
        self.resize_quality_delay_ms = 180
        self.resize_quality_timer = QTimer(self)
        self.resize_quality_timer.setSingleShot(True)
        self.resize_quality_timer.timeout.connect(self.finish_resize_quality_render)
        self.prefetch_request_timer = QTimer(self)
        self.prefetch_request_timer.setSingleShot(True)
        self.prefetch_request_timer.timeout.connect(self.start_prefetch)
        self.display_warm_timer = QTimer(self)
        self.display_warm_timer.setSingleShot(True)
        self.display_warm_timer.timeout.connect(self.warm_nearby_display_cache)
        self.cache_maintenance_timer = QTimer(self)
        self.cache_maintenance_timer.setSingleShot(True)
        self.cache_maintenance_timer.timeout.connect(self.maintain_correction_cache)
        self.page_state_save_timer = QTimer(self)
        self.page_state_save_timer.setSingleShot(True)
        self.page_state_save_timer.timeout.connect(self.flush_page_changed)
        self.cursor_hidden = False
        self.cursor_hide_timer = QTimer(self)
        self.cursor_hide_timer.setSingleShot(True)
        self.cursor_hide_timer.setInterval(CURSOR_AUTO_HIDE_DELAY_MS)
        self.cursor_hide_timer.timeout.connect(self.hide_cursor_if_idle)
        self.signals = WorkerSignals()
        self.signals.upscale_page_done.connect(self.on_upscale_page_done)
        self.signals.upscale_done.connect(self.on_upscale_done)
        self.signals.display_image_done.connect(self.on_display_image_done)

        direction_label = "right-bound" if self.is_right_bound() else "left-bound"
        self.setWindowTitle(f"{APP_NAME}: {title} ({direction_label}, spread-{self.spread_order})")
        self.setStyleSheet(
            "QMainWindow, QWidget { background: #111111; color: #dddddd; font-size: 14px; } "
            "QLabel#pagePane { border: 1px solid #333333; } "
            "QWidget#controls { background: #181818; border-left: 1px solid #333333; } "
            "QPushButton, QComboBox, QSpinBox { min-height: 30px; font-size: 14px; } "
            "QCheckBox { min-height: 28px; } "
            "QStatusBar { font-size: 12px; }" + READER_STYLE_SHEET
        )

        root = QWidget(self)
        root.setObjectName("readerRoot")
        outer_layout = QVBoxLayout(root)
        outer_layout.setContentsMargins(12, 12, 12, 8)
        outer_layout.setSpacing(8)
        root_layout = QHBoxLayout()
        outer_layout.addLayout(root_layout, 1)
        self.reader_action_buttons = {}
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(12)
        image_host = QWidget(root)
        image_host.setMouseTracking(True)
        self.image_host = image_host
        image_host_layout = QVBoxLayout(image_host)
        image_host_layout.setContentsMargins(0, 0, 0, 0)
        image_host_layout.setSpacing(8)
        self.next_book_banner = QPushButton(tr("次の巻へ"), image_host)
        self.next_book_banner.setToolTip(tr("読了後に本棚順の次の巻を開きます"))
        self.next_book_banner.clicked.connect(self.open_next_book)
        self.next_book_banner.setStyleSheet(
            "QPushButton {"
            " background: rgba(12, 12, 12, 165);"
            " border: 1px solid rgba(255, 255, 255, 58);"
            " border-radius: 8px;"
            " color: #ffffff;"
            " font-size: 17px;"
            " font-weight: bold;"
            " padding: 12px 18px;"
            "}"
            "QPushButton:hover { background: rgba(36, 36, 36, 190); }"
            "QPushButton:pressed { background: rgba(60, 60, 60, 210); }"
        )
        self.next_book_banner.setVisible(False)
        self.next_book_banner.setCursor(Qt.ArrowCursor)
        self.viewport = SpreadViewport(image_host)
        self.page_layout = self.viewport.page_layout
        # Keep the established pane attributes as compatibility aliases for
        # rendering, input filters and extension code while the viewport owns
        # only their geometry.
        self.left = self.viewport.left
        self.right = self.viewport.right
        self.left.installEventFilter(self)
        self.right.installEventFilter(self)
        image_host_layout.addWidget(self.viewport, 1)
        self.build_reading_overlay(image_host)
        root_layout.addWidget(image_host, 1)
        self.controls_panel = self.build_controls()
        root_layout.addWidget(self.controls_panel, 0)
        self.setCentralWidget(root)
        QApplication.instance().installEventFilter(self)

        self.resize(1400, 900)
        self.position_reading_info_overlay()
        self.render_spread()

    def build_controls(self) -> QWidget:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(350)
        scroll.setStyleSheet("QScrollArea { border: 0; background: #181818; }")
        controls = QWidget(scroll)
        controls.setObjectName("controls")
        controls.setMinimumWidth(330)
        layout = QVBoxLayout(controls)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(tr("読書設定"), controls)
        title.setStyleSheet("font-weight: bold; font-size: 18px;")
        header.addWidget(title, 1)
        help_button = QPushButton("×  P", controls)
        help_button.setFixedWidth(62)
        help_button.setToolTip(tr("読書設定を閉じる"))
        help_button.clicked.connect(self.toggle_controls)
        header.addWidget(help_button)
        layout.addLayout(header)

        self.settings_mode_combo = QComboBox(controls)
        self.settings_mode_combo.addItem(tr("かんたん"), "simple")
        self.settings_mode_combo.addItem(tr("マニュアル"), "manual")
        self.settings_mode_combo.currentIndexChanged.connect(self.on_settings_mode_changed)
        self.settings_mode_combo.hide()

        self.quality_state_card = QWidget(controls)
        self.quality_state_card.setObjectName("qualityState")
        self.quality_state_card.setStyleSheet(
            "QWidget#qualityState { background: #202a34; border: 1px solid #354351; border-radius: 8px; }"
        )
        state_layout = QVBoxLayout(self.quality_state_card)
        state_layout.setContentsMargins(10, 8, 10, 8)
        state_layout.setSpacing(4)
        self.quality_mode_label = QLabel(tr("画質: {mode}", mode=tr("自然")), self.quality_state_card)
        self.quality_engine_label = QLabel(
            tr("エンジン: Real-CUGAN / {model}", model="models-se"),
            self.quality_state_card,
        )
        self.quality_correction_label = QLabel(
            tr("状態: {state}", state=tr("原画表示中")),
            self.quality_state_card,
        )
        self.quality_prefetch_label = QLabel(
            tr(
                "先読み: {state} / 縦{threshold}px以上は原画",
                state=tr("待機中"),
                threshold=self.upscale_height_threshold_default,
            ),
            self.quality_state_card,
        )
        for label in (
            self.quality_mode_label,
            self.quality_engine_label,
            self.quality_correction_label,
            self.quality_prefetch_label,
        ):
            label.setWordWrap(True)
            label.setStyleSheet("background: transparent; color: #eeeeee; font-size: 13px;")
            state_layout.addWidget(label)
        layout.addWidget(self.quality_state_card)

        back_button = QPushButton(tr("本棚へ戻る"), controls)
        back_button.clicked.connect(self.return_to_bookshelf)
        layout.addWidget(back_button)

        self.next_book_button = QPushButton(tr("次の巻へ"), controls)
        self.next_book_button.setToolTip(tr("読了後に本棚順の次の巻を開きます"))
        self.next_book_button.clicked.connect(self.open_next_book)
        layout.addWidget(self.next_book_button)
        self.next_book_hint = self.help_label("")
        layout.addWidget(self.next_book_hint)
        self.update_next_book_action()

        self.simple_panel = QWidget(controls)
        self.simple_panel.setObjectName("simplePanel")
        self.simple_panel.setStyleSheet("QWidget#simplePanel { background: transparent; }")
        simple_layout = QVBoxLayout(self.simple_panel)
        simple_layout.setContentsMargins(0, 0, 0, 0)
        simple_layout.setSpacing(8)
        preset_title = QLabel(tr("画質モード"), self.simple_panel)
        preset_title.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 4px;")
        simple_layout.addWidget(preset_title)
        preset_grid = QGridLayout()
        preset_grid.setSpacing(8)
        self.preset_buttons = {}
        subtitles = ["補正しない", "線とトーンを自然に", "汚れ・ノイズを軽減", "細部までくっきり"]
        for index, preset in enumerate(PRESETS):
            button = ChoiceButton(display_preset_name(preset["name"]), tr(subtitles[index]), self.simple_panel)
            button.clicked.connect(lambda _checked=False, item=preset: self.select_quality_preset(item))
            self.preset_buttons[preset["name"]] = button
            preset_grid.addWidget(button, index // 2, index % 2)
        simple_layout.addLayout(preset_grid)
        self.preset_status = QLabel(
            tr("選択中: {name}", name=display_preset_name("自然")),
            self.simple_panel,
        )
        self.preset_status.setWordWrap(True)
        self.preset_status.setStyleSheet("color: #dddddd; font-size: 13px;")
        self.preset_status.hide()
        layout.addWidget(self.simple_panel)

        layout_title = QLabel(tr("表示レイアウト"), controls)
        layout_title.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 8px;")
        layout.addWidget(layout_title)
        self.page_layout_combo = QComboBox(controls)
        self.page_layout_combo.addItem(tr("見開き（2画像）"), "spread")
        self.page_layout_combo.addItem(tr("単ページ（1画像）"), "single")
        self.page_layout_combo.currentIndexChanged.connect(self.on_page_layout_changed)
        self.page_layout_combo.hide()
        layout_row = QHBoxLayout()
        self.layout_buttons = {}
        for mode, title in (("spread", "見開き"), ("single", "単ページ")):
            # V toggles layouts; it does not select either of these two choices.
            button = QPushButton(tr(title), controls)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, value=mode: self.select_page_layout(value))
            self.layout_buttons[mode] = button
            layout_row.addWidget(button)
        layout.addLayout(layout_row)
        layout.addWidget(self.help_label(tr("見開きを含む1枚の画像は、単ページで中央に大きく表示します。")))

        spread_title = QLabel(tr("見開き調整"), controls)
        spread_title.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 8px;")
        layout.addWidget(spread_title)
        spread_buttons = QHBoxLayout()
        self.shift_back_button = self.make_reader_action("back_one", controls)
        spread_buttons.addWidget(self.shift_back_button)
        self.shift_forward_button = self.make_reader_action("forward_one", controls)
        spread_buttons.addWidget(self.shift_forward_button)
        self.swap_button = QPushButton(tr("左右入替"), controls)
        self.swap_button.clicked.connect(self.swap_spread_order)
        layout.addWidget(self.swap_button)
        layout.addLayout(spread_buttons)
        self.reset_spread_button = QPushButton(tr("標準見開きに戻す"), controls)
        self.reset_spread_button.clicked.connect(self.reset_spread_alignment)
        layout.addWidget(self.reset_spread_button)
        self.spread_status = QLabel("", controls)
        self.spread_status.setWordWrap(True)
        self.spread_status.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        layout.addWidget(self.spread_status)
        self.update_spread_status()

        self.advanced_toggle = QPushButton(tr("詳細設定"), controls)
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.clicked.connect(
            lambda checked: self.apply_settings_mode("manual" if checked else "simple", persist=True)
        )
        layout.addWidget(self.advanced_toggle)
        self.advanced_panel = QWidget(controls)
        self.advanced_panel.setObjectName("advancedPanel")
        self.advanced_panel.setStyleSheet("QWidget#advancedPanel { background: transparent; }")
        advanced_layout = QVBoxLayout(self.advanced_panel)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(8)
        custom_title = QLabel(tr("カスタム設定"), self.advanced_panel)
        custom_title.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 4px;")
        advanced_layout.addWidget(custom_title)
        self.custom_preset_combo = QComboBox(self.advanced_panel)
        self.custom_preset_combo.setToolTip(tr("保存済みの画質設定を選びます"))
        advanced_layout.addWidget(self.custom_preset_combo)
        custom_buttons = QHBoxLayout()
        load_custom_button = QPushButton(tr("読込"), self.advanced_panel)
        load_custom_button.clicked.connect(self.load_selected_custom_preset)
        custom_buttons.addWidget(load_custom_button)
        save_custom_button = QPushButton(tr("保存"), self.advanced_panel)
        save_custom_button.clicked.connect(self.save_current_custom_preset)
        custom_buttons.addWidget(save_custom_button)
        delete_custom_button = QPushButton(tr("削除"), self.advanced_panel)
        delete_custom_button.clicked.connect(self.delete_selected_custom_preset)
        custom_buttons.addWidget(delete_custom_button)
        advanced_layout.addLayout(custom_buttons)
        form = QFormLayout()
        self.scale_spin = QSpinBox(controls)
        self.scale_spin.setRange(1, 4)
        self.scale_spin.setValue(2)
        self.scale_spin.valueChanged.connect(lambda _value: self.on_processing_settings_changed())
        form.addRow(tr("倍率"), self.scale_spin)
        form.addRow("", self.help_label(tr("拡大倍率。漫画確認はまず2倍が扱いやすいです。")))

        self.noise_combo = QComboBox(controls)
        self.noise_combo.addItems(MODEL_NOISE_OPTIONS["models-se"])
        self.noise_combo.setCurrentText("0")
        self.noise_combo.currentTextChanged.connect(lambda _value: self.on_processing_settings_changed())
        form.addRow(tr("ノイズ除去"), self.noise_combo)
        form.addRow("", self.help_label(tr("0:自然 / 1:標準 / 3:強め。強いほど線が変わりやすいです。")))

        self.tile_spin = QSpinBox(controls)
        self.tile_spin.setRange(0, 4096)
        self.tile_spin.setSingleStep(32)
        self.tile_spin.setValue(0)
        self.tile_spin.valueChanged.connect(lambda _value: self.on_processing_settings_changed())
        form.addRow(tr("タイル"), self.tile_spin)
        form.addRow("", self.help_label(tr("処理タイルサイズ。0は自動、重い時だけ調整します。")))

        self.threshold_spin = QSpinBox(controls)
        self.threshold_spin.setRange(1, 12000)
        self.threshold_spin.setValue(self.upscale_height_threshold_default)
        self.threshold_spin.valueChanged.connect(lambda _value: self.on_processing_settings_changed())
        form.addRow(tr("補正スキップ縦px"), self.threshold_spin)
        form.addRow("", self.help_label(tr("この縦px以上は補正せず原画表示。今のMacは2234候補です。")))

        self.model_combo = QComboBox(controls)
        self.model_combo.addItems(["models-pro", "models-se"])
        self.model_combo.setCurrentText("models-se")
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        form.addRow(tr("モデル"), self.model_combo)
        form.addRow("", self.help_label(tr("seは自然な補正向け。proは処理時間より仕上がりを優先します。")))

        self.tta_check = QCheckBox("TTA", controls)
        self.tta_check.stateChanged.connect(lambda _state: self.on_processing_settings_changed())
        form.addRow("", self.tta_check)
        form.addRow("", self.help_label(tr("反転推論で精度を上げます。かなり遅くなります。")))
        advanced_layout.addLayout(form)
        layout.addWidget(self.advanced_panel)

        self.apply_button = QPushButton(tr("現在の見開きを補正"), controls)
        self.apply_button.clicked.connect(self.process_current_spread)
        layout.addWidget(self.apply_button)
        self.apply_help = self.help_label(tr("現在表示中の見開きだけ処理して表示を差し替えます。"))
        layout.addWidget(self.apply_help)

        self.original_check = QCheckBox(tr("原画を表示（OFFで補正版）"), controls)
        self.original_check.stateChanged.connect(lambda _state: self.on_original_compare_changed())
        self.original_check.hide()
        layout.addWidget(self.make_reader_action("original", controls))

        self.parameter_status = QLabel(tr("待機中"), controls)
        self.parameter_status.setWordWrap(True)
        self.parameter_status.setMinimumHeight(72)
        self.parameter_status.setMaximumHeight(108)
        layout.addWidget(self.parameter_status)
        layout.addStretch(1)
        self.on_model_changed(self.model_combo.currentText(), announce=False)
        self.refresh_custom_preset_combo()
        self.restore_quality_preferences()
        self._sync_initial_page_layout_controls()
        self.apply_settings_mode(self.settings_ui_mode, persist=False)
        self.update_reader_action_states()
        self.update_quality_state()
        scroll.setWidget(controls)
        return scroll

    def select_quality_preset(self, preset: dict) -> None:
        if (
            preset["name"] != self.current_quality_preset
            or preset["name"] != self.quality_preset_for_state
        ):
            self.apply_preset(preset)
        self.update_reader_action_states()

    def select_page_layout(self, mode: str) -> None:
        self.set_page_layout(mode)
        self.update_reader_action_states()

    def make_reader_action(self, action: str, parent: QWidget, *, compact: bool = False) -> ShortcutButton:
        callback = lambda: self.invoke_reader_action(action)
        button = ShortcutButton(
            tr(action_label(action)),
            action_keycap(action, self.reading_direction),
            parent,
            compact=compact,
        )
        button.setCheckable(action in {"settings", "original", "fullscreen", "layout"})
        button.clicked.connect(callback)
        self.reader_action_buttons.setdefault(action, []).append(button)
        return button

    def build_reading_overlay(self, parent: QWidget) -> None:
        self.reading_info_panel = OverlayPane(parent)
        self.reading_info_panel.dismissed.connect(self.dismiss_reading_overlay)
        panel_layout = QVBoxLayout(self.reading_info_panel)
        panel_layout.setContentsMargins(20, 18, 20, 18)
        panel_layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel(tr("読書コントロール"), self.reading_info_panel)
        title.setStyleSheet("font-size: 19px; font-weight: bold; background: transparent;")
        header.addWidget(title, 1)
        close = QPushButton("×", self.reading_info_panel)
        close.setAccessibleName(tr("閉じる"))
        close.setFixedWidth(44)
        close.clicked.connect(self.dismiss_reading_overlay)
        header.addWidget(close)
        panel_layout.addLayout(header)
        self.reading_info_scroll = QScrollArea(self.reading_info_panel)
        self.reading_info_scroll.setObjectName("readingControlsScroll")
        self.reading_info_scroll.setWidgetResizable(True)
        self.reading_info_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.reading_info_scroll.setFrameShape(QScrollArea.NoFrame)
        self.reading_info_content = QWidget(self.reading_info_scroll)
        self.reading_info_content.setObjectName("readingControlsContent")
        self.reading_info_scroll.setWidget(self.reading_info_content)
        self.reading_info_scroll.viewport().setObjectName("readingControlsScrollViewport")
        panel_layout.addWidget(self.reading_info_scroll)
        layout = QVBoxLayout(self.reading_info_content)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        self.reading_info_label = QLabel(self.reading_info_content)
        self.reading_info_label.setWordWrap(True)
        layout.addWidget(self.reading_info_label)
        self.reading_progress = QProgressBar(self.reading_info_content)
        self.reading_progress.setFixedHeight(18)
        layout.addWidget(self.reading_progress)
        page_jump_row = QHBoxLayout()
        page_label = QLabel(tr("ページ"), self.reading_info_content)
        page_jump_row.addWidget(page_label)
        self.reading_page_spin = QSpinBox(self.reading_info_content)
        self.reading_page_spin.setRange(1, max(1, len(self.pages)))
        self.reading_page_spin.setKeyboardTracking(False)
        self.reading_page_spin.setMinimumWidth(92)
        self.reading_page_spin.setAccessibleName(tr("ページ番号"))
        self.reading_page_spin.setToolTip(tr("ページ番号を入力して移動"))
        page_label.setBuddy(self.reading_page_spin)
        page_line_edit = self.reading_page_spin.lineEdit()
        if page_line_edit is not None:
            page_line_edit.textEdited.connect(self.mark_page_jump_input_dirty)
            page_line_edit.returnPressed.connect(self.confirm_page_jump)
        self.reading_page_spin.valueChanged.connect(self.mark_page_jump_value_dirty)
        page_jump_row.addWidget(self.reading_page_spin, 1)
        self.reading_page_jump_button = QPushButton(tr("移動"), self.reading_info_content)
        self.reading_page_jump_button.setAccessibleName(tr("ページ番号を入力して移動"))
        self.reading_page_jump_button.setToolTip(tr("ページ番号を入力して移動"))
        self.reading_page_jump_button.clicked.connect(self.confirm_page_jump)
        page_jump_row.addWidget(self.reading_page_jump_button)
        layout.addLayout(page_jump_row)
        zoom_controls = QVBoxLayout()
        zoom_controls.setSpacing(6)
        zoom_row = QHBoxLayout()
        zoom_label = QLabel(tr("表示倍率"), self.reading_info_content)
        zoom_row.addWidget(zoom_label)
        self.zoom_mode_combo = QComboBox(self.reading_info_content)
        self.zoom_mode_combo.setObjectName("zoomModeSelector")
        self.zoom_mode_combo.setAccessibleName(tr("表示倍率"))
        self.zoom_mode_combo.addItem(tr("全体に合わせる  0"), "fit")
        self.zoom_mode_combo.addItem(tr("幅に合わせる  W"), "width")
        self.zoom_mode_combo.addItem(tr("実寸  1"), "actual")
        self.zoom_mode_combo.addItem(tr("カスタム"), "custom")
        self.zoom_mode_combo.currentIndexChanged.connect(self.on_zoom_mode_changed)
        zoom_label.setBuddy(self.zoom_mode_combo)
        zoom_row.addWidget(self.zoom_mode_combo, 1)
        zoom_controls.addLayout(zoom_row)
        zoom_adjust_row = QHBoxLayout()
        zoom_adjust_row.addStretch(1)
        self.zoom_out_button = QPushButton("−", self.reading_info_content)
        self.zoom_out_button.setAccessibleName(tr("縮小"))
        self.zoom_out_button.setToolTip(tr("縮小"))
        self.zoom_out_button.clicked.connect(self.zoom_out)
        zoom_adjust_row.addWidget(self.zoom_out_button)
        self.zoom_value_label = QLabel(
            tr("全体比 ×{factor}", factor="1.00"), self.reading_info_content
        )
        self.zoom_value_label.setMinimumWidth(48)
        self.zoom_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.zoom_value_label.setToolTip(
            tr("全体表示を1倍とする倍率。実寸は原画1pxを画面の物理1pxで表示します。")
        )
        zoom_adjust_row.addWidget(self.zoom_value_label)
        self.zoom_in_button = QPushButton("＋", self.reading_info_content)
        self.zoom_in_button.setAccessibleName(tr("拡大"))
        self.zoom_in_button.setToolTip(tr("拡大"))
        self.zoom_in_button.clicked.connect(self.zoom_in)
        zoom_adjust_row.addWidget(self.zoom_in_button)
        zoom_adjust_row.addStretch(1)
        zoom_controls.addLayout(zoom_adjust_row)
        layout.addLayout(zoom_controls)
        grid = QGridLayout()
        grid.setSpacing(8)
        actions = overlay_action_ids(self.available_reader_actions(), self.reading_direction)
        for index, action in enumerate(actions):
            grid.addWidget(self.make_reader_action(action, self.reading_info_content), index // 2, index % 2)
        layout.addLayout(grid)
        self.reading_info_bookshelf_button = QPushButton(tr("本棚へ戻る"), self.reading_info_panel)
        self.reading_info_bookshelf_button.clicked.connect(self.return_to_bookshelf)
        panel_layout.addWidget(self.reading_info_bookshelf_button)
        self.reading_info_hint = QLabel(tr("ペインの外をクリックして閉じる"), self.reading_info_panel)
        self.reading_info_hint.setAlignment(Qt.AlignCenter)
        self.reading_info_hint.setStyleSheet("color: #aeb8c2; background: transparent; font-size: 12px;")
        panel_layout.addWidget(self.reading_info_hint)
        self.reading_info_panel.hide()
        self.reading_info_panel.setCursor(Qt.ArrowCursor)

    def current_page_label(self) -> QLabel:
        return self.right if getattr(self, "pane_page_indexes", {}).get("right") == self.index else self.left

    def page_fit_width(self, index: int, label: QLabel) -> float:
        image_width, image_height = self.image_size(index)
        if image_width <= 0 or image_height <= 0:
            return float(max(1, label.width()))
        return min(label.width(), label.height() * image_width / image_height)

    def current_page_image_rect(self) -> tuple[float, float, float, float]:
        """Current page's actual image rectangle in movable-content coordinates."""
        label = self.current_page_label()
        image_width, image_height = self.image_size(self.index)
        if image_width <= 0 or image_height <= 0:
            return float(label.x()), float(label.y()), float(label.width()), float(label.height())
        scale = min(label.width() / image_width, label.height() / image_height)
        width = image_width * scale
        height = image_height * scale
        alignment = label.alignment()
        if alignment & Qt.AlignRight:
            x = label.x() + label.width() - width
        elif alignment & Qt.AlignLeft:
            x = label.x()
        else:
            x = label.x() + (label.width() - width) / 2
        if alignment & Qt.AlignTop:
            y = label.y()
        elif alignment & Qt.AlignBottom:
            y = label.y() + label.height() - height
        else:
            y = label.y() + (label.height() - height) / 2
        return x, y, width, height

    def viewport_zoom_for_mode(self, mode: str) -> float:
        self.viewport.reset_view()
        if mode == "fit" or not self.pages:
            return 1.0
        label = self.current_page_label()
        fitted_width = self.page_fit_width(self.index, label)
        if fitted_width <= 0:
            return 1.0
        image_width, _image_height = self.image_size(self.index)
        if mode == "actual" and image_width > 0:
            return actual_size_zoom_factor(
                image_width, fitted_width, self.viewport.devicePixelRatioF()
            )
        return self.viewport.width() / fitted_width

    def set_viewport_zoom(
        self,
        zoom: float,
        *,
        mode: str = "custom",
        top: bool = False,
        focus_page: bool = False,
        anchor=None,
        normal_range: bool = True,
    ) -> None:
        if not isfinite(zoom):
            return
        zoom = max(0.01, float(zoom))
        if normal_range:
            zoom = min(MAX_ZOOM_FACTOR, max(MIN_ZOOM_FACTOR, zoom))
        self.viewport.set_zoom_factor(zoom, anchor=anchor, top=top)
        if focus_page:
            self.viewport.focus_content_rect(self.current_page_image_rect(), top=top)
        self.clear_queued_display_requests()
        self.refresh_visible_display(high_quality=not self.fast_resize_render)
        if hasattr(self, "zoom_value_label"):
            self.zoom_value_label.setText(tr("全体比 ×{factor}", factor=f"{zoom:.2f}"))
        if hasattr(self, "zoom_mode_combo"):
            blocked = self.zoom_mode_combo.blockSignals(True)
            try:
                self.zoom_mode_combo.setCurrentIndex(self.zoom_mode_combo.findData(mode))
            finally:
                self.zoom_mode_combo.blockSignals(blocked)
        self.viewport_auto_mode_signature = (
            self.viewport_mode_signature(mode) if mode in {"width", "actual"} else None
        )

    def on_zoom_mode_changed(self) -> None:
        mode = self.zoom_mode_combo.currentData()
        if not isinstance(mode, str) or mode == "custom":
            return
        self.set_viewport_zoom(
            self.viewport_zoom_for_mode(mode),
            mode=mode,
            top=mode == "width",
            focus_page=mode in {"width", "actual"},
            normal_range=mode != "actual",
        )

    def zoom_in(self) -> None:
        self.set_viewport_zoom(self.viewport.zoom_factor * ZOOM_STEP, mode="custom")

    def zoom_out(self) -> None:
        self.set_viewport_zoom(self.viewport.zoom_factor / ZOOM_STEP, mode="custom")

    def viewport_mode_signature(self, mode: str) -> tuple:
        image_size = self.image_size(self.index) if 0 <= self.index < len(self.pages) else (0, 0)
        return (
            mode,
            self.index,
            self.page_layout_mode,
            self.reading_direction,
            self.spread_order,
            self.cover_single,
            self.viewport.width(),
            self.viewport.height(),
            round(self.viewport.devicePixelRatioF(), 4),
            image_size,
        )

    def reapply_auto_viewport_mode_if_needed(self) -> None:
        """Keep W/actual tied to the visible original page, not a prior one."""
        if not hasattr(self, "zoom_mode_combo"):
            return
        mode = self.zoom_mode_combo.currentData()
        if mode not in {"width", "actual"}:
            return
        signature = self.viewport_mode_signature(mode)
        if signature == self.viewport_auto_mode_signature:
            return
        pending_focus = self.pending_auto_page_focus
        self.pending_auto_page_focus = None
        self.set_viewport_zoom(
            self.viewport_zoom_for_mode(mode),
            mode=mode,
            top=mode == "width",
            focus_page=True,
            normal_range=mode != "actual",
        )
        if pending_focus is not None:
            image_x, image_y, image_width, image_height = self.current_page_image_rect()
            self.viewport.center_content_point(
                (image_x + image_width * pending_focus[0], image_y + image_height * pending_focus[1])
            )

    def capture_auto_page_focus_for_resize(self) -> None:
        """Remember the visible point in an auto-sized page before a resize."""
        if not hasattr(self, "zoom_mode_combo") or self.zoom_mode_combo.currentData() not in {"width", "actual"}:
            return
        image_x, image_y, image_width, image_height = self.current_page_image_rect()
        if image_width <= 0 or image_height <= 0:
            return
        content = self.viewport.content.geometry()
        relative_x = (self.viewport.width() / 2 - content.x() - image_x) / image_width
        relative_y = (self.viewport.height() / 2 - content.y() - image_y) / image_height
        self.pending_auto_page_focus = (
            min(1.0, max(0.0, relative_x)),
            min(1.0, max(0.0, relative_y)),
        )

    def dismiss_reading_overlay(self) -> None:
        self.cancel_page_jump_input()
        self.reading_info_visible = False
        self.reading_info_panel.hide()
        self.setFocus(Qt.OtherFocusReason)

    def mark_page_jump_input_dirty(self, _text: str) -> None:
        self.reading_page_input_dirty = True

    def mark_page_jump_value_dirty(self, _value: int) -> None:
        self.reading_page_input_dirty = True

    def sync_page_jump_spin(self, page_number: int) -> None:
        signals_were_blocked = self.reading_page_spin.blockSignals(True)
        try:
            self.reading_page_spin.setValue(page_number)
            line_edit = self.reading_page_spin.lineEdit()
            if line_edit is not None:
                line_edit.setText(self.reading_page_spin.text())
        finally:
            self.reading_page_spin.blockSignals(signals_were_blocked)

    def cancel_page_jump_input(self) -> None:
        if not hasattr(self, "reading_page_spin"):
            return
        current_page = min(max(self.index + 1, 1), max(1, len(self.pages)))
        self.reading_page_input_dirty = False
        self.sync_page_jump_spin(current_page)

    def confirm_page_jump(self) -> bool:
        if not self.pages or not hasattr(self, "reading_page_spin"):
            return False
        self.reading_page_spin.interpretText()
        return self.jump_to_page(self.reading_page_spin.value())

    def jump_to_page(self, page_number: int) -> bool:
        """Move to a one-based physical page without changing its meaning by RTL."""
        if (
            isinstance(page_number, bool)
            or not isinstance(page_number, int)
            or page_number < 1
            or page_number > len(self.pages)
        ):
            return False
        target_index = page_number - 1
        if self.page_layout_mode == "spread":
            target_index = standard_spread_index(target_index, self.cover_single)
        if target_index == self.index:
            self.reading_page_input_dirty = False
            self.update_reading_info()
            return True
        self.reading_page_input_dirty = False
        self.clear_queued_visible_requests()
        self.index = target_index
        self.invalidate_prefetch_for_navigation()
        self.render_spread()
        self.request_prefetch()
        self.record_correction_miss()
        self.notify_page_changed()
        self.update_spread_status()
        self.update_next_book_action()
        return True

    def update_reader_action_states(self) -> None:
        if not hasattr(self, "original_check"):
            return
        states = {
            "settings": self.controls_visible,
            "original": self.original_check.isChecked(),
            "fullscreen": self.is_fullscreen,
            "layout": self.page_layout_mode == "spread",
        }
        for action, buttons in self.reader_action_buttons.items():
            for button in buttons:
                if action in states:
                    button.setChecked(states[action])
                if action == "original":
                    button.set_title(tr("補正版に戻る" if states[action] else "原画と比較"))
                elif action == "fullscreen":
                    button.set_title(tr("全画面を解除" if states[action] else "全画面"))
                elif action == "layout":
                    button.set_title(tr("見開き" if states[action] else "単ページ"))
        for name, button in getattr(self, "preset_buttons", {}).items():
            button.setChecked(name == self.current_quality_preset)
        for mode, button in getattr(self, "layout_buttons", {}).items():
            button.setChecked(mode == self.page_layout_mode)

    def on_settings_mode_changed(self) -> None:
        mode = self.settings_mode_combo.currentData()
        self.apply_settings_mode(str(mode or "simple"), persist=True)

    def apply_settings_mode(self, mode: str, *, persist: bool) -> None:
        self.settings_ui_mode = "manual" if mode == "manual" else "simple"
        index = self.settings_mode_combo.findData(self.settings_ui_mode)
        if index >= 0 and self.settings_mode_combo.currentIndex() != index:
            self.settings_mode_combo.blockSignals(True)
            self.settings_mode_combo.setCurrentIndex(index)
            self.settings_mode_combo.blockSignals(False)
        is_manual = self.settings_ui_mode == "manual"
        self.simple_panel.setVisible(True)
        self.advanced_toggle.setChecked(is_manual)
        self.advanced_panel.setVisible(is_manual)
        self.apply_button.setVisible(is_manual)
        self.apply_help.setVisible(is_manual)
        self.parameter_status.setVisible(is_manual)
        self.quality_engine_label.setVisible(is_manual)
        self.quality_prefetch_label.setVisible(is_manual)
        if persist:
            self.persist_quality_preferences()

    def restore_quality_preferences(self) -> None:
        preset = None
        for name in (self.initial_quality_preset, self.quality_preferences["selected_preset"], "自然"):
            if name:
                preset = self.find_quality_preset(name)
            if preset is not None:
                break
        if preset is not None:
            self.apply_preset(preset, render=False, persist=False, request_prefetch=False)

    def _sync_initial_page_layout_controls(self) -> None:
        """Reflect the constructor layout choice without scheduling a render."""
        mode = self.page_layout_mode
        self.viewport.set_spread_visible(mode == "spread")
        for button in (
            self.shift_back_button,
            self.shift_forward_button,
            self.swap_button,
            self.reset_spread_button,
        ):
            button.setEnabled(mode == "spread")
        combo_index = self.page_layout_combo.findData(mode)
        if combo_index >= 0:
            signals_were_blocked = self.page_layout_combo.blockSignals(True)
            try:
                self.page_layout_combo.setCurrentIndex(combo_index)
            finally:
                self.page_layout_combo.blockSignals(signals_were_blocked)
        for name, button in self.layout_buttons.items():
            button.setChecked(name == mode)
        self.update_spread_status()

    def find_quality_preset(self, name: str) -> dict | None:
        return next(
            (preset for preset in [*PRESETS, *self.custom_presets] if preset["name"] == name),
            None,
        )

    def apply_preset(
        self,
        preset: dict,
        *,
        render: bool = True,
        persist: bool = True,
        request_prefetch: bool = True,
    ) -> None:
        is_original = preset.get("mode") == "original"
        if not is_original:
            self.set_engine_controls(preset)
            self.on_processing_settings_changed()
        self.original_check.blockSignals(True)
        self.original_check.setChecked(is_original)
        self.original_check.blockSignals(False)
        self.current_quality_preset = preset["name"]
        self.quality_preset_for_state = preset["name"]
        if not is_original:
            self.last_corrected_preset_name = preset["name"]
        displayed_name = display_preset_name(preset["name"])
        self.preset_status.setText(tr("選択中: {name}", name=displayed_name))
        if is_original:
            self.parameter_status.setText(tr("原画表示に切り替えました。補正処理は行いません。"))
        else:
            self.parameter_status.setText(
                tr(
                    "{name}に変更しました。補正はバックグラウンドで行います。",
                    name=displayed_name,
                )
            )
        if persist:
            self.persist_quality_preferences()
        self.update_quality_state()
        if render:
            self.render_spread()
        if request_prefetch and not is_original:
            self.request_prefetch()

    def set_engine_controls(self, preset: dict) -> None:
        model = str(preset.get("model", "models-se"))
        options = MODEL_NOISE_OPTIONS.get(model, ["0"])
        controls = (
            self.scale_spin,
            self.noise_combo,
            self.tile_spin,
            self.threshold_spin,
            self.model_combo,
            self.tta_check,
        )
        for control in controls:
            control.blockSignals(True)
        try:
            self.model_combo.setCurrentText(model)
            self.noise_combo.clear()
            self.noise_combo.addItems(options)
            self.noise_combo.setCurrentText(str(preset.get("noise", "0")))
            self.scale_spin.setValue(int(preset.get("scale", 2)))
            self.tile_spin.setValue(int(preset.get("tile", 0)))
            self.threshold_spin.setValue(int(preset.get("threshold", self.upscale_height_threshold_default)))
            self.tta_check.setChecked(bool(preset.get("tta", False)))
        finally:
            for control in controls:
                control.blockSignals(False)

    def current_custom_preset(self, name: str) -> dict | None:
        return validate_quality_preset(
            {
                "name": name,
                "model": self.model_combo.currentText(),
                "scale": self.scale_spin.value(),
                "noise": self.noise_combo.currentText(),
                "tile": self.tile_spin.value(),
                "threshold": self.threshold_spin.value(),
                "tta": self.tta_check.isChecked(),
                "description": (
                    f"{self.model_combo.currentText()} / {self.scale_spin.value()}倍 / "
                    f"noise {self.noise_combo.currentText()}"
                ),
            }
        )

    def refresh_custom_preset_combo(self, selected_name: str | None = None) -> None:
        self.custom_preset_combo.blockSignals(True)
        self.custom_preset_combo.clear()
        self.custom_preset_combo.addItem(tr("保存済み設定を選択"), None)
        for preset in sorted(self.custom_presets, key=lambda item: item["name"].casefold()):
            self.custom_preset_combo.addItem(preset["name"], preset["name"])
        if selected_name:
            index = self.custom_preset_combo.findData(selected_name)
            if index >= 0:
                self.custom_preset_combo.setCurrentIndex(index)
        self.custom_preset_combo.blockSignals(False)

    def load_selected_custom_preset(self) -> None:
        name = self.custom_preset_combo.currentData()
        preset = self.find_quality_preset(str(name)) if name else None
        if preset is None:
            self.parameter_status.setText(tr("読み込むカスタム設定を選んでください。"))
            return
        self.apply_preset(preset)

    def save_current_custom_preset(self) -> None:
        name, accepted = QInputDialog.getText(self, tr("カスタム設定を保存"), tr("設定名"))
        if not accepted or not name.strip():
            return
        if name.strip() in {preset["name"] for preset in PRESETS}:
            QMessageBox.warning(
                self,
                tr("保存できません"),
                tr("原画・自然・クリーニング・高画質とは別の名前を付けてください。"),
            )
            return
        preset = self.current_custom_preset(name.strip())
        if preset is None:
            QMessageBox.warning(
                self,
                tr("保存できません"),
                tr("現在のモデルとパラメータの組み合わせは保存できません。"),
            )
            return
        existing = next((item for item in self.custom_presets if item["name"] == preset["name"]), None)
        if existing is not None:
            answer = QMessageBox.question(
                self,
                tr("設定を上書き"),
                tr("「{name}」を現在の値で上書きしますか？", name=preset["name"]),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            self.custom_presets.remove(existing)
        self.custom_presets.append(preset)
        self.current_quality_preset = preset["name"]
        self.quality_preset_for_state = preset["name"]
        self.last_corrected_preset_name = preset["name"]
        self.refresh_custom_preset_combo(preset["name"])
        self.persist_quality_preferences()
        self.parameter_status.setText(
            tr("カスタム設定「{name}」を保存しました。", name=preset["name"])
        )
        self.update_quality_state()
        self.render_spread()
        self.request_prefetch()

    def delete_selected_custom_preset(self) -> None:
        name = self.custom_preset_combo.currentData()
        preset = next((item for item in self.custom_presets if item["name"] == name), None)
        if preset is None:
            self.parameter_status.setText(tr("削除するカスタム設定を選んでください。"))
            return
        answer = QMessageBox.question(
            self,
            tr("カスタム設定を削除"),
            tr("「{name}」を削除しますか？", name=preset["name"]),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.custom_presets.remove(preset)
        if self.current_quality_preset == preset["name"]:
            self.current_quality_preset = "カスタム補正"
        if self.quality_preset_for_state == preset["name"]:
            self.quality_preset_for_state = "カスタム補正"
            self.last_corrected_preset_name = "カスタム補正"
        self.refresh_custom_preset_combo()
        self.persist_quality_preferences()
        self.parameter_status.setText(
            tr("カスタム設定「{name}」を削除しました。", name=preset["name"])
        )
        self.update_quality_state()

    def persist_quality_preferences(self) -> None:
        save_quality_preferences(
            self.settings_path,
            ui_mode=self.settings_ui_mode,
            selected_preset=self.quality_preset_for_state,
            custom_presets=self.custom_presets,
        )

    def on_original_compare_changed(self) -> None:
        visible_indexes = self.visible_page_indexes()
        self.clear_queued_display_requests()
        self.display_pixmap_cache.clear()
        self.left.clear()
        self.right.clear()
        if self.original_check.isChecked():
            self.current_quality_preset = "原画"
            if visible_indexes and all(self.should_skip_upscale(index) for index in visible_indexes):
                self.parameter_status.setText(
                    tr("この見開きは高解像度のため補正対象外です。原画と補正版は同じ表示です。")
                )
            elif self.visible_missing_correction_indexes(visible_indexes):
                self.parameter_status.setText(
                    tr("原画を表示中です。補正版がまだないページは、チェック解除後に生成します。")
                )
            else:
                self.parameter_status.setText(tr("原画を表示中です。チェックを外すと補正版に戻ります。"))
        elif self.current_quality_preset == "原画":
            self.current_quality_preset = self.last_corrected_preset_name
        if not self.original_check.isChecked():
            if visible_indexes and all(self.should_skip_upscale(index) for index in visible_indexes):
                self.parameter_status.setText(
                    tr("この見開きは高解像度のため補正対象外です。原画を表示します。")
                )
            elif self.visible_missing_correction_indexes(visible_indexes):
                self.parameter_status.setText(
                    tr("この見開きはまだ補正待ちです。現在ページを優先して生成します。")
                )
                self.request_prefetch()
            else:
                self.parameter_status.setText(
                    tr("補正版を表示中です。チェックすると原画へ切り替わります。")
                )
        self.update_quality_state()
        self.render_spread(high_quality=True)
        self.left.repaint()
        self.right.repaint()

    def stop_prefetch(self, message: str) -> None:
        self.prefetch_suspended = True
        if hasattr(self, "parameter_status"):
            self.parameter_status.setText(tr("待機中"))
        self.statusBar().showMessage(message, 6000)
        self.update_quality_state()

    def on_model_changed(self, model: str, announce: bool = True) -> None:
        options = MODEL_NOISE_OPTIONS.get(model, ["0"])
        current_noise = self.noise_combo.currentText()
        selected_noise = current_noise if current_noise in options else "0" if "0" in options else options[0]
        self.noise_combo.blockSignals(True)
        self.noise_combo.clear()
        self.noise_combo.addItems(options)
        self.noise_combo.setCurrentText(selected_noise)
        self.noise_combo.blockSignals(False)
        if model == "models-pro" and self.scale_spin.value() < 3:
            self.scale_spin.setValue(3)
        if announce and current_noise and current_noise not in options and hasattr(self, "parameter_status"):
            self.parameter_status.setText(
                tr(
                    "{model} では noise {noise} は使えません。{selected} に変更しました。",
                    model=model,
                    noise=current_noise,
                    selected=selected_noise,
                )
            )
        if announce:
            self.on_processing_settings_changed()

    def on_processing_settings_changed(self) -> None:
        self.processing_generation += 1
        self.prefetch_suspended = False
        self.processed_pages = [None] * len(self.pages)
        self.clear_queued_display_requests()
        self.display_pixmap_cache.clear()
        self.correction_cache.clear_path_memo()
        self.last_disk_cache_prune_signature = None
        if bool(getattr(self, "original_check", None) and self.original_check.isChecked()):
            self.current_quality_preset = "原画"
        elif hasattr(self, "model_combo"):
            self.current_quality_preset = "カスタム補正"
            self.last_corrected_preset_name = "カスタム補正"
        if hasattr(self, "model_combo"):
            self.quality_preset_for_state = "カスタム補正"
        if hasattr(self, "parameter_status") and not self.upscale_running and not self.prefetch_running:
            self.parameter_status.setText(tr("設定を変更しました。古い先読み結果は使いません。"))
        if hasattr(self, "quality_mode_label"):
            self.update_quality_state()

    def help_label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        return label

    def help_text(self) -> str:
        return viewer_shortcuts_text(self.reading_direction, self.available_reader_actions())

    def current_quality_mode(self) -> str:
        if bool(getattr(self, "original_check", None) and self.original_check.isChecked()):
            return tr("原画")
        return display_preset_name(self.current_quality_preset)

    def current_noise_label(self) -> str:
        if not hasattr(self, "noise_combo"):
            return tr("自然")
        noise = self.noise_combo.currentText()
        return f"{noise} ({tr(NOISE_LABELS.get(noise, '調整'))})"

    def correction_state_text(self, visible_indexes: list[int] | None = None) -> str:
        if bool(getattr(self, "original_check", None) and self.original_check.isChecked()):
            return tr("原画表示中")
        if not visible_indexes:
            visible_indexes = self.visible_page_indexes()
        if not visible_indexes:
            return tr("ページなし")
        if any(self.should_skip_upscale(index) for index in visible_indexes):
            if len(visible_indexes) > 1:
                return tr("片側が高解像度のため見開き原画")
            return tr("高解像度のため補正スキップ")
        missing = self.visible_missing_correction_indexes(visible_indexes)
        if not missing:
            return tr("補正済み")
        if self.settings_ui_mode == "simple":
            return tr("原画表示中・補正準備中")
        if self.upscale_running:
            return tr("現在の見開きを補正中")
        if self.prefetch_running:
            return tr("先読み補正中 / 未処理 p.{page}", page=missing[0] + 1)
        return tr("原画表示中・補正待ち p.{page}", page=missing[0] + 1)

    def prefetch_state_text(self) -> str:
        if not self.prefetch_enabled:
            return tr("オフ / 0ページ")
        if self.prefetch_suspended:
            return tr("停止中 / 原画表示継続")
        if self.prefetch_running:
            return tr("生成中 / 自動{count}ページ先", count=self.adaptive_prefetch_count)
        return tr("自動 / {count}ページ先", count=self.adaptive_prefetch_count)

    def update_quality_state(self) -> None:
        if not hasattr(self, "quality_mode_label"):
            return
        model = self.model_combo.currentText() if hasattr(self, "model_combo") else "models-se"
        scale = self.scale_spin.value() if hasattr(self, "scale_spin") else 2
        threshold = self.threshold_spin.value() if hasattr(self, "threshold_spin") else self.upscale_height_threshold_default
        self.quality_mode_label.setText(tr("画質: {mode}", mode=self.current_quality_mode()))
        self.quality_engine_label.setText(tr("エンジン: Real-CUGAN / {model}", model=model))
        if self.settings_ui_mode == "simple":
            self.quality_correction_label.setText(
                tr("状態: {state}", state=self.correction_state_text())
            )
        else:
            self.quality_correction_label.setText(
                tr("状態: {state}", state=self.correction_state_text())
                + f" / {scale}x / noise {self.current_noise_label()}"
            )
        self.quality_prefetch_label.setText(
            tr(
                "先読み: {state} / 縦{threshold}px以上は原画",
                state=self.prefetch_state_text(),
                threshold=threshold,
            )
        )

        self.update_reader_action_states()

    def is_right_bound(self) -> bool:
        return self.reading_direction == "rtl"

    def is_spread_reversed(self) -> bool:
        return self.spread_order == "rtl"

    def eventFilter(self, watched, event) -> bool:
        self.track_cursor_activity(watched, event)
        if watched in {getattr(self, "left", None), getattr(self, "right", None)}:
            if event.type() == QEvent.Wheel:
                modifiers = event.modifiers()
                if (
                    modifiers & (Qt.ControlModifier | Qt.MetaModifier)
                    and self.reader_may_handle_viewport_input(watched)
                    and event.angleDelta().y()
                ):
                    factor = ZOOM_STEP if event.angleDelta().y() > 0 else 1 / ZOOM_STEP
                    anchor = self.viewport.mapFromGlobal(event.globalPosition().toPoint())
                    self.set_viewport_zoom(self.viewport.zoom_factor * factor, anchor=anchor)
                    return True
            if event.type() == QEvent.MouseButtonDblClick and event.button() in {Qt.LeftButton, Qt.RightButton}:
                self.suppress_next_mouse_release = True
                self.clear_mouse_press()
                return True
            if event.type() == QEvent.MouseButtonPress and event.button() in {Qt.LeftButton, Qt.RightButton}:
                # Some Qt platform event sequences omit the double-click
                # release. Never let its suppression consume a later click.
                self.suppress_next_mouse_release = False
                self.setFocus(Qt.MouseFocusReason)
                self.mouse_press_button = event.button()
                self.mouse_press_global_position = event.globalPosition()
                self.mouse_last_global_position = event.globalPosition()
                self.mouse_dragging = False
                return True
            if event.type() == QEvent.MouseMove and self.mouse_press_button is not None:
                current_position = event.globalPosition()
                if self.mouse_press_global_position is not None:
                    moved = (
                        abs(current_position.x() - self.mouse_press_global_position.x())
                        + abs(current_position.y() - self.mouse_press_global_position.y())
                    )
                    if moved > CLICK_DRAG_TOLERANCE_PX:
                        self.mouse_dragging = True
                if self.mouse_dragging and self.mouse_press_button == Qt.LeftButton:
                    previous_position = self.mouse_last_global_position or current_position
                    self.viewport.pan_by(
                        round(current_position.x() - previous_position.x()),
                        round(current_position.y() - previous_position.y()),
                    )
                self.mouse_last_global_position = current_position
                return True
            if event.type() == QEvent.MouseButtonRelease and event.button() in {Qt.LeftButton, Qt.RightButton}:
                if self.suppress_next_mouse_release:
                    self.suppress_next_mouse_release = False
                    self.clear_mouse_press()
                    return True
                if event.button() != self.mouse_press_button or self.mouse_press_global_position is None:
                    self.clear_mouse_press()
                    return True
                release_position = event.globalPosition()
                moved = (
                    abs(release_position.x() - self.mouse_press_global_position.x())
                    + abs(release_position.y() - self.mouse_press_global_position.y())
                )
                dragged = self.mouse_dragging
                self.clear_mouse_press()
                if dragged or moved > CLICK_DRAG_TOLERANCE_PX:
                    return True
                image_position = self.image_host.mapFromGlobal(release_position.toPoint())
                button = "right" if event.button() == Qt.RightButton else "left"
                action = reader_click_action(
                    image_position.x(),
                    self.image_host.width(),
                    self.reading_direction,
                    button,
                )
                self.handle_reader_click(action, bool(event.modifiers() & Qt.ShiftModifier))
                return True
        if event.type() == QEvent.KeyPress and self.reader_may_handle_key(event, watched) and self.handle_navigation_event(event):
            return True
        return super().eventFilter(watched, event)

    def reader_may_handle_key(self, event, watched=None) -> bool:
        if not self.isVisible() or not should_handle_global_shortcut(QApplication.activeModalWidget()):
            return False
        if QApplication.activePopupWidget() is not None:
            return False
        target = watched if isinstance(watched, QWidget) else QApplication.focusWidget()
        if target is not None and target is not self and not self.isAncestorOf(target):
            return False
        if event.key() == Qt.Key_Escape:
            return True
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QAbstractSpinBox, QComboBox)):
            return False
        if isinstance(focus, QAbstractButton) and event.key() in {Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter}:
            return False
        return not bool(event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier))

    def reader_may_handle_viewport_input(self, watched=None) -> bool:
        if not self.isVisible() or not should_handle_global_shortcut(QApplication.activeModalWidget()):
            return False
        if QApplication.activePopupWidget() is not None:
            return False
        if watched not in {getattr(self, "left", None), getattr(self, "right", None)}:
            return False
        focus = QApplication.focusWidget()
        return not isinstance(focus, (QLineEdit, QAbstractSpinBox, QComboBox))

    def clear_mouse_press(self) -> None:
        self.mouse_press_button = None
        self.mouse_press_global_position = None
        self.mouse_last_global_position = None
        self.mouse_dragging = False

    def handle_reader_click(self, action: str | None, one_page: bool = False) -> bool:
        if self.reading_info_visible:
            self.dismiss_reading_overlay()
            return True
        if action == "info":
            self.toggle_reading_info()
            return True
        if action == "next":
            self.move_by(1 if one_page else self.page_turn_step())
            return True
        if action == "previous":
            self.move_by(-1 if one_page else -self.page_turn_step())
            return True
        return False

    def resizeEvent(self, event) -> None:
        self.capture_auto_page_focus_for_resize()
        super().resizeEvent(event)
        self.position_reading_info_overlay()
        self.position_next_book_overlay()
        self.clear_queued_display_requests()
        self.fast_resize_render = True
        self.render_spread(high_quality=False)
        self.resize_quality_timer.start(self.resize_quality_delay_ms)

    def finish_resize_quality_render(self) -> None:
        self.fast_resize_render = False
        self.render_spread(high_quality=True)

    def keyPressEvent(self, event) -> None:
        if self.reader_may_handle_key(event) and self.handle_navigation_event(event):
            return
        super().keyPressEvent(event)

    def handle_navigation_event(self, event) -> bool:
        return self.handle_navigation_key(event.key(), event.modifiers())

    def handle_navigation_key(self, key: int, modifiers=Qt.NoModifier) -> bool:
        # Keep the previous distinction for a numeric-keypad modifier: arrows
        # remain reader navigation, while keypad zoom/mode keys are not treated
        # as the dedicated top-row shortcuts.
        if modifiers & Qt.KeypadModifier and key in {
            Qt.Key_Plus,
            Qt.Key_Equal,
            Qt.Key_Minus,
            Qt.Key_0,
            Qt.Key_1,
            Qt.Key_W,
            Qt.Key_T,
        }:
            return False
        key_names = {
            Qt.Key_Plus: "plus",
            Qt.Key_Equal: "equal",
            Qt.Key_Minus: "minus",
            Qt.Key_0: "0",
            Qt.Key_1: "1",
            Qt.Key_W: "w",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Space: "space",
            Qt.Key_Backspace: "backspace",
            Qt.Key_E: "e",
            Qt.Key_Q: "q",
            Qt.Key_F: "f",
            Qt.Key_P: "p",
            Qt.Key_V: "v",
            Qt.Key_O: "o",
            Qt.Key_B: "b",
            Qt.Key_T: "t",
            Qt.Key_H: "h",
            Qt.Key_Question: "question",
            Qt.Key_Escape: "escape",
        }
        key_name = key_names.get(key)
        if key_name is None:
            return False
        modifier_names = frozenset(
            name
            for flag, name in (
                (Qt.ShiftModifier, "shift"),
                (Qt.ControlModifier, "control"),
                (Qt.MetaModifier, "meta"),
                (Qt.AltModifier, "alt"),
            )
            if modifiers & flag
        )
        action = resolve_action(
            key_name,
            modifier_names,
            self.reading_direction,
            self.available_reader_actions(),
        )
        return self.invoke_reader_action(action) if action is not None else False

    def available_reader_actions(self) -> frozenset[str]:
        available = {"always"}
        if self.bookmark_callback is not None:
            available.add("bookmark_add")
        if self.bookmarks_provider is not None:
            available.add("bookmark_list")
        return frozenset(available)

    def invoke_reader_action(self, action: str) -> bool:
        if action == "next":
            self.move_by(self.page_turn_step())
        elif action == "previous":
            self.move_by(-self.page_turn_step())
        elif action == "forward_one":
            self.move_by(1)
        elif action == "back_one":
            self.move_by(-1)
        elif action == "zoom_in":
            self.zoom_in()
        elif action == "zoom_out":
            self.zoom_out()
        elif action == "fit":
            self.set_viewport_zoom(1.0, mode="fit")
        elif action == "width":
            self.set_viewport_zoom(self.viewport_zoom_for_mode("width"), mode="width", top=True, focus_page=True)
        elif action == "actual":
            self.set_viewport_zoom(
                self.viewport_zoom_for_mode("actual"), mode="actual", focus_page=True, normal_range=False
            )
        elif action == "fullscreen":
            self.toggle_fullscreen()
        elif action == "settings":
            self.toggle_controls()
        elif action == "layout":
            self.toggle_page_layout()
        elif action == "original":
            self.original_check.toggle()
        elif action == "bookmark":
            self.add_bookmark()
        elif action == "bookmarks":
            self.show_bookmarks()
        elif action == "pages":
            self.show_page_overview()
        elif action == "help":
            self.show_shortcuts_help()
        elif action == "escape":
            if self.reading_info_visible:
                self.dismiss_reading_overlay()
            elif self.is_fullscreen:
                self.toggle_fullscreen()
            else:
                self.close()
        else:
            return False
        return True

    def page_turn_step(self) -> int:
        return 1 if self.page_layout_mode == "single" else 2

    def on_page_layout_changed(self) -> None:
        self.set_page_layout(str(self.page_layout_combo.currentData()))

    def toggle_page_layout(self) -> None:
        mode = "single" if self.page_layout_mode == "spread" else "spread"
        self.set_page_layout(mode)

    def set_page_layout(self, mode: str) -> None:
        mode = "single" if mode == "single" else "spread"
        if mode == self.page_layout_mode:
            return
        self.page_layout_mode = mode
        if mode == "spread":
            self.index = standard_spread_index(self.index, self.cover_single)
        self.viewport.set_spread_visible(mode == "spread")
        for button in (
            self.shift_back_button,
            self.shift_forward_button,
            self.swap_button,
            self.reset_spread_button,
        ):
            button.setEnabled(mode == "spread")
        combo_index = self.page_layout_combo.findData(mode)
        if combo_index >= 0 and combo_index != self.page_layout_combo.currentIndex():
            self.page_layout_combo.blockSignals(True)
            self.page_layout_combo.setCurrentIndex(combo_index)
            self.page_layout_combo.blockSignals(False)
        self.clear_queued_visible_requests()
        self.invalidate_prefetch_for_navigation()
        self.render_spread(high_quality=True)
        self.update_spread_status()
        self.update_next_book_action()
        self.notify_page_changed()

    def move_by(self, step: int) -> None:
        if not self.pages:
            return
        previous_index = self.index
        if self.cover_single and step == 2 and self.index == 0:
            next_index = 1
        elif self.cover_single and step == -2 and self.index <= 1:
            next_index = 0
        else:
            next_index = self.index + step
        self.index = max(0, min(len(self.pages) - 1, next_index))
        if self.index != previous_index:
            self.clear_queued_visible_requests()
            self.record_navigation_speed(abs(self.index - previous_index))
            self.invalidate_prefetch_for_navigation()
        self.render_spread()
        if self.index != previous_index:
            # Correction scheduling must not wait for the resize debounce:
            # fast rendering affects display quality, not which page we need.
            self.request_prefetch()
            self.record_correction_miss()
        self.notify_page_changed()
        self.update_spread_status()
        self.update_next_book_action()

    def record_navigation_speed(self, pages_moved: int) -> None:
        now = time.monotonic()
        if self.last_navigation_at is not None and pages_moved > 0:
            interval_per_page = (now - self.last_navigation_at) / pages_moved
            if 0.05 <= interval_per_page <= 30:
                self.navigation_intervals.append(interval_per_page)
        self.last_navigation_at = now
        if not self.navigation_intervals:
            return
        self.adaptive_prefetch_count = adaptive_forward_prefetch_count(
            self.navigation_intervals,
            base_count=self.prefetch_count_default,
            correction_seconds_per_page=self.correction_seconds_per_page,
            lead_factor=correction_lead_factor(self.correction_misses),
        )

    def record_correction_miss(self) -> None:
        """Remember whether the spread just shown had to fall back to the original image."""
        if not self.prefetch_enabled or bool(getattr(self, "original_check", None) and self.original_check.isChecked()):
            return
        visible_indexes = self.visible_page_indexes()
        if not visible_indexes or all(self.should_skip_upscale(index) for index in visible_indexes):
            return
        self.correction_misses.append(bool(self.visible_missing_correction_indexes(visible_indexes)))

    def invalidate_prefetch_for_navigation(self) -> None:
        # A failed batch pauses automatic retries while the reader stays put.
        # A new navigation is an explicit opportunity to try again.
        self.prefetch_suspended = False
        self.prefetch_target_indexes = set(self.visible_and_prefetch_indexes())

    def notify_page_changed(self) -> None:
        if self.page_changed_callback is not None:
            self.page_state_save_timer.start(PAGE_STATE_SAVE_DEBOUNCE_MS)

    def flush_page_changed(self) -> None:
        self.page_state_save_timer.stop()
        if self.page_changed_callback is not None:
            self.page_changed_callback(self.index)

    def add_bookmark(self) -> None:
        if self.bookmark_callback is not None:
            result = self.bookmark_callback(self.index)
            if result is False:
                self.statusBar().showMessage(tr("このページにはしおりがあります。"))
            else:
                self.statusBar().showMessage(tr("しおりを追加しました: p.{page}", page=self.index + 1))

    def show_bookmarks(self) -> None:
        if self.bookmarks_provider is None:
            self.statusBar().showMessage(tr("しおり一覧を利用できません。"))
            return
        from mangacrisp_app.bookmark_dialog import BookmarkDialog

        bookmarks = list(self.bookmarks_provider() or [])
        dialog = BookmarkDialog(
            self,
            bookmarks,
            len(self.pages),
            delete_callback=self.bookmark_delete_callback,
            edit_callback=self.bookmark_edit_callback,
        )
        try:
            if (
                dialog.exec() == QDialog.DialogCode.Accepted
                and dialog.selected_page_index is not None
                and not self.jump_to_page(dialog.selected_page_index + 1)
            ):
                self.statusBar().showMessage(tr("しおりのページが見つかりません。"))
        finally:
            dialog.deleteLater()

    def show_page_overview(self) -> None:
        from mangacrisp_app.page_overview import PageOverviewDialog

        dialog = PageOverviewDialog(self, self.pages, self.index)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_page_index is not None:
                self.jump_to_page(dialog.selected_page_index + 1)
        finally:
            dialog.shutdown()
            dialog.deleteLater()
            self.activateWindow()
            self.setFocus(Qt.ActiveWindowFocusReason)

    def show_shortcuts_help(self) -> None:
        show_help_dialog(self, viewer_shortcuts_text(self.reading_direction, self.available_reader_actions()))
        self.activateWindow()
        self.setFocus(Qt.ActiveWindowFocusReason)

    def toggle_fullscreen(self) -> None:
        self.is_fullscreen = not self.is_fullscreen
        fullscreen_target = self.window() if self.embedded else self
        if self.is_fullscreen:
            self.statusBar().hide()
            fullscreen_target.showFullScreen()
            self.restart_cursor_hide_timer()
        else:
            fullscreen_target.showNormal()
            self.statusBar().show()
            self.show_cursor()
            self.cursor_hide_timer.stop()
        self.update_reader_action_states()
        QTimer.singleShot(0, lambda: self.render_spread(high_quality=True))

    CURSOR_ACTIVITY_EVENTS = frozenset(
        {
            QEvent.MouseMove,
            QEvent.MouseButtonPress,
            QEvent.MouseButtonRelease,
            QEvent.MouseButtonDblClick,
            QEvent.Wheel,
            QEvent.KeyPress,
        }
    ) if QEvent is not None else frozenset()

    CURSOR_SHOW_EVENTS = frozenset(
        {
            QEvent.WindowDeactivate,
            QEvent.FocusOut,
            QEvent.Leave,
        }
    ) if QEvent is not None else frozenset()

    def track_cursor_activity(self, watched, event) -> None:
        if not self.is_fullscreen or self.is_closing or not hasattr(self, "image_host"):
            return
        event_type = event.type()
        if event_type not in self.CURSOR_ACTIVITY_EVENTS and event_type not in self.CURSOR_SHOW_EVENTS:
            return
        if not isinstance(watched, QWidget) or watched.window() is not self.cursor_window():
            return
        if event_type in self.CURSOR_SHOW_EVENTS:
            if watched is self.cursor_window() or event_type == QEvent.FocusOut:
                self.show_cursor()
                self.restart_cursor_hide_timer()
            return
        self.note_cursor_activity()

    def cursor_window(self):
        return self.window() if self.embedded else self

    def cursor_auto_hide_state(self) -> CursorAutoHideState:
        window = self.cursor_window()
        pointer_over_overlay = False
        if hasattr(self, "image_host") and QCursor is not None:
            local = self.image_host.mapFromGlobal(QCursor.pos())
            child = self.image_host.childAt(local)
            pointer_over_overlay = child is not None and child not in {
                self.left,
                self.right,
                self.viewport,
            }
        return CursorAutoHideState(
            fullscreen=self.is_fullscreen,
            window_active=window.isActiveWindow(),
            drag_active=self.mouse_press_button is not None,
            modal_open=QApplication.activeModalWidget() is not None or QApplication.activePopupWidget() is not None,
            pointer_over_overlay=pointer_over_overlay,
            closing=self.is_closing,
        )

    def note_cursor_activity(self) -> None:
        self.show_cursor()
        self.restart_cursor_hide_timer()

    def restart_cursor_hide_timer(self) -> None:
        if self.is_fullscreen and not self.is_closing:
            self.cursor_hide_timer.start()
        else:
            self.cursor_hide_timer.stop()

    def hide_cursor_if_idle(self) -> None:
        state = self.cursor_auto_hide_state()
        if cursor_may_hide(state):
            if not self.cursor_hidden:
                self.image_host.setCursor(Qt.BlankCursor)
                self.cursor_hidden = True
            return
        self.show_cursor()
        if state.fullscreen and not state.closing:
            self.cursor_hide_timer.start()

    def show_cursor(self) -> None:
        if self.cursor_hidden:
            self.image_host.unsetCursor()
            self.cursor_hidden = False

    def toggle_controls(self) -> None:
        self.dismiss_reading_overlay()
        self.controls_visible = not self.controls_visible
        self.controls_panel.setVisible(self.controls_visible)
        self.render_spread()

    def swap_spread_order(self) -> None:
        self.spread_order = "rtl" if self.spread_order == "ltr" else "ltr"
        self.render_spread()
        self.update_spread_status()
        self.notify_page_changed()

    def reset_spread_alignment(self) -> None:
        if not self.pages:
            return
        self.index = standard_spread_index(self.index, self.cover_single)
        self.spread_order = default_spread_order(self.reading_direction)
        self.render_spread()
        self.update_spread_status()
        self.notify_page_changed()

    def update_spread_status(self) -> None:
        if not hasattr(self, "spread_status"):
            return
        if self.page_layout_mode == "single":
            self.spread_status.setText(tr("単ページ / 1画像ずつ / 中央表示"))
            return
        direction = tr("右綴じ") if self.is_right_bound() else tr("左綴じ")
        order = tr("左→右") if self.spread_order == "ltr" else tr("右→左")
        phase = tr("表紙単独") if self.cover_single else tr("通常")
        self.spread_status.setText(
            tr("{direction} / 表示順 {order} / {phase}", direction=direction, order=order, phase=phase)
        )

    def render_spread(self, high_quality: bool | None = None) -> None:
        if self.is_closing:
            return
        if not isinstance(high_quality, bool):
            high_quality = not self.fast_resize_render
        visible_indexes = self.visible_page_indexes()
        self.load_cached_outputs(visible_indexes)
        left_index, right_index = self.spread_pane_indexes()
        self.pane_page_indexes = {"left": left_index, "right": right_index}
        self.update_page_pane_alignment(left_index, right_index)
        self.reapply_auto_viewport_mode_if_needed()
        self.render_label(self.left, left_index, high_quality=high_quality)
        self.render_label(self.right, right_index, high_quality=high_quality)
        self.apply_ready_spread_pixmaps()
        page_text = page_progress_text(visible_indexes, len(self.pages))
        processed_count = sum(1 for path in self.processed_pages if path is not None)
        file_text = visible_file_names(self.pages, visible_indexes)
        self.statusBar().showMessage(
            f"{page_text}    {file_text}    processed {processed_count}/{len(self.pages)}"
        )
        self.update_quality_state()
        self.update_reading_info()
        if high_quality:
            self.display_warm_timer.start(DISPLAY_WARM_DEBOUNCE_MS)
            self.cache_maintenance_timer.start(CACHE_MAINTENANCE_DEBOUNCE_MS)
            self.request_prefetch()
        self.update_next_book_action()

    def spread_pane_indexes(self) -> tuple[int, int]:
        if self.page_layout_mode == "single":
            return self.index, -1
        if self.cover_single and self.index == 0:
            return (-1, 0) if self.is_right_bound() else (0, -1)
        if self.index + 1 >= len(self.pages):
            return (-1, self.index) if self.is_right_bound() else (self.index, -1)
        if self.is_spread_reversed():
            return self.index + 1, self.index
        return self.index, self.index + 1

    def refresh_visible_display(self, *, high_quality: bool) -> None:
        """Repaint a zoom/pan resize without touching correction scheduling."""
        pane_indexes = getattr(self, "pane_page_indexes", {})
        self.render_label(self.left, pane_indexes.get("left", -1), high_quality=high_quality)
        self.render_label(self.right, pane_indexes.get("right", -1), high_quality=high_quality)
        self.apply_ready_spread_pixmaps()

    def update_page_pane_alignment(self, left_index: int, right_index: int) -> None:
        if self.page_layout_mode == "single":
            self.viewport.set_pane_alignments(Qt.AlignCenter, Qt.AlignCenter)
            return
        is_pair = 0 <= left_index < len(self.pages) and 0 <= right_index < len(self.pages)
        if is_pair:
            self.viewport.set_pane_alignments(
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignLeft | Qt.AlignVCenter,
            )
            return
        self.viewport.set_pane_alignments(Qt.AlignCenter, Qt.AlignCenter)

    def render_label(self, label: QLabel, index: int, high_quality: bool = True) -> None:
        if index < 0 or index >= len(self.pages):
            self.desired_display_keys[id(label)] = None
            self.fallback_display_keys[id(label)] = None
            label.setText("")
            label.setPixmap(QPixmap())
            return
        display_path, normalize_color = self.display_source_for_index(index)
        original_path = self.pages[index]
        source_size = self.image_size(index)
        fallback_key = None
        if display_path != original_path:
            _fallback, fallback_key = self.request_display_pixmap(
                original_path,
                label,
                high_quality=high_quality,
                normalize_color=False,
                visible=True,
                source_size=source_size,
            )
        _cached, cache_key = self.request_display_pixmap(
            display_path,
            label,
            high_quality=high_quality,
            normalize_color=normalize_color,
            visible=True,
            source_size=source_size,
        )
        self.desired_display_keys[id(label)] = cache_key
        self.fallback_display_keys[id(label)] = fallback_key or cache_key

    def display_path_for_index(self, index: int) -> Path:
        return self.display_source_for_index(index)[0]

    def display_source_for_index(self, index: int) -> tuple[Path, bool]:
        visible_indexes = self.visible_page_indexes()
        show_original = index in visible_indexes and self.visible_spread_uses_original(visible_indexes)
        display_path = self.pages[index] if show_original else self.processed_pages[index] or self.pages[index]
        if display_path == self.pages[index]:
            return display_path, False
        # Old display-cache files were intentionally grayscale. Processed engine
        # output is already lossless PNG, so normalize that file directly.
        return display_path, True

    def visible_spread_uses_original(self, visible_indexes: list[int] | None = None) -> bool:
        if bool(getattr(self, "original_check", None) and self.original_check.isChecked()):
            return True
        if not visible_indexes:
            visible_indexes = self.visible_page_indexes()
        if len(visible_indexes) > 1 and any(self.should_skip_upscale(index) for index in visible_indexes):
            return True
        return bool(self.visible_missing_correction_indexes(visible_indexes))

    def display_cache_key(
        self,
        display_path: Path,
        target,
        high_quality: bool,
        normalize_color: bool,
        source_size: tuple[int, int] | None = None,
    ) -> tuple | None:
        key = display_image_key(
            display_path, target.width(), target.height(), high_quality, normalize_color
        )
        if key is None:
            return None
        device_pixel_ratio = target_device_pixel_ratio(target)
        _physical_width, _physical_height, effective_dpr = display_decode_target(
            target, device_pixel_ratio, source_size
        )
        # Keep the established key shape in the common fit/DPR-1 case.  The
        # tail separates capped or high-DPI images that share a logical size.
        if abs(device_pixel_ratio - 1.0) < 0.001 and abs(effective_dpr - 1.0) < 0.001:
            return key
        return (*key, _physical_width, _physical_height, round(effective_dpr * 1_000_000))

    def request_display_pixmap(
        self,
        display_path: Path,
        target,
        *,
        high_quality: bool = True,
        normalize_color: bool = False,
        visible: bool = False,
        source_size: tuple[int, int] | None = None,
    ) -> tuple[QPixmap | None, tuple | None]:
        key = self.display_cache_key(
            display_path, target, high_quality, normalize_color, source_size
        )
        if key is None:
            return None, None
        cached = self.display_pixmap_cache.get(key)
        if cached is not None:
            return cached, key
        priority = 1 if visible else 0
        pending_priority = self.pending_display_renders.get(key, -1)
        if pending_priority < priority or key not in self.pending_display_renders:
            self.pending_display_renders[key] = priority
            target_width, target_height, _effective_dpr = display_decode_target(
                target, target_device_pixel_ratio(target), source_size
            )
            task = DisplayRenderTask(
                self.signals,
                key,
                display_path,
                target_width,
                target_height,
                high_quality,
                normalize_color,
            )
            pool = self.visible_display_pool if visible else self.warm_display_pool
            pool.start(task)
        return None, key

    def cache_display_pixmap(self, key: tuple, pixmap: QPixmap) -> None:
        # Both corrected panes must remain ready together. Late warm/old-page
        # decodes must not evict the first pane while its partner is pending,
        # otherwise the spread can remain on the original indefinitely.
        protected = {
            candidate
            for candidate in (*self.desired_display_keys.values(), *self.fallback_display_keys.values())
            if candidate is not None
        }
        self.display_pixmap_cache.put(key, pixmap, protected=protected)

    def clear_queued_visible_requests(self) -> None:
        self.visible_display_pool.clear()
        self.warm_display_pool.clear()
        self.pending_display_renders.clear()

    def clear_queued_display_requests(self) -> None:
        self.visible_display_pool.clear()
        self.warm_display_pool.clear()
        self.pending_display_renders.clear()

    def on_display_image_done(self, key: tuple, image: QImage, elapsed_ms: int) -> None:
        if self.is_closing:
            return
        self.pending_display_renders.pop(key, None)
        if image.isNull():
            return
        self.display_decode_times_ms.append(elapsed_ms)
        pixmap = QPixmap.fromImage(image)
        if len(key) >= 10:
            pixmap.setDevicePixelRatio(key[-1] / 1_000_000)
        self.cache_display_pixmap(key, pixmap)
        self.apply_ready_spread_pixmaps()

    def apply_ready_spread_pixmaps(self) -> None:
        labels = (self.left, self.right)
        desired = [(label, self.desired_display_keys.get(id(label))) for label in labels]
        fallback = [(label, self.fallback_display_keys.get(id(label))) for label in labels]

        def ready(items: list[tuple[QLabel, tuple | None]]) -> bool:
            return all(key is None or key in self.display_pixmap_cache for _label, key in items)

        def still_shown(label: QLabel, key: tuple | None) -> bool:
            # The label already shows this same file at this size (only the
            # cache key's mtime changed), so keep it instead of flashing the
            # original while the re-decode is pending.
            return (
                key is not None
                and display_keys_show_same_image(self.shown_display_keys.get(id(label)), key)
                and not label.pixmap().isNull()
            )

        if not ready(desired) and all(
            key is None or key in self.display_pixmap_cache or still_shown(label, key) for label, key in desired
        ):
            for label, key in desired:
                if key is not None and key in self.display_pixmap_cache:
                    self.show_display_pixmap(label, key)
            return

        selected = desired if ready(desired) else fallback if ready(fallback) else None
        if selected is None:
            for label, key in desired:
                if key is not None:
                    self.clear_display_pixmap(label)
            return
        for label, key in selected:
            if key is None:
                self.clear_display_pixmap(label)
                continue
            self.show_display_pixmap(label, key)

    def show_display_pixmap(self, label: QLabel, key: tuple) -> None:
        pixmap = self.display_pixmap_cache[key]
        label.setText("")
        label.setPixmap(pixmap)
        self.shown_display_keys[id(label)] = key

    def clear_display_pixmap(self, label: QLabel) -> None:
        label.setText("")
        label.setPixmap(QPixmap())
        self.shown_display_keys[id(label)] = None

    def warm_display_pixmap_cache(self, indexes: list[int]) -> None:
        if not indexes:
            return
        targets = []
        seen_targets: set[tuple[int, int, float]] = set()
        labels = (self.left,) if self.page_layout_mode == "single" else (self.left, self.right)
        for target in labels:
            dimensions = (
                target.width(),
                target.height(),
                target_device_pixel_ratio(target),
            )
            if dimensions in seen_targets:
                continue
            seen_targets.add(dimensions)
            targets.append(target)
        for index in indexes:
            if index < 0 or index >= len(self.pages):
                continue
            display_path, normalize_color = self.display_source_for_index(index)
            source_size = self.image_size(index)
            for target in targets:
                self.request_display_pixmap(
                    display_path,
                    target,
                    high_quality=True,
                    normalize_color=normalize_color,
                    visible=False,
                    source_size=source_size,
                )

    def warm_nearby_display_cache(self) -> None:
        if self.is_closing:
            return
        indexes = prefetch_window_indexes(
            self.index,
            len(self.pages),
            self.visible_page_indexes(),
            DISPLAY_WARM_AHEAD_COUNT,
            DISPLAY_WARM_PREVIOUS_COUNT,
        )
        self.warm_display_pixmap_cache(indexes)

    def visible_page_indexes(self) -> list[int]:
        if self.index < 0 or self.index >= len(self.pages):
            return []
        if self.page_layout_mode == "single":
            return [self.index]
        if self.cover_single and self.index == 0:
            return [0]
        if self.index + 1 >= len(self.pages):
            return [self.index]
        return [self.index, self.index + 1]

    def return_to_bookshelf(self) -> None:
        """Save the reading position and close the reader so the bookshelf shows again."""
        if self.is_closing:
            return
        if self.is_fullscreen:
            self.toggle_fullscreen()
        self.flush_page_changed()
        self.close()

    def toggle_reading_info(self) -> None:
        self.reading_info_visible = not self.reading_info_visible
        self.position_reading_info_overlay()
        self.reading_info_panel.setVisible(self.reading_info_visible)
        self.reading_info_panel.raise_()
        self.update_reading_info()

    def position_reading_info_overlay(self) -> None:
        if not hasattr(self, "reading_info_panel") or not hasattr(self, "image_host"):
            return
        margin = 12
        width = min(580, max(1, self.image_host.width() - margin * 2))
        height = min(
            self.reading_overlay_preferred_height(width),
            max(1, self.image_host.height() - margin * 2),
        )
        x = max(0, (self.image_host.width() - width) // 2)
        y = max(0, (self.image_host.height() - height) // 2)
        self.reading_info_panel.setGeometry(x, y, width, height)
        if self.reading_info_panel.isVisible():
            self.reading_info_panel.raise_()

    def reading_overlay_preferred_height(self, width: int) -> int:
        """Measure fixed header/footer and scroll body before clamping the pane."""
        panel_layout = self.reading_info_panel.layout()
        if panel_layout is None or not hasattr(self, "reading_info_content"):
            return self.reading_info_panel.sizeHint().height()
        margins = panel_layout.contentsMargins()
        body_width = max(1, width - margins.left() - margins.right())
        body_layout = self.reading_info_content.layout()
        body_height = (
            body_layout.totalHeightForWidth(body_width)
            if body_layout is not None
            else self.reading_info_content.sizeHint().height()
        )
        header_height = panel_layout.itemAt(0).sizeHint().height()
        footer_height = (
            self.reading_info_bookshelf_button.sizeHint().height()
            + self.reading_info_hint.sizeHint().height()
        )
        return (
            margins.top()
            + header_height
            + body_height
            + footer_height
            + margins.bottom()
            + panel_layout.spacing() * 3
            # A vertical scrollbar reduces the body's effective width and can
            # add one wrapped line. Reserve its small style-dependent slack
            # so a pane that otherwise fits does not create a needless scroll.
            + 16
        )

    def position_next_book_overlay(self) -> None:
        if not hasattr(self, "next_book_banner") or not hasattr(self, "image_host"):
            return
        margin = 18
        self.next_book_banner.adjustSize()
        width = min(max(320, self.next_book_banner.sizeHint().width()), max(320, self.image_host.width() - margin * 2))
        height = max(54, self.next_book_banner.sizeHint().height())
        x = max(margin, (self.image_host.width() - width) // 2)
        y = max(margin, int(self.image_host.height() * 0.44) - height // 2)
        self.next_book_banner.setGeometry(x, y, width, height)
        if self.next_book_banner.isVisible():
            self.next_book_banner.raise_()

    def update_reading_info(self) -> None:
        if not hasattr(self, "reading_info_panel"):
            return
        visible_indexes = self.visible_page_indexes()
        page_text = page_progress_text(visible_indexes, len(self.pages))
        file_text = visible_file_names(self.pages, visible_indexes)
        quality_text = f"{self.current_quality_mode()} / {self.correction_state_text(visible_indexes)}"
        self.reading_info_label.setText(f"{page_text}    {quality_text}")
        self.reading_info_label.setToolTip(file_text)
        self.reading_progress.setRange(0, max(1, len(self.pages)))
        value = visible_indexes[-1] + 1 if visible_indexes else 0
        self.reading_progress.setValue(value)
        self.reading_progress.setFormat(page_text)
        if hasattr(self, "reading_page_spin") and not self.reading_page_input_dirty:
            current_page = min(max(self.index + 1, 1), max(1, len(self.pages)))
            self.sync_page_jump_spin(current_page)

    def is_at_end(self) -> bool:
        visible_indexes = self.visible_page_indexes()
        return bool(visible_indexes and visible_indexes[-1] >= len(self.pages) - 1)

    def update_next_book_action(self) -> None:
        if not hasattr(self, "next_book_button"):
            return
        visible = self.next_book_callback is not None and self.is_at_end()
        self.next_book_button.setVisible(visible)
        self.next_book_hint.setVisible(visible)
        if not visible:
            if hasattr(self, "next_book_banner"):
                self.next_book_banner.setVisible(False)
            return
        label = self.next_book_label or tr("次の巻")
        self.next_book_button.setText(tr("次の巻へ: {label}", label=label))
        self.next_book_hint.setText(tr("最後まで読んだので、続きの巻を開けます。"))
        if hasattr(self, "next_book_banner"):
            self.next_book_banner.setText(tr("次の巻へ: {label}", label=label))
            self.position_next_book_overlay()
            self.next_book_banner.setVisible(True)
            self.next_book_banner.raise_()

    def open_next_book(self) -> None:
        if self.next_book_callback is not None:
            self.next_book_callback()

    def visible_and_prefetch_indexes(self) -> list[int]:
        return prefetch_window_indexes(
            self.index,
            len(self.pages),
            self.visible_page_indexes(),
            self.adaptive_prefetch_count if self.prefetch_enabled else 0,
            self.previous_prefetch_count if self.prefetch_enabled else 0,
        )

    def visible_missing_correction_indexes(self, visible_indexes: list[int] | None = None) -> list[int]:
        if not visible_indexes:
            visible_indexes = self.visible_page_indexes()
        skipped = [index for index in visible_indexes if self.should_skip_upscale(index)]
        return missing_processed_indexes(self.processed_pages, visible_indexes, skipped)

    def image_size(self, index: int) -> tuple[int, int]:
        cached = self.image_size_cache.get(index)
        if cached is not None:
            return cached
        try:
            with Image.open(self.pages[index]) as image:
                size = image.size
        except Exception:  # noqa: BLE001 - provider failures must not break size-dependent UI.
            size = (0, 0)
        self.image_size_cache[index] = size
        return size

    def should_skip_upscale(self, index: int) -> bool:
        width, height = self.image_size(index)
        return bool(width and height and height >= self.threshold_spin.value())

    def load_cached_outputs(self, indexes: list[int]) -> None:
        if not hasattr(self, "scale_spin") or bool(
            getattr(self, "original_check", None) and self.original_check.isChecked()
        ):
            return
        for index in indexes:
            if index < 0 or index >= len(self.pages):
                continue
            processed_path = self.processed_pages[index]
            if processed_path is not None and not processed_path.is_file():
                self.processed_pages[index] = None
            output_path = self.correction_cache.cached_path(
                self.pages, index, self.current_parameter_key(), self.scale_spin.value(),
                active_outputs=self.active_output_paths,
            )
            if output_path is not None:
                self.processed_pages[index] = output_path

    def current_parameter_key(self) -> str:
        model = self.model_combo.currentText()
        model_suffix = f"_syncgap{PRO_SYNC_GAP}" if model == "models-pro" else ""
        tta = "_tta" if self.tta_check.isChecked() else ""
        return (
            f"scale{self.scale_spin.value()}_noise{self.noise_combo.currentText()}_"
            f"tile{self.tile_spin.value()}_{model}{model_suffix}{tta}"
        )

    def current_output_path(self, index: int) -> Path:
        return self.correction_cache.output_path(
            self.pages, index, self.current_parameter_key(), self.scale_spin.value()
        )

    def maintain_correction_cache(self) -> None:
        if (
            not hasattr(self, "scale_spin")
            or self.is_closing
        ):
            return
        keep = set(
            prefetch_window_indexes(
                self.index,
                len(self.pages),
                self.visible_page_indexes(),
                min(MAX_FORWARD_PREFETCH_COUNT, self.adaptive_prefetch_count + 4),
                max(DISK_PROTECTED_PREVIOUS_COUNT, self.previous_prefetch_count),
            )
        )
        signature = (self.current_parameter_key(), tuple(sorted(keep)))
        if signature == self.last_disk_cache_prune_signature:
            return

        for index, processed_path in enumerate(self.processed_pages):
            if index in keep or processed_path in self.active_output_paths:
                continue
            if processed_path is not None:
                self.processed_pages[index] = None
                # Release the session's working set, but keep completed PNGs
                # for backtracking. The size/age LRU below bounds disk usage;
                # a page-distance cutoff needlessly forced expensive repeats.
        protected = {self.current_output_path(index) for index in keep}
        self.correction_cache.prune(
            protected=protected, active_outputs=self.active_output_paths
        )
        self.last_disk_cache_prune_signature = signature

    def current_engine_settings(self) -> dict | None:
        model = self.model_combo.currentText()
        noise_text = self.noise_combo.currentText()
        if noise_text not in MODEL_NOISE_OPTIONS.get(model, []):
            self.parameter_status.setText(
                tr("{model} では noise {noise} は使えません。", model=model, noise=noise_text)
            )
            return None
        if model == "models-pro" and self.scale_spin.value() < 3:
            self.parameter_status.setText(
                tr("models-pro は scale 3 / noise 3 の実験用に制限しています。")
            )
            return None
        return {
            "scale": self.scale_spin.value(),
            "noise": int(noise_text),
            "tile": self.tile_spin.value(),
            "model": model,
            "tta": self.tta_check.isChecked(),
        }

    def process_current_spread(self) -> None:
        if self.upscale_running or self.prefetch_running:
            return
        indexes = self.visible_page_indexes()
        if not indexes:
            return
        settings = self.current_engine_settings()
        if settings is None:
            return
        output_paths = {index: self.current_output_path(index) for index in indexes if not self.should_skip_upscale(index)}
        if not output_paths:
            self.parameter_status.setText(tr("現在見開きは閾値以上のため原画表示です。"))
            self.update_quality_state()
            return
        self.upscale_running = True
        self.active_output_paths = set(output_paths.values())
        self.apply_button.setEnabled(False)
        generation = self.processing_generation
        parameter_key = self.current_parameter_key()
        self.running_parameter_key = parameter_key
        self.correction_queue.reset(output_paths, indexes)
        self.parameter_status.setText(tr("現在の見開きを補正中..."))
        self.update_quality_state()
        self.update_reading_info()
        threading.Thread(
            target=self._process_pages_worker,
            args=(settings, generation, parameter_key, False),
            daemon=True,
        ).start()

    def request_prefetch(self) -> None:
        if self.prefetch_suspended or self.is_closing:
            return
        if not self.prefetch_enabled:
            if hasattr(self, "quality_mode_label"):
                self.update_quality_state()
            return
        if bool(getattr(self, "original_check", None) and self.original_check.isChecked()):
            self.update_quality_state()
            return
        if self.prefetch_count_default <= 0:
            self.parameter_status.setText(
                tr("先読みページ数が0のため、先読み補正は実行しません。")
            )
            self.update_quality_state()
            return
        if realcugan_executable() is None:
            self.stop_prefetch(
                tr("AI先読み補正を停止しました。Real-CUGANエンジンが見つかりません。")
            )
            return
        self.prefetch_target_indexes = set(self.visible_and_prefetch_indexes())
        if self.prefetch_running:
            self.refresh_correction_queue()
        self.prefetch_request_timer.start(PREFETCH_DEBOUNCE_MS)

    def refresh_correction_queue(self) -> None:
        """Let a running prefetch pick up the current spread first instead of finishing its old list."""
        if self.running_parameter_key != self.current_parameter_key():
            return
        target_indexes = self.visible_and_prefetch_indexes()
        self.load_cached_outputs(target_indexes)
        additions: dict[int, Path] = {}
        for index in target_indexes:
            if self.should_skip_upscale(index) or self.processed_pages[index] is not None:
                continue
            if index == self.correction_queue.in_flight:
                continue
            output_path = self.current_output_path(index)
            if output_path.exists():
                continue
            additions[index] = output_path
        self.correction_queue.refresh(additions, target_indexes)
        self.active_output_paths.update(self.correction_queue.active_outputs)

    def start_prefetch(self) -> None:
        if self.is_closing:
            return
        if self.prefetch_running or self.upscale_running or not self.prefetch_enabled:
            return
        if self.prefetch_suspended:
            return
        if bool(getattr(self, "original_check", None) and self.original_check.isChecked()):
            self.update_quality_state()
            return
        if self.prefetch_count_default <= 0:
            self.parameter_status.setText(
                tr("先読みページ数が0のため、先読み補正は実行しません。")
            )
            self.update_quality_state()
            return
        if realcugan_executable() is None:
            self.stop_prefetch(
                tr("AI先読み補正を停止しました。Real-CUGANエンジンが見つかりません。")
            )
            return
        settings = self.current_engine_settings()
        if settings is None:
            return
        target_indexes = self.visible_and_prefetch_indexes()
        self.load_cached_outputs(target_indexes)
        indexes = [
            index
            for index in target_indexes
            if not self.should_skip_upscale(index) and not self.current_output_path(index).exists()
        ]
        if not indexes:
            self.update_quality_state()
            return
        output_paths = {index: self.current_output_path(index) for index in indexes}
        self.prefetch_running = True
        self.active_output_paths = set(output_paths.values())
        self.correction_queue.reset(output_paths, target_indexes)
        skipped_count = len(target_indexes) - len(indexes)
        suffix = tr(" / {count}ページはスキップ", count=skipped_count) if skipped_count else ""
        self.parameter_status.setText(
            tr("先読み補正中: {count}ページ{suffix}", count=len(indexes), suffix=suffix)
        )
        self.update_quality_state()
        self.update_reading_info()
        generation = self.processing_generation
        parameter_key = self.current_parameter_key()
        self.running_parameter_key = parameter_key
        threading.Thread(
            target=self._process_pages_worker,
            args=(settings, generation, parameter_key, True),
            daemon=True,
        ).start()

    def take_next_correction(self, is_prefetch: bool) -> tuple[int, Path] | None:
        targets = self.prefetch_target_indexes if is_prefetch else None
        return self.correction_queue.take(targets)

    def _process_pages_worker(
        self,
        settings: dict,
        generation: int,
        parameter_key: str,
        is_prefetch: bool,
    ) -> None:
        started = time.perf_counter()
        errors: list[str] = []
        completed_output_paths: dict[int, Path] = {}
        while generation == self.processing_generation and not self.is_closing:
            item = self.take_next_correction(is_prefetch)
            if item is None:
                break
            index, output_path = item
            try:
                source = self.pages[index]
                result = run_realcugan(
                    source,
                    output_path,
                    scale=settings["scale"],
                    noise=settings["noise"],
                    tile=settings["tile"],
                    model=settings["model"],
                    tta=settings["tta"],
                )
                if result.returncode != 0 or not result.output_exists:
                    errors.append(f"{source.name}: code {result.returncode}")
                else:
                    completed_output_paths[index] = output_path
                    self.signals.upscale_page_done.emit(
                        index,
                        output_path,
                        generation,
                        parameter_key,
                    )
            except Exception as exc:  # noqa: BLE001 - always release the job and report batch completion.
                # A lazy provider can itself fail. Do not index it again while
                # reporting that failure, or the worker never signals done.
                errors.append(f"Page {index + 1}: {exc}")
            finally:
                self.correction_queue.complete(index)
        self.signals.upscale_done.emit(
            round((time.perf_counter() - started) * 1000),
            completed_output_paths,
            errors,
            generation,
            parameter_key,
            is_prefetch,
        )

    def on_upscale_page_done(
        self,
        index: int,
        output_path: Path,
        generation: int,
        parameter_key: str,
    ) -> None:
        if (
            self.is_closing
            or generation != self.processing_generation
            or parameter_key != self.current_parameter_key()
        ):
            return
        if not output_path.is_file():
            return
        self.active_output_paths.discard(output_path)
        self.last_disk_cache_prune_signature = None
        self.cache_maintenance_timer.start(CACHE_MAINTENANCE_DEBOUNCE_MS)
        self.processed_pages[index] = output_path
        visible_indexes = self.visible_page_indexes()
        if index in visible_indexes and not self.visible_missing_correction_indexes(visible_indexes):
            self.render_spread(high_quality=True)
        else:
            self.warm_display_pixmap_cache([index])
            self.update_quality_state()
            self.update_reading_info()

    def on_upscale_done(
        self,
        elapsed_ms: int,
        output_paths: dict[int, Path],
        errors: list[str],
        generation: int,
        parameter_key: str,
        is_prefetch: bool,
    ) -> None:
        if self.is_closing:
            return
        stale = generation != self.processing_generation or parameter_key != self.current_parameter_key()
        if output_paths:
            measured_seconds = (elapsed_ms / 1000) / len(output_paths)
            self.correction_seconds_per_page = (
                self.correction_seconds_per_page * 0.7 + measured_seconds * 0.3
            )
        for index, output_path in output_paths.items():
            if not stale and output_path.exists():
                self.processed_pages[index] = output_path
        self.upscale_running = False
        self.prefetch_running = False
        self.running_parameter_key = None
        self.correction_queue.clear()
        self.active_output_paths.clear()
        self.last_disk_cache_prune_signature = None
        self.apply_button.setEnabled(True)
        if stale:
            self.parameter_status.setText(tr("古い先読み結果を破棄しました。"))
            self.load_cached_outputs(self.visible_and_prefetch_indexes())
            self.update_quality_state()
            self.request_prefetch()
            self.render_spread()
            return
        if errors:
            if is_prefetch:
                self.stop_prefetch(tr("AI先読み補正を停止しました。原画表示は継続します。"))
                self.render_spread()
                return
            self.parameter_status.setText(
                tr(
                    "補正エラーあり: {seconds:.1f}秒\n{errors}",
                    seconds=elapsed_ms / 1000,
                    errors="\n".join(errors[:2]),
                )
            )
        else:
            prefix = tr("先読み補正完了") if is_prefetch else tr("補正完了")
            self.parameter_status.setText(
                tr("{prefix}: {seconds:.1f}秒", prefix=prefix, seconds=elapsed_ms / 1000)
            )
        if not is_prefetch:
            self.original_check.setChecked(False)
        self.update_quality_state()
        self.render_spread()

    def closeEvent(self, event) -> None:
        if self.is_closing:
            super().closeEvent(event)
            return
        self.is_closing = True
        self.prefetch_suspended = True
        self.processing_generation += 1
        self.resize_quality_timer.stop()
        self.prefetch_request_timer.stop()
        self.display_warm_timer.stop()
        self.cache_maintenance_timer.stop()
        self.page_state_save_timer.stop()
        self.cursor_hide_timer.stop()
        self.show_cursor()
        self.clear_queued_display_requests()
        application = QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        self.left.removeEventFilter(self)
        self.right.removeEventFilter(self)
        self.left.clear()
        self.right.clear()
        self.display_pixmap_cache.clear()
        self.flush_page_changed()
        if self.cleanup_dir is not None:
            shutil.rmtree(self.cleanup_dir, ignore_errors=True)
            self.cleanup_dir = None
        if self.close_callback is not None:
            self.close_callback(self)
        super().closeEvent(event)


def parse_args(argv: list[str]) -> Namespace:
    parser = ArgumentParser(description="Manual two-page spread smoke viewer.")
    parser.add_argument("sample", nargs="?", help="folder/archive/image sample path")
    parser.add_argument("--bookshelf", action="store_true", help=f"open the {APP_NAME} bookshelf window")
    parser.add_argument("--smoke-test", action="store_true", help="open and close an isolated bookshelf for build validation")
    parser.add_argument("--smoke-close-ms", type=int, default=0, help="close a direct reader automatically for package validation")
    parser.add_argument("--processed-dir", help="directory containing processed images")
    parser.add_argument("--original", action="store_true", help="ignore processed images")
    parser.add_argument("--use-processed", action="store_true", help="auto-load processed benchmark images when available")
    parser.add_argument("--no-auto-prefetch", action="store_true", help="disable interactive correction prefetch")
    parser.add_argument("--no-cover-single", action="store_true", help="start with a normal two-page spread instead of a single cover")
    parser.add_argument(
        "--prefetch",
        type=int,
        default=DEFAULT_FORWARD_PREFETCH_COUNT,
        help="number of pages to correct ahead",
    )
    parser.add_argument(
        "--previous-prefetch",
        type=int,
        default=DEFAULT_PREVIOUS_PREFETCH_COUNT,
        help="number of previous pages to retain",
    )
    parser.add_argument("--skip-height", type=int, default=2234, help="skip correction when source height is this value or higher")
    parser.add_argument(
        "--direction",
        choices=["rtl", "ltr"],
        default="rtl",
        help="page-turn direction: rtl for right-bound manga, ltr for western comics",
    )
    parser.add_argument(
        "--spread-order",
        choices=["ltr", "rtl"],
        default=None,
        help="visual page placement in a spread: ltr shows current/current+1, rtl reverses them",
    )
    args, _unknown = parser.parse_known_args([arg for arg in argv[1:] if not arg.startswith("-psn_")])
    return args


def should_open_bookshelf(args: Namespace) -> bool:
    return bool(args.bookshelf or not args.sample)


def choose_source(sample_arg: str | None) -> Path:
    if sample_arg:
        return Path(sample_arg).expanduser()
    samples = discover_samples(SAMPLE_DIR)
    if not samples:
        raise SystemExit(f"No samples found. Put folders or archives in {SAMPLE_DIR}")
    return samples[0]


def choose_source_with_dialog(parent=None) -> Path:
    path, _selected_filter = QFileDialog.getOpenFileName(
        parent,
        f"Open {APP_NAME} sample",
        str(Path.home()),
        "PDF, images and archives (*.pdf *.zip *.cbz *.rar *.cbr *.7z *.cb7 *.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff *.avif);;All files (*)",
    )
    if not path:
        raise SystemExit("No sample selected.")
    return Path(path).expanduser()


def default_processed_dir(source: Path) -> Path:
    return DEFAULT_UPSCALE_DIR / source.stem / "realcugan"


def collect_processed_pages(source_pages: Sequence[Path], processed_dir: Path | None) -> list[Path | None]:
    if processed_dir is None or not processed_dir.is_dir():
        return [None] * len(source_pages)
    processed: list[Path | None] = []
    page_stem = getattr(source_pages, "page_stem", None)
    for zero_index in range(len(source_pages)):
        source_stem = (
            page_stem(zero_index)
            if callable(page_stem)
            else Path(source_pages[zero_index]).stem
        )
        pattern_stem = glob_escape(source_stem)
        candidates = sorted(processed_dir.glob(f"{zero_index + 1:04d}_{pattern_stem}_*.png"))
        processed.append(candidates[0].resolve() if candidates else None)
    return processed


def main() -> None:
    if PYSIDE_IMPORT_ERROR is not None:
        raise SystemExit("PySide6 is required: python3 -m pip install PySide6") from PYSIDE_IMPORT_ERROR
    args = parse_args(sys.argv)
    if not args.smoke_test:
        migrate_legacy_application_state()
        remove_legacy_display_cache()
    initialize_language(DEFAULT_QUALITY_SETTINGS_PATH)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    # Wayland compositors and XDG portals identify the app by its .desktop ID.
    app.setDesktopFileName(APP_BUNDLE_IDENTIFIER)
    if should_open_bookshelf(args):
        from mangacrisp_app.bookshelf import BookshelfWindow

        if args.smoke_test:
            from mangacrisp_app.library import (
                LibraryPaths,
                LibraryService,
                save_library_settings,
            )

            with TemporaryDirectory(prefix="mangacrisp-smoke-") as temporary_directory:
                paths = LibraryPaths.for_base_dir(Path(temporary_directory))
                save_library_settings(paths, library_dir_confirmed=True)
                window = BookshelfWindow(LibraryService.open(paths))
                window.show()
                QTimer.singleShot(500, app.quit)
                exit_code = app.exec()
                window.close()
                if exit_code:
                    raise SystemExit(exit_code)
            return

        window = BookshelfWindow()
        window.show()
        window.raise_()
        window.activateWindow()
        QTimer.singleShot(0, window.raise_)
        QTimer.singleShot(0, window.activateWindow)
        app.exec()
        return
    if args.sample:
        source = choose_source(args.sample)
    else:
        try:
            source = choose_source(None)
        except SystemExit:
            source = choose_source_with_dialog()
    pages, cleanup_dir = open_pages_for_viewer(source)
    if not pages:
        raise SystemExit(f"No images found in {source}")
    if args.original:
        processed_dir = None
    elif args.processed_dir:
        processed_dir = Path(args.processed_dir).expanduser()
    elif args.use_processed:
        processed_dir = default_processed_dir(source)
    else:
        processed_dir = None
    processed_pages = collect_processed_pages(pages, processed_dir)
    window = SpreadWindow(
        pages,
        source.name,
        cleanup_dir,
        processed_pages=processed_pages,
        reading_direction=args.direction,
        spread_order=args.spread_order or default_spread_order(args.direction),
        cover_single=not args.no_cover_single,
        auto_prefetch=not args.no_auto_prefetch,
        prefetch_count=args.prefetch,
        previous_prefetch_count=args.previous_prefetch,
        upscale_height_threshold=args.skip_height,
    )
    window.show()
    window.raise_()
    window.activateWindow()
    QTimer.singleShot(0, window.raise_)
    QTimer.singleShot(0, window.activateWindow)
    if args.smoke_close_ms > 0:
        QTimer.singleShot(args.smoke_close_ms, window.close)
    app.exec()


if __name__ == "__main__":
    main()
