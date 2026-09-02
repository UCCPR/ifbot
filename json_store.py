"""Thread-safe JSON persistence for the bot's file-backed repositories."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Callable, TypeVar


T = TypeVar("T")
_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, threading.RLock] = {}


def _path_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def keyed_lock(namespace: str, key):
    """Serialize a multi-file operation identified by a stable business key."""
    lock = _path_lock(Path(f"__lock__/{namespace}/{key}"))
    with lock:
        yield


def synchronized(namespace: str, key_function):
    """Decorate a function with a re-entrant business-key lock."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            key = key_function(*args, **kwargs)
            with keyed_lock(namespace, key):
                return function(*args, **kwargs)
        return wrapped
    return decorate


def _new_default(default_factory: Callable[[], T] | T) -> T:
    if callable(default_factory):
        return default_factory()
    return copy.deepcopy(default_factory)


def read_json(path, default_factory: Callable[[], T] | T) -> T:
    """Read JSON under the same per-path lock used by writers."""
    target = Path(path)
    with _path_lock(target):
        try:
            with target.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return _new_default(default_factory)


def atomic_write_json(path, data, *, ensure_ascii=False, indent=2) -> None:
    """Durably replace a JSON file without exposing a partially written file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with _path_lock(target):
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=ensure_ascii, indent=indent)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise


def update_json(path, default_factory: Callable[[], T] | T, mutator: Callable[[T], None]) -> T:
    """Perform an in-process atomic read-modify-write transaction."""
    target = Path(path)
    with _path_lock(target):
        data = read_json(target, default_factory)
        mutator(data)
        atomic_write_json(target, data)
        return data
