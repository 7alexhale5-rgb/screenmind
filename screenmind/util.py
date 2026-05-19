"""Shared utilities — currently just the binary-path cache."""

import os
import shutil
from typing import Optional

_binary_cache: dict[str, Optional[str]] = {}


def find_binary(name: str) -> Optional[str]:
    """Find a binary on disk, checking /opt/homebrew/bin/ first for Apple Silicon.

    Cached after first lookup. Returns None if not found anywhere.
    """
    if name in _binary_cache:
        return _binary_cache[name]

    homebrew_path = f"/opt/homebrew/bin/{name}"
    if os.path.isfile(homebrew_path) and os.access(homebrew_path, os.X_OK):
        _binary_cache[name] = homebrew_path
        return homebrew_path

    result = shutil.which(name)
    _binary_cache[name] = result
    return result
