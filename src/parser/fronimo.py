"""
Fronimo .ft3 bridge: convert a .ft3 file to Wayne Cripps TAB via luteconv,
then delegate to the standard tab_parser.

luteconv is an open-source C++ CLI tool by Luke Emmet:
  https://github.com/LukeEmmet/luteconv

Pre-built Windows binaries are available on the GitHub releases page.
Add the luteconv executable to your PATH, or set LUTECONV_PATH in your
environment to its full path.

If luteconv is not installed, this module raises LuteconvNotFoundError with
setup instructions.
"""

from __future__ import annotations
import os
import subprocess
import tempfile
from pathlib import Path

from src.models import Piece
from src.parser.tab_parser import parse_tab_file


class LuteconvNotFoundError(RuntimeError):
    pass


def _luteconv_exe() -> str:
    """Return the luteconv executable path, checking PATH and LUTECONV_PATH."""
    env_path = os.environ.get("LUTECONV_PATH", "")
    if env_path and Path(env_path).is_file():
        return env_path
    # Try to find on PATH
    import shutil
    found = shutil.which("luteconv") or shutil.which("luteconv.exe")
    if found:
        return found
    raise LuteconvNotFoundError(
        "luteconv not found.\n"
        "To parse .ft3 files, install luteconv:\n"
        "  1. Download from https://github.com/LukeEmmet/luteconv/releases\n"
        "  2. Add the executable to your PATH, or set the LUTECONV_PATH environment variable.\n"
        "Alternatively, download the piece in Wayne Cripps .tab format directly from\n"
        "wp.lutemusic.org (Files → navigate to piece → right-click the TAB link)."
    )


def check_luteconv() -> bool:
    """Return True if luteconv is available, False otherwise."""
    try:
        _luteconv_exe()
        return True
    except LuteconvNotFoundError:
        return False


def parse_ft3_file(path: str | Path) -> Piece:
    """
    Convert an .ft3 file to Wayne Cripps TAB via luteconv, then parse it.

    Raises LuteconvNotFoundError if luteconv is not installed.
    Raises RuntimeError if luteconv returns a non-zero exit code.
    """
    exe = _luteconv_exe()
    src = Path(path).resolve()

    with tempfile.NamedTemporaryFile(suffix=".tab", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [exe, "-i", "ft3", "-o", "tab", str(src), tmp_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"luteconv failed (exit {result.returncode}):\n{result.stderr}"
            )
        tab_content = Path(tmp_path).read_text(encoding="utf-8", errors="replace")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    piece = parse_tab_file(tab_content)
    piece.source_format = "ft3"
    return piece
