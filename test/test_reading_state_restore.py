from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image

import mangacrisp_app.viewer as viewer_module
from mangacrisp_app.bookshelf import BookshelfWindow, reading_state_from_window
from mangacrisp_app.i18n import set_language
from mangacrisp_app.library import (
    LibraryPaths,
    LibraryService,
    ReadingState,
    save_library_settings,
)
from mangacrisp_app.quality_settings import (
    load_quality_preferences,
    save_quality_preferences,
)
from mangacrisp_app.viewer import SpreadWindow


def _pages(root: Path, count: int = 6) -> list[Path]:
    pages = []
    for index in range(count):
        path = root / f"{index:04d}.png"
        Image.new("RGB", (80, 120), (30 + index, 80, 140)).save(path)
        pages.append(path)
    return pages


def _close_reader(window: SpreadWindow, qapp) -> None:
    window.resize_quality_timer.stop()
    window.prefetch_request_timer.stop()
    window.display_warm_timer.stop()
    window.cache_maintenance_timer.stop()
    window.clear_queued_display_requests()
    window.visible_display_pool.waitForDone(5000)
    window.warm_display_pool.waitForDone(5000)
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_initial_saved_quality_layout_and_page_are_ready_before_first_render(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(viewer_module, "DEFAULT_UPSCALE_DIR", tmp_path / "upscale")
    monkeypatch.setattr(viewer_module, "DISPLAY_CACHE_DIR", tmp_path / "display")
    settings_path = tmp_path / "settings.json"
    save_quality_preferences(
        settings_path,
        ui_mode="simple",
        selected_preset="自然",
        custom_presets=[],
    )
    settings_before = settings_path.read_bytes()
    observed: list[tuple[int, str, str, str]] = []
    original_load = SpreadWindow.load_cached_outputs

    def observe_first_cache_load(window: SpreadWindow, indexes: list[int]) -> None:
        observed.append(
            (
                window.index,
                window.page_layout_mode,
                window.current_quality_preset,
                window.current_parameter_key(),
            )
        )
        original_load(window, indexes)

    monkeypatch.setattr(SpreadWindow, "load_cached_outputs", observe_first_cache_load)
    window = SpreadWindow(
        _pages(tmp_path),
        "initial state",
        auto_prefetch=False,
        settings_path=settings_path,
        initial_page_index=4,
        initial_page_layout="single",
        initial_quality_preset="高画質",
    )
    try:
        assert observed == [(4, "single", "高画質", "scale3_noise3_tile0_models-pro_syncgap1")]
        assert window.quality_preset_for_state == "高画質"
        assert window.right.isVisible() is False
        assert settings_path.read_bytes() == settings_before
    finally:
        _close_reader(window, qapp)


def test_original_compare_is_not_saved_but_original_quality_card_is(qapp, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(viewer_module, "DEFAULT_UPSCALE_DIR", tmp_path / "upscale")
    monkeypatch.setattr(viewer_module, "DISPLAY_CACHE_DIR", tmp_path / "display")
    settings_path = tmp_path / "settings.json"
    save_quality_preferences(settings_path, ui_mode="simple", selected_preset="自然", custom_presets=[])
    window = SpreadWindow(_pages(tmp_path), "quality state", auto_prefetch=False, settings_path=settings_path)
    try:
        high_quality = window.find_quality_preset("高画質")
        original = window.find_quality_preset("原画")
        assert high_quality is not None and original is not None
        window.apply_preset(high_quality, persist=False, request_prefetch=False)
        window.original_check.setChecked(True)  # O comparison state
        assert window.current_quality_preset == "原画"
        assert reading_state_from_window("book", window).correction_preset == "高画質"

        # Saving unrelated quality UI preferences while comparing must retain
        # the selected correction preset instead of converting it to Original.
        window.apply_settings_mode("manual", persist=True)
        assert load_quality_preferences(settings_path)["selected_preset"] == "高画質"

        window.select_quality_preset(original)
        assert window.quality_preset_for_state == "原画"
        window.original_check.setChecked(False)  # temporary compare toggled off
        assert reading_state_from_window("book", window).correction_preset == "原画"
    finally:
        _close_reader(window, qapp)


def test_bookshelf_restores_valid_state_and_falls_back_for_deleted_preset(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(viewer_module, "DEFAULT_UPSCALE_DIR", tmp_path / "upscale")
    monkeypatch.setattr(viewer_module, "DISPLAY_CACHE_DIR", tmp_path / "display")
    set_language("en")
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    save_quality_preferences(paths.settings_path, ui_mode="simple", selected_preset="クリーニング", custom_presets=[])
    source = tmp_path / "source"
    source.mkdir()
    _pages(source)
    library = LibraryService.open(paths)
    shelf = None
    try:
        book = library.register_local_book(source)
        library.reading_states.save(
            ReadingState(
                book_id=book.id,
                page_index=4,
                spread_mode="single",
                reading_direction="ltr",
                cover_single=False,
                correction_preset="高画質",
            )
        )
        settings_before = paths.settings_path.read_bytes()
        shelf = BookshelfWindow(library)
        shelf.open_book(book.id)
        reader = shelf.active_reader
        assert reader is not None
        assert (reader.index, reader.page_layout_mode, reader.reading_direction, reader.spread_order) == (
            4,
            "single",
            "ltr",
            "ltr",
        )
        assert reader.cover_single is False
        assert reader.quality_preset_for_state == "高画質"
        assert paths.settings_path.read_bytes() == settings_before
        reader.close()
        qapp.processEvents()
        restored = library.reading_states.get(book.id)
        assert restored is not None
        assert (restored.spread_mode, restored.correction_preset) == ("single", "高画質")

        library.reading_states.save(
            ReadingState(
                book_id=book.id,
                page_index=1,
                spread_mode="invalid",
                reading_direction="invalid",
                cover_single=True,
                correction_preset="deleted custom preset",
            )
        )
        shelf.open_book(book.id)
        reader = shelf.active_reader
        assert reader is not None
        assert (reader.page_layout_mode, reader.reading_direction, reader.quality_preset_for_state) == (
            "spread",
            "rtl",
            "クリーニング",
        )
        reader.close()
        qapp.processEvents()
        library.reading_states.save(
            ReadingState(
                book_id=book.id,
                page_index=0,
                correction_preset="原画",
            )
        )
        shelf.open_book(book.id)
        reader = shelf.active_reader
        assert reader is not None
        assert reader.quality_preset_for_state == "原画"
    finally:
        if shelf is not None:
            shelf.close_active_reader(return_to_bookshelf=False)
            shelf.close()
        library.close()
        qapp.processEvents()


def test_bookshelf_keeps_two_books_custom_and_original_states_isolated(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(viewer_module, "DEFAULT_UPSCALE_DIR", tmp_path / "upscale")
    monkeypatch.setattr(viewer_module, "DISPLAY_CACHE_DIR", tmp_path / "display")
    set_language("en")
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    custom_name = "Ink cleanup"
    save_quality_preferences(
        paths.settings_path,
        ui_mode="simple",
        selected_preset="自然",
        custom_presets=[
            {
                "name": custom_name,
                "model": "models-se",
                "scale": 2,
                "noise": "2",
                "tile": 64,
                "threshold": 2000,
                "tta": False,
            }
        ],
    )
    source_a = tmp_path / "source-a"
    source_b = tmp_path / "source-b"
    source_a.mkdir()
    source_b.mkdir()
    _pages(source_a)
    _pages(source_b)
    library = LibraryService.open(paths)
    shelf = None
    try:
        book_a = library.register_local_book(source_a)
        book_b = library.register_local_book(source_b)
        library.reading_states.save(
            ReadingState(
                book_id=book_a.id,
                page_index=99,  # Clamp before the first render, then retain the real last page.
                spread_mode="single",
                reading_direction="ltr",
                cover_single=False,
                correction_preset=custom_name,
            )
        )
        library.reading_states.save(
            ReadingState(
                book_id=book_b.id,
                page_index=2,
                spread_mode="spread",
                reading_direction="rtl",
                cover_single=True,
                correction_preset="原画",
            )
        )
        settings_before = paths.settings_path.read_bytes()
        shelf = BookshelfWindow(library)

        shelf.open_book(book_a.id)
        reader_a = shelf.active_reader
        assert reader_a is not None
        assert (reader_a.index, reader_a.page_layout_mode, reader_a.quality_preset_for_state) == (
            5,
            "single",
            custom_name,
        )
        assert reader_a.current_parameter_key() == "scale2_noise2_tile64_models-se"
        assert paths.settings_path.read_bytes() == settings_before
        reader_a.close()
        qapp.processEvents()

        shelf.open_book(book_b.id)
        reader_b = shelf.active_reader
        assert reader_b is not None
        assert (reader_b.index, reader_b.page_layout_mode, reader_b.quality_preset_for_state) == (
            2,
            "spread",
            "原画",
        )
        assert paths.settings_path.read_bytes() == settings_before
        reader_b.close()
        qapp.processEvents()

        shelf.open_book(book_a.id)
        reopened_a = shelf.active_reader
        assert reopened_a is not None
        assert (reopened_a.index, reopened_a.page_layout_mode, reopened_a.quality_preset_for_state) == (
            5,
            "single",
            custom_name,
        )
        assert paths.settings_path.read_bytes() == settings_before
    finally:
        if shelf is not None:
            shelf.close_active_reader(return_to_bookshelf=False)
            shelf.close()
        library.close()
        qapp.processEvents()
