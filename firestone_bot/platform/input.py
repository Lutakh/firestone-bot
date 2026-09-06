"""Mouse and keyboard injection via pynput (SendInput on Windows, CGEvents on macOS).

All coordinates are physical screen pixels (platform/types.py); on macOS pynput moves in
points, so positions are divided by the Retina factor in _pos(). Sleeps are NOT added here;
feature modules keep the AHK timing explicitly.
"""

from __future__ import annotations

import time

from .window import pixels_per_point

# pynput opens the display / installs hooks at import time, so it is imported on first use:
# importing the feature modules (tests, headless CI) must not need a display.
_mouse = None
_keyboard = None
_KEYS: dict[str, object] = {}
_Button = None
# Last injected event: (monotonic time, pointer position in pynput coordinates or None). The
# input guard (inputguard.py) uses it to tell the bot's own events from the user's.
_last_injection: tuple[float, tuple[float, float] | None] = (0.0, None)


def _note(pos: tuple[float, float] | None = None) -> None:
    global _last_injection
    _last_injection = (time.monotonic(), pos if pos is not None else _last_injection[1])


def last_injection() -> tuple[float, tuple[float, float] | None]:
    return _last_injection


def restore_position() -> None:
    """Put the pointer back where the bot last left it (after a pause the user moved it)."""
    pos = _last_injection[1]
    if pos is not None and _mouse is not None:
        _note(pos)
        _mouse.position = pos


def prepare() -> None:
    """macOS: run pynput's main-thread-only layout lookups now (call from the main thread
    before any worker creates a controller or listener). No-op elsewhere."""
    import sys

    if sys.platform == "darwin":
        from .mac.pynput_fix import prepare_on_main_thread

        prepare_on_main_thread()


def _ensure() -> None:
    global _mouse, _keyboard, _Button
    if _mouse is not None:
        return
    prepare()
    from pynput.keyboard import Controller as KeyboardController
    from pynput.keyboard import Key
    from pynput.mouse import Button
    from pynput.mouse import Controller as MouseController

    _mouse = MouseController()
    _keyboard = KeyboardController()
    _Button = Button
    _KEYS.update(
        {
            "alt": Key.alt,
            "enter": Key.enter,
            "tab": Key.tab,
            "left": Key.left,
            "right": Key.right,
            "esc": Key.esc,
        }
    )


def _pos(x: int, y: int) -> tuple[float, float]:
    """Physical pixels -> pynput coordinates (points on macOS, pixels elsewhere)."""
    f = pixels_per_point()
    return (x, y) if f == 1.0 else (x / f, y / f)


def move(x: int, y: int) -> None:
    _ensure()
    _note(_pos(x, y))
    _mouse.position = _pos(x, y)


def click(button: str = "left") -> None:
    _ensure()
    _note()
    _mouse.click(_Button.left if button == "left" else _Button.right)


def click_at(x: int, y: int) -> None:
    move(x, y)
    click()


def drag(x1: int, y1: int, x2: int, y2: int, steps: int = 8, step_interval: float = 0.04) -> None:
    """Left-button drag from (x1,y1) to (x2,y2) in `steps` moves (screen pixels)."""
    _ensure()
    _note(_pos(x1, y1))
    _mouse.position = _pos(x1, y1)
    time.sleep(0.2)
    _note()
    _mouse.press(_Button.left)
    time.sleep(0.15)
    for i in range(1, steps + 1):
        pos = _pos(x1 + (x2 - x1) * i // steps, y1 + (y2 - y1) * i // steps)
        _note(pos)
        _mouse.position = pos
        time.sleep(step_interval)
    time.sleep(0.15)
    _note()
    _mouse.release(_Button.left)


def wheel(notches: int, interval: float = 0.2) -> None:
    """Scroll `notches` wheel clicks (negative = down, like AHK WheelDown), `interval` apart."""
    _ensure()
    step = 1 if notches > 0 else -1
    for _ in range(abs(notches)):
        _note()
        _mouse.scroll(0, step)
        time.sleep(interval)


def _key(name: str):
    _ensure()
    return _KEYS.get(name.lower(), name)


def key(name: str) -> None:
    _ensure()
    _note()
    _keyboard.tap(_key(name))


def key_down(name: str) -> None:
    _ensure()
    _note()
    _keyboard.press(_key(name))


def key_up(name: str) -> None:
    _ensure()
    _note()
    _keyboard.release(_key(name))


def hotkey(*names: str) -> None:
    """Press keys in order, release in reverse (e.g. hotkey("alt", "enter"))."""
    _ensure()
    keys = [_key(n) for n in names]
    for k in keys:
        _keyboard.press(k)
    for k in reversed(keys):
        _keyboard.release(k)
