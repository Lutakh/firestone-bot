# Mac live test: locked research boxes and meteorite nodes

Owner request (2026-09-29): the Mac's game account still has locked firestone research boxes
and locked meteorite nodes, which no account has shown the bot yet (every column of the Windows
account's tree is open). This file is the brief for a session on the Mac. The code to test is
`python-rework` from 87fba9e on (research priorities, meteorite research); it is still
labelled 0.3.29, no release. Everything in the repository stays in English; the owner chats
in French. No tag without the owner's explicit yes.

## Get the build

README "macOS: testing a build before its release": the CI artifact of the latest push, or
`.venv/bin/python -m firestone_bot.tools.build_exe` from the clone (signed with the "Firestone
Bot" certificate when `~/Library/Keychains/firestone-bot.keychain-db` exists; never run
`mac_codesign create`, a new certificate loses the permissions). Before installing, keep the
installed bundle aside (`mv`, never copy onto a bundle) and check the new one:
`codesign --verify --deep --strict <app>` silent, `codesign -dv <app>` shows
`Authority=Firestone Bot`, `find <app> -name meteorite_refs.json` finds the file.

Which build runs: the version number does not tell (0.3.29 everywhere). This build shows the
Automations groups "Meteorite research" and "Guardian enlightenment", "Priority 1".."Priority 5"
and "Research something else" under Research, and logs `Research: a slot is free, looking for
a research to start` (0.3.29 said "a node").

Settings, log and diagnostics of the bundle live in `~/Library/Application Support/FirestoneBot`
(`diagnostics/` keeps only the 3 newest files of each name: copy them after each test). Never
copy a settings.ini over an existing one; a source run reads the clone's own settings.ini.

## Tests (game zoomed, Fullscreen OFF, pointer parked off the tree)

0. **Reference captures**, bot stopped, from the clone:
   `sleep 3; .venv/bin/python -m firestone_bot.tools.capture_tool --activate --out captures/<name>.png`
   (a terminal over the game ends up in the capture). Take: the Firestone tab at its start and
   at each scroll stop up to the end, especially the stops with locked boxes; the slot panels
   (and a locked slot 2 if there is one); the popup of a locked box and of an open box, opened
   by hand; the Meteorite tab; the popup of a locked node and of an open node. Check the probes
   with `python -m firestone_bot.tools.probe_check captures/<name>.png`: `rs_popup_research`
   must HIT on the open box's popup (positive control) and miss on the locked one, and
   `rs_popup_close_x` must HIT on both. If `rs_popup_research` misses everywhere on the Mac,
   every box reads locked: stop there, that is the first fix.
1. **Meteorite, dry run** (clicks nothing, spends nothing): open Town > Library > Meteorite by
   hand, then `sleep 5; .venv/bin/python -m firestone_bot.tools.run_feature meteorite --dry-run
   --set 'MeteoritePriority1=<a node the game shows locked>' --set MeteoriteAnyOther=1`
   (click the game's title bar within the 5 s: a dry run does not activate the game). Expect
   `Meteorite research: <counter> meteorites; <N> nodes, ...`: N is 13 when the locked nodes
   are detected. Then either `dry run, <name>'s popup would be checked here, stopping` or
   `<name> is not found in this tree` (the locked node was not detected: a bug).
2. **Firestone research, live** (starts one research, which the bot does anyway; needs a free
   slot): Research ON, Priority 1 = a research in a locked column, Priority 2 = one in an open
   column, "Research something else" OFF for the test only. Expect the summary line
   (`Research: tree like <roman>, <n> boxes (...)`), then
   `Research: <box> started to unlock <priority 1> (priority 1)` with <box> in the nearest open
   column before it, or `Research: <priority 2> started (priority 2)`, or
   `Research: slot left free (priorities: <name> <why>, ...)`. Check in the game that the
   started research is the one the log names. Put "Research something else" back ON.
3. **Meteorite, live** (spends meteorites): "Meteorites to keep" = the stock to protect,
   "Spend on other nodes" OFF, Priority 1 = a locked node whose node before it is affordable,
   Meteorite research ON. Expect `<locked> is locked, trying <parent> before it`, then
   `<parent> bought (level <L>, <cost> meteorites, <left> left) to unlock <locked>`. Check the
   counter and the levels in the game. The unlock levels come from the wiki
   (`vision/research_trees.json`, "unlock").

Retesting at once needs a bot restart: research waits 15 min after a search that started
nothing, meteorite research 1 h after a visit that bought nothing and stays off after an
unconfirmed click; some lines are written once per game day.

## Bug signs

- Research: `started to unlock` while the priority's box is open in the game (false lock);
  `the popup of <box> did not open, skipped` on a locked box that does open a popup (the
  locked popup is not the one the code knows); locked boxes counted as available or
  unidentified in the summary; many `unidentified` boxes (the modelled Mac colour correction,
  `vision/research_icons.py`, is off: an available box should read about 0x2848D8 on the Mac);
  `the Research button did not start a research` repeated while slot 2 is locked.
- Meteorite: fewer than 13 nodes with `<name> is not found in this tree` for a visible locked
  node (locked nodes not detected, their parent never bought); `<goal> costs <n>, <m>
  meteorites: saving up for it` on a node that is locked, not too expensive;
  `shows no Research button though <parent> is at level <L> (<need> unlocks it)` on a truly
  locked node (wrong wiki unlock level); `the popup shows ... instead of <name>` on a locked
  node; `the Research click on <name> is not confirmed` (meteorite research then stays off
  until restart).
- Counters measured on 1920x1009 only: `the meteorite counter is not readable`, `Tavern: the
  token counter is not readable`, `the guardian multiplier is not readable`.

## Afterwards

Fix what the tests show without breaking Windows, the other resolutions or the classic style
(`pytest -q` and `ruff` before each push, fixtures as .npy, no Pillow in tests); record the
locked colours and popups in docs/MEASUREMENTS.md, update the "Research priorities and
meteorite research" item of docs/BACKLOG.md, and confirm the in-game meteorite names seen
(only Tank specialization and Attribute armor are confirmed). `git pull --rebase` before every
commit and push (a Windows session works on the same branch).
