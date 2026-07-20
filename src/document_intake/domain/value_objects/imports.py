"""PR-008 import value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass

from document_intake.domain.errors import InvalidValueError

_BATCH_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_PHASH_RE = re.compile(r"^[0-9a-f]{16}$")


@dataclass(frozen=True, slots=True, order=True)
class BatchNumber:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidValueError("batch_number: invalid_type")
        if not _BATCH_RE.fullmatch(self.value):
            raise InvalidValueError("batch_number: invalid_format")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class SourceBasename:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidValueError("source_basename: invalid_type")
        if not 1 <= len(self.value) <= 255:
            raise InvalidValueError("source_basename: invalid_length")
        if self.value in {".", ".."}:
            raise InvalidValueError("source_basename: invalid_name")
        if "/" in self.value or "\\" in self.value or "\x00" in self.value:
            raise InvalidValueError("source_basename: invalid_character")
        if any(ord(char) < 32 or ord(char) == 127 for char in self.value):
            raise InvalidValueError("source_basename: invalid_character")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return "SourceBasename(<redacted>)"


@dataclass(frozen=True, slots=True, order=True)
class Sha256Digest:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _SHA_RE.fullmatch(self.value):
            raise InvalidValueError("sha256_digest: invalid_format")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return "Sha256Digest(<redacted>)"


@dataclass(frozen=True, slots=True, order=True)
class PerceptualHash:
    algorithm_id: str
    algorithm_version: int
    bit_width: int
    hex_value: str

    def __post_init__(self) -> None:
        if self.algorithm_id != "DHASH64":
            raise InvalidValueError("perceptual_hash.algorithm_id: invalid_value")
        if self.algorithm_version != 1 or self.bit_width != 64:
            raise InvalidValueError("perceptual_hash: incompatible_version")
        if not isinstance(self.hex_value, str) or not _PHASH_RE.fullmatch(self.hex_value):
            raise InvalidValueError("perceptual_hash.hex_value: invalid_format")

    def __repr__(self) -> str:
        return "PerceptualHash(algorithm_id='DHASH64', algorithm_version=1, bit_width=64, hex_value=<redacted>)"
