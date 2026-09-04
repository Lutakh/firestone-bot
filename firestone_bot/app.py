"""Wires settings, GUI, game context and runner together."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time

from firestone_bot.gui.main_window import MainWindow
from firestone_bot.platform.dpi import set_dpi_aware
from firestone_bot.settings import Settings

# The bot side (numpy, mss, pynput, features) is imported in _late_init(), after the window is
# on screen, so the user gets a window as early as possible.

log = logging.getLogger("firestone_bot.app")


def base_dir() -> str:
    """Directory holding settings.ini: next to the exe when frozen, else the cwd."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


class App:
    def __init__(self) -> None:
        self.dpi_mode = set_dpi_aware()
        self.base = base_dir()
        self.settings = Settings.load(os.path.join(self.base, "settings.ini"))
        self.game = None
        self.runner = None
        self.window = MainWindow(
            self.settings,
            on_start=self.start,
            on_stop=self.stop,
            on_dry_run=self.dry_run,
            on_self_test=self.self_test,
            on_exit=self.exit,
            is_running=lambda: self.runner is not None and self.runner.running,
            base_dir=self.base,
        )
        self._hotkey_listener = None
        self._exit_heartbeat: threading.Thread | None = None
        self._close_splash()
        # Screenshot / test helpers: open the GUI on a given page or appearance.
        if page := os.environ.get("FIRESTONE_GUI_PAGE"):
            self.window.show_page(page)
        if look := os.environ.get("FIRESTONE_GUI_APPEARANCE"):
            self.window.set_appearance(look)

    # -- startup --------------------------------------------------------------------------
    @staticmethod
    def _close_splash() -> None:
        """Close the PyInstaller splash (present only in the packaged build)."""
        try:
            import pyi_splash  # type: ignore[import-not-found]
        except ImportError:
            return  # no splash outside the frozen build
        try:
            pyi_splash.close()
        except Exception:
            log.debug("splash close failed", exc_info=True)

    def _late_init(self) -> None:
        """Import and wire the bot side once the window is on screen."""
        if self.runner is not None:
            return
        from firestone_bot.game import Game
        from firestone_bot.runner import Runner

        self.game = Game(self.settings, status_cb=self._status)
        self.game.map_state_path = os.path.join(self.base, "MapStartState.ini")
        self.runner = Runner(self.settings, self.game)
        self.runner.on_finished = lambda: self.window.root.after(600, self.present)
        self.window.on_env_restored = self._raise_window
        self._install_hotkey()
        self.window.root.after(100, self.present)

    def present(self) -> None:
        """While the bot is idle: game window in front (restored if minimised), then the bot
        window on top of it, so the user sees both."""
        if self.runner is not None and self.runner.running:
            return
        from firestone_bot.platform.window import GameWindowNotFound, activate, find_game_window

        try:
            activate(find_game_window())
        except GameWindowNotFound:
            pass
        root = self.window.root
        root.after(350, self._raise_window)

    def _raise_window(self) -> None:
        root = self.window.root
        try:
            if root.state() == "iconic":
                root.deiconify()
            root.lift()
            root.attributes("-topmost", True)
            root.after(400, lambda: root.attributes("-topmost", False))
            root.focus_force()
        except Exception:
            log.debug("raise window failed", exc_info=True)

    # -- callbacks --------------------------------------------------------------------------
    def _status(self, text: str) -> None:
        self.window.post_status(text)

    def start(self) -> None:
        self._late_init()
        if self.runner.running:
            return
        self.game.dry_run = False
        self.runner.start()
        self.window.set_bot_state("running")

    def dry_run(self) -> None:
        self._late_init()
        if self.runner.running:
            return
        self.game.dry_run = True
        self.runner.start()
        self.window.set_bot_state("dry run (no input)")

    def stop(self) -> None:
        if self.runner is None:
            return
        self.runner.stop()
        self.window.set_bot_state("stopping...")

    def exit(self) -> None:
        """Called on the Tk thread from the window's exit path, before settings are flushed:
        stop the runner and wait briefly so the bot thread's own settings.save() is over."""
        if self.runner is None:
            if self._hotkey_listener:
                self._hotkey_listener.stop()
            return
        self.runner.stop()
        # Blocking urlopen (10 s timeout): keep it off the UI thread, joined after mainloop.
        self._exit_heartbeat = threading.Thread(
            target=lambda: self.game.heartbeat("Exit Bot", is_stop=True, important=True),
            name="exit-heartbeat",
            daemon=True,
        )
        self._exit_heartbeat.start()
        t = self.runner.thread
        if t and t.is_alive():
            t.join(timeout=3)
        if self._hotkey_listener:
            self._hotkey_listener.stop()

    def self_test(self, restore: bool = False) -> dict[str, str]:
        from firestone_bot.platform import capture, process
        from firestone_bot.platform.window import GameWindowNotFound, activate, find_game_window
        from firestone_bot.vision.viewport import Viewport

        out = {"dpi": self.dpi_mode}
        try:
            win = find_game_window()
        except GameWindowNotFound:
            if process.find_game_process() is None:
                installs = ", ".join(process.installed_platforms()) or "none found"
                out.update(
                    window=f"game not running (installs: {installs}); START launches it",
                    platform="-",
                    client="-",
                    scale="-",
                    capture="-",
                )
            else:
                out.update(
                    window="game starting (no window yet)",
                    platform="-",
                    client="-",
                    scale="-",
                    capture="-",
                )
            return out
        restored = False
        if win.client.w == 0 and restore:  # minimised: bring it back to run the checks
            activate(win)
            time.sleep(0.6)
            win = find_game_window()
            restored = True
        if win.client.w == 0 or win.client.h == 0:
            out.update(
                window="game window minimised (Re-check restores it; START does too)"
                if not restore
                else "game window minimised and could not be restored",
                platform=process.detect_platform(win.exe),
                client="-",
                scale="-",
                capture="-",
            )
            return out
        vp = Viewport(win.client)
        out["window"] = (
            f"'{win.title}' pid {win.pid}"
            + (" maximized" if win.maximized else "")
            + (" (restored from minimised)" if restored else "")
        )
        out["platform"] = process.detect_platform(win.exe)
        out["client"] = f"{win.client.w}x{win.client.h} at ({win.client.x},{win.client.y})"
        aspect_ok = abs(win.client.w / win.client.h - 1920 / 1009) < 0.01
        out["scale"] = (
            f"{vp.rel_scale:.3f} (canvas {vp.scale:.3f}), aspect {'OK' if aspect_ok else 'differs from reference: anchors in use'}"
        )
        t0 = time.perf_counter()
        try:
            img = capture.grab(win.client)
            out["capture"] = (
                f"OK {img.shape[1]}x{img.shape[0]} in {1000 * (time.perf_counter() - t0):.0f} ms"
            )
        except Exception as e:  # noqa: BLE001
            out["capture"] = f"FAILED: {e}"
        out["input"] = "pynput SendInput (move test happens in the dry run trace)"
        return out

    # -- Win+Esc exit hotkey (AHK ~*#$Esc) ---------------------------------------------------
    def _install_hotkey(self) -> None:
        if self._hotkey_listener is not None:
            return
        try:
            from pynput import keyboard
        except Exception:  # noqa: BLE001
            return
        pressed: set = set()

        def on_press(key):
            pressed.add(key)
            if key == keyboard.Key.esc and (
                keyboard.Key.cmd in pressed
                or keyboard.Key.cmd_l in pressed
                or keyboard.Key.cmd_r in pressed
            ):
                self.window.request_exit()

        def on_release(key):
            pressed.discard(key)

        self._hotkey_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()

    def run(self) -> None:
        # wire the bot side shortly after the first frame; START/DRY RUN also do it on demand
        self.window.root.after(400, self._late_init)
        self.window.run()
        if self._exit_heartbeat is not None:
            self._exit_heartbeat.join(timeout=2)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(base_dir(), "firestone-bot.log"), encoding="utf-8")
        ],
    )
    App().run()
    return 0
