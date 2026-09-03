"""Resize / move / maximize the game window (used for the 4.2 and 4.6 measurements).

python -m firestone_bot.tools.window_tool --client 1280x720
python -m firestone_bot.tools.window_tool --client 1600x1000 --pos 100,50
python -m firestone_bot.tools.window_tool --maximize
python -m firestone_bot.tools.window_tool --toggle-fullscreen   (Alt+Enter in the game)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict

from firestone_bot.platform.dpi import set_dpi_aware

set_dpi_aware()


def main(argv: list[str] | None = None) -> int:
    import ctypes

    from firestone_bot.platform import input as inp
    from firestone_bot.platform.window import activate, find_game_window

    user32 = ctypes.windll.user32
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", help="WxH client size (restores the window first)")
    ap.add_argument("--pos", default="0,0", help="x,y of the window's outer top-left")
    ap.add_argument("--maximize", action="store_true")
    ap.add_argument("--toggle-fullscreen", action="store_true")
    args = ap.parse_args(argv)

    win = find_game_window()
    if args.toggle_fullscreen:
        activate(win)
        time.sleep(0.5)
        inp.hotkey("alt", "enter")
        time.sleep(3)
    elif args.maximize:
        user32.ShowWindow(win.handle, 9)  # SW_RESTORE
        time.sleep(0.3)
        user32.ShowWindow(win.handle, 3)  # SW_MAXIMIZE
        time.sleep(1.5)
    elif args.client:
        w, h = (int(v) for v in args.client.lower().split("x"))
        x, y = (int(v) for v in args.pos.split(","))
        user32.ShowWindow(win.handle, 9)  # SW_RESTORE
        time.sleep(0.5)
        win = find_game_window()
        fw = win.outer.w - win.client.w
        fh = win.outer.h - win.client.h
        user32.SetWindowPos(
            win.handle, 0, x, y, w + fw, h + fh, 0x0004 | 0x0040
        )  # NOZORDER|SHOWWINDOW
        time.sleep(1.5)
    win = find_game_window()
    print(json.dumps(asdict(win), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
