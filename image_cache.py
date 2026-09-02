"""进程级共享图片缓存。

缓存按解码后的像素字节计费，而不是按文件数量计费。1024×1024 的角色原图
不进入静态缓存；各业务模块只缓存已经裁剪/缩放后的卡面。
"""
import os
import threading
from collections import OrderedDict
from io import BytesIO
from pathlib import Path

from PIL import Image


BASE_DIR = Path(__file__).parent.resolve()
ICON_DIR = (BASE_DIR / "iconimage").resolve()
STATIC_CACHE_BUDGET = 32 * 1024 * 1024
RENDERED_CACHE_BUDGET = 64 * 1024 * 1024


def _is_character_icon(path: str) -> bool:
    try:
        return os.path.commonpath((str(ICON_DIR), os.path.abspath(path))) == str(ICON_DIR)
    except (OSError, ValueError):
        return False


class CompressedImageLRU:
    """保存最近使用图片的压缩 PNG 字节，命中时才解码。"""
    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        self.current_bytes = 0
        self._items = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key):
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            self._items.move_to_end(key)
            compressed = item[0]
        with Image.open(BytesIO(compressed)) as source:
            image = source.copy()
            image.load()
        return image

    def put(self, key, image: Image.Image):
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=False, compress_level=6)
        compressed = buffer.getvalue()
        size = len(compressed)
        if size > self.max_bytes:
            return
        with self._lock:
            previous = self._items.pop(key, None)
            if previous is not None:
                self.current_bytes -= previous[1]
            self._items[key] = (compressed, size)
            self.current_bytes += size
            while self.current_bytes > self.max_bytes and self._items:
                _, (_, removed_size) = self._items.popitem(last=False)
                self.current_bytes -= removed_size

    def stats(self) -> dict:
        with self._lock:
            return {
                "items": len(self._items),
                "bytes": self.current_bytes,
                "max_bytes": self.max_bytes,
            }

    def clear(self):
        with self._lock:
            self._items.clear()
            self.current_bytes = 0


STATIC_IMAGE_CACHE = CompressedImageLRU(STATIC_CACHE_BUDGET)
RENDERED_IMAGE_CACHE = CompressedImageLRU(RENDERED_CACHE_BUDGET)


def load_shared_image(path, mode="RGBA"):
    """加载图片；小型静态素材共享缓存，角色原图只解码不常驻。"""
    if not path or not os.path.exists(path):
        return None
    absolute = os.path.abspath(str(path))
    key = (absolute, mode)
    cached = STATIC_IMAGE_CACHE.get(key)
    if cached is not None:
        return cached

    with Image.open(absolute) as source:
        loaded = source.convert(mode)
        loaded.load()

    if not _is_character_icon(absolute):
        STATIC_IMAGE_CACHE.put(key, loaded)
    return loaded


def get_rendered_image(namespace: str, key):
    return RENDERED_IMAGE_CACHE.get((namespace, key))


def put_rendered_image(namespace: str, key, image: Image.Image):
    RENDERED_IMAGE_CACHE.put((namespace, key), image)


def cache_stats() -> dict:
    return {
        "static": STATIC_IMAGE_CACHE.stats(),
        "rendered": RENDERED_IMAGE_CACHE.stats(),
    }
