from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from mangacrisp_app.correction_queue import CorrectionQueue, pick_next_correction_index


def _outputs(tmp_path: Path, *indexes: int) -> dict[int, Path]:
    return {index: tmp_path / f"{index:04d}.png" for index in indexes}


def test_pick_next_correction_index_respects_priority_and_targets() -> None:
    assert pick_next_correction_index([3, 1, 2], {1, 2, 3}) == 3
    assert pick_next_correction_index([3, 1, 2], {1, 2}) == 1
    assert pick_next_correction_index([3, 1, 2], {1, 2, 3}, {2}) == 2
    assert pick_next_correction_index([3, 1], {2}) is None


def test_reset_take_and_active_outputs_snapshot(tmp_path: Path) -> None:
    outputs = _outputs(tmp_path, 1, 2, 3)
    queue = CorrectionQueue()

    queue.reset(outputs, [3, 1, 2])
    assert queue.pending == outputs
    assert queue.priority == [3, 1, 2]
    assert queue.active_outputs == set(outputs.values())

    assert queue.take({1, 2}) == (1, outputs[1])
    assert queue.in_flight == 1
    assert queue.pending == {2: outputs[2], 3: outputs[3]}
    assert queue.active_outputs == {outputs[1], outputs[2], outputs[3]}


def test_take_with_no_eligible_target_clears_pending_but_keeps_in_flight(
    tmp_path: Path,
) -> None:
    outputs = _outputs(tmp_path, 1, 2)
    queue = CorrectionQueue()
    queue.reset(outputs, [1, 2])

    assert queue.take() == (1, outputs[1])
    queue.refresh({2: outputs[2]}, [2, 1])
    assert queue.take({9}) is None
    assert queue.pending == {}
    assert queue.in_flight == 1
    assert queue.active_outputs == {outputs[1]}

    queue.complete(1)
    assert queue.in_flight is None
    assert queue.active_outputs == set()


def test_refresh_deduplicates_pending_and_complete_removes_requeued_index(
    tmp_path: Path,
) -> None:
    outputs = _outputs(tmp_path, 1, 2, 9)
    queue = CorrectionQueue()
    queue.reset({1: outputs[1]}, [1])

    assert queue.take() == (1, outputs[1])
    queue.refresh({1: outputs[9], 2: outputs[2]}, [2, 1])
    assert queue.pending == {1: outputs[9], 2: outputs[2]}
    assert queue.active_outputs == {outputs[1], outputs[2], outputs[9]}

    queue.complete(1)
    assert queue.in_flight is None
    assert queue.pending == {2: outputs[2]}
    assert queue.active_outputs == {outputs[2]}


def test_clear_resets_all_snapshots(tmp_path: Path) -> None:
    outputs = _outputs(tmp_path, 1, 2)
    queue = CorrectionQueue()
    queue.reset(outputs, [1, 2])
    assert queue.take() == (1, outputs[1])

    queue.clear()

    assert queue.in_flight is None
    assert queue.pending == {}
    assert queue.priority == []
    assert queue.active_outputs == set()


def test_concurrent_refreshes_keep_each_pending_output_and_in_flight_job(
    tmp_path: Path,
) -> None:
    outputs = _outputs(tmp_path, 0, 1, 2, 3)
    queue = CorrectionQueue()
    queue.reset({0: outputs[0]}, [0, 1, 2, 3])
    assert queue.take() == (0, outputs[0])

    barrier = Barrier(4)

    def refresh(index: int) -> None:
        barrier.wait()
        queue.refresh({index: outputs[index]}, [0, 1, 2, 3])

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(refresh, index) for index in (1, 2, 3)]
        barrier.wait()
        for future in futures:
            future.result()

    assert queue.in_flight == 0
    assert queue.pending == {1: outputs[1], 2: outputs[2], 3: outputs[3]}
    assert queue.active_outputs == set(outputs.values())
