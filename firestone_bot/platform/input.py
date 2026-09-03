"""Mouse and keyboard injection via pynput (SendInput with scan codes on Windows).

All coordinates are physical screen pixels. Sleeps are NOT added here; feature modules keep
the AHK timing explicitly.
"""

from __future__ import annotations

import time

from pynput.keyboard import Controller as _KeyboardController
from pynput.keyboard import Key
from pynput.mouse import Button
from pynput.mouse import Controller as _MouseController

_mouse = _MouseController()
_keyboard = _KeyboardController()

KEYS = {
    "alt": Key.alt,
    "enter": Key.enter,
    "tab": Key.tab,
    "left": Key.left,
    "right": Key.right,
    "esc": Key.esc,
}


def move(x: int, y: int) -> None:
    _mouse.position = (x, y)


def click(button: str = "left") -> None:
    _mouse.click(Button.left if button == "left" else Button.right)


def click_at(x: int, y: int) -> None:
    move(x, y)
    click()


def wheel(notches: int, interval: float = 0.2) -> None:
    """Scroll `notches` wheel clicks (negative = down, like AHK WheelDown), `interval` apart."""
    step = 1 if notches > 0 else -1
    for _ in range(abs(notches)):
        _mouse.scroll(0, step)
        time.sleep(interval)


def _key(name: str):
    return KEYS.get(name.lower(), name)


def key(name: str) -> None:
    _keyboard.tap(_key(name))


def key_down(name: str) -> None:
    _keyboard.press(_key(name))


def key_up(name: str) -> None:
    _keyboard.release(_key(name))


def hotkey(*names: str) -> None:
    """Press keys in order, release in reverse (e.g. hotkey("alt", "enter"))."""
    keys = [_key(n) for n in names]
    for k in keys:
        _keyboard.press(k)
    for k in reversed(keys):
        _keyboard.release(k)
