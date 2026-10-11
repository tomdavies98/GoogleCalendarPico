# Reserve the GS4 framebuffer while the heap is still one contiguous region.
# Import/config only — call reserve() before loading display drivers.

import gc
import config as cfg

SIZE = cfg.HEIGHT * cfg.WIDTH // 2  # 76800 for 480x320 GS4

_buf = None


def reserve():
    """Allocate the slab once. Safe to call repeatedly."""
    global _buf
    if _buf is not None:
        return _buf
    gc.collect()
    gc.collect()
    print("FB reserve: free before", gc.mem_free(), "need", SIZE)
    _buf = bytearray(SIZE)
    print("FB reserve: ok, free after", gc.mem_free())
    return _buf


def get():
    return _buf


def release():
    """
    Drop the slab ref (after LCD/UI refs are gone) so TLS can use the RAM.

    Does not gc.collect() — caller must drop ssd/bus locals then collect.
    Collecting while the FrameBuffer is still live wastes work; under a
    fragmented heap collect's mark stack can itself MemoryError (~640B).
    """
    global _buf
    _buf = None
    print("FB slab released")


def ensure():
    """Re-allocate after network. Returns False if the heap is too fragmented."""
    global _buf
    if _buf is not None:
        return True
    gc.collect()
    gc.collect()
    try:
        _buf = bytearray(SIZE)
        print("FB re-reserve ok, free", gc.mem_free())
        return True
    except MemoryError as e:
        print("FB re-reserve failed:", e, "free", gc.mem_free())
        return False
