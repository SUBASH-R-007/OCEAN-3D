"""Versioned float32 display packets and an exactly byte-bounded response cache.

Native data exports never use this display-only encoding. NaN represents missing;
all finite values have already undergone the existing display rounding policy.
"""
from collections import OrderedDict
import json
import struct
import threading
import numpy as np

MEDIA_TYPE = 'application/vnd.ocean3d.volume'
MAX_CELLS = 64 * 64 * 96


def encode_volume(volume):
    metadata = {k: v for k, v in volume.items() if k != 'values'}
    metadata['encoding'] = {'version': 1, 'dtype': '<f4', 'missing': 'NaN'}
    header = json.dumps(metadata, separators=(',', ':'), allow_nan=False).encode('utf-8')
    header += b' ' * (-len(header) % 4)
    values = np.asarray(volume['values'], dtype='<f4')
    if values.size != np.prod(volume['dimensions']) or values.size > MAX_CELLS:
        raise ValueError('Invalid display packet size.')
    return b'OCV1' + struct.pack('<I', len(header)) + header + values.tobytes()


class ByteCache:
    """Immutable byte values; accounting is payload bytes, not Python overhead."""
    def __init__(self, limit=64 * 1024 * 1024, max_entries=128):
        self.limit, self.max_entries = limit, max_entries
        self.entries = OrderedDict()
        self.bytes = self.hits = self.misses = self.evictions = 0
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            value = self.entries.get(key)
            if value is None:
                self.misses += 1
            else:
                self.hits += 1
                self.entries.move_to_end(key)
            return value

    def put(self, key, value):
        if not isinstance(value, bytes):
            raise TypeError('Cache accepts immutable bytes only.')
        with self.lock:
            previous = self.entries.pop(key, None)
            if previous is not None:
                self.bytes -= len(previous)
            if len(value) > self.limit:
                return
            while self.entries and (self.bytes + len(value) > self.limit or len(self.entries) >= self.max_entries):
                _, old = self.entries.popitem(last=False)
                self.bytes -= len(old)
                self.evictions += 1
            self.entries[key] = value
            self.bytes += len(value)

    def clear(self):
        with self.lock:
            self.entries.clear()
            self.bytes = self.hits = self.misses = self.evictions = 0

    def stats(self):
        with self.lock:
            return dict(payload_bytes=self.bytes, limit_bytes=self.limit, entries=len(self.entries),
                        hits=self.hits, misses=self.misses, evictions=self.evictions)
