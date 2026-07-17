from __future__ import annotations

import os
import sqlite3
import statistics
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TimingSample:
    name: str
    payload_size: int
    sample_count: int
    minimum_ms: int
    median_ms: int
    maximum_ms: int


def _measure(
    name: str, payload_size: int, action: Callable[[], None], count: int = 3
) -> TimingSample:
    durations: list[int] = []
    for _ in range(count):
        start = time.perf_counter_ns()
        action()
        durations.append((time.perf_counter_ns() - start) // 1_000_000)
    return TimingSample(
        name,
        payload_size,
        len(durations),
        min(durations),
        int(statistics.median(durations)),
        max(durations),
    )


def measure_aes_gcm() -> list[TimingSample]:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        return []
    samples: list[TimingSample] = []
    for size in (1024, 102400, 1048576, 1992294):
        key = os.urandom(32)
        aes = AESGCM(key)

        def action(payload_size: int = size, cipher: AESGCM = aes) -> None:
            nonce = os.urandom(12)
            data = os.urandom(payload_size)
            encrypted = cipher.encrypt(nonce, data, b"aad")
            cipher.decrypt(nonce, encrypted, b"aad")

        samples.append(_measure("aes-gcm-roundtrip", size, action))
    return samples


def measure_standard_sqlite() -> list[TimingSample]:
    samples: list[TimingSample] = []
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "standard.db"

        def startup() -> None:
            conn = sqlite3.connect(db_path)
            conn.close()

        samples.append(_measure("sqlite-startup", 0, startup))
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, value BLOB)")
        conn.execute("CREATE INDEX ix_t_value ON t(value)")
        conn.commit()

        def insert() -> None:
            conn.execute("INSERT INTO t(value) VALUES (?)", (os.urandom(32),))
            conn.commit()

        def indexed_read() -> None:
            conn.execute("SELECT count(*) FROM t WHERE id >= 0").fetchone()

        def sequential_read() -> None:
            conn.execute("SELECT value FROM t").fetchall()

        samples.extend(
            [
                _measure("sqlite-insert", 32, insert),
                _measure("sqlite-indexed-read", 0, indexed_read),
                _measure("sqlite-sequential-read", 0, sequential_read),
            ]
        )
        conn.close()
    return samples
