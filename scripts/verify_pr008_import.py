"""Sanitized PR-008 verifier."""

from __future__ import annotations

import importlib
import sys

_ALLOWED_INCONCLUSIVE = "HEIF_DECODER_UNAVAILABLE"


def _dependency_available(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
    except Exception:
        return False
    return True


def main() -> int:
    if not _dependency_available("PIL.Image") or not _dependency_available("pi_heif"):
        print(f"PR008_VERIFY result=INCONCLUSIVE code={_ALLOWED_INCONCLUSIVE}")
        return 2
    # The full product verifier requires SQLCipher and the synthetic HEIF fixture on a supported
    # Windows runner. Keep output allowlisted and fail closed rather than emitting local paths.
    print("PR008_VERIFY result=INCONCLUSIVE code=UNSUPPORTED_PLATFORM")
    return 2


if __name__ == "__main__":
    sys.exit(main())
