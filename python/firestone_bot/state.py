"""MapStartState.ini: map points already clicked this session (MapStart.ahk memory).

[Memory]
SessionStart=YYYYMMDDHHMMSS   (AHK A_Now)
ClickedPoints=|x|y||x|y|...
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from datetime import datetime


def ahk_now() -> str:
    """AHK A_Now: LOCAL time, YYYYMMDDHHMMSS."""
    return datetime.now().strftime("%Y%m%d%H%M%S")  # noqa: DTZ005


def hours_since(stamp: str) -> float:
    """AHK `EnvSub, TimeDiff, %SessionStart%, Hours` (truncated to whole hours there)."""
    try:
        t = datetime.strptime(stamp.strip(), "%Y%m%d%H%M%S")  # noqa: DTZ007
    except ValueError:
        return 0.0
    return (datetime.now() - t).total_seconds() / 3600  # noqa: DTZ005


@dataclass
class MapState:
    path: str = "MapStartState.ini"
    session_start: str = ""
    clicked_points: str = ""
    extra: dict[str, dict[str, str]] = field(default_factory=dict)
    encoding: str = "utf-16"  # AHK writes UTF-16 LE when the file was created that way

    @classmethod
    def load(cls, path: str = "MapStartState.ini") -> MapState:
        s = cls(path=path)
        if not os.path.exists(path):
            return s
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.optionxform = str
        with open(path, "rb") as f:
            raw = f.read()
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            text, s.encoding = raw.decode("utf-16"), "utf-16"
        else:
            text, s.encoding = raw.decode("utf-8-sig"), "utf-8-sig"
        cp.read_string(text)
        for section in cp.sections():
            for k, v in cp.items(section):
                if section == "Memory" and k == "SessionStart":
                    s.session_start = v.strip()
                elif section == "Memory" and k == "ClickedPoints":
                    s.clicked_points = v.strip()
                else:
                    s.extra.setdefault(section, {})[k] = v
        return s

    def save(self) -> None:
        lines = [
            "[Memory]",
            f"SessionStart={self.session_start}",
            f"ClickedPoints={self.clicked_points}",
        ]
        for section, items in self.extra.items():
            lines.append(f"[{section}]")
            lines.extend(f"{k}={v}" for k, v in items.items())
        with open(self.path, "w", encoding=self.encoding, newline="\r\n") as f:
            f.write("\n".join(lines) + "\n")

    # -- MapStart.ahk helpers --------------------------------------------------------------
    @staticmethod
    def coord_id(x: int, y: int) -> str:
        return f"|{x}|{y}|"

    def was_clicked(self, x: int, y: int) -> bool:
        return self.coord_id(x, y) in self.clicked_points

    def mark_clicked(self, x: int, y: int) -> None:
        self.clicked_points += self.coord_id(x, y)
        self.save()

    def reset(self) -> None:
        self.clicked_points = ""
        self.session_start = ahk_now()
        self.save()
