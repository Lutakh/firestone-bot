"""macOS privacy permissions the bot depends on.

- Screen Recording: without it CGWindowListCreateImage (mss) silently returns the desktop
  wallpaper, so every probe misses. Checked with CGPreflightScreenCaptureAccess.
- Accessibility: pynput posts CGEvents (mouse, keyboard) and the window backend un-minimises /
  resizes through AXUIElement; both need the process to be trusted.

Permissions are granted to the RESPONSIBLE application: the terminal app for a venv run, the
bundle itself for FirestoneBot.app (System Settings > Privacy & Security).
"""

from __future__ import annotations

SETTINGS_HINT = "System Settings > Privacy & Security"


def _coregraphics_bool(name: str) -> bool:
    """Call a CoreGraphics function returning a bool through ctypes: pyobjc's lazy Quartz
    module lacks the metadata of these two functions in the PyInstaller bundle (KeyError
    'CGPreflightScreenCaptureAccess' at start-up in v0.2.10)."""
    import ctypes

    cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    fn = getattr(cg, name)
    fn.restype = ctypes.c_bool
    fn.argtypes = []
    return bool(fn())


def screen_recording_granted() -> bool:
    return _coregraphics_bool("CGPreflightScreenCaptureAccess")


def request_screen_recording() -> bool:
    """Shows the system prompt once per app; returns the current state."""
    return _coregraphics_bool("CGRequestScreenCaptureAccess")


def accessibility_granted(prompt: bool = False) -> bool:
    import ApplicationServices as AS

    if not prompt:
        return bool(AS.AXIsProcessTrusted())
    opts = {AS.kAXTrustedCheckOptionPrompt: True}
    return bool(AS.AXIsProcessTrustedWithOptions(opts))


def missing() -> list[str]:
    """Names of the permissions still to grant (empty when everything is in place)."""
    out = []
    if not screen_recording_granted():
        out.append("Screen Recording")
    if not accessibility_granted():
        out.append("Accessibility")
    return out


PANES = {
    "Screen Recording": "Privacy_ScreenCapture",
    "Accessibility": "Privacy_Accessibility",
}


def open_settings_pane(name: str) -> None:
    """Open System Settings on the Privacy pane for `name` (best effort)."""
    import subprocess

    pane = PANES.get(name)
    if pane:
        subprocess.Popen(
            ["open", f"x-apple.systempreferences:com.apple.preference.security?{pane}"]
        )
