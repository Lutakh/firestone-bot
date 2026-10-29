# Code signing of the Windows exe (SignPath Foundation)

Why: players' Microsoft Defender quarantines the unsigned `FirestoneBot.exe`
(`Trojan:Win32/Bearfoos.B!ml`, a machine-learning verdict, 2026-10; README "Antivirus
warnings", BACKLOG "Antivirus"). A signed exe names its publisher and keeps a reputation from
one release to the next. SignPath Foundation signs open-source projects for free
(<https://signpath.org/terms>): the certificate is issued to SignPath Foundation, only what
the project's CI built from its repository is signed, and a team member approves every
signing request.

## State (2026-10-29)

- Done: the MIT license (`LICENSE`; Deaeth85 and GeSpot1, authors of the AutoHotkey bot this
  one was ported from, agreed); the README's Privacy section (the privacy policy SignPath asks
  for: the bot sends data only to GitHub for the update check and, when the user turns them
  on or clicks, to the maintainer's server, which passes some of it on to Discord) and
  uninstall paragraph; the exe's version resource with the license's copyright line; Windows,
  macOS and Linux builds by GitHub Actions on every push and tag (the Linux build cannot drive
  the game yet); releases on GitHub since 2025-12.
- Done by the owner: two-factor authentication on the GitHub account (already on, confirmed
  2026-10-29; SignPath requires multi-factor authentication of every team member, on the
  repository and on SignPath: the SignPath account will need it too); `python-rework` as the
  repository's default branch (2026-10-29), so that the homepage shows this bot, its README
  and its license (GitHub now reads it as MIT), not the AutoHotkey bot of `main`.
- Done 2026-10-29 (code): SignPath's terms ask software that sends user data to systems the
  user did not choose to display its privacy policy during installation and to let the user
  turn those functions off. The zip has no installer, so from the first start the top banner
  shows the policy in short, with a button to the README's Privacy section, until the user
  closes it once (gui_state.json); until then the start-up update check waits a minute after
  the banner appears, so the policy is shown and the check can be turned off before anything
  goes out. Workshop > Help > Privacy keeps the policy, the heartbeat card and the Send report
  dialog link to it; the heartbeat is off by default, a report leaves only on a click, and
  Workshop > Files & app > Check for updates automatically turns off the update check, the
  one request the bot makes by itself.
- Left, the owner: the application at <https://signpath.org/apply> (personal fields,
  reCAPTCHA, Code of Conduct), answers below.
- After acceptance: the README section and the CI step below.

## Application answers

| Field | Answer |
|---|---|
| Project Name | Firestone Bot |
| Repository URL | https://github.com/Lutakh/firestone-bot |
| Homepage URL | https://github.com/Lutakh/firestone-bot |
| Download URL | https://github.com/Lutakh/firestone-bot/releases (the form says this page must mention SignPath: leave it empty until the README has the section below, or add it then) |
| Privacy Policy URL | https://github.com/Lutakh/firestone-bot#privacy |
| Tagline | Free, open-source automation bot for the idle game Firestone Idle RPG (Windows, macOS). |
| Category | the closest of the list (games, or utilities / automation) |
| Description | see below |
| Reputation | see below |
| Maintainer Type | individual |
| Build System | GitHub Actions |

Description:

> Firestone Bot plays the daily routine of Firestone Idle RPG (Steam and Epic builds) for the
> player: missions, chests, research, guild, events and more. It reads the game window's
> pixels and sends clicks to the game; it never reads the game's memory or network traffic.
> It is written in Python and packaged with PyInstaller. GitHub Actions builds the Windows and
> macOS versions from this repository (and a Linux build that cannot drive the game yet) and
> publishes them as GitHub releases with SHA-256 checksums, used by the bot's own updater. It
> began as a port of Deaeth85's AutoHotkey bot and is published under the MIT license with
> the original authors' agreement.

Reputation (figures of 2026-10-28 from GitHub's releases API, archives only: the updater's
`SHA256SUMS.txt` downloads left out):

> 1,104 downloads of the release archives over 51 releases since December 2025, 964 of them
> for the 46 Python versions published since September 2026 (170 for v0.3.34 in its first
> six days). Players report bugs and suggestions through the bot's Send report button and on
> Discord, and the release notes credit them.

## README section once accepted

The download page (README, release notes) must name SignPath, under the title "Code signing
policy":

```markdown
## Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by
[SignPath Foundation](https://signpath.org/).

- Committers and reviewers: [Lutakh](https://github.com/Lutakh)
- Approvers: [Lutakh](https://github.com/Lutakh)

Only builds made by this repository's GitHub Actions from its source are signed, each one
after an approver's review. Privacy: see [Privacy](#privacy).
```

The README's "The executable is not code-signed" paragraph (SmartScreen) and the antivirus
section then change with it.

## CI once accepted

SignPath gives an organization id, a project slug, signing policy slugs (one for releases)
and an artifact configuration (here: the Windows zip, `FirestoneBot.exe` inside it signed in
place), and a CI user's API token, which goes into a repository secret. The Windows job then
uploads the unsigned zip as an artifact and submits it with SignPath's GitHub action
(`signpath/github-action-submit-signing-request`, artifact id, wait for completion, output
directory); the approver accepts the request on signpath.io; the job gets the signed zip
back and continues with it. To keep:

- the `virustotal` job takes the signed zip's exe (it is the file players get);
- `SHA256SUMS.txt` is computed by the release job from the downloaded artifacts, so it
  already describes the signed zip and exe;
- branch pushes can stay unsigned (or use a test-signing policy): every signing request of
  the release policy waits for an approval.
