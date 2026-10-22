# Bug reports: the `/api/report` endpoint (brief for the server session)

Owner request (2026-10-22). Firestone Bot (Python desktop app, open source,
github.com/Lutakh/firestone-bot) gets a **Send report** button: it builds a zip of the bot's
logs, recent diagnostic captures, settings and environment, and uploads it to the owner's
server **fs-bot-logs.lutak.ovh** (a Docker container), which keeps it and tells the owner on
Discord. The player only gets an ID to give on Discord. No e-mail, no Discord attachment.

The same server already receives the bot's heartbeats; that route stays as it is:
`POST https://fs-bot-logs.lutak.ovh/api/heartbeat`, JSON
`{"client_id": "...", "discord_id": "...", "message": "...", "is_stop": false, "is_important": false}`.

This file is the contract: the bot side is written against it. Anything the server session
changes (URL, limits, headers, response) must be written back here.

## Upload

`POST https://fs-bot-logs.lutak.ovh/api/report`

Headers:

| Header | Required | Value |
|---|---|---|
| `Content-Type` | yes | `application/zip` |
| `Content-Length` | yes | size of the body (urllib sends it) |
| `X-Client-Id` | yes | the bot's `ClientID`, `YYYYMMDDHHMMSS-NNNNNN` (the heartbeat's `client_id`) |
| `X-Bot-Version` | yes | e.g. `0.3.32` |
| `X-Platform` | yes | `windows`, `macos` or `linux` |
| `X-Discord-Id` | no | the player's Discord ID (digits) when set in the bot, else absent |
| `X-Report-Note` | no | the player's description, UTF-8 then percent-encoded, at most 500 characters once decoded |

Body: the zip, raw (not multipart), at most **20 MB** (20,971,520 bytes).

Responses (JSON):

| Status | Body | When |
|---|---|---|
| 201 | `{"id": "7F3K2Q", "size": 3245123, "expires": "2026-11-21"}` | stored |
| 400 | `{"error": "<reason>"}` | missing/invalid `X-Client-Id` or `X-Bot-Version`, body not a zip (must start with `PK\x03\x04`), note too long, broken zip |
| 413 | `{"error": "too large", "max": 20971520}` | `Content-Length` or the streamed body above the cap |
| 429 | `{"error": "too many reports", "retry_after": 1800}` + `Retry-After` header | rate limit |
| 503 | `{"error": "storage full"}` | the storage cap is reached even after deleting expired reports |

The bot waits up to 60 s, shows the `id` to the player ("Report sent: 7F3K2Q, give this ID on
Discord"), and on any failure offers to save the zip locally instead.

## Server behaviour

- **ID**: 6 characters from an unambiguous alphabet (`23456789ABCDEFGHJKLMNPQRSTUVWXYZ`),
  unique among stored reports.
- **Storage** (Docker volume, e.g. `/data/reports`): `<YYYY-MM>/<id>.zip` plus `<id>.json`
  with `received_at` (UTC ISO), `client_id`, `discord_id`, `version`, `platform`, `note`,
  `size`, `sha256`, and the sender IP (or its hash).
- **Safety**:
  - stream the body to disk and stop at the cap: never hold 20 MB in memory, never trust
    `Content-Length` alone;
  - check the zip magic, then read its central directory without extracting anything (zip
    bombs): reject more than 500 entries or more than 300 MB declared uncompressed;
  - rate limits: 3 reports an hour per `X-Client-Id`, 10 an hour per IP, 200 a day in all;
  - no directory listing, no public access to the files: reports hold logs and screenshots of
    a player's game.
- **Retention**: delete reports older than 30 days (a daily job), and the oldest first when
  the total goes above 5 GB.
- **Notification**: on a stored report, tell the owner on Discord through what the server
  already uses for important heartbeats, or a webhook from an environment variable:
  `Report 7F3K2Q - v0.3.32 windows - 3.1 MB - client 20260913101500-123456 - <@discord_id> -
  "note..." - <download link>`.
- **Download (owner only)**: `GET /api/report/<id>` with `Authorization: Bearer
  <REPORT_ADMIN_TOKEN>` returns the zip (`Content-Disposition: attachment`); `GET /api/reports`
  (same token) lists the recent ones as JSON. The token lives in the server's environment,
  never in the bot.
- **Configuration** (environment): `REPORT_DIR`, `REPORT_MAX_BYTES` (20971520),
  `REPORT_RETENTION_DAYS` (30), `REPORT_STORAGE_MAX_BYTES` (5 GB), `REPORT_ADMIN_TOKEN`,
  `REPORT_DISCORD_WEBHOOK` (optional), rate limits.
- **Reverse proxy**: allow 20 MB bodies and 60 s uploads (nginx: `client_max_body_size 25m;`,
  `proxy_read_timeout 60s;`, and request buffering off or enough temp space).

## What the zip holds (made by the bot)

- `report.json`: `{"version", "platform", "created_at", "client_id", "note", "environment":
  {...}, "files": [...]}`; `environment` = the last environment block the bot logged (bot
  version, OS, store, game window client size and position, maximized/fullscreen, DPI scale,
  screen size, interface style, capture method), so it is there even when the game was
  closed before the click.
- `logs/firestone-bot.log` and the kept days `logs/firestone-bot.log.YYYY-MM-DD` (the bot keeps
  7 days; the report takes the newest up to about 8 MB).
- `diagnostics/*.png`: the newest captures, within the remaining size budget.
- `settings.ini` without `DiscordID` and `ClientID`.

## Checks before telling the bot side it is ready

```bash
curl -i -X POST https://fs-bot-logs.lutak.ovh/api/report -H "Content-Type: application/zip" -H "X-Client-Id: 20261022120000-123456" -H "X-Bot-Version: 0.3.32" -H "X-Platform: windows" --data-binary @report.zip
```

- a small zip gives 201 and an id, the owner gets the Discord message, the download with the
  token returns the same bytes (sha256);
- a text file gives 400, a 25 MB file 413 (rejected while streaming), a fourth report from the
  same client within the hour 429;
- the download without the token gives 401, an unknown id 404.

Then write the final URL and limits back into this file.
