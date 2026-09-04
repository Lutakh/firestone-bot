"""Binding layer between the widgets and the live Settings object, with debounced auto-save.

Every bound key gets one variable (tk.StringVar in the real GUI, any object with
get/set/trace_add in tests). Writes go to `settings.set()` immediately (the bot reads the live
object at call time) and arm a 750 ms debounce; the save is deferred while the bot runs.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import datetime

from firestone_bot.settings import Settings

log = logging.getLogger("firestone_bot.gui")

SAVE_DELAY_MS = 750


def _flip(value: str) -> str:
    return {"1": "0", "0": "1"}.get(value.strip(), value)


class Binder:
    def __init__(
        self,
        settings: Settings,
        scheduler,
        on_state: Callable[[str, str], None],
        is_running: Callable[[], bool] = lambda: False,
        var_factory: Callable[..., object] | None = None,
        save_delay_ms: int = SAVE_DELAY_MS,
    ) -> None:
        self.settings = settings
        self.scheduler = scheduler  # object with after(ms, fn) -> id and after_cancel(id)
        self.on_state = on_state
        self.is_running = is_running
        self.save_delay_ms = save_delay_ms
        if var_factory is None:
            import tkinter as tk

            var_factory = tk.StringVar
        self._var_factory = var_factory
        self._vars: dict[str, tuple[object, bool]] = {}
        self._registered: set[str] = set()
        self._reload_hooks: list[Callable[[], None]] = []
        self._loading = False
        self._pending = None
        self.dirty = False
        self.save_failed_once = False
        self.on_save_error: Callable[[str], None] | None = None

    # -- variables ---------------------------------------------------------------------------
    def var(self, name: str, inverted: bool = False):
        if name in self._vars:
            return self._vars[name][0]
        raw = self.settings.get(name)
        v = self._var_factory(value=_flip(raw) if inverted else raw)
        v.trace_add("write", lambda *_: self._on_write(name, v, inverted))
        self._vars[name] = (v, inverted)
        return v

    def register(self, *names: str) -> None:
        """Declare keys written through `set_many` by composite widgets (coverage)."""
        self._registered.update(names)

    def on_reload(self, fn: Callable[[], None]) -> None:
        self._reload_hooks.append(fn)

    def keys(self) -> set[str]:
        return set(self._vars) | self._registered

    def _on_write(self, name: str, v, inverted: bool) -> None:
        if self._loading:
            return
        value = v.get()
        self.settings.set(name, _flip(value) if inverted else value)
        self.touch()

    def set_many(self, mapping: dict[str, str]) -> None:
        """Atomic multi-key write (radios, ordered lists): one touch()."""
        self._loading = True
        try:
            for name, value in mapping.items():
                self.settings.set(name, value)
                if name in self._vars:
                    v, inverted = self._vars[name]
                    v.set(_flip(value) if inverted else value)
        finally:
            self._loading = False
        self.touch()

    # -- saving ------------------------------------------------------------------------------
    def _cancel_pending(self) -> None:
        try:
            self.scheduler.after_cancel(self._pending)
        except Exception:  # noqa: BLE001, S110 - the callback may already have fired
            pass
        self._pending = None

    def touch(self) -> None:
        self.dirty = True
        if self._pending is not None:
            self._cancel_pending()
        self._pending = self.scheduler.after(self.save_delay_ms, self._debounced_save)
        self.on_state("unsaved", "Unsaved changes")

    def _debounced_save(self) -> None:
        self._pending = None
        if self.is_running():
            self.on_state("deferred", "Change active, saved when the bot stops")
            return
        self._save()

    def flush(self, force: bool = False) -> None:
        """Save now. While the bot runs the save stays deferred (the bot thread writes the
        daily counters itself); `force=True` is for the exit path, after the runner stopped."""
        if self._pending is not None:
            self._cancel_pending()
            self._pending = None
        if not self.dirty:
            return
        if self.is_running() and not force:
            self.on_state("deferred", "Change active, saved when the bot stops")
            return
        self._save()

    def _save(self) -> None:
        created = not os.path.exists(self.settings.path)
        try:
            self.settings.save()
        except Exception as e:
            log.exception("saving settings.ini failed")
            self.on_state("error", f"Save failed: {e}")
            if not self.save_failed_once and self.on_save_error:
                self.save_failed_once = True
                self.on_save_error(str(e))
            return
        self.dirty = False
        stamp = datetime.now().strftime("%H:%M:%S")  # noqa: DTZ005
        self.on_state("saved", "Saved (settings.ini created)" if created else f"Saved {stamp}")

    def reload(self) -> None:
        """Re-read settings.ini into the existing object and push values into the vars."""
        fresh = Settings.load(self.settings.path)
        self.settings.values.update(fresh.values)
        self.settings.extra = fresh.extra
        self.settings.encoding = fresh.encoding
        self._loading = True
        try:
            for name, (v, inverted) in self._vars.items():
                raw = self.settings.get(name)
                v.set(_flip(raw) if inverted else raw)
            for fn in self._reload_hooks:
                fn()
        finally:
            self._loading = False
        if self._pending is not None:
            self._cancel_pending()
            self._pending = None
        self.dirty = False
        self.on_state("saved", "Reloaded from disk")
