"""Self-update from the GitHub Releases of the project (owner request 2026-09-06).

Flow (all steps are explicit user clicks in the GUI, nothing happens on its own):
  check_latest()  -> the newest release, compared with __version__ (GitHub API, no token)
  download()      -> the archive for this OS into a temp dir, SHA256 checked against the
                     SHA256SUMS.txt attached to the release
  extract()       -> the payload (FirestoneBot/ folder, or FirestoneBot.app on macOS) into a
                     staging dir next to the install
  apply()         -> a small detached script waits for this process to exit, swaps the old
                     install aside by rename (never deleted first, same idea as
                     tools/build_exe.py), moves the new one in and relaunches the bot.

The user's files (settings.ini, MapStartState.ini, gui_state.json, the log) live next to the
install, so a swap never touches them. Runs from source only get the notification: the
install step needs the packaged layout.

Layouts handled (what the CI archives contain):
  Windows  FirestoneBot-windows.zip    -> FirestoneBot.exe + _internal/ at the zip root
  Linux    FirestoneBot-linux.tar.gz   -> FirestoneBot/ folder
  macOS    FirestoneBot-macos.zip      -> FirestoneBot.app (ditto --keepParent)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field

from firestone_bot import __version__

log = logging.getLogger("firestone_bot.update")

REPO = "Lutakh/firestone-bot"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
CHECKSUMS_NAME = "SHA256SUMS.txt"
ASSET_NAMES = {
    "win32": "FirestoneBot-windows.zip",
    "darwin": "FirestoneBot-macos.zip",
    "linux": "FirestoneBot-linux.tar.gz",
}
USER_AGENT = f"firestone-bot/{__version__}"
TIMEOUT_S = 15


@dataclass
class Release:
    version: str  # "0.2.0"
    tag: str  # "v0.2.0"
    notes: str
    assets: dict[str, str] = field(default_factory=dict)  # name -> download url
    page: str = RELEASES_PAGE

    @property
    def asset_url(self) -> str | None:
        return self.assets.get(asset_name())

    @property
    def checksums_url(self) -> str | None:
        return self.assets.get(CHECKSUMS_NAME)


class UpdateError(RuntimeError):
    pass


# -- versions ----------------------------------------------------------------------------
def parse_version(text: str) -> tuple[int, ...]:
    """'v1.2.3' / '1.2' -> (1, 2, 3); anything unparsable -> ()."""
    m = re.match(r"v?(\d+(?:\.\d+)*)", (text or "").strip())
    return tuple(int(p) for p in m.group(1).split(".")) if m else ()


def is_newer(candidate: str, current: str = __version__) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    if not a or not b:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def asset_name(platform: str = sys.platform) -> str:
    return ASSET_NAMES.get(platform, ASSET_NAMES["linux"])


# -- GitHub ------------------------------------------------------------------------------
def _get(url: str, accept: str = "application/vnd.github+json") -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return r.read()


def check_latest() -> Release:
    """Newest release on GitHub (raises UpdateError when unreachable)."""
    try:
        data = json.loads(_get(API_LATEST))
    except Exception as e:
        raise UpdateError(f"cannot reach GitHub: {e}") from e
    return release_from_api(data)


def release_from_api(data: dict) -> Release:
    tag = str(data.get("tag_name") or "")
    return Release(
        version=".".join(str(p) for p in parse_version(tag)) or tag,
        tag=tag,
        notes=str(data.get("body") or "").strip(),
        assets={
            a["name"]: a["browser_download_url"]
            for a in data.get("assets", [])
            if "name" in a and "browser_download_url" in a
        },
        page=str(data.get("html_url") or RELEASES_PAGE),
    )


def parse_checksums(text: str) -> dict[str, str]:
    """sha256sum format: '<hex>  <name>' per line -> {name: hex}."""
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            out[parts[-1].lstrip("*")] = parts[0].lower()
    return out


# -- download ----------------------------------------------------------------------------
def download(
    release: Release, dest_dir: str, progress: Callable[[int, int], None] | None = None
) -> str:
    """Download this OS's archive into dest_dir, verify its SHA256. Returns the file path."""
    url = release.asset_url
    if not url:
        raise UpdateError(f"release {release.tag} has no {asset_name()} asset")
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, asset_name())
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r, open(path, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while chunk := r.read(256 * 1024):
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except OSError as e:
        raise UpdateError(f"download failed: {e}") from e
    expected = None
    if release.checksums_url:
        try:
            expected = parse_checksums(_get(release.checksums_url, "text/plain").decode()).get(
                asset_name()
            )
        except Exception as e:
            raise UpdateError(f"cannot read {CHECKSUMS_NAME}: {e}") from e
    if expected is None:
        raise UpdateError(f"no SHA256 for {asset_name()} in the release (refusing to install)")
    actual = sha256_of(path)
    if actual != expected:
        os.remove(path)
        raise UpdateError(
            f"checksum mismatch for {asset_name()}: {actual[:12]}... != {expected[:12]}..."
        )
    return path


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


# -- extract -----------------------------------------------------------------------------
def _safe_members(names: list[str]) -> None:
    for n in names:
        if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/"):
            raise UpdateError(f"unsafe path in archive: {n}")


def extract(archive: str, staging: str) -> str:
    """Unpack the archive into `staging` and return the payload path: the folder holding
    FirestoneBot.exe / FirestoneBot (one-dir build) or the FirestoneBot.app bundle."""
    if os.path.exists(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            _safe_members(z.namelist())
            if sys.platform == "darwin":
                # ditto zips carry symlinks and permissions Python's ZipFile drops: use ditto
                subprocess.run(["ditto", "-x", "-k", archive, staging], check=True)
            else:
                z.extractall(staging)
    else:
        with tarfile.open(archive) as t:
            _safe_members(t.getnames())
            t.extractall(staging, filter="data")
    return find_payload(staging)


def find_payload(root: str) -> str:
    entries = os.listdir(root)
    if "FirestoneBot.app" in entries:
        return os.path.join(root, "FirestoneBot.app")
    if "FirestoneBot.exe" in entries or ("FirestoneBot" in entries and "_internal" in entries):
        return root
    if "FirestoneBot" in entries and os.path.isdir(os.path.join(root, "FirestoneBot")):
        return find_payload(os.path.join(root, "FirestoneBot"))
    raise UpdateError(f"no FirestoneBot payload found in {root}: {entries}")


# -- install -------------------------------------------------------------------------------
def install_target() -> str | None:
    """What the updater replaces: the .app bundle on macOS, the one-dir folder elsewhere.
    None when running from source."""
    if not getattr(sys, "frozen", False):
        return None
    exe_dir = os.path.dirname(sys.executable)
    if sys.platform == "darwin":
        app = os.path.dirname(os.path.dirname(exe_dir))
        return app if app.endswith(".app") else None
    return exe_dir


def updater_script(
    pid: int, target: str, payload: str, relaunch: list[str]
) -> tuple[str, list[str]]:
    """Text of the detached script and the command that runs it (pure, unit-tested).

    The script: wait for `pid` to exit, rename `target` to `target.old` (a rename of a
    still-open folder fails cleanly and nothing is lost), move `payload` to `target`, remove
    the .old copy, relaunch. Any failure leaves the .old copy in place."""
    if sys.platform == "win32":
        q = " ".join(f'"{a}"' for a in relaunch)
        text = "\r\n".join(
            [
                "@echo off",
                ":wait",
                f'tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL',
                "if not errorlevel 1 (timeout /t 1 /nobreak >NUL & goto wait)",
                f'if exist "{target}.old" rmdir /s /q "{target}.old"',
                f'move "{target}" "{target}.old" || exit /b 1',
                f'move "{payload}" "{target}" || (move "{target}.old" "{target}" & exit /b 1)',
                f'rmdir /s /q "{target}.old"',
                f'start "" {q}',
                'del "%~f0"',
            ]
        )
        return text, ["cmd", "/c"]
    q = " ".join(f"'{a}'" for a in relaunch)
    launch = f"open -n '{target}'" if sys.platform == "darwin" and target.endswith(".app") else q
    text = "\n".join(
        [
            "#!/bin/sh",
            f"while kill -0 {pid} 2>/dev/null; do sleep 0.5; done",
            f"rm -rf '{target}.old'",
            f"mv '{target}' '{target}.old' || exit 1",
            f"mv '{payload}' '{target}' || {{ mv '{target}.old' '{target}'; exit 1; }}",
            f"rm -rf '{target}.old'",
            f"{launch} &",
            'rm -f "$0"',
        ]
    )
    return text, ["/bin/sh"]


def apply(payload: str, target: str | None = None) -> None:
    """Write the updater script and start it detached; the caller must exit right after."""
    target = target or install_target()
    if target is None:
        raise UpdateError("running from source: update with git pull")
    payload = os.path.abspath(payload)
    target = os.path.abspath(target)
    if sys.platform == "darwin":
        relaunch = ["open", "-n", target]
    else:
        relaunch = [
            os.path.join(target, "FirestoneBot.exe" if sys.platform == "win32" else "FirestoneBot")
        ]
    text, runner = updater_script(os.getpid(), target, payload, relaunch)
    suffix = ".bat" if sys.platform == "win32" else ".sh"
    fd, script = tempfile.mkstemp(prefix="firestone-update-", suffix=suffix)
    with os.fdopen(fd, "w", newline="") as f:
        f.write(text)
    if sys.platform != "win32":
        os.chmod(script, 0o700)
    kwargs: dict = {"cwd": os.path.dirname(target), "close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([*runner, script], **kwargs)
    log.info("updater started: %s -> %s", payload, target)


def staging_dir(target: str | None = None) -> str:
    """Where the new build is unpacked: next to the install (same volume, so a rename works)."""
    target = target or install_target() or os.getcwd()
    return os.path.join(os.path.dirname(os.path.abspath(target)), "FirestoneBot.update")


def cleanup(target: str | None = None) -> None:
    """Delete the staging dir of a finished update (best effort, called at start-up)."""
    target = target or install_target()
    if target is None:
        return
    staging = staging_dir(target)
    if os.path.isdir(staging):
        shutil.rmtree(staging, ignore_errors=True)
        log.info("removed update staging dir %s", staging)
