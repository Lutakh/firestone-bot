# Backlog (owner requests, not yet done)

- Battle Pass: claim available rewards.
- Robustness against network / server slowness: slow UI, clicks landing on the wrong screen,
  clicks not registered. Ideas: wait-for-probe helpers instead of fixed sleeps at screen
  transitions, verify the expected screen before clicking, retry once, and a "recover to the
  main screen" routine (main_menu) when a probe chain fails.
- 125 % DPI and 4K (Parsec virtual display) validation runs (plan 4.6).
- Linux (plan 4.9) and browser build (plan 4.10 / section 8).
- Mouse-usage detection (owner spec, 2026-09-04): detect that the USER moves the mouse while
  the bot runs (pynput 1.8 gives an `injected` flag on Windows, so the bot's own SendInput events
  can be told apart from the physical mouse). On detection: abort the current cycle, show a
  pop-up the user can validate or that closes by itself after 30 s, saying that the mouse was
  moved and that the bot will restart a NEW cycle from the beginning after 30 s without any
  mouse activity (each new movement restarts the 30 s countdown). Keyboard input should count
  too. Not active in dry runs.
- Global optimisation (owner request): make the cycles much faster WITHOUT losing reliability
  (network latency, server hiccups). Ideas: replace fixed 1000 ms sleeps by "wait until the
  expected screen/probe appears" with a timeout (fast when the game is fast, patient when it is
  slow); verify the target screen before each click chain and recover through main_menu on a
  miss; measure per-module durations in the log to find the slow spots; skip modules whose
  entry probe already says there is nothing to do; keep the AHK timing available as a fallback
  "safe mode" setting.
- Support the game's new interface style (the "new Adventure style" button layout that the AHK
  bot required to be OFF): measure the new positions/colours and make the atlas cover both
  styles, or detect which style is active.
- Map alignment: detect that the world map is not centred or is zoomed (zoom slider bottom
  right, drag offset) and re-centre / reset the zoom before clicking the mission points; today a
  moved map silently breaks every fixed mission coordinate.
- Map missions: inventory the mission icons the AHK list does not cover (e.g. the Frostfire
  north-west point added 2026-09-04) by capturing the map at several times of the day, and/or
  detect mission icons by colour instead of a fixed list.
