from __future__ import annotations

import importlib
import os
import sqlite3
import statistics
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


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


def _try_import_aesgcm() -> Any:
    """Import AESGCM conditionally; returns the class or None."""
    try:
        aead_mod = cast(
            Any,
            importlib.import_module("cryptography.hazmat.primitives.ciphers.aead"),
        )
    except ImportError:
        return None
    return aead_mod.AESGCM


def measure_aes_gcm() -> list[TimingSample]:
    try:
        aead_mod = cast(
            Any,
            importlib.import_module("cryptography.hazmat.primitives.ciphers.aead"),
        )
        AESGCM: Any = aead_mod.AESGCM
    except ImportError:
        return []
    samples: list[TimingSample] = []
    # Use a local alias to avoid type-checking issues with cryptography
    aesgcm_cls: Any = AESGCM
    for size in (1024, 102400, 1048576, 1992294):
        key = os.urandom(32)
        aes: Any = aesgcm_cls(key)

        def action(payload_size: int = size, cipher: Any = aes) -> None:
            nonce = os.urandom(12)
            data = os.urandom(payload_size)
            encrypted: Any = cipher.encrypt(nonce, data, b"aad")
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


def performance_evidence_note() -> str:
    """Measurement code exists but runtime performance evidence is NOT_DEMONSTRATED."""
    return (
        "NOT_DEMONSTRATED: measurement code exists "
        "but runtime performance evidence has not been collected by a runner"
    )
