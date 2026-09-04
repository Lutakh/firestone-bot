"""Small object handed to every page builder."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from firestone_bot.gui.binding import Binder
from firestone_bot.settings import Settings


@dataclass
class PageContext:
    settings: Settings
    binder: Binder
    callbacks: dict[str, Callable[..., Any]]
    show_page: Callable[[str], None]
    base_dir: str
    register_tick: Callable[[Callable[[], None]], None]
    root: Any = None
    window: Any = None
    extras: dict[str, Any] = field(default_factory=dict)

    def call(self, name: str, *args: Any) -> Any:
        fn = self.callbacks.get(name)
        return fn(*args) if fn else None
