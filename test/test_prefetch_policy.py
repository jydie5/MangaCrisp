from __future__ import annotations

from mangacrisp_app.viewer import (
    DEFAULT_FORWARD_PREFETCH_COUNT,
    DEFAULT_PREVIOUS_PREFETCH_COUNT,
    MAX_FORWARD_PREFETCH_COUNT,
    MIN_FORWARD_PREFETCH_COUNT,
    adaptive_forward_prefetch_count,
    correction_lead_factor,
    prefetch_window_indexes,
)


def forward(intervals, *, correction=1.25, lead_factor=1.0) -> int:
    return adaptive_forward_prefetch_count(
        intervals,
        base_count=DEFAULT_FORWARD_PREFETCH_COUNT,
        correction_seconds_per_page=correction,
        lead_factor=lead_factor,
    )


def test_defaults_are_the_documented_window() -> None:
    assert DEFAULT_FORWARD_PREFETCH_COUNT == 12
    assert DEFAULT_PREVIOUS_PREFETCH_COUNT == 6
    assert MIN_FORWARD_PREFETCH_COUNT == 6
    assert MAX_FORWARD_PREFETCH_COUNT == 24


def test_no_history_uses_base_count() -> None:
    assert forward([]) == 12


def test_normal_reader_keeps_base_count() -> None:
    # one page every 2 s: ceil(0.5 * 12) + 4 = 10 -> clamped up to the base 12
    assert forward([2.0, 2.0, 2.0]) == 12


def test_fast_reader_gets_more_lead_up_to_the_maximum() -> None:
    assert forward([1.0, 1.0, 1.0]) == 16
    assert forward([0.3, 0.3, 0.3]) == MAX_FORWARD_PREFETCH_COUNT


def test_slow_gpu_extends_lead() -> None:
    # correction 3 s/page -> lead 24 s; one page per second -> 28 -> capped at 24
    assert forward([1.0, 1.0, 1.0], correction=3.0) == MAX_FORWARD_PREFETCH_COUNT


def test_slow_reader_drops_to_the_minimum() -> None:
    # one page every 10 s: ceil(0.1 * 12) + 4 = 6
    assert forward([10.0, 10.0, 10.0]) == MIN_FORWARD_PREFETCH_COUNT
    # a slow reader on a slow GPU still needs at least what the lead says
    assert forward([10.0, 10.0, 10.0], correction=3.0) == 8


def test_slow_reader_floor_only_applies_at_the_threshold() -> None:
    assert forward([7.9, 7.9, 7.9]) == 12
    assert forward([8.0, 8.0, 8.0]) == 6


def test_recovery_from_slow_reading_follows_the_median() -> None:
    history = [10.0, 10.0, 10.0, 1.0, 1.0, 1.0, 1.0]
    assert forward(history) == 16


def test_lead_factor_stretches_the_window() -> None:
    assert forward([2.0, 2.0, 2.0]) == 12
    assert forward([2.0, 2.0, 2.0], lead_factor=1.5) == 14
    assert forward([10.0, 10.0, 10.0], lead_factor=1.5) == 6


def test_lead_factor_never_shrinks() -> None:
    assert forward([1.0, 1.0, 1.0], lead_factor=0.5) == forward([1.0, 1.0, 1.0])


def test_result_is_even_and_capped() -> None:
    for interval in (0.1, 0.5, 1.5, 3.0, 9.0, 20.0):
        count = forward([interval] * 5)
        assert count % 2 == 0
        assert MIN_FORWARD_PREFETCH_COUNT <= count <= MAX_FORWARD_PREFETCH_COUNT


def test_correction_lead_factor_counts_recent_misses() -> None:
    assert correction_lead_factor([]) == 1.0
    assert correction_lead_factor([False] * 10) == 1.0
    assert correction_lead_factor([True] + [False] * 9) == 1.0
    assert correction_lead_factor([True, False, True] + [False] * 7) == 1.5


def test_prefetch_window_orders_visible_then_forward_then_previous() -> None:
    window = prefetch_window_indexes(10, 100, [10, 11], 4, DEFAULT_PREVIOUS_PREFETCH_COUNT)
    assert window == [10, 11, 12, 13, 14, 15, 9, 8, 7, 6, 5, 4]


def test_prefetch_window_clips_to_the_book() -> None:
    assert prefetch_window_indexes(1, 3, [1, 2], 12, 6) == [1, 2, 0]
    assert prefetch_window_indexes(0, 1, [0], 12, 6) == [0]
