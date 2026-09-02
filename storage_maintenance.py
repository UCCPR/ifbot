"""生成文件、日志与备份的容量维护策略。"""
import os
import re
import shutil
import threading
import time
from pathlib import Path


LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5
OUTPUT_RETENTION_SECONDS = 24 * 3600
GIF_RETENTION_SECONDS = 7 * 24 * 3600
BATTLE_LOG_RETENTION_SECONDS = 30 * 24 * 3600
BACKUP_RETENTION_SECONDS = 30 * 24 * 3600
OUTPUT_MAX_BYTES = 256 * 1024 * 1024
GIF_CACHE_MAX_BYTES = 256 * 1024 * 1024
_LOG_LOCK = threading.RLock()
_DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_COMPACT_DATE_DIR_RE = re.compile(r"^\d{8}$")
RUNTIME_OUTPUT_PATTERNS = (
    "gacha_*", "limited_*", "sannoujo_*", "personal_3stars_*",
    "3star_pool_*", "team_*", "team_cards_*", "vs_*", "battle_*.gif",
)


def _rotate_log(path: Path, max_bytes=LOG_MAX_BYTES, backup_count=LOG_BACKUP_COUNT):
    if not path.exists() or path.stat().st_size < max_bytes:
        return
    for index in range(backup_count, 0, -1):
        source = path.with_name(path.name + (f".{index - 1}" if index > 1 else ""))
        target = path.with_name(path.name + f".{index}")
        if source.exists():
            if target.exists():
                target.unlink()
            os.replace(source, target)


def append_rotating_log(path, line: str):
    """追加日志，并在10MB时轮转，最多保留5份。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK:
        _rotate_log(path)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)


def _cleanup_files(directory: Path, pattern: str, cutoff: float, dry_run: bool):
    removed = []
    if not directory.exists():
        return removed
    patterns = (pattern,) if isinstance(pattern, str) else tuple(pattern)
    paths = {path for item in patterns for path in directory.glob(item)}
    for path in paths:
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                removed.append((str(path), path.stat().st_size))
                if not dry_run:
                    path.unlink()
        except OSError:
            continue
    return removed


def _trim_files(directory: Path, pattern: str, max_bytes: int, dry_run: bool, excluded=()):
    """按最后使用时间删除最旧文件，直到目录回到容量上限。"""
    if not directory.exists():
        return []
    excluded = {str(Path(path)) for path in excluded}
    files = []
    patterns = (pattern,) if isinstance(pattern, str) else tuple(pattern)
    paths = {path for item in patterns for path in directory.glob(item)}
    for path in paths:
        try:
            if path.is_file() and str(path) not in excluded:
                files.append((path.stat().st_mtime, path, path.stat().st_size))
        except OSError:
            continue
    total = sum(size for _, _, size in files)
    removed = []
    for _, path, size in sorted(files):
        if total <= max_bytes:
            break
        removed.append((str(path), size))
        total -= size
        if not dry_run:
            try:
                path.unlink()
            except OSError:
                pass
    return removed


def cleanup_storage(base_dir, now=None, dry_run=False) -> dict:
    """清理明确属于运行时生成物的过期文件，不触碰角色与UI素材。"""
    base = Path(base_dir).resolve()
    now = float(now or time.time())
    removed = []
    removed += _cleanup_files(
        base / "output", RUNTIME_OUTPUT_PATTERNS,
        now - OUTPUT_RETENTION_SECONDS, dry_run,
    )
    removed += _cleanup_files(base / "static_images" / "gifs", "*.gif", now - GIF_RETENTION_SECONDS, dry_run)
    removed += _cleanup_files(
        base / "static_images" / "battle_logs", "*.txt",
        now - BATTLE_LOG_RETENTION_SECONDS, dry_run,
    )
    removed += _trim_files(
        base / "output", RUNTIME_OUTPUT_PATTERNS, OUTPUT_MAX_BYTES, dry_run,
        excluded=(path for path, _ in removed),
    )
    removed += _trim_files(
        base / "static_images" / "gifs", "*.gif", GIF_CACHE_MAX_BYTES, dry_run,
        excluded=(path for path, _ in removed),
    )

    backup_root = (base / "backup").resolve()
    if backup_root.exists():
        for directory in backup_root.iterdir():
            try:
                # 仅清理 backup/YYYY-MM-DD，避免误删其他备份类别。
                resolved = directory.resolve()
                if (directory.is_dir() and _DATE_DIR_RE.fullmatch(directory.name)
                        and resolved.parent == backup_root
                        and directory.stat().st_mtime < now - BACKUP_RETENTION_SECONDS):
                    size = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
                    removed.append((str(directory), size))
                    if not dry_run:
                        shutil.rmtree(resolved)
            except OSError:
                continue

        battle_backup_root = (backup_root / "battle_logs").resolve()
        if battle_backup_root.exists() and battle_backup_root.parent == backup_root:
            for directory in battle_backup_root.iterdir():
                try:
                    resolved = directory.resolve()
                    if (directory.is_dir() and _COMPACT_DATE_DIR_RE.fullmatch(directory.name)
                            and resolved.parent == battle_backup_root
                            and directory.stat().st_mtime < now - BACKUP_RETENTION_SECONDS):
                        size = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
                        removed.append((str(directory), size))
                        if not dry_run:
                            shutil.rmtree(resolved)
                except OSError:
                    continue

    return {
        "files": len(removed),
        "bytes": sum(size for _, size in removed),
        "paths": [path for path, _ in removed],
        "dry_run": dry_run,
    }
