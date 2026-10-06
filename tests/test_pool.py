from bh_hidro.ingest.pool import fetch_workers, first_error, map_processes, map_threads


def test_fetch_workers_off_is_one():
    assert fetch_workers(False, 8) == 1
    assert fetch_workers(True, 4) == 4
    assert fetch_workers(True, 0) == 1


def test_map_threads_keeps_order_and_errors():
    def work(n: int) -> int:
        if n == 2:
            raise ValueError("boom")
        return n * 10

    rows = map_threads(work, [1, 2, 3], workers=3, desc="test")
    assert [item for item, _r, _e in rows] == [1, 2, 3]
    assert rows[0][1] == 10 and rows[0][2] is None
    assert rows[1][1] is None and isinstance(rows[1][2], ValueError)
    assert rows[2][1] == 30
    assert first_error(rows) is rows[1][2]


def test_map_threads_sequential_when_one_worker():
    seen: list[int] = []

    def work(n: int) -> int:
        seen.append(n)
        return n

    map_threads(work, [3, 1, 2], workers=1, desc="seq")
    assert seen == [3, 1, 2]


def _proc_work(n: int) -> int:
    if n == 2:
        raise ValueError("boom")
    return n * 10


def test_map_processes_keeps_order_and_errors():
    rows = map_processes(_proc_work, [1, 2, 3], workers=2, desc="proc")
    assert [item for item, _r, _e in rows] == [1, 2, 3]
    assert rows[0][1] == 10 and rows[0][2] is None
    assert rows[1][1] is None and isinstance(rows[1][2], ValueError)
    assert rows[2][1] == 30
