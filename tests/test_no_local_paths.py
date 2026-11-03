"""
tests/test_no_local_paths.py

Guards the public repository against leaking machine-specific absolute paths
(e.g. a Windows user profile directory) in committed files.

Coverage:
  - Every tracked or staged-candidate (untracked, not ignored) text file is
    scanned for user-profile paths on Windows, macOS, and Linux.
  - Failure output lists each offending file:line so it can be fixed fast.

Scripts should resolve paths relative to the repository (Path(__file__),
$PSScriptRoot) and docs should use relative commands (python -m pytest).
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Matches a drive-letter Users dir, /Users/<name>/ or /home/<name>/ followed by
# a concrete name. Placeholders such as <name>, %USERPROFILE% or $HOME are allowed.
LOCAL_PATH_PATTERN = re.compile(
    r"(?:\b[A-Za-z]:[\\/]Users[\\/](?![<%$])[^\\/\s`'\"]+"
    r"|(?<![\w.])/(?:Users|home)/(?![<%$])[^/\s`'\"]+/)",
    re.IGNORECASE,
)


def _candidate_files() -> list[Path]:
    """Return tracked files plus untracked files that are not gitignored."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"git is unavailable for the local-path scan: {exc}")
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line]


def _read_text(path: Path) -> str | None:
    """Read a file as UTF-8 text, returning None for binary or missing files."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def test_no_machine_specific_user_paths_committed():
    offenders = []
    for path in _candidate_files():
        text = _read_text(path)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = LOCAL_PATH_PATTERN.search(line)
            if match:
                rel = path.relative_to(REPO_ROOT).as_posix()
                offenders.append(f"{rel}:{lineno}: {match.group(0)}")

    assert not offenders, (
        "Machine-specific user paths found in committable files. Replace them "
        "with repo-relative paths (Path(__file__), $PSScriptRoot) or relative "
        "commands:\n  " + "\n  ".join(offenders)
    )
