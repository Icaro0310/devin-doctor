"""Path normalization for grouping keys (PM-3).

Session stores record ``working_directory``/``workspaceId`` in whatever
spelling the client used, so the same project can appear as
``C:\\Users\\X\\repo``, ``/c/Users/X/repo`` and (via a WSL UNC path)
``\\\\wsl.localhost\\Ubuntu\\home\\u\\repo`` ≡ ``/home/u/repo``. Without
normalization one project splits into several groups.

``normalize_path`` produces the *grouping key only* — output always keeps
the original path. Rules applied, in order:

- ``\\`` → ``/``, duplicate slashes collapsed, trailing ``/`` stripped;
- WSL UNC ``//wsl.localhost/<distro>/…`` / ``//wsl$/<distro>/…`` → the
  in-distro POSIX path (``/home/u/repo``);
- MSYS/Git-Bash ``/c/x`` and Cygwin ``/cygdrive/c/x`` → ``c:/x``;
- Windows drives ``C:\\x`` → ``c:/x``. Drive-rooted paths are
  **fully lowercased** (the Windows filesystem is case-insensitive);
- POSIX paths keep their case — ``/home/u/Foo`` ≠ ``/home/u/foo``.

What it deliberately does **not** do: map a POSIX home to a Windows
profile (``/home/u/repo`` vs ``c:/users/u/repo`` stay distinct — nothing
in the path itself proves they are the same directory).
"""

from __future__ import annotations

import re

_WSL_UNC_RE = re.compile(
    r"^//wsl(?:\.localhost|\$)/[^/]+(?P<rest>/.*)?$", re.IGNORECASE
)
_CYGWIN_DRIVE_RE = re.compile(r"^/cygdrive/(?P<drive>[A-Za-z])(?:/(?P<rest>.*))?$")
_MSYS_DRIVE_RE = re.compile(r"^/(?P<drive>[A-Za-z])(?:/(?P<rest>.*))?$")
_WIN_DRIVE_RE = re.compile(r"^(?P<drive>[A-Za-z]):(?P<rest>/.*)?$")
_DUP_SLASH_RE = re.compile(r"/{2,}")


def _drive_key(drive: str, rest: str | None) -> str:
    """``c`` + ``users/x`` → ``c:/users/x``; bare ``c:`` keeps no slash."""
    tail = (rest or "").strip("/")
    return f"{drive.lower()}:{f'/{tail}' if tail else ''}".lower()


def normalize_path(path: str) -> str:
    """Grouping key for a working directory / workspace path."""
    p = (path or "").strip().replace("\\", "/")
    wsl = _WSL_UNC_RE.match(p)
    if wsl:
        p = wsl.group("rest") or "/"
    p = _DUP_SLASH_RE.sub("/", p)
    for rx in (_CYGWIN_DRIVE_RE, _MSYS_DRIVE_RE, _WIN_DRIVE_RE):
        m = rx.match(p)
        if m:
            return _drive_key(m.group("drive"), m.group("rest"))
    if len(p) > 1:
        p = p.rstrip("/")
    return p
