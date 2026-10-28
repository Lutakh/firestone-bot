"""tools/virustotal: the CI's VirusTotal lookup and upload of FirestoneBot.exe, on a fake API."""

from __future__ import annotations

import hashlib
import http.client
import io
import json
import os
import re
import urllib.error

import pytest

from firestone_bot.tools import virustotal as vt

V3 = "https://www.virustotal.com/api/v3"  # the documented API root, not read from vt.API
EXE = b"MZ" + bytes(range(256)) * 16
SHA = hashlib.sha256(EXE).hexdigest()
LINK = "https://www.virustotal.com/gui/file/" + SHA
KEY = "test-key-not-a-real-one"
BEARFOOS = "Trojan:Win32/Bearfoos.B!ml"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Response:
    def __init__(self, data: bytes, cut: bool = False) -> None:
        self.data, self.cut = data, cut

    def read(self) -> bytes:
        if self.cut:
            raise http.client.IncompleteRead(self.data[:5], len(self.data))
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeApi:
    """urlopen stand-in. routes: (method, path prefix) -> answers [(status, body)], used in
    turn, the last one repeated; status "cut" ends the answer early, a bytes body is sent as is.
    Records (method, path, request)."""

    MAX_CALLS = 10  # a scan that never stops fails here instead of hanging the suite

    def __init__(self, routes: dict) -> None:
        self.routes = {k: list(v) for k, v in routes.items()}
        self.calls: list[tuple] = []

    def __call__(self, req):
        assert req.full_url.startswith(V3 + "/"), req.full_url
        method, path = req.get_method(), req.full_url[len(V3) :]
        self.calls.append((method, path, req))
        assert len(self.calls) <= self.MAX_CALLS, f"request {len(self.calls)}: no end in sight"
        key = next((k for k in self.routes if k[0] == method and path.startswith(k[1])), None)
        assert key is not None, f"unexpected {method} {path}"
        answers = self.routes[key]
        status, body = answers.pop(0) if len(answers) > 1 else answers[0]
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        if status == "cut":
            return _Response(data, cut=True)
        if status != 200:
            raise urllib.error.HTTPError(req.full_url, status, "refused", {}, io.BytesIO(data))
        return _Response(data)


def results(**flagged: str) -> dict:
    """Three engines that find nothing, one that cannot read the file, plus the flagged ones
    (engine=detection name; Microsoft=... replaces Microsoft's clean result)."""
    out = {
        "Bkav": {"category": "undetected", "result": None},
        "ESET-NOD32": {"category": "undetected", "result": None},
        "Microsoft": {"category": "undetected", "result": None},
        "Trapmine": {"category": "type-unsupported", "result": None},
    }
    for engine, hit in flagged.items():
        out[engine] = {"category": "malicious", "result": hit}
    return out


def known(res: dict) -> tuple[int, dict]:
    return 200, {"data": {"type": "file", "attributes": {"last_analysis_results": res}}}


def analysis(status: str, res: dict) -> tuple[int, dict]:
    return 200, {"data": {"type": "analysis", "attributes": {"status": status, "results": res}}}


def error(status: int, code: str) -> tuple[int, dict]:
    return status, {"error": {"code": code, "message": f"{code} message"}}


NOT_FOUND = error(404, "NotFoundError")
QUOTA = error(429, "QuotaExceededError")
UPLOADED = (200, {"data": {"type": "analysis", "id": "YWJjOjE3OTM="}})


@pytest.fixture
def exe(tmp_path):
    path = tmp_path / "FirestoneBot.exe"
    path.write_bytes(EXE)
    return str(path)


def client(api, sleeps=None):
    return vt.Client(KEY, api, sleep=(sleeps.append if sleeps is not None else lambda s: None))


def test_a_file_virustotal_knows_is_read_not_uploaded(exe):
    api = FakeApi({("GET", "/files/"): [known(results())]})
    held = []
    v = vt.scan(client(api), exe, held=held.append)
    assert [(m, p) for m, p, _ in api.calls] == [("GET", "/files/" + SHA)]
    assert v.complete and v.flagged == [] and v.judged == 3 and v.microsoft == "clean"
    assert v.sha256 == SHA and v.link == LINK and held == [SHA]
    req = api.calls[0][2]
    assert req.get_header("X-apikey") == KEY and KEY not in req.full_url


def test_an_unknown_file_is_uploaded_and_its_analysis_waited_for(exe):
    api = FakeApi(
        {
            ("GET", "/files/"): [NOT_FOUND],
            ("POST", "/files"): [UPLOADED],
            ("GET", "/analyses/"): [analysis("queued", {}), analysis("completed", results())],
        }
    )
    sleeps, held_after = [], []
    v = vt.scan(
        client(api, sleeps),
        exe,
        poll_s=7,
        clock=lambda: 5000.0,
        held=lambda sha: held_after.append((sha, len(api.calls))),
    )
    assert [m for m, _, _ in api.calls] == ["GET", "POST", "GET", "GET"]
    assert api.calls[2][1] == "/analyses/YWJjOjE3OTM="  # the id's padding is kept
    assert sleeps == [7, 7] and v.complete and v.judged == 3 and v.link == LINK
    assert held_after == [(SHA, 2)]  # the link is good from the upload on, before any poll
    upload = api.calls[1][2]
    content_type = upload.get_header("Content-type")
    assert content_type.startswith("multipart/form-data; boundary=")
    boundary = content_type.split("boundary=")[1]
    assert (
        upload.data
        == (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="FirestoneBot.exe"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + EXE
        + f"\r\n--{boundary}--\r\n".encode()
    )


def test_a_known_file_without_a_finished_analysis_is_uploaded_again(exe):
    api = FakeApi(
        {
            ("GET", "/files/"): [known({})],
            ("POST", "/files"): [UPLOADED],
            ("GET", "/analyses/"): [analysis("completed", results())],
        }
    )
    assert vt.scan(client(api), exe).complete
    assert [m for m, _, _ in api.calls] == ["GET", "POST", "GET"]


def test_a_slow_analysis_ends_with_what_the_engines_said_so_far(exe):
    api = FakeApi(
        {
            ("GET", "/files/"): [NOT_FOUND],
            ("POST", "/files"): [UPLOADED],
            ("GET", "/analyses/"): [analysis("in-progress", results(Microsoft=BEARFOOS))],
        }
    )
    times = iter([5000.0, 5030.0, 5060.0])  # deadline 60 s after the upload: two polls
    v = vt.scan(client(api), exe, timeout_s=60, poll_s=30, clock=lambda: next(times))
    assert not v.complete and v.flagged == [("Microsoft", BEARFOOS)] and v.link == LINK
    assert len(api.calls) == 4
    assert "still running" in vt.summary("FirestoneBot.exe", v)
    assert "analysis not finished" in vt.annotation("FirestoneBot.exe", v)


def test_the_rate_limit_waits_a_minute_and_tries_again(exe):
    api = FakeApi({("GET", "/files/"): [QUOTA, known(results())]})
    sleeps = []
    assert vt.scan(client(api, sleeps), exe).complete
    assert sleeps == [60] and len(api.calls) == 2


@pytest.mark.parametrize("status", [503, 504])
def test_a_busy_virustotal_is_tried_again(exe, status):
    api = FakeApi({("GET", "/files/"): [error(status, "TransientError"), known(results())]})
    sleeps = []
    assert vt.scan(client(api, sleeps), exe).complete
    assert sleeps == [60] and len(api.calls) == 2


def test_a_rate_limit_that_lasts_is_an_error(exe):
    api = FakeApi({("GET", "/files/"): [QUOTA]})
    sleeps = []
    with pytest.raises(vt.VirusTotalError, match="HTTP 429 QuotaExceededError"):
        vt.scan(client(api, sleeps), exe)
    assert sleeps == [60, 60, 60] and len(api.calls) == 4


class _CutBody(io.BytesIO):
    def read(self, *args):
        raise http.client.IncompleteRead(b'{"err', 40)


@pytest.mark.parametrize(
    ("status", "body"),
    [(400, _CutBody()), (503, _CutBody()), (401, io.BytesIO(b'{"error": "text"}'))],
)
def test_an_error_answer_that_is_cut_or_off_spec_keeps_the_request_and_status(exe, status, body):
    """A 503 here is the last of its tries; the message still names the request."""

    def urlopen(req):
        raise urllib.error.HTTPError(req.full_url, status, "refused", {}, body)

    with pytest.raises(vt.VirusTotalError, match=f"GET /files/{SHA}: HTTP {status} refused"):
        vt.scan(client(urlopen), exe)


@pytest.mark.parametrize("status", [400, 401])
def test_other_refusals_are_not_tried_again(exe, status):
    api = FakeApi({("GET", "/files/"): [error(status, "Refused")]})
    sleeps = []
    with pytest.raises(vt.VirusTotalError, match=f"HTTP {status} Refused Refused message"):
        vt.scan(client(api, sleeps), exe)
    assert sleeps == [] and len(api.calls) == 1


@pytest.mark.parametrize(
    ("answer", "what"), [(("cut", {"data": {}}), "IncompleteRead"), ((200, b"<html>"), "JSON")]
)
def test_a_cut_or_garbled_answer_is_a_virustotal_error(exe, answer, what):
    api = FakeApi({("GET", "/files/"): [answer]})
    with pytest.raises(vt.VirusTotalError, match=f"GET /files/{SHA}: .*{what}"):
        vt.scan(client(api), exe)


def test_an_analysis_virustotal_does_not_know_is_an_error(exe):
    api = FakeApi(
        {
            ("GET", "/files/"): [NOT_FOUND],
            ("POST", "/files"): [UPLOADED],
            ("GET", "/analyses/"): [NOT_FOUND],
        }
    )
    with pytest.raises(vt.VirusTotalError, match="analysis YWJjOjE3OTM= not found"):
        vt.scan(client(api), exe, clock=lambda: 5000.0)
    assert [m for m, _, _ in api.calls] == ["GET", "POST", "GET"]


def test_an_upload_over_the_endpoint_limit_is_refused_without_a_request(exe, monkeypatch):
    monkeypatch.setattr(vt, "UPLOAD_MAX", len(EXE) - 1)
    api = FakeApi({("GET", "/files/"): [NOT_FOUND]})
    with pytest.raises(vt.VirusTotalError, match="over 32 MB"):
        vt.scan(client(api), exe)
    assert [m for m, _, _ in api.calls] == ["GET"]


def test_sha256_file_hashes_the_whole_file_in_chunks(tmp_path):
    data = bytes(range(256)) * (4096 + 1)  # 1 MiB + 256 bytes: two reads, a short tail
    path = tmp_path / "big.exe"
    path.write_bytes(data)
    assert vt.sha256_file(str(path)) == hashlib.sha256(data).hexdigest()


def test_flagged_puts_microsoft_first_whatever_the_answer_order():
    # VirusTotal's answer is in engine-name order: Microsoft comes after A-L
    res = {e: {"category": "malicious", "result": f"Hit-{e}"} for e in ("Zeta", "eta", "Alpha")}
    res["Microsoft"] = {"category": "malicious", "result": BEARFOOS}
    res["Beta"] = {"category": "suspicious", "result": None}  # no name: its category stands in
    v = vt.Verdict(SHA, res)
    assert v.flagged == [
        ("Microsoft", BEARFOOS),
        ("Alpha", "Hit-Alpha"),
        ("Beta", "suspicious"),
        ("eta", "Hit-eta"),
        ("Zeta", "Hit-Zeta"),
    ]


def test_judged_counts_the_verdicts_only():
    res = results(Alpha="Gen:Variant")
    res["Webroot"] = {"category": "harmless", "result": None}  # a verdict
    res["Slow"] = {"category": "timeout", "result": None}  # none, like type-unsupported
    assert vt.Verdict(SHA, res).judged == 5
    harmless = {"Microsoft": {"category": "harmless", "result": None}}
    assert vt.Verdict(SHA, harmless).microsoft == "clean"
    timeout = {"Microsoft": {"category": "timeout", "result": None}}
    assert vt.Verdict(SHA, timeout).microsoft == "no verdict"
    assert vt.Verdict(SHA, {}).microsoft == "no verdict"


def test_summary_and_annotation_of_a_flagged_file():
    v = vt.Verdict(SHA, results(Microsoft=BEARFOOS, Cylance="Unsafe"))
    text = vt.summary("FirestoneBot.exe", v)
    assert text.startswith("### VirusTotal: FirestoneBot.exe\n\n**2 of 4 engines flag it**.\n")
    assert f"| Microsoft | `{BEARFOOS}` |" in text and "| Cylance | `Unsafe` |" in text
    assert f"Microsoft: {BEARFOOS} (its VirusTotal engine can disagree" in text
    assert f"SHA-256 `{SHA}`: [report]({LINK})" in text
    assert vt.annotation("FirestoneBot.exe", v) == (
        "::warning::VirusTotal: 2 of 4 engines flag FirestoneBot.exe "
        f"(Microsoft: {BEARFOOS}, Cylance: Unsafe). {LINK}"
    )


def test_the_annotation_names_five_engines_and_counts_the_others():
    v = vt.Verdict(SHA, results(**{f"E{i}": f"Hit{i}" for i in range(7)}))
    line = vt.annotation("FirestoneBot.exe", v)
    assert "E0: Hit0, E1: Hit1, E2: Hit2, E3: Hit3, E4: Hit4 and 2 more" in line


def test_a_clean_file_is_a_notice():
    v = vt.Verdict(SHA, results())
    assert vt.annotation("FirestoneBot.exe", v) == (
        "::notice::VirusTotal: no engine flags FirestoneBot.exe (3 engines; Microsoft: clean)."
        f" {LINK}"
    )
    text = vt.summary("FirestoneBot.exe", v)
    assert "\nNo engine flags it (3 engines).\n" in text and "\nMicrosoft: clean (" in text


def test_a_clean_result_of_an_unfinished_analysis_says_so():
    v = vt.Verdict(SHA, results(), complete=False)
    assert "No engine flags it (3 engines) so far (the analysis was still running" in (
        vt.summary("FirestoneBot.exe", v)
    )
    assert vt.annotation("FirestoneBot.exe", v) == (
        "::notice::VirusTotal: no engine flags FirestoneBot.exe "
        f"(3 engines, analysis not finished; Microsoft: clean). {LINK}"
    )


def test_workflow_command_text_is_escaped():
    assert vt._command("50% done\r\nnext") == "50%25 done%0D%0Anext"


def test_main_without_the_secret_skips_and_succeeds(exe, monkeypatch, capsys, tmp_path):
    monkeypatch.delenv(vt.KEY_ENV, raising=False)
    monkeypatch.setattr(vt, "_urlopen", FakeApi({}))  # any request fails the test
    notes = tmp_path / "virustotal.md"
    assert vt.main([exe, "--notes", str(notes)]) == 0
    assert "::notice::VirusTotal check of FirestoneBot.exe skipped" in capsys.readouterr().out
    assert not notes.exists()


def test_main_turns_a_refused_key_into_a_warning(exe, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv(vt.KEY_ENV, KEY)
    refused = error(401, "WrongCredentialsError")
    monkeypatch.setattr(vt, "_urlopen", FakeApi({("GET", "/files/"): [refused]}))
    notes = tmp_path / "virustotal.md"
    assert vt.main([exe, "--notes", str(notes)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("::warning::VirusTotal check of FirestoneBot.exe failed: GET /files/")
    assert "HTTP 401 WrongCredentialsError" in out and KEY not in out and LINK not in out
    assert not notes.exists()


def test_main_keeps_the_link_when_a_poll_fails_after_the_upload(exe, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv(vt.KEY_ENV, KEY)
    api = FakeApi(
        {
            ("GET", "/files/"): [NOT_FOUND],
            ("POST", "/files"): [UPLOADED],
            ("GET", "/analyses/"): [error(400, "BadRequestError")],
        }
    )
    monkeypatch.setattr(vt, "_urlopen", api)
    monkeypatch.setattr(vt, "POLL_S", 0)  # main's default poll interval: no real wait
    notes = tmp_path / "virustotal.md"
    assert vt.main([exe, "--notes", str(notes)]) == 0
    assert notes.read_text(encoding="utf-8") == f"VirusTotal report of FirestoneBot.exe: {LINK}\n"
    out = capsys.readouterr().out
    assert out.startswith("::warning::VirusTotal check of FirestoneBot.exe failed: GET /analyses/")
    assert out.rstrip().endswith(f". {LINK}")


def test_main_turns_any_error_into_a_warning(exe, monkeypatch, capsys):
    monkeypatch.setenv(vt.KEY_ENV, KEY)

    def broken(*args, **kwargs):
        raise RuntimeError("100% broken")

    monkeypatch.setattr(vt, "scan", broken)
    assert vt.main([exe]) == 0
    assert capsys.readouterr().out == (
        "::warning::VirusTotal check of FirestoneBot.exe failed: 100%25 broken.\n"
    )


def test_main_writes_the_summary_the_notes_and_the_warning(exe, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv(vt.KEY_ENV, KEY)
    monkeypatch.setattr(
        vt, "_urlopen", FakeApi({("GET", "/files/"): [known(results(Microsoft=BEARFOOS))]})
    )
    summary, notes = tmp_path / "summary.md", tmp_path / "virustotal.md"
    summary.write_text("### Earlier step\n", encoding="utf-8")
    assert vt.main([exe, "--summary", str(summary), "--notes", str(notes)]) == 0
    text = summary.read_text(encoding="utf-8")
    assert text.startswith("### Earlier step\n### VirusTotal: FirestoneBot.exe")
    assert f"| Microsoft | `{BEARFOOS}` |" in text
    assert notes.read_text(encoding="utf-8") == f"VirusTotal report of FirestoneBot.exe: {LINK}\n"
    out = capsys.readouterr().out
    assert (
        f"::warning::VirusTotal: 1 of 3 engines flag FirestoneBot.exe (Microsoft: {BEARFOOS})"
        in out
    )


def test_main_hands_timeout_and_poll_to_scan(exe, monkeypatch):
    monkeypatch.setenv(vt.KEY_ENV, KEY)
    calls = []

    def fake_scan(client, path, timeout_s, poll_s, held=None):
        calls.append((path, timeout_s, poll_s))
        return vt.Verdict(SHA, results())

    monkeypatch.setattr(vt, "scan", fake_scan)
    assert vt.main([exe, "--timeout", "90", "--poll", "15"]) == 0
    assert vt.main([exe]) == 0
    assert calls == [(exe, 90.0, 15.0), (exe, vt.TIMEOUT_S, vt.POLL_S)]


def test_the_waits_fit_the_quota_and_the_time_limits():
    assert vt.RETRY_WAIT_S >= 60  # a 429 outlasts the per-minute quota
    assert vt.POLL_S >= 20  # lookup, upload and polls stay under 4 requests a minute
    job = _workflow().split("\n  virustotal:\n")[1]
    job_minutes = int(re.search(r"\n    timeout-minutes: (\d+)\n", job).group(1))
    step = job.split("- name: VirusTotal verdict on FirestoneBot.exe\n")[1].split("- name:")[0]
    step_minutes = int(re.search(r"\n        timeout-minutes: (\d+)\n", step).group(1))
    # the scan step may run out of time (retry storms) without failing the job: the link
    # step after it still runs, inside the job's limit
    assert "\n        continue-on-error: true\n" in step
    assert job_minutes * 60 >= step_minutes * 60 + 120
    # a normal scan fits: the analysis wait, the poll that crosses it, one round of retries
    assert step_minutes * 60 >= vt.TIMEOUT_S + vt.POLL_S + vt.RETRY_TRIES * vt.RETRY_WAIT_S


def _workflow() -> str:
    with open(os.path.join(ROOT, ".github", "workflows", "build.yml"), encoding="utf-8") as f:
        return f.read()


def test_the_virustotal_job_scans_the_release_exe_apart_from_the_build_and_the_release():
    workflow = _workflow()
    build = workflow.split("\n  build:\n")[1].split("\n  release:\n")[0]
    release = workflow.split("\n  release:\n")[1].split("\n  virustotal:\n")[0]
    job = workflow.split("\n  virustotal:\n")[1]
    # nothing waits for VirusTotal: the archives and the release go on without it
    assert "virustotal" not in build.lower() and "virustotal" not in release.lower()
    assert release.startswith("    needs: build\n")
    # it scans the exe the run ships, after the release on a tag, and never fails the run
    assert "\n    needs: [build, release]\n" in job and "!cancelled()" in job
    assert "\n    continue-on-error: true\n" in job
    assert "name: FirestoneBot-windows.zip" in job
    assert "unzip -q artifacts/FirestoneBot-windows.zip FirestoneBot.exe -d exe" in job
    assert (
        "python -m firestone_bot.tools.virustotal exe/FirestoneBot.exe"
        ' --summary "$GITHUB_STEP_SUMMARY" --notes virustotal.md'
    ) in job
    assert "VT_API_KEY: ${{ secrets.VT_API_KEY }}" in job
    # the link goes into a published tag's notes only, once, and only when the file is there
    assert "needs.release.result == 'success' && hashFiles('virustotal.md') != ''" in job
    # an earlier attempt's link is dropped, and nothing else of the tag message: the pattern
    # matches the line notes_line writes and no line that merely starts like it
    pattern = re.search(r"grep -vE '([^']*)' body\.md", job).group(1)
    pattern = pattern.replace("[[:space:]]", r"\s")
    assert re.match(pattern, vt.notes_line("FirestoneBot.exe", SHA))
    assert re.match(pattern, vt.notes_line("FirestoneBot.exe", SHA).rstrip("\n") + "\r\n")
    assert not re.match(pattern, "VirusTotal report of 0.3.34: see the previous release\n")
    assert not re.match(pattern, vt.notes_line("FirestoneBot.exe", SHA[:40]))
