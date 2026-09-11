"""Keep an unattended run alive when the program that started it goes away (Windows).

A process joins the job object of the process that creates it. Applications that run
commands for the user (IDEs, AI assistants, some terminals) keep everything they start in a
job of their own and end it when they close or update: on 2026-09-11 the Claude desktop app
updated itself at 03:03:51 and took down a night run it had started (Windows logged the bot
as "stopped interacting with Windows and was closed" at that very second, after 152 clean
cycles). A process created through WMI (Win32_Process.Create) is a child of WmiPrvSE and
lives in the user session's own job instead (measured the same day: one probe started with
Start-Process shared its job with claude.exe, the same probe started through WMI shared it
with the session's programs, Epic and the game included).

So an unattended start (--start) of the Windows exe re-creates itself through WMI once and
exits; the new instance carries DETACHED_FLAG so it never does it again. A double-click start
is left alone, a start from source too, and any failure falls back to running in place.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

DETACHED_FLAG = "--detached"
CREATE_NO_WINDOW = 0x08000000


def should_detach(argv: Sequence[str], frozen: bool, platform: str) -> bool:
    """Only the Windows exe started unattended, and only once."""
    return platform == "win32" and frozen and "--start" in argv and DETACHED_FLAG not in argv


def command_line(exe: str, args: Sequence[str]) -> str:
    """The Windows command line of `exe args` (paths with spaces quoted)."""
    return subprocess.list2cmdline([exe, *args])


def _ps_quote(text: str) -> str:
    """A PowerShell single-quoted string literal."""
    return "'" + text.replace("'", "''") + "'"


def relaunch_detached(exe: str, args: Sequence[str], cwd: str, timeout: float = 30.0) -> bool:
    """Start `exe args --detached` through WMI. True when Windows reports the process created
    (then the caller exits and the new instance takes over), False on any failure."""
    cmd = command_line(exe, [*args, DETACHED_FLAG])
    script = (
        "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
        f"@{{CommandLine={_ps_quote(cmd)}; CurrentDirectory={_ps_quote(cwd)}}}; "
        "if ($r -and $r.ReturnValue -eq 0 -and $r.ProcessId) { exit 0 } else { exit 1 }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            check=False,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0
