"""Bug reports: a zip of the bot's logs, recent captures, settings and environment, uploaded to
the maintainer's server, which keeps it and tells him on Discord (owner request, 2026-10-22).
The player only gets an ID to give on Discord. The server side is docs/REPORT_API.md.

The environment (game window, store, scale, style...) is written to the log whenever it
changes, and again each day, as one `Environment: {json}` line: a player may close the game
before clicking Send report, and the report still says what the game looked like.
"""

from __future__ import annotations

import http.client
import io
import json
import logging
import os
import platform
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from firestone_bot import __version__, logfile

REPORT_URL = "https://fs-bot-logs.lutak.ovh/api/report"
MAX_BYTES = 20 * 1024 * 1024  # the server's cap on the zip
LOG_BUDGET = 8 * 1024 * 1024  # the newest log text, uncompressed (it compresses ~10x)
ZIP_MARGIN = 256 * 1024  # room for the central directory and report.json
NOTE_MAX = 500
UPLOAD_TIMEOUT_S = 60  # per block sent or read, not for the whole upload
ENV_MARK = "Environment: "
PRIVATE_KEYS = ("DiscordID", "ClientID")  # left out of the settings in the zip
log = logging.getLogger("firestone_bot.report")


class ReportError(Exception):
    """A report that could not be sent; the message is for the player."""


def platform_name() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def screen_size() -> str:
    if sys.platform != "win32":
        return "-"
    try:
        import ctypes

        user32 = ctypes.windll.user32
        return f"{user32.GetSystemMetrics(0)}x{user32.GetSystemMetrics(1)}"
    except Exception:  # noqa: BLE001 - informational only
        return "-"


_system: dict[str, str] = {}


def system_fields() -> dict[str, str]:
    """Bot version, OS, Python (read once) and the screen size (read each time: a laptop
    gets docked)."""
    if not _system:
        _system.update(
            bot_version=__version__, os=platform.platform(), python=platform.python_version()
        )
    return {**_system, "screen": screen_size()}


def window_fields(win) -> dict[str, str]:
    """The game window as the environment check shows it (same keys and wording)."""
    from firestone_bot.platform import process
    from firestone_bot.vision.viewport import Viewport

    # one word: the Mac backend reports a fullscreen window as maximized too
    state = " fullscreen" if win.fullscreen else " maximized" if win.maximized else ""
    out = {
        "window": f"'{win.title}' pid {win.pid}{state}",
        "platform": process.detect_platform(win.exe),
    }
    if win.client.w and win.client.h:
        vp = Viewport(win.client)
        aspect_ok = abs(win.client.w / win.client.h - 1920 / 1009) < 0.01
        out["client"] = f"{win.client.w}x{win.client.h} at ({win.client.x},{win.client.y})"
        out["scale"] = f"{vp.rel_scale:.3f} (canvas {vp.scale:.3f}), aspect " + (
            "OK" if aspect_ok else "differs from reference: anchors in use"
        )
    return out


_env: dict[str, str] = {}
_env_logged = ""
_env_lock = threading.Lock()


def _stable(env: dict[str, str]) -> str:
    """The environment without what changes at every check (the capture's time), and the
    day: logged once a day at least, so the kept log days always hold one."""
    steady = {k: re.sub(r" in \d+ ms", "", v) for k, v in env.items()}
    return time.strftime("%Y-%m-%d ") + json.dumps(steady, sort_keys=True)


def note_environment(fields: dict[str, str]) -> None:
    """Merge what a check or a cycle learnt; log the whole environment when it changed."""
    global _env_logged
    with _env_lock:
        fields = {k: str(v) for k, v in fields.items()}
        if fields.get("client", _env.get("client")) != _env.get("client"):
            # a capture size of the previous window would contradict the new one
            fields.setdefault("capture", "-")
        _env.update(system_fields())
        _env.update(fields)
        key = _stable(_env)
        if key == _env_logged:
            return
        _env_logged = key
        # under the lock: two threads never write their lines out of order
        log.info("%s%s", ENV_MARK, json.dumps(_env, sort_keys=True))


def last_environment(base: str) -> dict:
    """The last environment written to the logs (today's, then the kept days)."""
    for path in logfile.log_files(base):
        found = None
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    at = line.find(ENV_MARK)
                    if at >= 0:
                        found = line[at + len(ENV_MARK) :]
        except OSError:
            continue
        if found:
            try:
                return json.loads(found)
            except ValueError:
                pass
    return {}


def strip_private(text: str) -> str:
    """Settings text without the player's Discord ID and client id."""
    private = {k.lower() for k in PRIVATE_KEYS}
    keep = [
        line
        for line in text.splitlines()
        if "=" not in line or line.split("=", 1)[0].strip().lower() not in private
    ]
    return "\n".join(keep) + "\n"


def _home_patterns() -> list[re.Pattern[bytes]]:
    """The user's home folder as it shows in log lines (C:\\Users\\<name>, /Users/<name>)."""
    home = os.path.expanduser("~").rstrip("\\/")
    if len(home) < 4:
        return []
    forms = {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}
    flags = re.IGNORECASE if sys.platform == "win32" else 0
    return [re.compile(re.escape(f.encode("utf-8")), flags) for f in sorted(forms, key=len)[::-1]]


def _redact(data: bytes, patterns: list[re.Pattern[bytes]]) -> bytes:
    for pattern in patterns:
        data = pattern.sub(b"~", data)
    return data


def _tail(path: str, size: int) -> bytes:
    """The last `size` bytes of a file, from the first whole line."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        total = f.tell()
        f.seek(max(0, total - size))
        data = f.read(size)
    if total > size:
        cut = data.find(b"\n")
        data = data[cut + 1 :] if cut >= 0 else data
    return data


def _captures(base: str) -> list[str]:
    folder = os.path.join(base, "diagnostics")
    try:
        names = [n for n in os.listdir(folder) if n.lower().endswith(".png")]
    except OSError:
        return []
    paths = [os.path.join(folder, n) for n in names]

    def mtime(p: str) -> float:
        try:
            return os.path.getmtime(p)
        except OSError:
            return 0.0

    return sorted(paths, key=mtime, reverse=True)


def build(
    base: str,
    settings: str = "",
    note: str = "",
    env_now: dict | None = None,
    captures: bool = True,
    max_bytes: int = MAX_BYTES,
    log_budget: int = LOG_BUDGET,
) -> bytes:
    """The report zip: report.json, the newest logs (the home folder replaced by ~), the
    settings text without the private keys, the newest captures that fit."""
    buf = io.BytesIO()
    files: list[str] = []
    home = _home_patterns()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        left = log_budget
        for path in logfile.log_files(base):  # newest first; a cut file is the last one
            if left <= 0:
                break
            name = "logs/" + os.path.basename(path)
            try:
                cut = os.path.getsize(path) > left
                if cut:
                    data = _tail(path, left)
                else:
                    with open(path, "rb") as f:
                        data = f.read()
            except OSError:
                continue
            z.writestr(name, _redact(data, home))
            files.append(name)
            left -= len(data)
            if cut:
                break
        if settings:
            z.writestr("settings.ini", strip_private(settings))
            files.append("settings.ini")
        for path in _captures(base) if captures else ():
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if buf.tell() + size + ZIP_MARGIN > max_bytes:
                continue  # a smaller, older one may still fit
            name = "diagnostics/" + os.path.basename(path)
            try:
                z.write(path, name, compress_type=zipfile.ZIP_STORED)  # PNG: compressed already
            except OSError:
                continue
            files.append(name)
        info = {
            "version": __version__,
            "platform": platform_name(),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": note[:NOTE_MAX],
            "system": system_fields(),
            "environment": last_environment(base),
            "environment_now": env_now or {},
            "files": files,
        }
        z.writestr("report.json", json.dumps(info, indent=2, ensure_ascii=False))
    return buf.getvalue()


def upload(
    data: bytes,
    client_id: str,
    discord_id: str = "",
    note: str = "",
    timeout: float = UPLOAD_TIMEOUT_S,
) -> dict:
    """POST the zip; returns the server's answer ({"id", "size", "expires"})."""
    from firestone_bot.update import _ssl_context  # certifi roots (the macOS bundle has none)

    headers = {
        "Content-Type": "application/zip",
        # a file body is sent in blocks, each with its own timeout (one 20 MB write on a
        # slow line hit the timeout while data was still moving); the length is given so
        # urllib does not switch to chunked encoding
        "Content-Length": str(len(data)),
        "X-Client-Id": client_id,
        "X-Bot-Version": __version__,
        "X-Platform": platform_name(),
    }
    discord_id = discord_id.strip()
    if discord_id.isascii() and discord_id.isdigit():
        headers["X-Discord-Id"] = discord_id
    note = note.strip()[:NOTE_MAX]
    if note:
        headers["X-Report-Note"] = urllib.parse.quote(note, safe="")
    req = urllib.request.Request(REPORT_URL, data=io.BytesIO(data), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raise ReportError(_refusal(e)) from e
    except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
        reason = getattr(e, "reason", None) or e
        if isinstance(reason, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            # urllib sends the whole body before it reads an answer: a refusal sent early
            # (too many reports, server full, too large) reaches it as a cut connection
            raise ReportError(
                "the report server cut the connection during the upload (too many "
                "reports, server full or report too large); try again later"
            ) from e
        raise ReportError(f"the report server did not answer ({reason})") from e
    try:
        answer = json.loads(raw.decode("utf-8") or "{}")
    except ValueError as e:
        raise ReportError("the report server gave an unreadable answer") from e
    if not isinstance(answer, dict) or not answer.get("id"):
        raise ReportError("the report server gave no report ID")
    return answer


def _refusal(e: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(e.read().decode("utf-8") or "{}")
    except (ValueError, OSError, http.client.HTTPException):
        body = {}
    if not isinstance(body, dict):
        body = {}
    if e.code == 429:
        wait = body.get("retry_after") or (e.headers.get("Retry-After") if e.headers else 0)
        try:
            minutes = max(1, round(int(wait) / 60))
        except (TypeError, ValueError):
            minutes = 30
        return f"too many reports sent; try again in {minutes} min"
    if e.code == 413:
        return "the report is too large for the server"
    if e.code == 503:
        return "the report server is full for now; try again later"
    return f"the report server refused it ({e.code}: {body.get('error') or e.reason})"
