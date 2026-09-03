"""Process DPI awareness.

Must be called before anything creates a window or grabs the screen (mss sets its own
awareness on import, so this module has to run first). On non-Windows platforms it is a no-op.
"""

from __future__ import annotations

import ctypes
import sys

_DONE = False
_MODE = "none"


def set_dpi_aware() -> str:
    """Make the process per-monitor DPI aware. Returns the mode that was applied."""
    global _DONE, _MODE
    if _DONE:
        return _MODE
    _DONE = True
    _MODE = _apply()
    return _MODE


def _apply() -> str:
    if sys.platform != "win32":
        return "n/a"
    user32 = ctypes.windll.user32
    # Windows 10 1703+: DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
    try:
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return "per-monitor-v2"
    except (AttributeError, OSError):
        pass
    # Windows 8.1+: PROCESS_PER_MONITOR_DPI_AWARE = 2
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return "per-monitor"
    except (AttributeError, OSError):
        pass
    try:
        if user32.SetProcessDPIAware():
            return "system"
    except (AttributeError, OSError):
        pass
    return "none"
