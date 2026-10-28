"""VirusTotal verdict on a release file, for the `virustotal` job of .github/workflows/build.yml.

    python -m firestone_bot.tools.virustotal exe/FirestoneBot.exe \
        --summary "$GITHUB_STEP_SUMMARY" --notes virustotal.md

Players' Microsoft Defender quarantined the Windows release as Trojan:Win32/Bearfoos.B!ml
(2026-10). Every CI run now gives its FirestoneBot.exe to VirusTotal (owner, 2026-10-28: the
key of a free account is the repository secret VT_API_KEY). The file is looked up by SHA-256,
uploaded when VirusTotal has never seen it (every build is a new file: PyInstaller stamps the
build time) and its analysis waited for, minutes: the job runs apart, and neither the
archives nor the release wait for it.

- the run summary (--summary) lists the engines that flag the file, Microsoft's verdict and
  the report link; one annotation says the same in a line, a warning when an engine flags
  the file. Microsoft's engine on VirusTotal can disagree with Defender on a player's PC
  (VirusTotal's engines are not always set up like the installed products);
- --notes gets the report link as soon as VirusTotal holds the file, before the analysis is
  waited for; the job adds it to a tag's release notes;
- it never fails the run: without the key, on a VirusTotal error or when the analysis is not
  done after --timeout seconds, it says so and exits 0.

Public API limits: 4 requests a minute, 500 a day. One lookup, one upload, then one poll
every POLL_S; a 429 (quota) or a 503/504 (VirusTotal busy) waits RETRY_WAIT_S and tries again.
Standard library only, with the TLS roots of update._ssl_context: the job runs it from the
checkout without installing the bot.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass

API = "https://www.virustotal.com/api/v3"
REPORT = "https://www.virustotal.com/gui/file/"
KEY_ENV = "VT_API_KEY"
TIMEOUT_S = 600  # wait this long for an upload's analysis (--timeout)
POLL_S = 30  # one analysis poll this often (--poll); the public API allows 4 requests a minute
RETRY_STATUS = (429, 503, 504)  # quota exceeded, VirusTotal busy or slow: worth another try
RETRY_WAIT_S = 60  # ... after this long (a 429 is the per-minute quota), RETRY_TRIES times
RETRY_TRIES = 3
HTTP_TIMEOUT_S = 120  # one request, the upload included
UPLOAD_MAX = 32 * 1024 * 1024  # POST /files takes up to 32 MB (the exe is about 6 MB)
MICROSOFT = "Microsoft"  # VirusTotal's name for Defender's engine
FLAGGED = ("malicious", "suspicious")
# categories that are a verdict on the file; type-unsupported, timeout, confirmed-timeout and
# failure are not
JUDGED = FLAGGED + ("undetected", "harmless")
TOP = 5  # engines named in the one-line annotation


class VirusTotalError(Exception):
    """A request VirusTotal refused, cut or answered with something unexpected."""


@dataclass
class Verdict:
    """What the engines said about one file (results: engine -> {"category", "result"})."""

    sha256: str
    results: dict
    complete: bool = True  # False: the analysis was still running when the wait ended

    @property
    def link(self) -> str:
        return REPORT + self.sha256

    @property
    def judged(self) -> int:
        """Engines that gave a verdict (the denominator VirusTotal shows)."""
        return sum(1 for r in self.results.values() if r.get("category") in JUDGED)

    @property
    def flagged(self) -> list[tuple[str, str]]:
        """(engine, detection name) of the engines that flag the file, Microsoft first."""
        hits = [
            (engine, r.get("result") or r["category"])
            for engine, r in self.results.items()
            if r.get("category") in FLAGGED
        ]
        return sorted(hits, key=lambda h: (h[0] != MICROSOFT, h[0].lower()))

    @property
    def microsoft(self) -> str:
        """Microsoft's verdict in words: its detection name, "clean" or "no verdict"."""
        r = self.results.get(MICROSOFT) or {}
        category = r.get("category")
        if category in FLAGGED:
            return r.get("result") or category
        return "clean" if category in JUDGED else "no verdict"


def _urlopen(req: urllib.request.Request):
    from firestone_bot.update import _ssl_context  # certifi roots when certifi is installed

    return urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S, context=_ssl_context())


def _error_text(e: urllib.error.HTTPError) -> str:
    """VirusTotal's error code and message ({"error": {"code", "message"}}), or the reason."""
    try:
        error = json.loads(e.read() or b"{}").get("error") or {}
    except (ValueError, OSError, AttributeError, http.client.HTTPException):  # cut or not JSON
        error = {}
    if not isinstance(error, dict):  # off-spec, such as {"error": "text"}
        error = {}
    text = " ".join(str(error[k]) for k in ("code", "message") if error.get(k))
    return text or str(e.reason)


def multipart(field: str, filename: str, data: bytes) -> tuple[bytes, str]:
    """multipart/form-data body holding one file, and its Content-Type header."""
    boundary = uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode("ascii")
    return head + data + tail, f"multipart/form-data; boundary={boundary}"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Client:
    """The three API v3 calls the scan makes. Tests pass a fake `urlopen` and `sleep`."""

    def __init__(
        self,
        api_key: str,
        urlopen: Callable | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key
        self.urlopen = urlopen or _urlopen
        self.sleep = sleep

    def _call(
        self, method: str, path: str, body: bytes | None = None, content_type: str = ""
    ) -> dict | None:
        """The JSON answer, None on 404 (VirusTotal does not know the object). The key goes in
        a header, never in the URL: error messages and logs never carry it."""
        headers = {"x-apikey": self.api_key, "Accept": "application/json"}
        headers["User-Agent"] = "firestone-bot-ci"
        if content_type:
            headers["Content-Type"] = content_type
        for attempt in range(RETRY_TRIES + 1):
            req = urllib.request.Request(API + path, data=body, headers=headers, method=method)
            try:
                with self.urlopen(req) as r:
                    return json.loads(r.read() or b"{}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                if e.code in RETRY_STATUS and attempt < RETRY_TRIES:
                    self.sleep(RETRY_WAIT_S)
                    continue
                error = _error_text(e)
                raise VirusTotalError(f"{method} {path}: HTTP {e.code} {error}") from None
            except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as e:
                # no answer, a cut one or one that is not JSON
                raise VirusTotalError(f"{method} {path}: {type(e).__name__} {e}") from None
        raise AssertionError("the last attempt returns or raises")

    def file_report(self, sha256: str) -> dict | None:
        """Attributes of the file object, None when VirusTotal has never seen the file."""
        answer = self._call("GET", f"/files/{sha256}")
        return None if answer is None else (answer.get("data") or {}).get("attributes") or {}

    def upload(self, path: str) -> str:
        """Send the file for analysis; the analysis id."""
        size = os.path.getsize(path)
        if size > UPLOAD_MAX:
            raise VirusTotalError(f"{os.path.basename(path)} is {size} bytes, over 32 MB")
        with open(path, "rb") as f:
            body, content_type = multipart("file", os.path.basename(path), f.read())
        answer = self._call("POST", "/files", body, content_type) or {}
        analysis_id = (answer.get("data") or {}).get("id")
        if not analysis_id:
            raise VirusTotalError("the upload's answer has no analysis id")
        return analysis_id

    def analysis(self, analysis_id: str) -> dict:
        answer = self._call("GET", "/analyses/" + urllib.parse.quote(analysis_id, safe="="))
        attributes = ((answer or {}).get("data") or {}).get("attributes")
        if attributes is None:
            raise VirusTotalError(f"analysis {analysis_id} not found")
        return attributes


def scan(
    client: Client,
    path: str,
    timeout_s: float = TIMEOUT_S,
    poll_s: float = POLL_S,
    clock: Callable[[], float] = time.monotonic,
    held: Callable[[str], None] | None = None,
) -> Verdict:
    """The file's verdict: its last analysis when VirusTotal knows it, otherwise the analysis
    of an upload, waited for up to timeout_s (complete=False when it was still running).
    held(sha256) is called as soon as VirusTotal holds the file: its report link works from
    then on, whatever the polls do."""
    sha256 = sha256_file(path)
    known = client.file_report(sha256)
    if known and known.get("last_analysis_results"):
        if held:
            held(sha256)
        return Verdict(sha256, known["last_analysis_results"])
    analysis_id = client.upload(path)  # unknown, or known without a finished analysis
    if held:
        held(sha256)
    deadline = clock() + timeout_s
    while True:
        client.sleep(poll_s)
        attributes = client.analysis(analysis_id)
        results = attributes.get("results") or {}
        if attributes.get("status") == "completed":
            return Verdict(sha256, results)
        if clock() >= deadline:
            return Verdict(sha256, results, complete=False)


def summary(name: str, v: Verdict) -> str:
    """Markdown for the run summary."""
    pending = "" if v.complete else " so far (the analysis was still running: see the report)"
    lines = [f"### VirusTotal: {name}", ""]
    if v.flagged:
        lines.append(f"**{len(v.flagged)} of {v.judged} engines flag it**{pending}.")
        lines += ["", "| Engine | Detection |", "|---|---|"]
        lines += [f"| {engine} | `{hit}` |" for engine, hit in v.flagged]
    else:
        lines.append(f"No engine flags it ({v.judged} engines){pending}.")
    lines += [
        "",
        f"Microsoft: {v.microsoft} (its VirusTotal engine can disagree with Defender on a PC).",
        "",
        f"SHA-256 `{v.sha256}`: [report]({v.link})",
        "",
    ]
    return "\n".join(lines)


def _command(text: str) -> str:
    """Escape a workflow-command message (GitHub reads %, CR and LF as markup)."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def annotation(name: str, v: Verdict) -> str:
    """One workflow command: a warning when an engine flags the file, a notice otherwise."""
    pending = "" if v.complete else ", analysis not finished"
    if v.flagged:
        named = ", ".join(f"{engine}: {hit}" for engine, hit in v.flagged[:TOP])
        if len(v.flagged) > TOP:
            named += f" and {len(v.flagged) - TOP} more"
        text = f"{len(v.flagged)} of {v.judged} engines flag {name}{pending} ({named})"
        return f"::warning::VirusTotal: {_command(text)}. {v.link}"
    text = f"no engine flags {name} ({v.judged} engines{pending}; Microsoft: {v.microsoft})"
    return f"::notice::VirusTotal: {_command(text)}. {v.link}"


def notes_line(name: str, sha256: str) -> str:
    """The line added to the release notes (the in-app update dialog shows it too)."""
    return f"VirusTotal report of {name}: {REPORT}{sha256}\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="VirusTotal verdict on a release file (CI)")
    p.add_argument("path")
    p.add_argument("--summary", help="Markdown summary appended here ($GITHUB_STEP_SUMMARY)")
    p.add_argument("--notes", help="written with the release-notes line once VirusTotal has it")
    p.add_argument("--timeout", type=float, default=TIMEOUT_S, help="analysis wait, seconds")
    p.add_argument("--poll", type=float, default=POLL_S, help="seconds between two polls")
    args = p.parse_args(argv)
    name = os.path.basename(args.path)
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        print(f"::notice::VirusTotal check of {name} skipped: no {KEY_ENV} secret")
        return 0
    held: list[str] = []

    def hold(sha256: str) -> None:
        held.append(sha256)
        if args.notes:
            with open(args.notes, "w", encoding="utf-8") as f:
                f.write(notes_line(name, sha256))

    try:
        verdict = scan(Client(key), args.path, args.timeout, args.poll, held=hold)
        text = summary(name, verdict)
        print(text)
        if args.summary:
            with open(args.summary, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        print(annotation(name, verdict))
    except Exception as e:  # noqa: BLE001 - the run goes on whatever happens; the warning says why
        link = f" {REPORT}{held[0]}" if held else ""
        print(f"::warning::{_command(f'VirusTotal check of {name} failed: {e}')}.{link}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
