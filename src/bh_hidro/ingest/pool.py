"""Thread pool for I/O-bound downloads; process pool for balance pairs. CDO stays sequential."""

from __future__ import annotations

import logging
import multiprocessing
import threading
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")

CDO_LOCK = threading.Lock()


def fetch_workers(paralelo: bool, workers: int) -> int:
    if not paralelo:
        return 1
    return max(1, int(workers))


def map_threads(
    fn: Callable[[T], R],
    items: Sequence[T],
    workers: int,
    *,
    desc: str = "",
) -> list[tuple[T, R | None, BaseException | None]]:
    """Run fn(item) for each item. workers<=1 is sequential. Errors are returned, not raised."""
    if not items:
        return []
    workers = max(1, int(workers))
    label = desc or fn.__name__
    if workers == 1 or len(items) == 1:
        logger.info("%s sequential n=%s", label, len(items))
        out: list[tuple[T, R | None, BaseException | None]] = []
        for item in items:
            try:
                out.append((item, fn(item), None))
            except BaseException as exc:
                out.append((item, None, exc))
        return out

    n = min(workers, len(items))
    logger.info("%s threads=%s n=%s", label, n, len(items))
    indexed: dict[int, tuple[T, R | None, BaseException | None]] = {}
    with ThreadPoolExecutor(max_workers=n, thread_name_prefix=label) as pool:
        futures = {pool.submit(fn, item): i for i, item in enumerate(items)}
        for future in as_completed(futures):
            i = futures[future]
            item = items[i]
            try:
                indexed[i] = (item, future.result(), None)
            except BaseException as exc:
                indexed[i] = (item, None, exc)
    return [indexed[i] for i in range(len(items))]


def map_processes(
    fn: Callable[[T], R],
    items: Sequence[T],
    workers: int,
    *,
    desc: str = "",
) -> list[tuple[T, R | None, BaseException | None]]:
    """One process per item, capped at workers. spawn so asyncio/MySQL are not forked."""
    if not items:
        return []
    workers = max(1, int(workers))
    label = desc or fn.__name__
    if workers == 1 or len(items) == 1:
        logger.info("%s sequential n=%s", label, len(items))
        out: list[tuple[T, R | None, BaseException | None]] = []
        for item in items:
            try:
                out.append((item, fn(item), None))
            except BaseException as exc:
                out.append((item, None, exc))
        return out

    n = min(workers, len(items))
    logger.info("%s processes=%s n=%s", label, n, len(items))
    indexed: dict[int, tuple[T, R | None, BaseException | None]] = {}
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=n, mp_context=ctx) as pool:
        futures = {pool.submit(fn, item): i for i, item in enumerate(items)}
        for future in as_completed(futures):
            i = futures[future]
            item = items[i]
            try:
                indexed[i] = (item, future.result(), None)
            except BaseException as exc:
                indexed[i] = (item, None, exc)
    return [indexed[i] for i in range(len(items))]


def first_error(rows: Iterable[tuple[T, R | None, BaseException | None]]) -> BaseException | None:
    for _item, _result, err in rows:
        if err is not None:
            return err
    return None
