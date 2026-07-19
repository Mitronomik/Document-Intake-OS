from __future__ import annotations

import os
import stat
from types import SimpleNamespace

from document_intake.storage.filesystem import _FilesystemOperations


def test_filesystem_operations_request_binary_mode_when_available(
    tmp_path,
    monkeypatch,
) -> None:
    binary_flag = 1 << 20
    payload = b"\x00\r\n\x1a\xff"
    opened_flags: list[int] = []
    chunks = iter((payload, b""))

    monkeypatch.setattr(os, "O_BINARY", binary_flag, raising=False)

    def fake_open(path, flags, mode=0o777):
        opened_flags.append(flags)
        return len(opened_flags)

    monkeypatch.setattr(os, "open", fake_open)
    monkeypatch.setattr(
        os,
        "fstat",
        lambda _fd: SimpleNamespace(st_mode=stat.S_IFREG),
    )
    monkeypatch.setattr(os, "read", lambda _fd, _size: next(chunks))
    monkeypatch.setattr(os, "close", lambda _fd: None)

    operations = _FilesystemOperations()

    write_fd = operations.open_exclusive_no_follow(tmp_path / "write.diosobj")
    read_result = operations.read_bytes_no_follow(tmp_path / "read.diosobj")

    assert write_fd == 1
    assert read_result == payload
    assert len(opened_flags) == 2
    assert all(flags & binary_flag for flags in opened_flags)
