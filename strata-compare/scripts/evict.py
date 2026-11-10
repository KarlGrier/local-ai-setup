"""Drop a file's clean pages from the page cache (posix_fadvise DONTNEED; no root, no system setting changed).
Used to start every configuration with a cold n-gram table. Reports how much was cached before/after (mincore).
    evict.py FILE...          evict and report
    evict.py --report FILE... report only"""
import ctypes, os, sys
libc = ctypes.CDLL("libc.so.6", use_errno=True)
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
libc.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
PROT_READ, MAP_SHARED = 1, 1

def cached_bytes(path):
    size = os.path.getsize(path)
    fd = os.open(path, os.O_RDONLY)
    try:
        addr = libc.mmap(None, size, PROT_READ, MAP_SHARED, fd, 0)
        if addr in (None, ctypes.c_void_p(-1).value): return -1
        pages = (size + 4095) // 4096
        vec = (ctypes.c_ubyte * pages)()
        r = libc.mincore(addr, size, vec)
        libc.munmap(addr, size)
        if r != 0: return -1
        return bytes(vec).count(1) * 4096 + 0 if False else sum(1 for v in bytes(vec) if v & 1) * 4096
    finally:
        os.close(fd)

args = sys.argv[1:]
report = args and args[0] == "--report"
for p in args[1:] if report else args:
    before = cached_bytes(p)
    if not report:
        fd = os.open(p, os.O_RDONLY); os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED); os.close(fd)
        print(f"{p}: page cache {before/2**30:.2f} GiB -> {cached_bytes(p)/2**30:.2f} GiB")
    else:
        print(f"{p}: page cache {before/2**30:.2f} GiB")
