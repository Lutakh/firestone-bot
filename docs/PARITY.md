# Parity checklist

Progress of the Python port against the AHK bot. See docs/PYTHON_REWORK_PLAN.md section 4.

## Plan steps

| Step | Status | Notes |
|---|---|---|
| 4.0 Environment setup | done (2026-09-03) | Python 3.12.10 venv, deps installed, capture self-test OK. See MEASUREMENTS.md |
| 4.1 Reference frame | done (2026-09-03) | REF=(0,31,1920,1009); Win11 client is at y=23, handled by the viewport. Confirmed by the map troop probe |
| 4.2 Scaling behaviour | done (2026-09-03) | Unity canvas 1920x1080, scale=min(w/1920,h/1080), edge anchors, no letterbox. Anchored viewport implemented. Wheel test still to do |
| 4.3 Platform + vision layers | done (2026-09-03) | dpi/window/capture/input/process, atlas/viewport/probes, 23 unit tests, live smoke test OK |
| 4.4 Feature modules | in progress | see table below |
| 4.5 Settings, GUI, runner | done (2026-09-03) | dry run of a full cycle OK (434 actions); 3 unattended live cycles OK on the test account (31 min, 2194 actions, 600 clicks, no error, game back on the main screen). AHK-vs-Python side-by-side comparison not done |
| 4.6 Resolution runs | partial | 1280x720 live: HUD points, check_mail, town, alchemist OK; world map is centre-anchored (measured) and map_start uses it. 125 % DPI, a third size, wheel test and a full 720p cycle still to do |
| 4.7 Epic / Steam | done (2026-09-03) | every live test above ran on the Epic build. Steam: killed Epic, launched via steam://rungameid/1013320 (process up in 49 s), window 1920x1009 maximized, platform detected by exe path, start-button probe hit and clicked, main_menu + check_mail OK, full dry run OK |
| 4.8 Packaging and CI | in progress | `firestone-bot.spec` + `.github/workflows/build.yml`; local one-dir build OK (57 MB, 44 s); exe runs from a clean folder with only settings.ini next to it; CI run pending (push blocked by the GitHub credential prompt); SmartScreen documented in README.md |
| 4.9 Linux | todo | |
| 4.10 Browser | todo | |

## Feature modules

"Live" = ran alone through `tools/run_feature.py` on the test account (Epic build, 1920x1009
maximized) and the trace/captures matched the AHK behaviour. "Probe only" = the entry probe
was checked but the branch behind it was not exercised (nothing to claim at the time).

| AHK file | Python module | Ported | Live (Epic) | Steam | Notes |
|---|---|---|---|---|---|
| subFunctions/BigClose.ahk | big_close | yes | yes | | |
| subFunctions/MainMenu.ahk | main_menu | yes | yes | | Alt+Tab replaced by window activation; SafetyCap optional |
| subFunctions/OpenTown.ahk | open_town | yes | yes | | |
| subFunctions/GoMap.ahk | go_map | yes | yes | | |
| subFunctions/MapClose.ahk | map_close | yes | | | exercised inside map_start |
| ClaimEvents.ahk | claim_events | yes | probe only | | no event red dot at test time |
| Quests.ahk | quests | yes | yes | | AHK never calls BigClose (brace before it); reproduced |
| Shop.ahk | shop | yes | yes | | |
| CheckMail.ahk | check_mail | yes | yes | yes | claimed + deleted mail |
| OpenChests.ahk | open_chests, open_bless_chests | yes | yes | | Goto ladders -> tables; Nebula/Cosmic -> Galaxy kept; "close bag" click can hit the Town icon when the bag is already closed (AHK does the same) |
| subFunctions/OpenChestType.ahk | open_chest_type | yes | yes | | found-pixel click |
| subFunctions/OraclesGift.ahk | oracles_gift | yes | probe only | | |
| subFunctions/MysteryBox.ahk | mystery_box | yes | yes | | opened one box |
| Guardian.ahk | guardian | yes | yes | | training with GuardianTrain=3; 0x0F40000 literal = RED_DOT |
| ClaimBeer.ahk | claim_beer | yes | yes | | |
| subFunctions/UseTavernToken.ahk | use_tavern_token | yes | probe only | | |
| subFunctions/CraftArtifact.ahk | craft_artifact | yes | probe only | | |
| subFunctions/ScarabToken.ahk | scarab_token | yes | yes | | |
| Scarab.ahk | scarab | yes | yes | | |
| ClaimRituals.ahk | claim_rituals | yes | yes | | one ritual claimed, oracle daily gift claimed |
| UpgradeBlessings.ahk | upgrade_blessings | yes | probe only | | 9 o'clock y2=5541 typo fixed to 554 |
| subFunctions/ClickBless.ahk | click_bless | yes | | | |
| subFunctions/OracleDaily.ahk | oracle_daily | yes | yes | | |
| ClaimEngineer.ahk | claim_engineer | yes | yes | | tools claimed; WM branch not exercised (UpgradeWM = Don't Upgrade) |
| subFunctions/WMUpgrade.ahk | wm_upgrade | yes | no | | 13 blocks -> table; unknown WMOptions falls through to the next machine like AHK |
| subFunctions/WMLevelOnly.ahk | wm_level_only | yes | no | | |
| subFunctions/WMBlueprintsOnly.ahk | wm_blueprints_only | yes | no | | |
| ExoticMerchant.ahk | exotic_merchant | yes | yes | | 35-notch scroll ran; nothing to sell |
| subFunctions/ExoticUpgrades.ahk | exotic_upgrades | yes | no | | ExoticUpgrades=0 in the test settings |
| subFunctions/BuyExotic.ahk | buy_exotic | yes | yes | | nothing affordable |
| Arena.ahk | arena | yes | yes | | ran in cycle 1 of the unattended run (5 battles) |
| subFunctions/ArenaBattle.ahk | arena_battle | yes | yes | | unbounded wait; SafetyCap optional |
| Alchemist.ahk | alchemist | yes | yes | | collected 2 experiments, started Dragon Blood |
| Research.ahk | research (go_research) | yes | yes | | started one node, slot 2 went in progress |
| subFunctions/ResearchStart.ahk | research_start | yes | yes | | |
| subFunctions/ResearchSlotTest.ahk | research_slot_test | yes | yes | | |
| subFunctions/ResearchClicks.ahk | research_clicks | yes | yes | | |
| subFunctions/ResearchAfterStartTest.ahk | research_after_start_test | yes | no | | not included by any AHK file (dead) |
| Guild.ahk | guild | yes | yes | | expedition started, pickaxes/crystal probes miss |
| subFunctions/Awaken.ahk | awaken | yes | yes | | x80 then auto |
| subFunctions/Chaos.ahk | chaos | yes | yes | | |
| subFunctions/PTree.ahk | ptree | yes | no | | PTree=0 in test settings; 20 blocks -> table |
| subFunctions/LiberationInProgressCheck.ahk | liberation_in_progress_check | yes | no | | unbounded wait; SafetyCap optional |
| subFunctions/FirestoneNew1st.ahk | (not ported) | n/a | | | never called; includes a missing FirestoneClicks.ahk, so it cannot run in AHK either |
| RestartGameRoutine.ahk | restart_game_routine | yes | partial | yes | kill + Steam URL relaunch + start-button wait exercised step by step (not through the runner's timer) |
| SendHeartbeat.ahk | heartbeat | yes | no | | opt-in (EnableHeartbeat=1); wired into Game.heartbeat by the runner |
| subFunctions/GetColor.ahk | (not ported) | n/a | | | returns nothing, never used |
| MapRedeem.ahk | map_redeem | yes | yes | | ran 340 s incl. claim_campaign + liberation (see below) |
| subFunctions/MapStart.ahk | map_start | yes | yes | | inside map_redeem; MapStartState.ini via state.py; TimeDiff unused in AHK |
| subFunctions/ClaimCampaign.ahk | claim_campaign | yes | yes | | |
| subFunctions/LiberationMissions.ahk | liberation_missions | yes | yes | | all missions + dungeon ran (Liberation=1, DungeonQuest=1) |
| HeroUpgrade.ahk | hero_upgrade | yes | yes | | Next Milestone mode, 86 actions; unbounded click loops, SafetyCap optional |
| firestone-bot.ahk MainScript | runner | yes | yes (3 cycles) | | unknown Delay value stops the bot like AHK |
| Gui.ahk | gui/main_window | yes | yes | | 5 tabs, same controls; Gui.ahk's "Upgrade FireCracker" / "Health Only" / "Armor Only" never match the code (AHK bug) and are kept so behaviour is identical; extra Status panel, Dry run, Stop, SafetyCap, EnableHeartbeat |

Dead AHK files not ported on purpose (plan 1.2): the 20 per-rarity chest files, `*.bak`,
`MapStart.ahk.bak`.

## Changes beyond AHK parity (owner requests, 2026-09-04)

| Change | Where | Notes |
|---|---|---|
| Tavern token-shop button probe | `atlas.TAVERN_BEER_CLAIM_READY` | game update: button is green 0x0AA008 at (407,611)-(652,654), AHK looked for yellow 0xFFBB33 |
| Daily shop free mystery box | `features/shop.py` | box moved to the end of the scrolling "Daily deals" row; AHK click (591,857) now hits a paid deal and was removed |
| Daily reset detection | `daily.py`, `shop.py` | free box claimable = new game day; shop is visited every cycle (when its red dot shows) regardless of the Shop setting |
| Tavern token limit | `MaxTokens` (GUI: Tavern group), `TokenCountDaily` | 0 = unlimited; counters persisted in settings.ini, cleared at the detected reset |
| Arena once per day | `ArenaDoneDaily` | set after the 5 battles (or the "buy more" pop-up); the 6 h timer still applies too |
| Chaos rift with free tokens only | `features/chaos.py`, `MaxChaos`/`ChaosCountDaily` | AHK toggled Auto (spends paid orange tokens too). Rework hits manually only while the Hit button shows the blue free-token icon, closes/reopens the rift between hits (resolves the 3-4 min battle instantly), max MaxChaos per game day (GUI: Daily Routine group) |
| Guardian chaos-rift upgrades | `features/guardian_chaos.py`, `ChaosGuardianOrder` | third tab of the guardian screen; guardians with a roster bell are upgraded in the user's order while the green Upgrade button stays green; runs in guardian() each cycle (when the tab bell shows) and right after the day's chaos hits |
| Scarab game with free tokens only | `features/scarab.py`, `MaxScarab`/`ScarabCountDaily` | AHK played one token per cycle regardless of its kind. Rework plays in a loop only while the Play button shows the silver free coin (the paid coin has a purple ring), max MaxScarab per game day, and skips the tavern game once the limit is reached |
