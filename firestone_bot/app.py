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
    """Directory holding settings.ini (see firestone_bot.paths.data_dir)."""
    from firestone_bot.paths import data_dir

    return data_dir()


class App:
    def __init__(self, autostart: bool = False) -> None:
        self.autostart = autostart
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
        self._update: dict = {"release": None, "payload": None, "busy": False, "last": 0.0}
        self.window.on_check_updates = lambda: self.check_updates(manual=True)
        self.window.on_install_update = self.install_update
        self.window.on_rollback_update = self.rollback_update
        self.window.on_import_settings = self.import_settings
        self._close_splash()
        self.window.root.after(800, self._startup_dialogs)
        # Screenshot / test helpers: open the GUI on a given page or appearance.
        if page := os.environ.get("FIRESTONE_GUI_PAGE"):
            self.window.show_page(page)
        if look := os.environ.get("FIRESTONE_GUI_APPEARANCE"):
            self.window.set_appearance(look)

    # -- startup --------------------------------------------------------------------------
    @staticmethod
    def _close_splash() -> None:
        """Close the PyInstaller splash (present only in the packaged build)."""
        if sys.platform == "darwin":
            return  # no Splash on macOS; importing pyi_splash there logs a KeyError traceback
        try:
            import pyi_splash  # type: ignore[import-not-found]
        except ImportError:
            return  # no splash outside the frozen build
        try:
            pyi_splash.close()
        except Exception:
            log.debug("splash close failed", exc_info=True)

    def _mac_permissions_guide(self) -> None:
        """First-run help on macOS: name the missing permissions, trigger the system prompts
        and open the right pane of System Settings (owner request 2026-09-06)."""
        from tkinter import messagebox

        from firestone_bot.platform.mac import permissions

        missing = permissions.missing()
        if not missing:
            return
        names = " and ".join(missing)
        messagebox.showinfo(
            "macOS permissions",
            f"Firestone Bot needs {names}.\n\n"
            "System Settings > Privacy & Security opens next: enable Firestone Bot (or the "
            "terminal app that runs it) under each of these entries, then restart the bot.\n\n"
            "Screen Recording lets the bot read the game screen; Accessibility lets it move "
            "the mouse and type.",
            parent=self.window.root,
        )
        if "Screen Recording" in missing:
            permissions.request_screen_recording()  # system prompt, once per app
        if "Accessibility" in missing:
            permissions.accessibility_granted(prompt=True)
        permissions.open_settings_pane(missing[0])

    def _startup_dialogs(self) -> None:
        """One after the other (each is modal): settings import, then macOS permissions."""
        if not os.path.exists(self.settings.path):
            self._offer_settings_import()
        if sys.platform == "darwin":
            self._mac_permissions_guide()

    # -- user files (settings.ini next to the bot) -------------------------------------------
    def _offer_settings_import(self) -> None:
        """No settings.ini in the data folder (fresh manual download): look for one in the
        usual places and offer to copy it, never moving or overwriting anything. On macOS
        only the folder holding the .app is looked at, and only when that folder is not a
        protected one (Desktop, Documents, Downloads: reading them would trigger a privacy
        prompt); Advanced > Files imports from anywhere on an explicit click."""
        from tkinter import messagebox

        from firestone_bot import userfiles

        try:
            found = userfiles.find_candidates(self.base)
        except Exception:
            log.exception("settings search failed")
            found = []
        if not found:
            log.info("no settings.ini next to the bot and none found nearby")
            return
        best = found[0]
        more = f"\n\n({len(found) - 1} other folder(s) found; Advanced > Files imports any.)"
        if not messagebox.askyesno(
            "Import your settings?",
            "There is no settings.ini next to this bot, so defaults are in use.\n\n"
            f"Found one in:\n{best.label}\n\nCopy it here (with MapStartState.ini and "
            "gui_state.json when present)? The old folder is left untouched."
            + (more if len(found) > 1 else ""),
            parent=self.window.root,
        ):
            return
        self._import_from(best.folder)

    def import_settings(self) -> None:
        """Advanced > Files: pick a folder and copy the user files from it."""
        from tkinter import filedialog

        folder = filedialog.askdirectory(
            title="Folder holding your settings.ini", parent=self.window.root
        )
        if folder:
            self._import_from(folder)

    def _import_from(self, folder: str) -> None:
        from tkinter import messagebox

        from firestone_bot import userfiles

        try:
            copied, skipped = userfiles.import_user_files(folder, self.base)
        except Exception as e:
            log.exception("import from %s failed", folder)
            messagebox.showerror("Import failed", str(e), parent=self.window.root)
            return
        log.info("imported %s from %s (skipped %s)", copied, folder, skipped)
        if not copied:
            messagebox.showinfo(
                "Nothing imported",
                "No settings.ini in that folder"
                if not skipped
                else f"Already present here, not overwritten: {', '.join(skipped)}",
                parent=self.window.root,
            )
            return
        if "settings.ini" in copied:
            try:
                self.window.binder.reload()
            except Exception:
                log.exception("reload after import failed")
        text = f"Copied {', '.join(copied)} from {folder}."
        if skipped:
            text += f"\nAlready here, kept as is: {', '.join(skipped)}."
        if "gui_state.json" in copied:
            text += "\nWindow layout applies at next start."
        messagebox.showinfo("Settings imported", text, parent=self.window.root)

    def _late_init(self) -> None:
        """Import and wire the bot side once the window is on screen."""
        if self.runner is not None:
            return
        from firestone_bot.game import Game
        from firestone_bot.platform import input as inp
        from firestone_bot.runner import Runner

        inp.prepare()  # macOS: pynput layout lookups on the Tk (main) thread, see mac/pynput_fix
        self.game = Game(self.settings, status_cb=self._status)
        self.game.map_state_path = os.path.join(self.base, "MapStartState.ini")
        self.runner = Runner(self.settings, self.game)
        self.runner.on_finished = lambda: self.window.root.after(600, self.present)
        self.window.on_env_restored = self._raise_window
        self._install_hotkey()
        self.window.root.after(100, self.present)
        self.window.root.after(2000, self._update_cleanup)
        self.window.root.after(2500, self._announce_previous)
        self.window.root.after(3000, self.check_updates)
        self.window.root.after(60_000, self._update_tick)

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
        if sys.platform == "darwin":
            from firestone_bot.platform.mac import permissions

            missing = permissions.missing()
            if missing:
                out["window"] = (
                    "macOS permission missing: "
                    + ", ".join(missing)
                    + f" ({permissions.SETTINGS_HINT})"
                )
                out.update(platform="-", client="-", scale="-", capture="-", input="-")
                return out
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
        if sys.platform == "darwin":
            from firestone_bot.platform.window import pixels_per_point

            out["dpi"] = (
                f"macOS, {pixels_per_point():g} px per point (capture in pixels, input in points)"
            )
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
        out["input"] = (
            "pynput CGEvent, Accessibility granted (move test happens in the dry run trace)"
            if sys.platform == "darwin"
            else "pynput SendInput (move test happens in the dry run trace)"
        )
        return out

    # -- self-update (firestone_bot.update) --------------------------------------------------
    UPDATE_CHECK_INTERVAL_S = 24 * 3600

    def _update_cleanup(self) -> None:
        """Remove the staging dir a previous update left next to the install."""
        from firestone_bot import update

        threading.Thread(target=update.cleanup, name="update-cleanup", daemon=True).start()

    def _announce_previous(self) -> None:
        """Right after an update: say that the old version is one click away."""
        from firestone_bot import update

        marker = update.previous_marker()
        if not marker or marker.get("replaced_by") != update.__version__:
            return
        self.window.show_update(
            f"Updated to {update.__version__}. Version {marker.get('version')} is kept: "
            "Advanced > Updates restores it in one click.",
            None,
        )
        self.window.root.after(30_000, lambda: self.window.show_update("", None))

    def rollback_update(self) -> None:
        """Advanced > Updates: swap FirestoneBot.previous back in and restart."""
        from tkinter import messagebox

        from firestone_bot import update

        if self.runner is not None and self.runner.running:
            messagebox.showinfo(
                "Restore", "Stop the bot first, then restore.", parent=self.window.root
            )
            return
        prev = update.previous_version()
        if prev is None:
            messagebox.showinfo("Restore", "No previous version is kept.", parent=self.window.root)
            return
        if not messagebox.askyesno(
            "Restore previous version",
            f"Go back to version {prev}? The bot closes, the program files are swapped back "
            f"(your settings.ini stays), and version {update.__version__} is kept in its place "
            "so you can return to it the same way.",
            parent=self.window.root,
        ):
            return
        try:
            update.rollback()
        except Exception as e:
            log.exception("rollback failed")
            messagebox.showerror("Restore failed", str(e), parent=self.window.root)
            return
        self.window.request_exit()

    def _update_tick(self) -> None:
        if time.monotonic() - self._update["last"] > self.UPDATE_CHECK_INTERVAL_S:
            self.check_updates()
        self.window.root.after(60_000, self._update_tick)

    def check_updates(self, manual: bool = False) -> None:
        """Query GitHub on a worker thread; show the banner when a newer release exists."""
        from firestone_bot import update

        if self._update["busy"]:
            return
        self._update["last"] = time.monotonic()
        win = self.window

        def worker():
            try:
                rel = update.check_latest()
            except update.UpdateError as e:
                msg = str(e)
                log.info("update check: %s", msg)
                if manual:
                    win.post_call(lambda: win.show_update(f"Update check failed: {msg}", None))
                return
            if update.is_newer(rel.version):
                self._update["release"] = rel
                self._update["payload"] = None
                frozen = update.install_target() is not None
                text = f"Version {rel.version} is available (you run {update.__version__})."
                if not frozen:
                    text += " Running from source: update with git pull."
                win.post_call(
                    lambda: win.show_update(
                        text, "Update" if frozen else "Open releases page", "warn"
                    )
                )
            elif manual:
                win.post_call(
                    lambda: win.show_update(
                        f"You run the latest version ({update.__version__}).", None, "ok"
                    )
                )
                win.root.after(8000, lambda: win.show_update("", None))

        threading.Thread(target=worker, name="update-check", daemon=True).start()

    def install_update(self) -> None:
        """Download + verify on a worker thread, then ask before swapping and restarting."""
        import webbrowser
        from tkinter import messagebox

        from firestone_bot import update

        rel = self._update["release"]
        if rel is None or self._update["busy"]:
            return
        if self._update["payload"] is not None:
            self._ask_install()  # already downloaded: the banner button installs
            return
        target = update.install_target()
        if target is None:
            webbrowser.open(rel.page)
            return
        if self.runner is not None and self.runner.running:
            messagebox.showinfo(
                "Update", "Stop the bot first, then update.", parent=self.window.root
            )
            return
        from firestone_bot.gui.update_dialog import UpdateDialog

        UpdateDialog(
            self.window.root,
            title="Update available",
            headline=f"Version {rel.version} is available",
            subtitle=f"You run {update.__version__}. The download is verified (SHA256) and "
            "the bot asks again before installing.",
            notes=rel.notes,
            buttons=[
                ("Download", self._download_update, True),
                ("Release page", lambda: webbrowser.open(rel.page), False),
                ("Later", None, False),
            ],
        )

    def _download_update(self) -> None:
        """Download + verify on a worker thread, then offer to install."""
        from firestone_bot import update

        rel = self._update["release"]
        if rel is None or self._update["busy"]:
            return
        target = update.install_target()
        self._update["busy"] = True
        win = self.window

        def worker():
            try:
                tmp = os.path.join(update.staging_dir(target), "download")
                win.post_call(lambda: win.show_update(f"Downloading {rel.version}…", None))

                def progress(done, total):
                    pct = f" {100 * done // total} %" if total else f" {done // 1_000_000} MB"
                    win.post_call(lambda: win.show_update(f"Downloading {rel.version}…{pct}", None))

                archive = update.download(rel, tmp, progress)
                win.post_call(lambda: win.show_update("Checksum OK, unpacking…", None))
                payload = update.extract(archive, os.path.join(update.staging_dir(target), "new"))
                self._update["payload"] = payload
                win.post_call(self._ask_install)
            except Exception as e:
                msg = str(e)
                log.exception("update failed")
                win.post_call(lambda: win.show_update(f"Update failed: {msg}", "Retry", "err"))
            finally:
                self._update["busy"] = False

        threading.Thread(target=worker, name="update-download", daemon=True).start()

    def _ask_install(self) -> None:
        """The archive is unpacked: green banner and a modal to install now or later."""
        from firestone_bot.gui.update_dialog import UpdateDialog

        rel = self._update["release"]
        self.window.show_update(
            f"Version {rel.version} is downloaded and verified.", "Install and restart", "ok"
        )
        UpdateDialog(
            self.window.root,
            title="Install update",
            headline=f"Install version {rel.version}?",
            subtitle="The bot closes, the new version replaces the program files (your "
            "settings.ini and counters stay) and starts again. The current version is kept "
            "for a one-click rollback (Advanced > Updates).",
            notes=rel.notes,
            buttons=[("Install and restart", self._install_now, True), ("Later", None, False)],
        )

    def _install_now(self) -> None:
        from firestone_bot import update

        rel, payload = self._update["release"], self._update["payload"]
        if self.runner is not None and self.runner.running:
            self.window.show_update(
                "Stop the bot first, then install.", "Install and restart", "warn"
            )
            return
        try:
            update.apply(payload, new_version=rel.version)
        except Exception as e:
            log.exception("update apply failed")
            self.window.show_update(f"Update failed: {e}", "Retry", "err")
            return
        self.window.request_exit()

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
        if self.autostart:
            self.window.root.after(1500, self.start)
        self.window.run()
        if self._exit_heartbeat is not None:
            self._exit_heartbeat.join(timeout=2)


def main(autostart: bool = False) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(base_dir(), "firestone-bot.log"), encoding="utf-8")
        ],
    )
    App(autostart=autostart).run()
    return 0
