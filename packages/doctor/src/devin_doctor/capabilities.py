"""Capability profile — reports what this machine can actually do for the
Devin ecosystem, as JSON.

Two profiles exist: ``corporate`` (the default — fail-closed: assume nothing
may run in the background or spawn a daemon) and ``personal`` (only when
explicitly declared). Declaration precedence:

1. ``DEVIN_ECOSYSTEM_PROFILE`` environment variable (``corporate``|``personal``)
2. ``devin-profile.json`` in the Devin config dir — ``{"profile": "personal"}``
   (``~/.config/Devin`` on Linux, ``%APPDATA%\\Devin`` on Windows; see
   ``paths.default_config_dir``)
3. fallback: ``corporate``

All probing is LOCAL ONLY: PATH lookups, well-known config dirs and RAM size
via stdlib. ``net.outbound``/``net.listener`` report ``"unknown"`` unless the
caller passes ``probe_network=True`` (the ``--probe-network`` flag), which
performs exactly ONE outbound TCP connect (2 s timeout) and one loopback
bind — the only network access devin-doctor can perform.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sys
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

PROFILE_ENV_VAR = "DEVIN_ECOSYSTEM_PROFILE"
PROFILE_FILENAME = "devin-profile.json"
PROFILE_CHOICES = ("corporate", "personal")

RAM_HEAVY_BYTES = 24 * 1024**3  # 24 GiB

NET_PROBE_HOST = "1.1.1.1"
NET_PROBE_PORT = 443
NET_PROBE_TIMEOUT = 2.0

_PROXY_ENV_VARS = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy")
_COMMS_ENV_VARS = ("SLACK_BOT_TOKEN", "SLACK_TOKEN", "TELEGRAM_BOT_TOKEN")


# ---------------------------------------------------------------------------
# profile resolution
# ---------------------------------------------------------------------------


def _profile_from_file(config_dir: Path) -> str | None:
    path = Path(config_dir) / PROFILE_FILENAME
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if isinstance(obj, dict):
        value = obj.get("profile")
        if isinstance(value, str) and value.lower() in PROFILE_CHOICES:
            return value.lower()
    return None


def resolve_profile(
    environ: Mapping[str, str] | None = None,
    config_dir: Path | None = None,
) -> tuple[str, str]:
    """Return ``(profile, source)``. The env var wins over the config file;
    anything undeclared falls back to ``corporate`` (fail-closed)."""
    env = os.environ if environ is None else environ
    value = env.get(PROFILE_ENV_VAR, "").strip().lower()
    if value in PROFILE_CHOICES:
        return value, f"env {PROFILE_ENV_VAR}"
    if config_dir is not None:
        file_value = _profile_from_file(Path(config_dir))
        if file_value is not None:
            return file_value, str(Path(config_dir) / PROFILE_FILENAME)
    return "corporate", "default"


# ---------------------------------------------------------------------------
# local probes (no network, ever)
# ---------------------------------------------------------------------------


def _which(name: str, env: Mapping[str, str]) -> str | None:
    return shutil.which(name, path=env.get("PATH"))


def _has_scheduler(env: Mapping[str, str], plat: str) -> bool:
    if plat.startswith("win"):
        return _which("schtasks", env) is not None
    if plat == "darwin":
        return True  # launchd is always present on macOS
    return (
        _which("crontab", env) is not None
        or _which("systemctl", env) is not None
        or Path("/run/systemd/system").is_dir()
    )


def _home(env: Mapping[str, str], plat: str) -> Path:
    if plat.startswith("win"):
        raw = env.get("USERPROFILE")
    else:
        raw = env.get("HOME")
    return Path(raw).expanduser() if raw else Path.home()


def _comms_dirs(env: Mapping[str, str], plat: str) -> list[Path]:
    home = _home(env, plat)
    if plat.startswith("win"):
        appdata = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
        return [appdata / "Slack", appdata / "Telegram Desktop"]
    if plat == "darwin":
        support = home / "Library" / "Application Support"
        return [support / "Slack", support / "Telegram Desktop"]
    config_home = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
    data_home = Path(env.get("XDG_DATA_HOME") or home / ".local" / "share")
    return [
        config_home / "Slack",
        config_home / "slack",
        config_home / "telegram-desktop",
        data_home / "TelegramDesktop",
    ]


def _has_comms(env: Mapping[str, str], plat: str) -> bool:
    if any(env.get(var) for var in _COMMS_ENV_VARS):
        return True
    return any(d.is_dir() for d in _comms_dirs(env, plat))


def _total_ram_windows() -> int | None:
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return int(stat.ullTotalPhys)
    except (AttributeError, OSError):
        pass
    return None


def _total_ram_macos() -> int | None:
    import ctypes
    import ctypes.util

    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        value = ctypes.c_uint64(0)
        size = ctypes.c_size_t(ctypes.sizeof(value))
        if (
            libc.sysctlbyname(
                b"hw.memsize", ctypes.byref(value), ctypes.byref(size), None, 0
            )
            == 0
        ):
            return int(value.value)
    except (AttributeError, OSError):
        pass
    return None


def total_ram_bytes(plat: str | None = None) -> int | None:
    """Total physical RAM, stdlib only. ``None`` when it cannot be told."""
    plat = sys.platform if plat is None else plat
    if plat.startswith("win"):
        return _total_ram_windows()
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(
            os.sysconf("SC_PHYS_PAGES")
        )
    except (AttributeError, ValueError, OSError):
        pass
    if plat == "darwin":
        return _total_ram_macos()
    return None


# ---------------------------------------------------------------------------
# opt-in network probe (the ONLY network call in devin-doctor)
# ---------------------------------------------------------------------------


def _proxy_target(env: Mapping[str, str]) -> tuple[str, int] | None:
    for var in _PROXY_ENV_VARS:
        raw = env.get(var)
        if not raw:
            continue
        url = urlparse(raw if "://" in raw else f"http://{raw}")
        if url.hostname:
            return url.hostname, url.port or 8080
    return None


def _probe_outbound(env: Mapping[str, str]) -> bool:
    target = _proxy_target(env) or (NET_PROBE_HOST, NET_PROBE_PORT)
    try:
        with socket.create_connection(target, timeout=NET_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def _probe_listener() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# profile assembly
# ---------------------------------------------------------------------------


def collect_profile(
    config_dir: Path | None = None,
    probe_network: bool = False,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> dict[str, object]:
    """Build the capability profile dict. Pure JSON output is the contract;
    ``probe_network=True`` performs exactly one outbound TCP connect."""
    env = os.environ if environ is None else environ
    plat = sys.platform if platform is None else platform
    profile, _source = resolve_profile(env, config_dir)

    ram = total_ram_bytes(plat)
    outbound: bool | str = "unknown"
    listener: bool | str = "unknown"
    if probe_network:
        outbound = _probe_outbound(env)
        listener = _probe_listener()

    return {
        "profile": profile,
        "capabilities": {
            "scheduler": _has_scheduler(env, plat),
            "daemon": profile == "personal",
            "net.outbound": outbound,
            "net.listener": listener,
            "llm.local": (
                _which("ollama", env) is not None or bool(env.get("OLLAMA_HOST"))
            ),
            "comms": _has_comms(env, plat),
            "containers": (
                _which("docker", env) is not None
                or _which("podman", env) is not None
            ),
            "proxy": (
                _which("mitmproxy", env) is not None
                or _which("mitmdump", env) is not None
            ),
            "ram.heavy": ram is not None and ram >= RAM_HEAVY_BYTES,
            "multi-host": False,
        },
    }


def render_profile(profile: dict[str, object]) -> str:
    return json.dumps(profile, indent=2)
