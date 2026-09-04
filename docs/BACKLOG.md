# Backlog (owner requests, not yet done)

- Events page: claim rewards of the active events (the AHK `ClaimEvents` only handles the top
  event's three challenges).
- Battle Pass: claim available rewards.
- Robustness against network / server slowness: slow UI, clicks landing on the wrong screen,
  clicks not registered. Ideas: wait-for-probe helpers instead of fixed sleeps at screen
  transitions, verify the expected screen before clicking, retry once, and a "recover to the
  main screen" routine (main_menu) when a probe chain fails.
- 125 % DPI and 4K (Parsec virtual display) validation runs (plan 4.6).
- Linux (plan 4.9) and browser build (plan 4.10 / section 8).
