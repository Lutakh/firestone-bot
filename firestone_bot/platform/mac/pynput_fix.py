"""pynput on macOS 26: the keyboard layout lookups must run on the main thread.

pynput.keyboard Controller.__init__ and Listener._run call keycode_context(), which uses
Carbon's TISCopyCurrentKeyboardInputSource / TISGetInputSourceProperty. Since macOS 26 these
assert the main dispatch queue and kill the process with SIGTRAP when called from another
thread (the bot worker creating the controller, the hotkey listener thread) - measured
2026-09-05, crash report in dispatch_assert_queue_fail <- TSMGetInputSourceProperty.

The context is a plain tuple (keyboard type, layout data bytes), so it is computed once on the
main thread and handed back to pynput from then on. Keyboard layout changes while the bot runs
are not picked up (the bot only sends ASCII keys and hotkeys).
"""

from __future__ import annotations

import contextlib
import threading

_context = None


def prepare_on_main_thread() -> bool:
    """Compute the layout context now (main thread only) and patch pynput to reuse it.
    Returns True when done (or already done), False when called from another thread."""
    global _context
    if _context is not None:
        return True
    if threading.current_thread() is not threading.main_thread():
        return False
    from pynput._util import darwin as util

    with util.keycode_context() as ctx:
        _context = ctx

    @contextlib.contextmanager
    def fixed_context():
        yield _context

    util.keycode_context = fixed_context
    try:
        from pynput.keyboard import _darwin

        _darwin.keycode_context = fixed_context  # imported by name there
    except ImportError:
        pass
    return True
